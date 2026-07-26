from django.core.management.base import BaseCommand

from accounts.models import Department, Designation, Position, User, UserDesignation
from repository.models import Repository


class Command(BaseCommand):
    help = "Create local demonstration accounts and a shared repository"

    def handle(self, *args, **options):
        departments = {name: Department.objects.get_or_create(name=name)[0] for name in ("TVL", "ABM & Mathematics", "Science & Social Sciences", "PE & Language", "Admin")}
        position_names = {
            User.Role.TEACHER: [f"Teacher {level}" for level in ("I", "II", "III", "IV", "V", "VI", "VII")],
            User.Role.MASTER_TEACHER: [f"Master Teacher {level}" for level in ("I", "II", "III", "IV", "V")],
            User.Role.ASSISTANT_PRINCIPAL: [f"Principal {level}" for level in ("I", "II", "III", "IV", "V")],
        }
        positions = {(role, name): Position.objects.get_or_create(role=role, name=name)[0] for role, names in position_names.items() for name in names}
        people = [
            ("superadmin", "superadmin@school.edu", User.Role.ASSISTANT_PRINCIPAL, "System", "Administrator", "Admin", None, True),
            ("admin", "admin@school.edu", User.Role.ASSISTANT_PRINCIPAL, "Ana", "Reyes", "Admin", "Principal I", False),
            ("teacher", "teacher@school.edu", User.Role.TEACHER, "Maria", "Santos", "Science & Social Sciences", "Teacher I", False),
            ("masterteacher", "master@school.edu", User.Role.MASTER_TEACHER, "Ramon", "Cruz", "ABM & Mathematics", "Master Teacher I", False),
        ]
        users = []
        for username, email, role, first_name, last_name, department, position, is_superuser in people:
            user, created = User.objects.get_or_create(username=username, defaults={"email": email, "role": role, "first_name": first_name, "last_name": last_name, "department": departments[department], "position": positions.get((role, position)), "employee_id": f"DEMO-{username.upper()}", "is_staff": role == User.Role.ASSISTANT_PRINCIPAL, "is_superuser": is_superuser})
            if created:
                user.set_password("DemoPass!2026")
                user.save(update_fields=["password"])
            users.append(user)
        admin = users[1]
        research, _ = Designation.objects.get_or_create(name="Research Coordinator", defaults={"description": "Coordinates faculty research initiatives and resources.", "can_create_shared_repositories": True})
        UserDesignation.objects.get_or_create(user=users[3], designation=research, defaults={"assigned_by": admin})
        Repository.objects.get_or_create(name="School-Wide Teaching Resources", kind=Repository.Kind.SHARED, defaults={"description": "Teaching materials available to all faculty.", "owner": admin})
        self.stdout.write(self.style.SUCCESS("Demo ready. Sign in with superadmin@school.edu, admin@school.edu, teacher@school.edu, or master@school.edu using DemoPass!2026"))
