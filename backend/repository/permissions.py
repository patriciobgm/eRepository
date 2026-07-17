from rest_framework.permissions import BasePermission, SAFE_METHODS
from repository.models import Repository


class RepositoryAccessPermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        repository = obj if isinstance(obj, Repository) else obj.repository
        if request.user.is_assistant_principal:
            return True
        if repository.kind == Repository.Kind.PRIVATE:
            return repository.owner_id == request.user.id
        if request.method in SAFE_METHODS:
            return not repository.members.exists() or repository.members.filter(pk=request.user.pk).exists()
        if hasattr(obj, "owner_id"):
            return obj.owner_id == request.user.id
        return False

