from django.urls import include, path
from rest_framework.routers import DefaultRouter
from accounts.views import (ChangePasswordView, LoginView, PasswordResetConfirmView, RegistrationView,
    PasswordResetRequestView, ProfileView, StaffUserViewSet, TwoFactorSetupView,
    TwoFactorVerifyView)

router = DefaultRouter()
router.register("users", StaffUserViewSet, basename="users")

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("register/", RegistrationView.as_view(), name="register"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="password-reset"),
    path("password-reset/<uidb64>/<token>/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("2fa/setup/", TwoFactorSetupView.as_view(), name="2fa-setup"),
    path("2fa/verify/", TwoFactorVerifyView.as_view(), name="2fa-verify"),
    path("", include(router.urls)),
]
