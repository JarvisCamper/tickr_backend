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
import logging
# from .models import User
from .serializers import UserSerializer, LoginSerializer, SignupSerializer
from admin_site.admin_config import get_admin_setting
from admin_site.utils import log_user_access_event

logger = logging.getLogger(__name__)

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

        log_user_access_event(user, "login", request=request)

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


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        log_user_access_event(request.user, "logout", request=request)

        response = Response({"message": "Logout successful"}, status=status.HTTP_200_OK)
        response.delete_cookie("access", path="/")
        response.delete_cookie("refresh", path="/")
        return response
    
class SignupView(APIView):
    permission_classes = [AllowAny]
    serializer_class = SignupSerializer

    def post(self, request, *args, **kwargs):
        if not get_admin_setting("allow_public_registration"):
            return Response(
                {"detail": "Public registration is currently disabled by the administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )

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
            try:
                serializer.save()
            except OSError:
                logger.exception("Avatar upload failed for user %s", request.user.pk)
                return Response(
                    {"detail": "Avatar upload is temporarily unavailable. Please try again later."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
