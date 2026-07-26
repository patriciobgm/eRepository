import pyotp
from django.contrib.auth.models import AbstractUser
from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class Position(models.Model):
    class Role(models.TextChoices):
        TEACHER = "TEACHER", "Teacher"
        MASTER_TEACHER = "MASTER_TEACHER", "Master Teacher"
        PRINCIPAL = "ASSISTANT_PRINCIPAL", "Principal"

    name = models.CharField(max_length=120)
    role = models.CharField(max_length=24, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("role", "name")
        constraints = [models.UniqueConstraint(fields=("name", "role"), name="unique_position_per_role")]

    def __str__(self):
        return self.name


class Designation(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    can_create_shared_repositories = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class User(AbstractUser):
    class Role(models.TextChoices):
        TEACHER = "TEACHER", "Teacher"
        MASTER_TEACHER = "MASTER_TEACHER", "Master Teacher"
        ASSISTANT_PRINCIPAL = "ASSISTANT_PRINCIPAL", "Principal"

    class AuthProvider(models.TextChoices):
        PASSWORD = "PASSWORD", "Email and password"
        GOOGLE = "GOOGLE", "Google"
        BOTH = "BOTH", "Email/password and Google"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=24, choices=Role.choices, default=Role.TEACHER)
    employee_id = models.CharField(max_length=40, unique=True, null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="users", null=True, blank=True)
    position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name="users", null=True, blank=True)
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to="avatars/%Y/%m/", blank=True, null=True)
    mobile = models.CharField(max_length=30, blank=True)
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.CharField(max_length=64, blank=True)
    auth_provider = models.CharField(max_length=12, choices=AuthProvider.choices, default=AuthProvider.PASSWORD)
    google_subject = models.CharField(max_length=255, unique=True, null=True, blank=True, editable=False)
    designations = models.ManyToManyField(Designation, through="UserDesignation", through_fields=("user", "designation"), related_name="users", blank=True)

    @property
    def is_superadmin(self):
        return self.is_superuser

    @property
    def is_assistant_principal(self):
        return self.role == self.Role.ASSISTANT_PRINCIPAL or self.is_superuser

    @property
    def can_manage_repositories(self):
        return self.role == self.Role.ASSISTANT_PRINCIPAL and not self.is_superuser

    @property
    def can_create_shared_repositories(self):
        if self.is_superuser:
            return False
        if self.role == self.Role.ASSISTANT_PRINCIPAL:
            return True
        return self.role in (self.Role.TEACHER, self.Role.MASTER_TEACHER) and self.designations.filter(
            is_active=True,
            can_create_shared_repositories=True,
        ).exists()

    def can_manage_shared_repository(self, repository):
        return not self.is_superuser and repository.kind == "SHARED" and (
            self.can_manage_repositories or repository.owner_id == self.pk
        )

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.department = None
            self.position = None
            self.bio = ""
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"department", "position", "bio"}
        elif self.role == self.Role.ASSISTANT_PRINCIPAL:
            admin_department = Department.objects.filter(name__iexact="Admin").first()
            if admin_department:
                self.department = admin_department
                update_fields = kwargs.get("update_fields")
                if update_fields is not None:
                    kwargs["update_fields"] = set(update_fields) | {"department"}
        if not self.is_superuser and self.position_id and not Position.objects.filter(pk=self.position_id, role=self.role).exists():
            self.position = None
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"position"}
        super().save(*args, **kwargs)

    def ensure_two_factor_secret(self):
        if not self.two_factor_secret:
            self.two_factor_secret = pyotp.random_base32()
            self.save(update_fields=["two_factor_secret"])
        return self.two_factor_secret

    def verify_otp(self, code):
        return bool(self.two_factor_secret and pyotp.TOTP(self.two_factor_secret).verify(str(code), valid_window=1))


class UserDesignation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="designation_assignments")
    designation = models.ForeignKey(Designation, on_delete=models.PROTECT, related_name="assignments")
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="designation_assignments_made", null=True, blank=True)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("designation__name",)
        constraints = [models.UniqueConstraint(fields=("user", "designation"), name="unique_user_designation")]

    def __str__(self):
        return f"{self.user} — {self.designation}"
