from django.db import migrations


def clear_superadmin_profile_fields(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(is_superuser=True).update(department=None, position="", bio="")


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_google_subject")]
    operations = [migrations.RunPython(clear_superadmin_profile_fields, migrations.RunPython.noop)]
