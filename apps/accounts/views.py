import logging

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import Throttled, ValidationError
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import two_factor
from .emails import send_password_reset_email
from .models import EmailCode, User
from .serializers import (
    ChangePasswordSerializer,
    CodeSerializer,
    LoginChallengeSerializer,
    PasswordConfirmSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterResponseSerializer,
    RegisterSerializer,
    ResendLoginCodeSerializer,
    TokenPairSerializer,
    UserSerializer,
    VerifyLoginCodeSerializer,
)

logger = logging.getLogger(__name__)

TAG = ['Auth']
RESET_EMAIL_COOLDOWN_SECONDS = 60


@extend_schema(
    tags=TAG,
    auth=[],
    summary='Create an account',
    description=(
        'Registers a user with an email, a first name (the last name is optional) and a password, '
        'and signs them in: the response holds the `access` and `refresh` tokens. '
        'The email is stored in lower case and must be unique. '
        'Passwords go through the standard Django strength rules.'
    ),
    request={'application/json': RegisterSerializer},
    responses={201: RegisterResponseSerializer},
    examples=[
        OpenApiExample(
            'Registration',
            request_only=True,
            value={
                'email': 'sara@example.com', 'first_name': 'Sara', 'last_name': 'Ali',
                'password': 'a-long-passphrase-42',
            },
        ),
    ],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    return Response(RegisterResponseSerializer.for_user(user).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        tags=TAG,
        summary='Get the signed-in user',
        description='Returns the account that owns the access token. Send `Authorization: Bearer <access>`.',
        responses={200: UserSerializer},
    ),
    patch=extend_schema(
        tags=TAG,
        summary='Update your profile',
        description=(
            'Changes the signed-in user\'s `first_name` and/or `last_name`. Send only the fields that '
            'changed. The email cannot be changed. `first_name` cannot be blank. Returns the updated user.'
        ),
        request={'application/json': UserSerializer},
        responses={200: UserSerializer, 400: OpenApiResponse(description='A field is invalid.')},
        examples=[
            OpenApiExample('Rename', request_only=True, value={'first_name': 'Sara', 'last_name': 'Ali'}),
        ],
    ),
)
class MeView(RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    # No PUT: only the fields that changed are sent.
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_object(self):
        return self.request.user


@extend_schema(
    tags=TAG,
    summary='Change your password',
    description=(
        'Checks the current password, then sets the new one, which must pass the same strength rules as '
        'registration and differ from the old one. Returns `204`. Access tokens already issued keep '
        'working until they expire (30 minutes); the client should sign in again to get fresh ones.'
    ),
    request={'application/json': ChangePasswordSerializer},
    responses={
        204: OpenApiResponse(description='The password was changed.'),
        400: OpenApiResponse(description='The current password is wrong or the new one is not accepted.'),
    },
    examples=[
        OpenApiExample(
            'Change password',
            request_only=True,
            value={'old_password': 'a-long-passphrase-42', 'new_password': 'a-newer-passphrase-77'},
        ),
    ],
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=TAG,
    auth=[],
    summary='Sign in',
    description=(
        'Exchanges an email and password for an `access` token (30 minutes) and a `refresh` '
        'token (7 days). A wrong email or password returns `401`.\n\n'
        'If the account has two-step verification on, no tokens are returned. The response is `202` '
        'with a `challenge`: a code was emailed, so call `POST /api/auth/login/verify/` with the '
        '`challenge` and the code to get the tokens.'
    ),
    responses={
        200: TokenPairSerializer,
        202: LoginChallengeSerializer,
        401: OpenApiResponse(description='Wrong email or password.'),
        503: OpenApiResponse(description='The sign-in code could not be sent. Try again.'),
    },
)
class LoginView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as error:
            raise InvalidToken(error.args[0])

        user = serializer.user
        if not user.two_factor_enabled:
            return Response(serializer.validated_data, status=status.HTTP_200_OK)

        try:
            two_factor.issue_code(user, EmailCode.Purpose.LOGIN)
        except two_factor.CooldownError:
            # A code was sent a moment ago and is still valid: let the user use it.
            pass
        except Exception:
            logger.exception('Could not send a sign-in code')
            return Response(
                {'detail': 'The sign-in code could not be sent. Please try again.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(_challenge_body(user), status=status.HTTP_202_ACCEPTED)


def _challenge_body(user):
    return {
        'requires_2fa': True,
        'challenge': two_factor.make_challenge(user),
        'email': two_factor.mask_email(user.email),
        'resend_after': two_factor.seconds_until_resend(user, EmailCode.Purpose.LOGIN),
    }


def _tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {'access': str(refresh.access_token), 'refresh': str(refresh)}


def _wrong_code(error):
    raise ValidationError({'code': [error.message], 'error': error.code})


@extend_schema(
    tags=TAG,
    auth=[],
    summary='Finish signing in with an emailed code',
    description=(
        'Second step of signing in to an account with two-step verification. Send the `challenge` from '
        '`POST /api/auth/login/` and the six digit `code` from the email. Returns the `access` and '
        '`refresh` tokens. A code works once, for 10 minutes, and stops after 5 wrong attempts. '
        '`400` carries an `error` of `invalid`, `expired`, `too_many_attempts` or `no_code`; `401` means '
        'the challenge is invalid or too old, so sign in again.'
    ),
    request={'application/json': VerifyLoginCodeSerializer},
    responses={
        200: TokenPairSerializer,
        400: OpenApiResponse(description='The code is wrong, expired or used up.'),
        401: OpenApiResponse(description='The challenge is invalid or expired. Sign in again.'),
    },
    examples=[
        OpenApiExample('Verify', request_only=True, value={'challenge': 'eyJ1c2VyIjo...', 'code': '482913'}),
    ],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def verify_login_code(request):
    serializer = VerifyLoginCodeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = two_factor.user_from_challenge(serializer.validated_data['challenge'])
    if user is None:
        return Response({'detail': 'This sign-in has expired. Please sign in again.'}, status=401)
    try:
        two_factor.check_code(user, EmailCode.Purpose.LOGIN, serializer.validated_data['code'])
    except two_factor.CodeError as error:
        _wrong_code(error)
    return Response(_tokens_for(user))


@extend_schema(
    tags=TAG,
    auth=[],
    summary='Send the sign-in code again',
    description=(
        'Emails a new code for a pending sign-in and invalidates the previous one. At most one code '
        'every 30 seconds: asking sooner returns `429` with a `Retry-After` header.'
    ),
    request={'application/json': ResendLoginCodeSerializer},
    responses={
        204: OpenApiResponse(description='A new code was sent.'),
        401: OpenApiResponse(description='The challenge is invalid or expired. Sign in again.'),
        429: OpenApiResponse(description='A code was sent a moment ago.'),
        503: OpenApiResponse(description='The email could not be sent.'),
    },
)
@api_view(['POST'])
@permission_classes([AllowAny])
def resend_login_code(request):
    serializer = ResendLoginCodeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = two_factor.user_from_challenge(serializer.validated_data['challenge'])
    if user is None:
        return Response({'detail': 'This sign-in has expired. Please sign in again.'}, status=401)
    try:
        two_factor.issue_code(user, EmailCode.Purpose.LOGIN)
    except two_factor.CooldownError as error:
        raise Throttled(wait=error.wait)
    except Exception:
        logger.exception('Could not send a sign-in code')
        return Response({'detail': 'The code could not be sent. Please try again.'}, status=503)
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=TAG,
    auth=[],
    summary='Ask for a password reset email',
    description=(
        'Emails a link to choose a new password, valid for one hour. The answer is always `204`, '
        'whether or not the email belongs to an account, so this cannot be used to find out who has one. '
        'The link points to the frontend at `/reset-password?uid=...&token=...`. At most one email per '
        'minute is sent to the same address.'
    ),
    request={'application/json': PasswordResetRequestSerializer},
    responses={204: OpenApiResponse(description='If the account exists, an email was sent.')},
    examples=[OpenApiExample('Request', request_only=True, value={'email': 'sara@example.com'})],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_request(request):
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data['email'].lower()

    user = User.objects.filter(email__iexact=email, is_active=True).first()
    # cache.add only succeeds for the first request in the minute.
    if user is not None and cache.add(f'password-reset:{user.pk}', 1, RESET_EMAIL_COOLDOWN_SECONDS):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        link = f'{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}'
        try:
            send_password_reset_email(user, link)
        except Exception:
            # The answer must not reveal whether the account exists, so a failure is only logged.
            logger.exception('Could not send a password reset email')
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=TAG,
    auth=[],
    summary='Choose a new password from a reset link',
    description=(
        'Sets a new password. Send the `uid` and `token` from the link in the email and the new '
        'password, which must pass the same strength rules as registration. A link works once: it stops '
        'working as soon as the password changes. An invalid or expired link returns `400` with `detail`.'
    ),
    request={'application/json': PasswordResetConfirmSerializer},
    responses={
        204: OpenApiResponse(description='The password was changed.'),
        400: OpenApiResponse(description='The link is invalid or expired, or the password is not accepted.'),
    },
    examples=[
        OpenApiExample(
            'Reset', request_only=True,
            value={'uid': 'MQ', 'token': 'c1x2y3-abc...', 'new_password': 'a-newer-passphrase-77'},
        ),
    ],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    serializer = PasswordResetConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=TAG,
    summary='Start turning on two-step verification',
    description=(
        'Checks your password and emails a six digit code to your address. Finish with '
        '`POST /api/auth/two-factor/confirm/`. This proves the email works before it is required to '
        'sign in. `400` if it is already on.'
    ),
    request={'application/json': PasswordConfirmSerializer},
    responses={
        204: OpenApiResponse(description='A code was sent.'),
        400: OpenApiResponse(description='Wrong password, or two-step verification is already on.'),
        429: OpenApiResponse(description='A code was sent a moment ago.'),
        503: OpenApiResponse(description='The email could not be sent.'),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def two_factor_enable(request):
    serializer = PasswordConfirmSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    if request.user.two_factor_enabled:
        raise ValidationError({'detail': 'Two-step verification is already on.'})
    try:
        two_factor.issue_code(request.user, EmailCode.Purpose.ENABLE_2FA)
    except two_factor.CooldownError as error:
        raise Throttled(wait=error.wait)
    except Exception:
        logger.exception('Could not send a two-step verification code')
        return Response({'detail': 'The code could not be sent. Please try again.'}, status=503)
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=TAG,
    summary='Finish turning on two-step verification',
    description=(
        'Send the six digit code that was emailed by `POST /api/auth/two-factor/enable/`. On success '
        'two-step verification is on and the updated user is returned.'
    ),
    request={'application/json': CodeSerializer},
    responses={
        200: UserSerializer,
        400: OpenApiResponse(description='The code is wrong, expired or used up (`error` says which).'),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def two_factor_confirm(request):
    serializer = CodeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        two_factor.check_code(request.user, EmailCode.Purpose.ENABLE_2FA, serializer.validated_data['code'])
    except two_factor.CodeError as error:
        _wrong_code(error)
    request.user.two_factor_enabled = True
    request.user.save(update_fields=['two_factor_enabled'])
    return Response(UserSerializer(request.user).data)


@extend_schema(
    tags=TAG,
    summary='Turn off two-step verification',
    description='Checks your password, then turns two-step verification off. Returns the updated user.',
    request={'application/json': PasswordConfirmSerializer},
    responses={
        200: UserSerializer,
        400: OpenApiResponse(description='Wrong password.'),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def two_factor_disable(request):
    serializer = PasswordConfirmSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    request.user.two_factor_enabled = False
    request.user.save(update_fields=['two_factor_enabled'])
    return Response(UserSerializer(request.user).data)


@extend_schema(
    tags=TAG,
    auth=[],
    summary='Get a new access token',
    description=(
        'Exchanges a valid `refresh` token for a new `access` token. '
        'An invalid or expired one returns `401`.'
    ),
)
class RefreshView(TokenRefreshView):
    pass
