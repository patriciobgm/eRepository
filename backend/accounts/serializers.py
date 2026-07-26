import base64
import secrets
from io import BytesIO

import pyotp
import qrcode
from django.conf import settings
from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from accounts.models import Department, Designation, Position, User, UserDesignation


def unique_username(email):
    base = email.split("@")[0][:120]
    username = base
    index = 1
    while User.objects.filter(username=username).exists():
        index += 1
        username = f"{base}{index}"
    return username


def token_response(user, context):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh), "user": UserSerializer(user, context=context).data}


class DepartmentSerializer(serializers.ModelSerializer):
    user_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Department
        fields = ("id", "name", "is_active", "user_count", "created_at", "updated_at")
        read_only_fields = ("id", "user_count", "created_at", "updated_at")

    def validate_name(self, value):
        queryset = Department.objects.filter(name__iexact=value.strip())
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("A department with this name already exists.")
        return value.strip()


class PositionSerializer(serializers.ModelSerializer):
    user_count = serializers.IntegerField(read_only=True)
    role_label = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = Position
        fields = ("id", "name", "role", "role_label", "is_active", "user_count", "created_at", "updated_at")
        read_only_fields = ("id", "role_label", "user_count", "created_at", "updated_at")

    def validate(self, attrs):
        name = attrs.get("name", getattr(self.instance, "name", "")).strip()
        role = attrs.get("role", getattr(self.instance, "role", None))
        queryset = Position.objects.filter(name__iexact=name, role=role)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError({"name": "This position already exists for the selected role."})
        attrs["name"] = name
        return attrs


class DesignationSerializer(serializers.ModelSerializer):
    user_count = serializers.SerializerMethodField()

    class Meta:
        model = Designation
        fields = ("id", "name", "description", "can_create_shared_repositories", "is_active", "user_count", "created_at", "updated_at")
        read_only_fields = ("id", "user_count", "created_at", "updated_at")

    def get_user_count(self, obj):
        if hasattr(obj, "user_count"):
            return obj.user_count
        return obj.assignments.count()

    def validate_name(self, value):
        name = value.strip()
        queryset = Designation.objects.filter(name__iexact=name)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("A designation with this name already exists.")
        return name


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    department = serializers.CharField(source="department.name", read_only=True, allow_null=True)
    department_id = serializers.PrimaryKeyRelatedField(source="department", queryset=Department.objects.all(), required=False, allow_null=True)
    position = serializers.CharField(source="position.name", read_only=True, allow_null=True)
    position_id = serializers.PrimaryKeyRelatedField(source="position", queryset=Position.objects.all(), required=False, allow_null=True)
    role_label = serializers.CharField(source="get_role_display", read_only=True)
    has_usable_password = serializers.SerializerMethodField()
    designations = DesignationSerializer(many=True, read_only=True)
    designation_ids = serializers.SerializerMethodField()
    can_create_shared_repositories = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "full_name", "role", "role_label", "employee_id", "department", "department_id", "position", "position_id", "designations", "designation_ids", "can_create_shared_repositories", "bio", "mobile", "avatar", "avatar_url", "two_factor_enabled", "auth_provider", "has_usable_password", "is_active", "is_superuser", "date_joined")
        read_only_fields = ("id", "username", "role", "role_label", "employee_id", "department", "position", "two_factor_enabled", "auth_provider", "has_usable_password", "is_active", "is_superuser", "date_joined", "avatar_url")

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_avatar_url(self, obj):
        if not obj.avatar:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.avatar.url) if request else obj.avatar.url

    def get_has_usable_password(self, obj):
        return obj.has_usable_password()

    def get_designation_ids(self, obj):
        return [designation.pk for designation in obj.designations.all()]

    def validate(self, attrs):
        role = attrs.get("role", getattr(self.instance, "role", None))
        position = attrs.get("position", getattr(self.instance, "position", None))
        if position and position.role != role:
            raise serializers.ValidationError({"position_id": "Select a position assigned to this role."})
        if attrs.get("is_superuser", getattr(self.instance, "is_superuser", False)):
            attrs["position"] = None
        if role == User.Role.ASSISTANT_PRINCIPAL:
            admin_department = Department.objects.filter(name__iexact="Admin").first()
            if admin_department:
                attrs["department"] = admin_department
        return attrs


