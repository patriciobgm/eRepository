from django.core.management.base import BaseCommand

from accounts.models import User
from repository.models import Repository


class Command(BaseCommand):
    help = "Create local demonstration accounts and a shared repository"

    def handle(self, *args, **options):
        people = [
            ("admin", "admin@school.edu", User.Role.ASSISTANT_PRINCIPAL, "Ana", "Reyes", "Office of the Principal", "Assistant Principal"),
            ("teacher", "teacher@school.edu", User.Role.TEACHER, "Maria", "Santos", "Science", "Teacher I"),
            ("masterteacher", "master@school.edu", User.Role.MASTER_TEACHER, "Ramon", "Cruz", "Mathematics", "Master Teacher I"),
        ]
        users = []
        for username, email, role, first_name, last_name, department, position in people:
            user, created = User.objects.get_or_create(username=username, defaults={"email": email, "role": role, "first_name": first_name, "last_name": last_name, "department": department, "position": position, "employee_id": f"DEMO-{username.upper()}", "is_staff": role == User.Role.ASSISTANT_PRINCIPAL})
            if created:
                user.set_password("DemoPass!2026")
                user.save(update_fields=["password"])
            users.append(user)
        admin = users[0]
        Repository.objects.get_or_create(name="School-Wide Teaching Resources", kind=Repository.Kind.SHARED, defaults={"description": "Teaching materials available to all faculty.", "owner": admin})
        self.stdout.write(self.style.SUCCESS("Demo ready. Sign in with admin@school.edu, teacher@school.edu, or master@school.edu using DemoPass!2026"))

