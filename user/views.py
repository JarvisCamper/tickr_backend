from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from django.db import DatabaseError, IntegrityError
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
# from .models import User
from .serializers import UserSerializer, LoginSerializer, SignupSerializer

@method_decorator(csrf_exempt, name='dispatch')
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        try:
            serializer = self.serializer_class(data=request.data)
            serializer.is_valid(raise_exception=True)
        except DatabaseError:
            return Response(
                {"detail": "Database temporarily unavailable. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        # Determine if user is admin
        is_staff = bool(getattr(user, "is_staff", False))
        is_superuser = bool(getattr(user, "is_superuser", False))
        is_admin = is_staff or is_superuser
        role = "admin" if is_admin else "employee"
        
        # Build response payload; include admin flags and redirect_url
        payload = {
            "message": "Login successful",
            "access": str(access),
            "refresh": str(refresh),
            "user": UserSerializer(user).data,
            # Top-level admin flags for convenience in frontends
            "is_staff": is_staff,
            "is_superuser": is_superuser,
            "is_admin": is_admin,
            "role": role,
            # Tell frontend where to redirect based on role
            "redirect_url": "/admin" if is_admin else "/employee",
        }

        response = Response(payload, status=status.HTTP_200_OK)

        # Set HttpOnly auth cookies. Use secure cross-site cookies in production.
        try:
            secure_cookie = not settings.DEBUG
            same_site = "None" if secure_cookie else "Lax"
            response.set_cookie(
                key="access",
                value=str(access),
                httponly=True,
                secure=secure_cookie,
                samesite=same_site,
                path="/",
            )
            response.set_cookie(
                key="refresh",
                value=str(refresh),
                httponly=True,
                secure=secure_cookie,
                samesite=same_site,
                path="/",
            )
        except Exception:
            # If cookies can't be set (e.g., response type or environment), continue with JSON-only tokens
            pass

        return response
    
class SignupView(APIView):
    permission_classes = [AllowAny]
    serializer_class = SignupSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(
                {"message": "User registered successfully", "data": serializer.data},
                status=status.HTTP_201_CREATED,
            )
        except IntegrityError:
            return Response(
                {"detail": "An account with this email already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError:
            return Response(
                {"detail": "Database temporarily unavailable. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class CurrentUserView(APIView):
    """Get or update the current authenticated user."""
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
