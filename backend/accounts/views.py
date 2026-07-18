from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Department, Position, User
from accounts.serializers import (ChangePasswordSerializer, DepartmentSerializer, GoogleAuthSerializer, LoginSerializer,
    PasswordResetRequestSerializer, PositionSerializer, RegistrationSerializer, StaffUserSerializer, TwoFactorSetupSerializer,
    TwoFactorVerifySerializer, UserSerializer)


class LoginView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer
    throttle_scope = "login"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class RegistrationView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegistrationSerializer
    throttle_scope = "registration"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Registration submitted. The Principal must approve your account before you can sign in."}, status=status.HTTP_201_CREATED)


class GoogleAuthView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = GoogleAuthSerializer
    throttle_scope = "google_auth"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        response_status = status.HTTP_201_CREATED if result.get("pending_approval") else status.HTTP_200_OK
        return Response(result, status=response_status)


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        if request.user.is_superuser:
            raise PermissionDenied("Superadmin profile details are system-managed and cannot be edited.")
        return super().update(request, *args, **kwargs)


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
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "If the account exists, a reset link has been sent."})


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "password_reset"

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
    search_fields = ("first_name", "last_name", "email", "employee_id", "department__name", "position__name")
    filterset_fields = ("role", "department", "position", "is_active")

    def get_queryset(self):
        queryset = super().get_queryset().exclude(pk=self.request.user.pk)
        if not self.request.user.is_superuser:
            queryset = queryset.exclude(Q(is_superuser=True) | Q(role=User.Role.ASSISTANT_PRINCIPAL))
        return queryset

    def check_permissions(self, request):
        super().check_permissions(request)
        if not request.user.is_assistant_principal:
            self.permission_denied(request, message="Only the Principal can manage staff accounts.")

    def _enforce_management_boundary(self, target=None, proposed=None):
        if self.request.user.is_superuser:
            return
        if target and target.pk == self.request.user.pk:
            raise PermissionDenied("Principals cannot edit their own staff access. A superadmin is required.")
        if target and (target.role == User.Role.ASSISTANT_PRINCIPAL or target.is_superuser):
            raise PermissionDenied("Only a superadmin can manage Principal or superadmin access.")
        if proposed and (proposed.get("role") == User.Role.ASSISTANT_PRINCIPAL or proposed.get("is_superuser")):
            raise PermissionDenied("Only a superadmin can grant Principal or superadmin access.")

    def create(self, request, *args, **kwargs):
        self._enforce_management_boundary(proposed=request.data)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        self._enforce_management_boundary(target=self.get_object(), proposed=request.data)
        return super().update(request, *args, **kwargs)

    def perform_create(self, serializer):
        self._enforce_management_boundary(proposed=serializer.validated_data)
        serializer.save()

    def perform_update(self, serializer):
        self._enforce_management_boundary(target=self.get_object(), proposed=serializer.validated_data)
        serializer.save()

    def perform_destroy(self, instance):
        self._enforce_management_boundary(target=instance)
        instance.delete()

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        user = self.get_object()
        self._enforce_management_boundary(target=user)
        user.is_active = True
        user.save(update_fields=["is_active"])
        from repository.models import Notification
        from repository.services import notify_users
        notify_users(
            [user.pk],
            category=Notification.Category.ACCOUNT,
            title="Account approved",
            message="Your faculty account has been approved. Welcome to the eRepository.",
            actor=request.user,
            link="/",
        )
        return Response({"detail": "Account approved.", "user": self.get_serializer(user).data})


class DepartmentViewSet(viewsets.ModelViewSet):
    serializer_class = DepartmentSerializer
    search_fields = ("name",)
    ordering_fields = ("name", "created_at")

    def get_queryset(self):
        queryset = Department.objects.annotate(user_count=Count("users")).order_by("name")
        if self.request.user.is_authenticated and self.request.user.is_superuser:
            return queryset
        return queryset.filter(is_active=True)

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method not in SAFE_METHODS and not request.user.is_superuser:
            self.permission_denied(request, message="Only a superadmin can manage departments.")

    def perform_destroy(self, instance):
        if instance.name.casefold() == "admin":
            raise PermissionDenied("The Admin department is required and cannot be deleted.")
        try:
            instance.delete()
        except ProtectedError:
            raise PermissionDenied("Move staff out of this department before deleting it.")

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.name.casefold() == "admin":
            proposed_name = serializer.validated_data.get("name", instance.name)
            proposed_active = serializer.validated_data.get("is_active", instance.is_active)
            if proposed_name.casefold() != "admin" or not proposed_active:
                raise PermissionDenied("The required Admin department cannot be renamed or deactivated.")
        serializer.save()


class PositionViewSet(viewsets.ModelViewSet):
    serializer_class = PositionSerializer
    search_fields = ("name",)
    filterset_fields = ("role", "is_active")
    ordering_fields = ("role", "name", "created_at")

    def get_queryset(self):
        queryset = Position.objects.annotate(user_count=Count("users")).order_by("role", "name")
        if self.request.user.is_authenticated and self.request.user.is_superuser:
            return queryset
        return queryset.filter(is_active=True)

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method not in SAFE_METHODS and not request.user.is_superuser:
            self.permission_denied(request, message="Only a superadmin can manage positions.")

    def perform_update(self, serializer):
        instance = self.get_object()
        proposed_role = serializer.validated_data.get("role", instance.role)
        if instance.users.exists() and proposed_role != instance.role:
            raise PermissionDenied("A position assigned to staff cannot be moved to another role.")
        serializer.save()

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise PermissionDenied("Reassign staff using this position before deleting it.")
