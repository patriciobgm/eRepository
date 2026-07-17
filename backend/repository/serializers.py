import mimetypes
from django.conf import settings
from django.db import transaction
from rest_framework import serializers

from accounts.models import User
from accounts.serializers import UserSerializer
from repository.models import AuditLog, Document, DocumentVersion, Repository


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
    member_ids = serializers.PrimaryKeyRelatedField(source="members", many=True, queryset=User.objects.all(), required=False, write_only=True)
    document_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Repository
        fields = ("id", "name", "description", "kind", "owner", "member_ids", "document_count", "created_at", "updated_at")
        read_only_fields = ("id", "owner", "kind", "created_at", "updated_at")


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

    class Meta:
        model = Document
        fields = ("id", "repository", "repository_name", "owner", "title", "description", "tags", "is_archived", "latest_version", "version_count", "created_at", "updated_at")
        read_only_fields = ("id", "repository", "owner", "is_archived", "created_at", "updated_at")

    def get_latest_version(self, obj):
        version = obj.latest_version
        return DocumentVersionSerializer(version, context=self.context).data if version else None


class DocumentCreateSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True, validators=[validate_document_file])
    revision_notes = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Document
        fields = ("id", "repository", "title", "description", "tags", "file", "revision_notes")

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