class StaffUserSerializer(UserSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    designation_ids = serializers.PrimaryKeyRelatedField(source="designations", many=True, queryset=Designation.objects.filter(is_active=True), required=False)

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ("password",)
        read_only_fields = ("id", "department", "position", "role_label", "date_joined", "two_factor_enabled", "auth_provider", "has_usable_password", "avatar_url")

    def validate_employee_id(self, value):
        return value or None

    def validate(self, attrs):
        attrs = super().validate(attrs)
        role = attrs.get("role", getattr(self.instance, "role", None))
        designations = attrs.get("designations")
        if designations and role not in (User.Role.TEACHER, User.Role.MASTER_TEACHER):
            raise serializers.ValidationError({"designation_ids": "Only Teachers and Master Teachers can receive designations."})
        return attrs

    def _apply_designations(self, user, designations):
        designation_ids = {designation.pk for designation in designations}
        previous = {assignment.designation_id: assignment.designation.name for assignment in UserDesignation.objects.filter(user=user).select_related("designation")}
        UserDesignation.objects.filter(user=user).exclude(designation_id__in=designation_ids).delete()
        existing_ids = set(UserDesignation.objects.filter(user=user).values_list("designation_id", flat=True))
        assigned_by = self.context.get("request").user if self.context.get("request") else None
        UserDesignation.objects.bulk_create([
            UserDesignation(user=user, designation=designation, assigned_by=assigned_by)
            for designation in designations
            if designation.pk not in existing_ids
        ])
        current = {designation.pk: designation.name for designation in designations}
        added = [current[pk] for pk in current.keys() - previous.keys()]
        removed = [previous[pk] for pk in previous.keys() - current.keys()]
        if added or removed:
            from repository.models import Notification
            from repository.services import notify_users
            changes = []
            if added:
                changes.append(f"Assigned: {', '.join(sorted(added))}")
            if removed:
                changes.append(f"Removed: {', '.join(sorted(removed))}")
            notify_users(
                [user.pk],
                category=Notification.Category.ACCOUNT,
                title="Designations updated",
                message=". ".join(changes) + ".",
                actor=assigned_by,
                link="/profile",
            )

    def create(self, validated_data):
        password = validated_data.pop("password", None) or secrets.token_urlsafe(12)
        designations = validated_data.pop("designations", [])
        if validated_data.get("is_superuser"):
            validated_data["is_staff"] = True
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        if user.role in (User.Role.TEACHER, User.Role.MASTER_TEACHER):
            self._apply_designations(user, designations)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        designation_supplied = "designations" in validated_data
        designations = validated_data.pop("designations", [])
        if "is_superuser" in validated_data:
            validated_data["is_staff"] = validated_data["is_superuser"]
        instance = super().update(instance, validated_data)
        if instance.role not in (User.Role.TEACHER, User.Role.MASTER_TEACHER) or instance.is_superuser:
            instance.designation_assignments.all().delete()
        elif designation_supplied:
            self._apply_designations(instance, designations)
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
        return token_response(user, self.context)


class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    department_id = serializers.PrimaryKeyRelatedField(source="department", queryset=Department.objects.filter(is_active=True))
    position_id = serializers.PrimaryKeyRelatedField(source="position", queryset=Position.objects.filter(is_active=True))

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "employee_id", "department_id", "position_id", "role", "password", "password_confirm")
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
        if attrs["position"].role != attrs["role"]:
            raise serializers.ValidationError({"position_id": "Select a position assigned to this role."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        email = validated_data["email"].lower()
        user = User(username=unique_username(email), email=email, is_active=False, **{k: v for k, v in validated_data.items() if k != "email"})
        user.set_password(password)
        user.save()
        from repository.models import Notification
        from repository.services import management_recipients, notify_users
        notify_users(
            management_recipients(),
            category=Notification.Category.ACCOUNT,
            title="New registration awaiting approval",
            message=f"{user.get_full_name() or user.email} submitted a faculty account application.",
            actor=user,
            link="/staff",
        )
        return user


class GoogleAuthSerializer(serializers.Serializer):
    credential = serializers.CharField(write_only=True)
    mode = serializers.ChoiceField(choices=("login", "register"), default="login")
    employee_id = serializers.CharField(required=False, allow_blank=True)
    department_id = serializers.PrimaryKeyRelatedField(source="department", queryset=Department.objects.filter(is_active=True), required=False)
    position_id = serializers.PrimaryKeyRelatedField(source="position", queryset=Position.objects.filter(is_active=True), required=False)
    role = serializers.ChoiceField(choices=(User.Role.TEACHER, User.Role.MASTER_TEACHER), required=False)

    def validate(self, attrs):
        if not settings.GOOGLE_OAUTH_CLIENT_ID:
            raise serializers.ValidationError("Google sign-in is not configured.")
        try:
            claims = id_token.verify_oauth2_token(attrs["credential"], google_requests.Request(), settings.GOOGLE_OAUTH_CLIENT_ID)
        except ValueError:
            raise serializers.ValidationError("Google could not verify this sign-in. Please try again.")
        if not claims.get("email_verified") or not claims.get("email"):
            raise serializers.ValidationError("A verified Google email address is required.")
        email = claims["email"].lower()
        if not email.endswith("@gmail.com") and not claims.get("hd"):
            raise serializers.ValidationError("Use a Gmail or Google Workspace account.")
        if not claims.get("sub"):
            raise serializers.ValidationError("Google did not provide a stable account identifier.")
        attrs["claims"] = claims
        if attrs["mode"] == "register":
            required = {"employee_id": attrs.get("employee_id"), "department_id": attrs.get("department"), "position_id": attrs.get("position"), "role": attrs.get("role")}
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise serializers.ValidationError({name: "This field is required for Google registration." for name in missing})
            if User.objects.filter(employee_id=attrs["employee_id"]).exists():
                raise serializers.ValidationError({"employee_id": "A faculty account already uses this employee ID."})
            if attrs["position"].role != attrs["role"]:
                raise serializers.ValidationError({"position_id": "Select a position assigned to this role."})
        return attrs

    def save(self):
        claims = self.validated_data["claims"]
        email = claims["email"].lower()
        user = User.objects.filter(google_subject=claims["sub"]).first() or User.objects.filter(email__iexact=email).first()
        if not user:
            if self.validated_data["mode"] != "register":
                raise serializers.ValidationError({"detail": "No faculty account uses this Google email. Register first."})
            user = User(
                username=unique_username(email), email=email,
                first_name=claims.get("given_name", ""), last_name=claims.get("family_name", ""),
                employee_id=self.validated_data["employee_id"], department=self.validated_data["department"],
                position=self.validated_data["position"], role=self.validated_data["role"],
                auth_provider=User.AuthProvider.GOOGLE, google_subject=claims["sub"], is_active=False,
            )
            user.set_unusable_password()
            user.save()
            from repository.models import Notification
            from repository.services import management_recipients, notify_users
            notify_users(
                management_recipients(),
                category=Notification.Category.ACCOUNT,
                title="New Google registration awaiting approval",
                message=f"{user.get_full_name() or user.email} submitted a faculty account application.",
                actor=user,
                link="/staff",
            )
            return {"pending_approval": True, "detail": "Google registration submitted. The Principal must approve your account before you can sign in."}
        if not user.is_active:
            raise serializers.ValidationError({"detail": "Your faculty account is awaiting Principal approval."})
        if user.auth_provider == User.AuthProvider.PASSWORD:
            user.auth_provider = User.AuthProvider.BOTH
        if not user.google_subject:
            user.google_subject = claims["sub"]
        user.save(update_fields=["auth_provider", "google_subject"])
        return token_response(user, self.context)


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
        send_mail("Your eRepository password changed", "Your eRepository password was changed successfully. If this was not you, contact the Principal immediately.", None, [user.email])
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def save(self):
        user = User.objects.filter(email__iexact=self.validated_data["email"], is_active=True).first()
        if user:
            if user.auth_provider == User.AuthProvider.GOOGLE and not user.has_usable_password():
                send_mail("Use Google to access your eRepository", "This account uses Google sign-in and does not have an eRepository password. Return to the sign-in page and choose Continue with Google.", None, [user.email])
                return
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
