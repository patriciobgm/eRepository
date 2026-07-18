import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models.functions import Lower


class Migration(migrations.Migration):
    dependencies = [
        ("repository", "0003_notification"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Folder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="owned_folders", to=settings.AUTH_USER_MODEL)),
                ("repository", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="folders", to="repository.repository")),
            ],
            options={
                "ordering": ("name",),
                "constraints": [models.UniqueConstraint(Lower("name"), models.F("repository"), name="unique_folder_name_per_repository")],
            },
        ),
        migrations.AddField(
            model_name="document",
            name="folder",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="documents", to="repository.folder"),
        ),
    ]
