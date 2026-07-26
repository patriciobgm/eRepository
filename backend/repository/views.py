from django.db.models import Count, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Department, Position, User
from accounts.serializers import UserSerializer
from repository.models import AuditLog, Document, DocumentVersion, Folder, Notification, Repository
from repository.permissions import RepositoryAccessPermission
from repository.serializers import (AuditLogSerializer, DocumentCreateSerializer,
    DocumentSerializer, DocumentVersionSerializer, FolderSerializer, NotificationSerializer, RepositorySerializer,
    VersionUploadSerializer)
from repository.services import notify_users, shared_repository_audience


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")


def log_event(request, action, target, details=None):
    AuditLog.objects.create(actor=request.user, action=action, target_type=target.__class__.__name__, target_id=str(target.pk), target_name=str(target), details=details or {}, ip_address=client_ip(request))


def accessible_repositories(user):
    if user.is_assistant_principal:
        return Repository.objects.all()
    return Repository.objects.filter(
        Q(kind=Repository.Kind.PRIVATE, owner=user)
        | Q(kind=Repository.Kind.SHARED, owner=user)
        | Q(kind=Repository.Kind.SHARED, members=user)
        | Q(kind=Repository.Kind.SHARED, members__isnull=True)
    ).distinct()


class RepositoryViewSet(viewsets.ModelViewSet):
    serializer_class = RepositorySerializer
    permission_classes = [RepositoryAccessPermission]
    search_fields = ("name", "description")

    def get_queryset(self):
        return accessible_repositories(self.request.user).select_related("owner").prefetch_related("members", "owner__designations").annotate(document_count=Count("documents", filter=Q(documents__is_archived=False))).order_by("kind", "name")

    def perform_create(self, serializer):
        if not self.request.user.can_create_shared_repositories:
            raise PermissionDenied("A Principal or faculty member with an authorized designation is required to create a shared repository.")
        if not serializer.validated_data.get("description", "").strip():
            raise ValidationError({"description": "Explain the purpose of this shared repository."})
        repository = serializer.save(owner=self.request.user, kind=Repository.Kind.SHARED)
        log_event(self.request, AuditLog.Action.CREATED, repository)
        notify_users(
            shared_repository_audience(repository),
            category=Notification.Category.REPOSITORY,
            title="Shared repository available",
            message=f"You can now access {repository.name}.",
            actor=self.request.user,
            link="/repositories",
        )

    def perform_update(self, serializer):
        if not self.request.user.can_manage_shared_repository(serializer.instance):
            raise PermissionDenied("Only the Principal or repository initiator can update this shared repository.")
        description = serializer.validated_data.get("description", serializer.instance.description)
        if not description.strip():
            raise ValidationError({"description": "Explain the purpose of this shared repository."})
        previous_audience = set(shared_repository_audience(serializer.instance).values_list("pk", flat=True))
        repository = serializer.save()
        log_event(self.request, AuditLog.Action.UPDATED, repository)
        current_audience = set(shared_repository_audience(repository).values_list("pk", flat=True))
        added = current_audience - previous_audience
        removed = previous_audience - current_audience
        retained = current_audience & previous_audience
        notify_users(added, category=Notification.Category.REPOSITORY, title="Repository access granted", message=f"You can now access {repository.name}.", actor=self.request.user, link="/repositories")
        notify_users(removed, category=Notification.Category.REPOSITORY, title="Repository access removed", message=f"Your access to {repository.name} was removed.", actor=self.request.user)
        notify_users(retained, category=Notification.Category.REPOSITORY, title="Shared repository updated", message=f"{repository.name} details or audience were updated.", actor=self.request.user, link="/repositories")

    @action(detail=False, methods=["get"], url_path="eligible-members")
    def eligible_members(self, request):
        if not request.user.can_create_shared_repositories:
            raise PermissionDenied("An authorized designation is required to select shared repository members.")
        members = User.objects.filter(
            is_active=True,
            is_superuser=False,
            role__in=(User.Role.TEACHER, User.Role.MASTER_TEACHER),
        ).select_related("department", "position").order_by("last_name", "first_name", "username")
        return Response(UserSerializer(members, many=True, context={"request": request}).data)

    def perform_destroy(self, instance):
        if not self.request.user.can_manage_shared_repository(instance):
            raise PermissionDenied("Private repositories cannot be deleted; only the Principal or repository initiator can delete shared repositories.")
        log_event(self.request, AuditLog.Action.DELETED, instance)
        instance.delete()


class FolderViewSet(viewsets.ModelViewSet):
    serializer_class = FolderSerializer
    pagination_class = None
    search_fields = ("name", "owner__first_name", "owner__last_name")
    filterset_fields = ("repository", "owner")
    ordering_fields = ("name", "created_at", "updated_at")

    def get_queryset(self):
        return Folder.objects.filter(repository__in=accessible_repositories(self.request.user)).select_related(
            "repository", "owner", "owner__department", "owner__position"
        ).prefetch_related("owner__designations").annotate(document_count=Count("documents", filter=Q(documents__is_archived=False))).order_by("name")

    def _can_manage(self, folder):
        user = self.request.user
        return not user.is_superuser and (
            folder.owner_id == user.pk
            or user.can_manage_shared_repository(folder.repository)
        )

    def perform_create(self, serializer):
        repository = serializer.validated_data["repository"]
        user = self.request.user
        if user.is_superuser:
            raise PermissionDenied("Superadmins have read-only repository access and cannot create folders.")
        if repository.kind == Repository.Kind.PRIVATE and repository.owner_id != user.pk:
            raise PermissionDenied("You can only create folders in your own private repository.")
        if repository.kind == Repository.Kind.SHARED and not accessible_repositories(user).filter(pk=repository.pk).exists():
            raise PermissionDenied("You do not have access to this shared repository.")
        folder = serializer.save(owner=user)
        log_event(self.request, AuditLog.Action.CREATED, folder, {"repository": repository.name})
        if repository.kind == Repository.Kind.SHARED:
            notify_users(
                shared_repository_audience(repository),
                category=Notification.Category.REPOSITORY,
                title="New shared folder",
                message=f"{user.get_full_name() or user.username} created the {folder.name} folder in {repository.name}.",
                actor=user,
                link="/repositories",
            )

    def perform_update(self, serializer):
        if not self._can_manage(serializer.instance):
            raise PermissionDenied("Only the folder owner or Principal can update this folder.")
        folder = serializer.save()
        log_event(self.request, AuditLog.Action.UPDATED, folder, {"repository": folder.repository.name})

    def perform_destroy(self, instance):
        if not self._can_manage(instance):
            raise PermissionDenied("Only the folder owner or Principal can remove this folder.")
        log_event(self.request, AuditLog.Action.DELETED, instance, {"repository": instance.repository.name, "documents_moved_to_root": instance.documents.count()})
        instance.delete()


