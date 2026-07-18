from django.db import migrations


def remove_empty_superadmin_repositories(apps, schema_editor):
    Repository = apps.get_model("repository", "Repository")
    Repository.objects.filter(
        kind="PRIVATE",
        owner__is_superuser=True,
        documents__isnull=True,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_clear_superadmin_profile_fields"),
        ("repository", "0001_initial"),
    ]
    operations = [migrations.RunPython(remove_empty_superadmin_repositories, migrations.RunPython.noop)]
