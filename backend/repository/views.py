from django.db.models import Count, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from repository.models import AuditLog, Document, DocumentVersion, Repository
from repository.permissions import RepositoryAccessPermission
from repository.serializers import (AuditLogSerializer, DocumentCreateSerializer,
    DocumentSerializer, DocumentVersionSerializer, RepositorySerializer,
    VersionUploadSerializer)


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")


def log_event(request, action, target, details=None):
    AuditLog.objects.create(actor=request.user, action=action, target_type=target.__class__.__name__, target_id=str(target.pk), target_name=str(target), details=details or {}, ip_address=client_ip(request))


def accessible_repositories(user):
    if user.is_assistant_principal:
        return Repository.objects.all()
    return Repository.objects.filter(Q(kind=Repository.Kind.PRIVATE, owner=user) | Q(kind=Repository.Kind.SHARED, members=user) | Q(kind=Repository.Kind.SHARED, members__isnull=True)).distinct()


class RepositoryViewSet(viewsets.ModelViewSet):
    serializer_class = RepositorySerializer
    permission_classes = [RepositoryAccessPermission]
    search_fields = ("name", "description")

    def get_queryset(self):
        return accessible_repositories(self.request.user).select_related("owner").prefetch_related("members").annotate(document_count=Count("documents", filter=Q(documents__is_archived=False))).order_by("kind", "name")

    def perform_create(self, serializer):
        if not self.request.user.is_assistant_principal:
            raise PermissionDenied("Only the Assistant Principal can create shared repositories.")
        repository = serializer.save(owner=self.request.user, kind=Repository.Kind.SHARED)
        log_event(self.request, AuditLog.Action.CREATED, repository)

    def perform_update(self, serializer):
        if not self.request.user.is_assistant_principal:
            raise PermissionDenied("Only the Assistant Principal can update repositories.")
        repository = serializer.save()
        log_event(self.request, AuditLog.Action.UPDATED, repository)

    def perform_destroy(self, instance):
        if not self.request.user.is_assistant_principal or instance.kind == Repository.Kind.PRIVATE:
            raise PermissionDenied("Private repositories cannot be deleted; only the Assistant Principal can delete shared repositories.")
        log_event(self.request, AuditLog.Action.DELETED, instance)
        instance.delete()


class DocumentViewSet(viewsets.ModelViewSet):
    permission_classes = [RepositoryAccessPermission]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    search_fields = ("title", "description", "tags", "owner__first_name", "owner__last_name", "versions__original_filename")
    filterset_fields = ("repository", "owner", "is_archived")
    ordering_fields = ("title", "created_at", "updated_at")

    def get_queryset(self):
        return Document.objects.filter(repository__in=accessible_repositories(self.request.user)).select_related("owner", "repository").prefetch_related("versions__uploaded_by").annotate(version_count=Count("versions")).distinct().order_by("-updated_at")

    def get_serializer_class(self):
        return DocumentCreateSerializer if self.action == "create" else DocumentSerializer

    def perform_create(self, serializer):
        repository = serializer.validated_data["repository"]
        if not accessible_repositories(self.request.user).filter(pk=repository.pk).exists():
            raise PermissionDenied("You do not have access to this repository.")
        document = serializer.save()
        log_event(self.request, AuditLog.Action.CREATED, document, {"repository": repository.name})

    def perform_update(self, serializer):
        document = self.get_object()
        if not self.request.user.is_assistant_principal and document.owner_id != self.request.user.id:
            raise PermissionDenied("You can only edit documents you own.")
        document = serializer.save()
        log_event(self.request, AuditLog.Action.UPDATED, document)

    def perform_destroy(self, instance):
        if not self.request.user.is_assistant_principal and instance.owner_id != self.request.user.id:
            raise PermissionDenied("You can only delete documents you own.")
        log_event(self.request, AuditLog.Action.DELETED, instance)
        instance.delete()

    @action(detail=True, methods=["get", "post"])
    def versions(self, request, pk=None):
        document = self.get_object()
        if request.method == "GET":
            return Response(DocumentVersionSerializer(document.versions.select_related("uploaded_by"), many=True, context={"request": request}).data)
        if not request.user.is_assistant_principal and document.owner_id != request.user.id:
            raise PermissionDenied("You can only upload revisions to documents you own.")
        serializer = VersionUploadSerializer(data=request.data, context={"request": request, "document": document})
        serializer.is_valid(raise_exception=True)
        version = serializer.save()
        document.save(update_fields=["updated_at"])
        log_event(request, AuditLog.Action.UPLOADED_VERSION, document, {"version": version.version_number, "filename": version.original_filename})
        return Response(DocumentVersionSerializer(version, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        document = self.get_object()
        if not request.user.is_assistant_principal and document.owner_id != request.user.id:
            raise PermissionDenied("You can only archive documents you own.")
        document.is_archived = not document.is_archived
        document.save(update_fields=["is_archived", "updated_at"])
        action_name = AuditLog.Action.ARCHIVED if document.is_archived else AuditLog.Action.RESTORED
        log_event(request, action_name, document)
        return Response(DocumentSerializer(document, context={"request": request}).data)


class VersionDownloadView(APIView):
    permission_classes = [RepositoryAccessPermission]

    def get(self, request, pk):
        version = get_object_or_404(DocumentVersion.objects.select_related("document__repository", "document__owner"), pk=pk)
        self.check_object_permissions(request, version.document)
        log_event(request, AuditLog.Action.DOWNLOADED, version.document, {"version": version.version_number, "filename": version.original_filename})
        return FileResponse(version.file.open("rb"), as_attachment=True, filename=version.original_filename)


class AuditLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = AuditLogSerializer
    search_fields = ("target_name", "actor__first_name", "actor__last_name", "actor__email")
    filterset_fields = ("action", "actor")

    def get_queryset(self):
        queryset = AuditLog.objects.select_related("actor")
        if self.request.user.is_assistant_principal:
            return queryset
        return queryset.filter(Q(actor=self.request.user) | Q(target_type="Document", target_id__in=self.request.user.documents.values("id")))


class DashboardView(APIView):
    def get(self, request):
        repositories = accessible_repositories(request.user)
        documents = Document.objects.filter(repository__in=repositories, is_archived=False)
        total_bytes = DocumentVersion.objects.filter(document__in=documents).aggregate(total=__import__("django.db.models", fromlist=["Sum"]).Sum("file_size"))["total"] or 0
        data = {
            "repositories": repositories.count(),
            "documents": documents.count(),
            "my_documents": documents.filter(owner=request.user).count(),
            "storage_bytes": total_bytes,
            "recent_documents": DocumentSerializer(documents.select_related("owner", "repository").prefetch_related("versions__uploaded_by").annotate(version_count=Count("versions"))[:6], many=True, context={"request": request}).data,
            "recent_activity": AuditLogSerializer(AuditLog.objects.filter(Q(actor=request.user) | Q(target_id__in=documents.values("id"))).select_related("actor")[:8], many=True).data,
            "generated_at": timezone.now(),
        }
        return Response(data)
