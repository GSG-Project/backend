from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'name']
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['email', 'name', 'password']
        extra_kwargs = {'name': {'allow_blank': False}}

    def validate_email(self, value):
        email = value.lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return email

    def validate(self, attrs):
        # Run the password rules with the user's details so "too similar to the email" is caught.
        validate_password(attrs['password'], user=User(email=attrs['email'], name=attrs['name']))
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
