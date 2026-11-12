from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import (
    RegisterResponseSerializer,
    RegisterSerializer,
    UserSerializer,
)

TAG = ['Auth']


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
