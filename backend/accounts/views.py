from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.serializers import (ChangePasswordSerializer, LoginSerializer,
    PasswordResetRequestSerializer, RegistrationSerializer, StaffUserSerializer, TwoFactorSetupSerializer,
    TwoFactorVerifySerializer, UserSerializer)


class LoginView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class RegistrationView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Registration submitted. The Assistant Principal must approve your account before you can sign in."}, status=status.HTTP_201_CREATED)


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class ChangePasswordView(generics.GenericAPIView):
    serializer_class = ChangePasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password changed. A confirmation email has been sent."})


class PasswordResetRequestView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetRequestSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "If the account exists, a reset link has been sent."})


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, uidb64, token):
        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
        except (ValueError, User.DoesNotExist):
            user = None
        if not user or not default_token_generator.check_token(user, token):
            return Response({"detail": "This reset link is invalid or expired."}, status=status.HTTP_400_BAD_REQUEST)
        password = request.data.get("password", "")
        try:
            from django.contrib.auth.password_validation import validate_password
            validate_password(password, user)
        except Exception as exc:
            return Response({"password": list(getattr(exc, "messages", [str(exc)]))}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(password)
        user.save(update_fields=["password"])
        return Response({"detail": "Password reset successfully."})


class TwoFactorSetupView(generics.RetrieveAPIView):
    serializer_class = TwoFactorSetupSerializer

    def get_object(self):
        return self.request.user


class TwoFactorVerifyView(generics.GenericAPIView):
    serializer_class = TwoFactorVerifySerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.two_factor_enabled = True
        request.user.save(update_fields=["two_factor_enabled"])
        return Response({"detail": "Two-factor authentication enabled."})

    def delete(self, request):
        if not request.user.check_password(request.data.get("password", "")):
            return Response({"password": "Password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)
        request.user.two_factor_enabled = False
        request.user.two_factor_secret = ""
        request.user.save(update_fields=["two_factor_enabled", "two_factor_secret"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class StaffUserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.order_by("last_name", "first_name")
    serializer_class = StaffUserSerializer
    search_fields = ("first_name", "last_name", "email", "employee_id", "department")
    filterset_fields = ("role", "department", "is_active")

    def check_permissions(self, request):
        super().check_permissions(request)
        if not request.user.is_assistant_principal:
            self.permission_denied(request, message="Only the Assistant Principal can manage staff accounts.")

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=["is_active"])
        return Response({"detail": "Account approved.", "user": self.get_serializer(user).data})
