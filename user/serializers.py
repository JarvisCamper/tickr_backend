# serializers.py
from rest_framework import serializers
from .models import User
from django.contrib.auth import authenticate
from rest_framework.exceptions import AuthenticationFailed
from django.utils.timezone import now
from rest_framework_simplejwt.tokens import RefreshToken

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name', 'phone', 'date_of_birth', 'password']
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)  # Hash the password
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance
    
class LoginSerializer(serializers.Serializer):
    email = serializers.CharField()
    password = serializers.CharField(style={"input_type": "password"}, write_only=True)

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("The user does not exist.")

        if not user.is_active:
            raise serializers.ValidationError(
                "Account is inactive, please contact the administrator."
            )

        user = authenticate(username=email, password=password)
        if user is None:
            raise AuthenticationFailed("Invalid credentials.")

        # Update last login
        user.last_login = now()
        user.save(update_fields=["last_login"])

        # Generate tokens
        refresh = RefreshToken.for_user(user)

        return {
            "refresh_token": str(refresh),
            "access_token": str(refresh.access_token),
        }
