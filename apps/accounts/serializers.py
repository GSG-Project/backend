from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User


class UserSerializer(serializers.ModelSerializer):
    """The account as the client sees it. Only the names can be changed; the email cannot."""

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name']
        read_only_fields = ['id', 'email']
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
