from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import User


@receiver(post_save, sender=User)
def synchronize_private_repository(sender, instance, **kwargs):
    if instance.is_superuser:
        return

    from repository.models import Repository

    display_name = (instance.get_full_name() or instance.username).strip()
    repository_name = f"{display_name}'s Repository"[: Repository._meta.get_field("name").max_length]
    repository, created = Repository.objects.get_or_create(
        owner=instance,
        kind=Repository.Kind.PRIVATE,
        defaults={"name": repository_name},
    )
    if not created and repository.name != repository_name:
        Repository.objects.filter(pk=repository.pk).update(name=repository_name)
