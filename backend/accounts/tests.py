from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Department, Designation, Position, User, UserDesignation
from repository.models import Notification, Repository


class RegistrationTests(APITestCase):
    def setUp(self):
        self.department = Department.objects.get(name="Science & Social Sciences")
        self.position = Position.objects.get(name="Teacher I", role=User.Role.TEACHER)

    def test_registration_requires_approval_and_creates_private_repository(self):
        response = self.client.post(reverse("register"), {
            "first_name": "Maria", "last_name": "Santos", "email": "maria@school.edu",
            "employee_id": "SHS-100", "department_id": self.department.id, "position_id": self.position.id,
            "role": User.Role.TEACHER, "password": "StrongFaculty!2026", "password_confirm": "StrongFaculty!2026",
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="maria@school.edu")
        self.assertFalse(user.is_active)
        self.assertEqual(user.department, self.department)
        self.assertTrue(Repository.objects.filter(owner=user, kind=Repository.Kind.PRIVATE).exists())

    def test_registration_cannot_claim_assistant_principal_role(self):
        response = self.client.post(reverse("register"), {
            "first_name": "Fake", "last_name": "Admin", "email": "fake@school.edu",
            "employee_id": "SHS-101", "department_id": self.department.id, "position_id": self.position.id,
            "role": User.Role.ASSISTANT_PRINCIPAL, "password": "StrongFaculty!2026", "password_confirm": "StrongFaculty!2026",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_registration_notifies_active_management(self):
        principal = User.objects.create_user("principal", "principal@school.edu", "Password!2026", role=User.Role.ASSISTANT_PRINCIPAL)
        response = self.client.post(reverse("register"), {
            "first_name": "Pending", "last_name": "Teacher", "email": "pending@school.edu",
            "employee_id": "SHS-102", "department_id": self.department.id, "position_id": self.position.id,
            "role": User.Role.TEACHER, "password": "StrongFaculty!2026", "password_confirm": "StrongFaculty!2026",
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Notification.objects.filter(recipient=principal, category=Notification.Category.ACCOUNT, link="/staff").exists())


class AdministrationBoundaryTests(APITestCase):
    def setUp(self):
        self.admin_department = Department.objects.get(name="Admin")
        self.science = Department.objects.get(name="Science & Social Sciences")
        self.teacher_position = Position.objects.get(name="Teacher I", role=User.Role.TEACHER)
        self.principal_position = Position.objects.get(name="Principal I", role=User.Role.ASSISTANT_PRINCIPAL)
        self.superadmin = User.objects.create_superuser("superadmin", "superadmin@school.edu", "Password!2026", role=User.Role.ASSISTANT_PRINCIPAL)
        self.assistant = User.objects.create_user("assistant", "assistant@school.edu", "Password!2026", role=User.Role.ASSISTANT_PRINCIPAL)
        self.teacher = User.objects.create_user("teacher", "teacher@school.edu", "Password!2026", role=User.Role.TEACHER, department=self.science, position=self.teacher_position)

    def test_assistant_principal_department_is_always_admin(self):
        self.assistant.department = self.science
        self.assistant.save()
        self.assertEqual(self.assistant.department, self.admin_department)

    def test_superadmin_has_no_organizational_profile_and_cannot_edit_profile(self):
        self.superadmin.department = self.science
        self.superadmin.position = self.principal_position
        self.superadmin.bio = "Should be removed"
        self.superadmin.save()
        self.assertIsNone(self.superadmin.department)
        self.assertIsNone(self.superadmin.position)
        self.assertEqual(self.superadmin.bio, "")
        self.client.force_authenticate(self.superadmin)
        response = self.client.patch("/api/auth/profile/", {"first_name": "Changed"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_list_hides_current_and_protected_accounts(self):
        self.client.force_authenticate(self.superadmin)
        superadmin_view = self.client.get("/api/auth/users/")
        superadmin_ids = [item["id"] for item in superadmin_view.data["results"]]
        self.assertNotIn(self.superadmin.id, superadmin_ids)
        self.assertIn(self.assistant.id, superadmin_ids)

        self.client.force_authenticate(self.assistant)
        assistant_view = self.client.get("/api/auth/users/")
        assistant_ids = [item["id"] for item in assistant_view.data["results"]]
        self.assertNotIn(self.assistant.id, assistant_ids)
        self.assertNotIn(self.superadmin.id, assistant_ids)
        self.assertIn(self.teacher.id, assistant_ids)

    def test_assistant_principal_cannot_edit_self_or_grant_assistant_role(self):
        self.client.force_authenticate(self.assistant)
        own_response = self.client.patch(f"/api/auth/users/{self.assistant.id}/", {"position": "Changed"})
        promote_response = self.client.patch(f"/api/auth/users/{self.teacher.id}/", {"role": User.Role.ASSISTANT_PRINCIPAL})
        self.assertEqual(own_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(promote_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superadmin_can_manage_assistant_principal(self):
        self.client.force_authenticate(self.superadmin)
        principal_two = Position.objects.get(name="Principal II", role=User.Role.ASSISTANT_PRINCIPAL)
        response = self.client.patch(f"/api/auth/users/{self.assistant.id}/", {"position_id": principal_two.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_account_approval_notifies_the_user(self):
        self.teacher.is_active = False
        self.teacher.save(update_fields=["is_active"])
        self.client.force_authenticate(self.assistant)
        response = self.client.post(f"/api/auth/users/{self.teacher.id}/approve/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Notification.objects.filter(recipient=self.teacher, title="Account approved").exists())

    def test_only_superadmin_can_create_departments(self):
        self.client.force_authenticate(self.assistant)
        denied = self.client.post("/api/auth/departments/", {"name": "New Department"})
        self.client.force_authenticate(self.superadmin)
        created = self.client.post("/api/auth/departments/", {"name": "New Department"})
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)

    def test_positions_are_superadmin_managed_and_role_bound(self):
        self.client.force_authenticate(self.assistant)
        denied = self.client.post("/api/auth/positions/", {"name": "Teacher VIII", "role": User.Role.TEACHER})
        self.client.force_authenticate(self.superadmin)
        created = self.client.post("/api/auth/positions/", {"name": "Teacher VIII", "role": User.Role.TEACHER})
        mismatch = self.client.patch(f"/api/auth/users/{self.teacher.id}/", {"position_id": self.principal_position.id})
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(mismatch.status_code, status.HTTP_400_BAD_REQUEST)

    def test_principal_can_assign_designations_with_audit_and_notification(self):
        research = Designation.objects.get(name="Research Coordinator")
        self.client.force_authenticate(self.assistant)
        response = self.client.patch(f"/api/auth/users/{self.teacher.id}/", {"designation_ids": [research.id]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        assignment = UserDesignation.objects.get(user=self.teacher, designation=research)
        self.assertEqual(assignment.assigned_by, self.assistant)
        self.assertTrue(response.data["can_create_shared_repositories"])
        self.assertTrue(Notification.objects.filter(recipient=self.teacher, title="Designations updated").exists())

    def test_designation_types_are_superadmin_managed(self):
        self.client.force_authenticate(self.assistant)
        denied = self.client.post("/api/auth/designations/", {"name": "Program Coordinator", "can_create_shared_repositories": True})
        self.client.force_authenticate(self.superadmin)
        created = self.client.post("/api/auth/designations/", {"name": "Program Coordinator", "description": "Coordinates a school program.", "can_create_shared_repositories": True})
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)

    def test_inactive_designation_revokes_repository_initiation_permission(self):
        research = Designation.objects.get(name="Research Coordinator")
        UserDesignation.objects.create(user=self.teacher, designation=research, assigned_by=self.assistant)
        self.assertTrue(self.teacher.can_create_shared_repositories)
        research.is_active = False
        research.save(update_fields=["is_active"])
        self.assertFalse(self.teacher.can_create_shared_repositories)

    def test_profile_name_change_updates_only_the_private_repository_name(self):
        shared = Repository.objects.create(
            owner=self.assistant,
            kind=Repository.Kind.SHARED,
            name="Faculty Resources",
        )
        self.client.force_authenticate(self.teacher)

        response = self.client.patch(
            "/api/auth/profile/",
            {"first_name": "Juan", "last_name": "Dela Cruz", "mobile": "+63 917 123 4567"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        private = Repository.objects.get(owner=self.teacher, kind=Repository.Kind.PRIVATE)
        shared.refresh_from_db()
        self.assertEqual(private.name, "Juan Dela Cruz's Repository")
        self.assertEqual(shared.name, "Faculty Resources")
        self.assertEqual(response.data["mobile"], "+63 917 123 4567")


@override_settings(GOOGLE_OAUTH_CLIENT_ID="test-client.apps.googleusercontent.com")
class GoogleAuthenticationTests(APITestCase):
    def setUp(self):
        self.department = Department.objects.get(name="TVL")
        self.position = Position.objects.get(name="Teacher I", role=User.Role.TEACHER)

    @patch("accounts.serializers.id_token.verify_oauth2_token")
    def test_google_registration_creates_unusable_password_pending_account(self, verify):
        verify.return_value = {"sub": "google-account-100", "email": "google.teacher@gmail.com", "email_verified": True, "given_name": "Google", "family_name": "Teacher"}
        response = self.client.post("/api/auth/google/", {"credential": "verified-token", "mode": "register", "employee_id": "G-100", "department_id": self.department.id, "position_id": self.position.id, "role": User.Role.TEACHER})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="google.teacher@gmail.com")
        self.assertEqual(user.auth_provider, User.AuthProvider.GOOGLE)
        self.assertEqual(user.google_subject, "google-account-100")
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_active)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_sends_google_guidance_for_google_only_account(self):
        user = User(username="googleonly", email="googleonly@gmail.com", auth_provider=User.AuthProvider.GOOGLE, is_active=True)
        user.set_unusable_password()
        user.save()
        response = self.client.post(reverse("password-reset"), {"email": user.email})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Use Google", mail.outbox[0].subject)


class RateLimitTests(APITestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_login_scope_returns_429_after_limit(self):
        responses = [self.client.post(reverse("login"), {"email": "unknown@school.edu", "password": "invalid"}) for _ in range(11)]
        self.assertTrue(all(response.status_code == status.HTTP_400_BAD_REQUEST for response in responses[:10]))
        self.assertEqual(responses[10].status_code, status.HTTP_429_TOO_MANY_REQUESTS)
