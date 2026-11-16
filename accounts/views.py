from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import RegisterSerializer, UserSerializer


@extend_schema(tags=["auth"], summary="Create an account")
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []
    throttle_scope = "auth"


@extend_schema(tags=["auth"], summary="Exchange email + password for access/refresh JWTs")
class LoginView(TokenObtainPairView):
    throttle_scope = "auth"


@extend_schema(tags=["auth"], summary="Exchange a refresh token for a new access token")
class RefreshView(TokenRefreshView):
    throttle_scope = "auth"


@extend_schema(tags=["auth"], summary="Current user")
class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user
