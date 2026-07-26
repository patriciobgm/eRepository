import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


DEFAULT_DESIGNATIONS = (
    ("Research Coordinator", "Coordinates faculty research initiatives and resources."),
    ("Curriculum Leader", "Leads curriculum planning, alignment, and implementation."),
    ("Focal Person", "Coordinates an assigned school program or priority area."),
)


def seed_designations(apps, schema_editor):
    Designation = apps.get_model("accounts", "Designation")
    for name, description in DEFAULT_DESIGNATIONS:
        Designation.objects.get_or_create(
            name=name,
            defaults={
                "description": description,
                "can_create_shared_repositories": True,
                "is_active": True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0007_rename_phone_user_mobile"),
    ]

    operations = [
        migrations.CreateModel(
            name="Designation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("description", models.TextField(blank=True)),
                ("can_create_shared_repositories", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="UserDesignation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("assigned_at", models.DateTimeField(auto_now_add=True)),
                ("assigned_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="designation_assignments_made", to=settings.AUTH_USER_MODEL)),
                ("designation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="assignments", to="accounts.designation")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="designation_assignments", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("designation__name",),
                "constraints": [models.UniqueConstraint(fields=("user", "designation"), name="unique_user_designation")],
            },
        ),
        migrations.AddField(
            model_name="user",
            name="designations",
            field=models.ManyToManyField(blank=True, related_name="users", through="accounts.UserDesignation", through_fields=("user", "designation"), to="accounts.designation"),
        ),
        migrations.RunPython(seed_designations, migrations.RunPython.noop),
    ]
