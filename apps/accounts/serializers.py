from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User


class UserSerializer(serializers.ModelSerializer):
    """The account as the client sees it. Only the names can be changed; the email cannot."""

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'two_factor_enabled']
        read_only_fields = ['id', 'email', 'two_factor_enabled']
        extra_kwargs = {'first_name': {'allow_blank': False}}


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'password']
        extra_kwargs = {'first_name': {'required': True, 'allow_blank': False}}

    def validate_email(self, value):
        email = value.lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return email

    def validate(self, attrs):
        # Run the password rules with the user's details so "too similar to the email" is caught.
        user = User(
            email=attrs['email'], first_name=attrs['first_name'], last_name=attrs.get('last_name', ''),
        )
        validate_password(attrs['password'], user=user)
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class RegisterResponseSerializer(serializers.Serializer):
    """The new account plus tokens, so the client can sign the user in straight away."""

    user = UserSerializer()
    access = serializers.CharField()
    refresh = serializers.CharField()

    @classmethod
    def for_user(cls, user):
        refresh = RefreshToken.for_user(user)
        return cls({'user': user, 'access': str(refresh.access_token), 'refresh': str(refresh)})


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    new_password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate_old_password(self, value):
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError('The current password is not correct.')
        return value

    def validate_new_password(self, value):
        validate_password(value, user=self.context['request'].user)
        return value

    def validate(self, attrs):
        if attrs['old_password'] == attrs['new_password']:
            raise serializers.ValidationError({'new_password': ['The new password must be different.']})
        return attrs

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(help_text='The email of the account. Always answered the same way.')


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(help_text='The `uid` from the link in the email.')
    token = serializers.CharField(help_text='The `token` from the link in the email.')
    new_password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        invalid = serializers.ValidationError({'detail': 'This reset link is invalid or has expired.'})
        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(attrs['uid'])), is_active=True)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            raise invalid
        if not default_token_generator.check_token(user, attrs['token']):
            raise invalid
        # Raises a field error for a weak password.
        try:
            validate_password(attrs['new_password'], user=user)
        except Exception as error:
            messages = list(getattr(error, 'messages', [str(error)]))
            raise serializers.ValidationError({'new_password': messages})
        attrs['user'] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data['user']
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        return user


class LoginChallengeSerializer(serializers.Serializer):
    """Returned instead of tokens when the account has two-step verification on."""

    requires_2fa = serializers.BooleanField(help_text='Always true.')
    challenge = serializers.CharField(help_text='Send this back with the code. Valid for 10 minutes.')
    email = serializers.CharField(help_text='The address the code was sent to, partly hidden.')
    resend_after = serializers.IntegerField(help_text='Seconds to wait before asking for another code.')


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class VerifyLoginCodeSerializer(serializers.Serializer):
    challenge = serializers.CharField()
    code = serializers.CharField(help_text='The six digit code from the email.')


class ResendLoginCodeSerializer(serializers.Serializer):
    challenge = serializers.CharField()


class PasswordConfirmSerializer(serializers.Serializer):
    """Used to turn two-step verification on or off: the user proves who they are again."""

    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate_password(self, value):
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError('The password is not correct.')
        return value


class CodeSerializer(serializers.Serializer):
    code = serializers.CharField(help_text='The six digit code from the email.')
