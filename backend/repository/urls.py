from django.urls import include, path
from rest_framework.routers import DefaultRouter
from repository.views import AuditLogViewSet, DashboardView, DocumentViewSet, RepositoryViewSet, VersionDownloadView

router = DefaultRouter()
router.register("repositories", RepositoryViewSet, basename="repositories")
router.register("documents", DocumentViewSet, basename="documents")
router.register("audit-logs", AuditLogViewSet, basename="audit-logs")

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("versions/<int:pk>/download/", VersionDownloadView.as_view(), name="version-download"),
    path("", include(router.urls)),
]

