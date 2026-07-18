from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_sync_private_repository_names"),
    ]

    operations = [
        migrations.RenameField(
            model_name="user",
            old_name="phone",
            new_name="mobile",
        ),
    ]
