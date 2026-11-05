from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import RegisterResponseSerializer, RegisterSerializer, UserSerializer

TAG = ['Auth']


@extend_schema(
    tags=TAG,
    auth=[],
    summary='Create an account',
    description=(
        'Registers a user with an email, a name and a password, and signs them in: the response '
        'holds the `access` and `refresh` tokens. The email is stored in lower case and must be unique. '
        'Passwords go through the standard Django strength rules.'
    ),
    request={'application/json': RegisterSerializer},
    responses={201: RegisterResponseSerializer},
    examples=[
        OpenApiExample(
            'Registration',
            request_only=True,
            value={'email': 'sara@example.com', 'name': 'Sara', 'password': 'a-long-passphrase-42'},
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


@extend_schema(
    tags=TAG,
    summary='Get the signed-in user',
    description='Returns the account that owns the access token. Send `Authorization: Bearer <access>`.',
    responses={200: UserSerializer},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(UserSerializer(request.user).data)


@extend_schema(
    tags=TAG,
    auth=[],
    summary='Sign in',
    description=(
        'Exchanges an email and password for an `access` token (30 minutes) and a `refresh` '
        'token (7 days). A wrong email or password returns `401`.'
    ),
)
class LoginView(TokenObtainPairView):
    pass


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
