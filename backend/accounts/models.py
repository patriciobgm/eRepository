import pyotp
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        TEACHER = "TEACHER", "Teacher"
        MASTER_TEACHER = "MASTER_TEACHER", "Master Teacher"
        ASSISTANT_PRINCIPAL = "ASSISTANT_PRINCIPAL", "Assistant Principal"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=24, choices=Role.choices, default=Role.TEACHER)
    employee_id = models.CharField(max_length=40, unique=True, null=True, blank=True)
    department = models.CharField(max_length=120, blank=True)
    position = models.CharField(max_length=120, blank=True)
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to="avatars/%Y/%m/", blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True)
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.CharField(max_length=64, blank=True)

    @property
    def is_assistant_principal(self):
        return self.role == self.Role.ASSISTANT_PRINCIPAL or self.is_superuser

    def ensure_two_factor_secret(self):
        if not self.two_factor_secret:
            self.two_factor_secret = pyotp.random_base32()
            self.save(update_fields=["two_factor_secret"])
        return self.two_factor_secret

    def verify_otp(self, code):
        return bool(self.two_factor_secret and pyotp.TOTP(self.two_factor_secret).verify(str(code), valid_window=1))

