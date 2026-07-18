import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("repository", "0002_remove_empty_superadmin_repositories"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("category", models.CharField(choices=[("ACCOUNT", "Account"), ("REPOSITORY", "Repository"), ("DOCUMENT", "Document"), ("SYSTEM", "System")], default="SYSTEM", max_length=20)),
                ("title", models.CharField(max_length=180)),
                ("message", models.CharField(max_length=500)),
                ("link", models.CharField(blank=True, max_length=255)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="triggered_notifications", to=settings.AUTH_USER_MODEL)),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("-created_at",),
                "indexes": [models.Index(fields=["recipient", "read_at", "-created_at"], name="notification_inbox_idx")],
            },
        ),
    ]
