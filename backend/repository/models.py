import hashlib
import os
import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


def document_upload_path(instance, filename):
    suffix = Path(filename).suffix.lower()
    return f"documents/{instance.document.repository_id}/{instance.document_id}/{uuid.uuid4().hex}{suffix}"


class Repository(models.Model):
    class Kind(models.TextChoices):
        PRIVATE = "PRIVATE", "Private"
        SHARED = "SHARED", "Shared"

    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_repositories")
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="shared_repositories")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("kind", "name")
        constraints = [models.UniqueConstraint(fields=("owner", "kind"), condition=models.Q(kind="PRIVATE"), name="one_private_repository_per_user")]

    def __str__(self):
        return self.name


class Folder(models.Model):
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name="folders")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="owned_folders")
    name = models.CharField(max_length=180)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        constraints = [models.UniqueConstraint(Lower("name"), "repository", name="unique_folder_name_per_repository")]

    def __str__(self):
        return self.name


class Document(models.Model):
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name="documents")
    folder = models.ForeignKey(Folder, on_delete=models.SET_NULL, related_name="documents", null=True, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="documents")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    tags = models.CharField(max_length=500, blank=True, help_text="Comma-separated tags")
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    @property
    def latest_version(self):
        return self.versions.order_by("-version_number").first()

    def __str__(self):
        return self.title


class DocumentVersion(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    file = models.FileField(upload_to=document_upload_path)
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveBigIntegerField(default=0)
    mime_type = models.CharField(max_length=150, blank=True)
    checksum = models.CharField(max_length=64, blank=True)
    revision_notes = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="uploaded_versions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-version_number",)
        constraints = [models.UniqueConstraint(fields=("document", "version_number"), name="unique_document_version")]

    def save(self, *args, **kwargs):
        if self.file and not self.file_size:
            self.file_size = self.file.size
        if self.file and not self.original_filename:
            self.original_filename = os.path.basename(self.file.name)
        if self.file and not self.checksum:
            digest = hashlib.sha256()
            for chunk in self.file.chunks():
                digest.update(chunk)
            self.checksum = digest.hexdigest()
            self.file.seek(0)
        super().save(*args, **kwargs)


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATED = "CREATED", "Created"
        UPDATED = "UPDATED", "Updated"
        ARCHIVED = "ARCHIVED", "Archived"
        RESTORED = "RESTORED", "Restored"
        UPLOADED_VERSION = "UPLOADED_VERSION", "Uploaded revision"
        DOWNLOADED = "DOWNLOADED", "Downloaded"
        DELETED = "DELETED", "Deleted"

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="audit_events")
    action = models.CharField(max_length=30, choices=Action.choices)
    target_type = models.CharField(max_length=80)
    target_id = models.CharField(max_length=80)
    target_name = models.CharField(max_length=255)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class Notification(models.Model):
    class Category(models.TextChoices):
        ACCOUNT = "ACCOUNT", "Account"
        REPOSITORY = "REPOSITORY", "Repository"
        DOCUMENT = "DOCUMENT", "Document"
        SYSTEM = "SYSTEM", "System"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="triggered_notifications")
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.SYSTEM)
    title = models.CharField(max_length=180)
    message = models.CharField(max_length=500)
    link = models.CharField(max_length=255, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("recipient", "read_at", "-created_at"), name="notification_inbox_idx")]

    @property
    def is_read(self):
        return self.read_at is not None

    def __str__(self):
        return self.title