class DocumentViewSet(viewsets.ModelViewSet):
    permission_classes = [RepositoryAccessPermission]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    search_fields = ("title", "description", "tags", "owner__first_name", "owner__last_name", "versions__original_filename")
    filterset_fields = ("repository", "owner", "is_archived")
    ordering_fields = ("title", "created_at", "updated_at")

    def get_queryset(self):
        return Document.objects.filter(repository__in=accessible_repositories(self.request.user)).select_related("owner", "repository", "folder", "folder__owner").prefetch_related("owner__designations", "folder__owner__designations", "versions__uploaded_by__designations").annotate(version_count=Count("versions")).distinct().order_by("-updated_at")

    def get_serializer_class(self):
        return DocumentCreateSerializer if self.action == "create" else DocumentSerializer

    def perform_create(self, serializer):
        if self.request.user.is_superuser:
            raise PermissionDenied("Superadmins have read-only repository access and cannot upload documents.")
        repository = serializer.validated_data["repository"]
        if not accessible_repositories(self.request.user).filter(pk=repository.pk).exists():
            raise PermissionDenied("You do not have access to this repository.")
        document = serializer.save()
        log_event(self.request, AuditLog.Action.CREATED, document, {"repository": repository.name})
        if repository.kind == Repository.Kind.SHARED:
            notify_users(
                shared_repository_audience(repository),
                category=Notification.Category.DOCUMENT,
                title="New shared document",
                message=f"{self.request.user.get_full_name() or self.request.user.username} uploaded {document.title} to {repository.name}.",
                actor=self.request.user,
                link="/repositories",
            )

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
            return Response(DocumentVersionSerializer(document.versions.select_related("uploaded_by").prefetch_related("uploaded_by__designations"), many=True, context={"request": request}).data)
        if not request.user.is_assistant_principal and document.owner_id != request.user.id:
            raise PermissionDenied("You can only upload revisions to documents you own.")
        serializer = VersionUploadSerializer(data=request.data, context={"request": request, "document": document})
        serializer.is_valid(raise_exception=True)
        version = serializer.save()
        document.save(update_fields=["updated_at"])
        log_event(request, AuditLog.Action.UPLOADED_VERSION, document, {"version": version.version_number, "filename": version.original_filename})
        if document.repository.kind == Repository.Kind.SHARED:
            notify_users(
                shared_repository_audience(document.repository),
                category=Notification.Category.DOCUMENT,
                title="New document revision",
                message=f"{request.user.get_full_name() or request.user.username} uploaded version {version.version_number} of {document.title}.",
                actor=request.user,
                link="/repositories",
            )
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
        queryset = AuditLog.objects.select_related("actor").prefetch_related("actor__designations")
        if self.request.user.is_assistant_principal:
            return queryset
        return queryset.filter(Q(actor=self.request.user) | Q(target_type="Document", target_id__in=self.request.user.documents.values("id")))


class NotificationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).select_related("actor").prefetch_related("actor__designations")

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        return Response({"count": self.get_queryset().filter(read_at__isnull=True).count()})

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        updated = self.get_queryset().filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({"updated": updated})

    @action(detail=False, methods=["delete"], url_path="clear-all")
    def clear_all(self, request):
        deleted, _ = self.get_queryset().delete()
        return Response({"deleted": deleted})


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
            "recent_documents": DocumentSerializer(documents.select_related("owner", "repository", "folder", "folder__owner").prefetch_related("owner__designations", "folder__owner__designations", "versions__uploaded_by__designations").annotate(version_count=Count("versions"))[:6], many=True, context={"request": request}).data,
            "recent_activity": AuditLogSerializer(AuditLog.objects.filter(Q(actor=request.user) | Q(target_id__in=documents.values("id"))).select_related("actor").prefetch_related("actor__designations")[:8], many=True).data,
            "generated_at": timezone.now(),
        }
        if request.user.is_superuser:
            faculty = User.objects.filter(is_superuser=False)
            data["management"] = {
                "faculty_accounts": faculty.count(),
                "pending_accounts": faculty.filter(is_active=False).count(),
                "principals": faculty.filter(role=User.Role.ASSISTANT_PRINCIPAL, is_active=True).count(),
                "departments": Department.objects.filter(is_active=True).count(),
                "positions": Position.objects.filter(is_active=True).count(),
            }
            data["recent_activity"] = AuditLogSerializer(AuditLog.objects.select_related("actor").prefetch_related("actor__designations")[:8], many=True).data
        return Response(data)
