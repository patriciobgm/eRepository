from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import User


@receiver(post_save, sender=User)
def create_private_repository(sender, instance, created, **kwargs):
    if created:
        from repository.models import Repository

        Repository.objects.get_or_create(
            owner=instance,
            kind=Repository.Kind.PRIVATE,
            defaults={"name": f"{instance.get_full_name() or instance.username}'s Repository"},
        )

