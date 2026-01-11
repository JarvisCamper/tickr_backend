# serializers.py
from rest_framework import serializers
from .models import User
from django.contrib.auth import authenticate
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    avatar = serializers.ImageField(required=False, allow_null=True, use_url=True)
    is_admin = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'password', 'avatar', 'is_staff', 'is_superuser', 'is_admin', 'role']
        extra_kwargs = {
            'password': {'write_only': True},
            'is_staff': {'read_only': True},
            'is_superuser': {'read_only': True},
        }

    def get_is_admin(self, obj):
        return bool(getattr(obj, 'is_staff', False) or getattr(obj, 'is_superuser', False))

    def get_role(self, obj):
        return 'admin' if self.get_is_admin(obj) else 'member'

    def create(self, validated_data):
        password = validated_data.pop('password')
        avatar = validated_data.pop('avatar', None)
        user = User(**validated_data)
        user.set_password(password)  
        if avatar:
            user.avatar = avatar
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        avatar = validated_data.pop('avatar', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        if avatar is not None:
            instance.avatar = avatar
        instance.save()
        return instance
    
class LoginSerializer(serializers.Serializer):
    email = serializers.CharField(required=False)
    username = serializers.CharField(required=False)
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get("email")
        username = data.get("username")
        password = data.get("password")

        if not email and not username:
            raise AuthenticationFailed("Email or username is required")

        try:
            # Try login by email
            if email:
                user = User.objects.get(email=email)
            # Or login by username
            else:
                user = User.objects.get(username=username)

        except User.DoesNotExist:
            raise AuthenticationFailed("User not found")

        # Password check
        if not user.check_password(password):
            raise AuthenticationFailed("Invalid credentials")

        # Return user object so the view can access it
        return {
            "user": user,
        }

class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['email', 'username', 'password', 'password2']

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError("Passwords do not match.")
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user