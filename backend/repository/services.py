from django.db.models import Q

from accounts.models import User
from repository.models import Notification, Repository


def notify_users(recipients, *, category, title, message, actor=None, link=""):
    recipient_ids = recipients.values_list("pk", flat=True) if hasattr(recipients, "values_list") else recipients
    unique_ids = {recipient_id for recipient_id in recipient_ids if recipient_id and recipient_id != getattr(actor, "pk", None)}
    Notification.objects.bulk_create([
        Notification(
            recipient_id=recipient_id,
            actor=actor,
            category=category,
            title=title,
            message=message,
            link=link,
        )
        for recipient_id in unique_ids
    ])


def management_recipients():
    return User.objects.filter(is_active=True).filter(Q(is_superuser=True) | Q(role=User.Role.ASSISTANT_PRINCIPAL))


def shared_repository_audience(repository):
    if repository.kind != Repository.Kind.SHARED:
        return User.objects.none()
    if repository.members.exists():
        audience = User.objects.filter(pk__in=repository.members.values("pk"), is_active=True)
    else:
        audience = User.objects.filter(
            is_active=True,
            is_superuser=False,
            role__in=(User.Role.TEACHER, User.Role.MASTER_TEACHER),
        )
    return User.objects.filter(Q(pk__in=audience.values("pk")) | Q(pk=repository.owner_id), is_active=True).distinct()
