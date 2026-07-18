from django.db import migrations


def sync_private_repository_names(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Repository = apps.get_model("repository", "Repository")
    max_length = Repository._meta.get_field("name").max_length

    for user in User.objects.filter(is_superuser=False).iterator():
        full_name = f"{user.first_name} {user.last_name}".strip() or user.username
        Repository.objects.filter(owner_id=user.pk, kind="PRIVATE").update(
            name=f"{full_name}'s Repository"[:max_length]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_managed_positions"),
        ("repository", "0002_remove_empty_superadmin_repositories"),
    ]

    operations = [
        migrations.RunPython(sync_private_repository_names, migrations.RunPython.noop),
    ]
