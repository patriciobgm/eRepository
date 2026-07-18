from django.contrib import admin
from repository.models import AuditLog, Document, DocumentVersion, Folder, Notification, Repository


class DocumentVersionInline(admin.TabularInline):
    model = DocumentVersion
    extra = 0
    readonly_fields = ("version_number", "original_filename", "file_size", "checksum", "uploaded_by", "created_at")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "repository", "owner", "is_archived", "updated_at")
    list_filter = ("repository__kind", "is_archived", "created_at")
    search_fields = ("title", "description", "tags", "owner__email")
    inlines = [DocumentVersionInline]


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "owner", "created_at")
    list_filter = ("kind",)
    filter_horizontal = ("members",)


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ("name", "repository", "owner", "created_at")
    list_filter = ("repository__kind", "created_at")
    search_fields = ("name", "repository__name", "owner__email")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "target_type", "target_name", "ip_address")
    list_filter = ("action", "target_type")
    readonly_fields = tuple(field.name for field in AuditLog._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "recipient", "category", "title", "read_at")
    list_filter = ("category", "read_at", "created_at")
    search_fields = ("recipient__email", "recipient__first_name", "recipient__last_name", "title", "message")
    readonly_fields = tuple(field.name for field in Notification._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
