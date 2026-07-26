from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from accounts.models import Department, Designation, Position, User, UserDesignation


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "is_active", "created_at")
    list_filter = ("role", "is_active")
    search_fields = ("name",)


@admin.register(Designation)
class DesignationAdmin(admin.ModelAdmin):
    list_display = ("name", "can_create_shared_repositories", "is_active", "created_at")
    list_filter = ("can_create_shared_repositories", "is_active")
    search_fields = ("name", "description")


class UserDesignationInline(admin.TabularInline):
    model = UserDesignation
    fk_name = "user"
    extra = 0


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("School profile", {"fields": ("role", "employee_id", "department", "position", "mobile", "bio", "avatar", "auth_provider", "two_factor_enabled")}),)
    list_display = ("username", "email", "first_name", "last_name", "role", "department", "is_active")
    list_filter = ("role", "department", "is_active")
    inlines = (UserDesignationInline,)
