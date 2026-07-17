import base64
import secrets
from io import BytesIO

import pyotp
import qrcode
from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "full_name", "role", "employee_id", "department", "position", "bio", "phone", "avatar", "avatar_url", "two_factor_enabled", "is_active", "date_joined")
        read_only_fields = ("id", "username", "role", "employee_id", "two_factor_enabled", "is_active", "date_joined", "avatar_url")

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_avatar_url(self, obj):
        if not obj.avatar:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.avatar.url) if request else obj.avatar.url


class StaffUserSerializer(UserSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ("password",)
        read_only_fields = ("id", "date_joined", "two_factor_enabled", "avatar_url")

    def validate_employee_id(self, value):
        return value or None

    def create(self, validated_data):
        password = validated_data.pop("password", None) or secrets.token_urlsafe(12)
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=["password"])
        return instance


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    otp = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        try:
            username = User.objects.get(email__iexact=attrs["email"]).username
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email or password.")
        user = authenticate(username=username, password=attrs["password"])
        if not user or not user.is_active:
            raise serializers.ValidationError("Invalid email or password.")
        if user.two_factor_enabled:
            if not attrs.get("otp"):
                raise serializers.ValidationError({"otp": "A verification code is required.", "requires_otp": True})
            if not user.verify_otp(attrs["otp"]):
                raise serializers.ValidationError({"otp": "The verification code is invalid."})
        refresh = RefreshToken.for_user(user)
        return {"access": str(refresh.access_token), "refresh": str(refresh), "user": UserSerializer(user, context=self.context).data}


class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "employee_id", "department", "position", "role", "password", "password_confirm")
        extra_kwargs = {"employee_id": {"required": True, "allow_blank": False}}

    def validate_role(self, value):
        if value not in (User.Role.TEACHER, User.Role.MASTER_TEACHER):
            raise serializers.ValidationError("Only Teacher and Master Teacher applications are accepted.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        try:
            password_validation.validate_password(attrs["password"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        email = validated_data["email"].lower()
        base = email.split("@")[0][:120]
        username = base
        index = 1
        while User.objects.filter(username=username).exists():
            index += 1
            username = f"{base}{index}"
        user = User(username=username, email=email, is_active=False, **{k: v for k, v in validated_data.items() if k != "email"})
        user.set_password(password)
        user.save()
        return user


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError({"current_password": "Current password is incorrect."})
        try:
            password_validation.validate_password(attrs["new_password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})
        return attrs

    def save(self):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        send_mail("Your eRepository password changed", "Your eRepository password was changed successfully. If this was not you, contact the Assistant Principal immediately.", None, [user.email])
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def save(self):
        user = User.objects.filter(email__iexact=self.validated_data["email"], is_active=True).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            frontend_url = self.context.get("frontend_url", "http://localhost:5173")
            send_mail("Reset your eRepository password", f"Use this link to reset your password: {frontend_url}/reset-password/{uid}/{token}", None, [user.email])


class TwoFactorSetupSerializer(serializers.Serializer):
    def to_representation(self, instance):
        user = instance
        secret = user.ensure_two_factor_secret()
        uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="School eRepository")
        image = qrcode.make(uri)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return {"secret": secret, "otpauth_uri": uri, "qr_code": f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}"}


class TwoFactorVerifySerializer(serializers.Serializer):
    code = serializers.CharField(min_length=6, max_length=6)

    def validate_code(self, value):
        user = self.context["request"].user
        user.ensure_two_factor_secret()
        if not user.verify_otp(value):
            raise serializers.ValidationError("Invalid verification code.")
        return value
