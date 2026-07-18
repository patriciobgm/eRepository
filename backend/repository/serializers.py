import mimetypes
from django.conf import settings
from django.db import transaction
from rest_framework import serializers

from accounts.models import User
from accounts.serializers import UserSerializer
from repository.models import AuditLog, Document, DocumentVersion, Folder, Notification, Repository


ALLOWED_EXTENSIONS = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf", ".txt", ".csv", ".odt", ".ods", ".odp", ".jpg", ".jpeg", ".png", ".zip"}


def validate_document_file(file):
    from pathlib import Path
    extension = Path(file.name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise serializers.ValidationError(f"Unsupported file type: {extension or 'unknown'}.")
    if file.size > settings.MAX_DOCUMENT_SIZE:
        raise serializers.ValidationError("The file exceeds the 50 MB upload limit.")
    return file


class RepositorySerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    member_ids = serializers.PrimaryKeyRelatedField(
        source="members",
        many=True,
        queryset=User.objects.filter(
            is_active=True,
            is_superuser=False,
            role__in=(User.Role.TEACHER, User.Role.MASTER_TEACHER),
        ),
        required=False,
    )
    document_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Repository
        fields = ("id", "name", "description", "kind", "owner", "member_ids", "document_count", "created_at", "updated_at")
        read_only_fields = ("id", "owner", "kind", "created_at", "updated_at")


class FolderSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    repository_name = serializers.CharField(source="repository.name", read_only=True)
    document_count = serializers.SerializerMethodField()

    class Meta:
        model = Folder
        fields = ("id", "repository", "repository_name", "owner", "name", "document_count", "created_at", "updated_at")
        read_only_fields = ("id", "repository_name", "owner", "document_count", "created_at", "updated_at")

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Folder name cannot be empty.")
        return name

    def get_document_count(self, obj):
        if hasattr(obj, "document_count"):
            return obj.document_count
        return obj.documents.filter(is_archived=False).count()

    def validate(self, attrs):
        repository = attrs.get("repository", getattr(self.instance, "repository", None))
        name = attrs.get("name", getattr(self.instance, "name", ""))
        if self.instance and repository != self.instance.repository:
            raise serializers.ValidationError({"repository": "A folder cannot be moved to another repository."})
        duplicate = Folder.objects.filter(repository=repository, name__iexact=name)
        if self.instance:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError({"name": "A folder with this name already exists in this repository."})
        return attrs


class DocumentVersionSerializer(serializers.ModelSerializer):
    uploaded_by = UserSerializer(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = DocumentVersion
        fields = ("id", "version_number", "file_url", "original_filename", "file_size", "mime_type", "checksum", "revision_notes", "uploaded_by", "created_at")

    def get_file_url(self, obj):
        request = self.context.get("request")
        path = f"/api/versions/{obj.pk}/download/"
        return request.build_absolute_uri(path) if request else path


class DocumentSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    latest_version = serializers.SerializerMethodField()
    version_count = serializers.IntegerField(read_only=True)
    repository_name = serializers.CharField(source="repository.name", read_only=True)
    folder_name = serializers.CharField(source="folder.name", read_only=True, allow_null=True)
    folder_owner = UserSerializer(source="folder.owner", read_only=True, allow_null=True)

    class Meta:
        model = Document
        fields = ("id", "repository", "repository_name", "folder", "folder_name", "folder_owner", "owner", "title", "description", "tags", "is_archived", "latest_version", "version_count", "created_at", "updated_at")
        read_only_fields = ("id", "repository", "folder", "owner", "is_archived", "created_at", "updated_at")

    def get_latest_version(self, obj):
        version = obj.latest_version
        return DocumentVersionSerializer(version, context=self.context).data if version else None


class DocumentCreateSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True, validators=[validate_document_file])
    revision_notes = serializers.CharField(write_only=True, required=False, allow_blank=True)
    folder = serializers.PrimaryKeyRelatedField(queryset=Folder.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Document
        fields = ("id", "repository", "folder", "title", "description", "tags", "file", "revision_notes")

    def validate(self, attrs):
        folder = attrs.get("folder")
        if folder and folder.repository_id != attrs["repository"].pk:
            raise serializers.ValidationError({"folder": "Select a folder from the chosen repository."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        file = validated_data.pop("file")
        revision_notes = validated_data.pop("revision_notes", "Initial upload")
        user = self.context["request"].user
        document = Document.objects.create(owner=user, **validated_data)
        DocumentVersion.objects.create(document=document, version_number=1, file=file, original_filename=file.name, file_size=file.size, mime_type=getattr(file, "content_type", "") or mimetypes.guess_type(file.name)[0] or "", revision_notes=revision_notes, uploaded_by=user)
        return document


class VersionUploadSerializer(serializers.Serializer):
    file = serializers.FileField(validators=[validate_document_file])
    revision_notes = serializers.CharField(required=False, allow_blank=True)

    def create(self, validated_data):
        document = self.context["document"]
        file = validated_data["file"]
        number = (document.versions.order_by("-version_number").values_list("version_number", flat=True).first() or 0) + 1
        return DocumentVersion.objects.create(document=document, version_number=number, file=file, original_filename=file.name, file_size=file.size, mime_type=getattr(file, "content_type", "") or mimetypes.guess_type(file.name)[0] or "", revision_notes=validated_data.get("revision_notes", ""), uploaded_by=self.context["request"].user)


class AuditLogSerializer(serializers.ModelSerializer):
    actor = UserSerializer(read_only=True)

    class Meta:
        model = AuditLog
        fields = ("id", "actor", "action", "target_type", "target_id", "target_name", "details", "ip_address", "created_at")


class NotificationSerializer(serializers.ModelSerializer):
    actor = UserSerializer(read_only=True)
    is_read = serializers.BooleanField(read_only=True)

    class Meta:
        model = Notification
        fields = ("id", "category", "title", "message", "link", "actor", "is_read", "read_at", "created_at")
        read_only_fields = fields
