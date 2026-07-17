from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from repository.models import Repository


class RegistrationTests(APITestCase):
    def test_registration_requires_approval_and_creates_private_repository(self):
        response = self.client.post(reverse("register"), {
            "first_name": "Maria", "last_name": "Santos", "email": "maria@school.edu",
            "employee_id": "SHS-100", "department": "Science", "position": "Teacher I",
            "role": User.Role.TEACHER, "password": "StrongFaculty!2026", "password_confirm": "StrongFaculty!2026",
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="maria@school.edu")
        self.assertFalse(user.is_active)
        self.assertTrue(Repository.objects.filter(owner=user, kind=Repository.Kind.PRIVATE).exists())

    def test_registration_cannot_claim_assistant_principal_role(self):
        response = self.client.post(reverse("register"), {
            "first_name": "Fake", "last_name": "Admin", "email": "fake@school.edu",
            "employee_id": "SHS-101", "department": "Admin", "position": "AP",
            "role": User.Role.ASSISTANT_PRINCIPAL, "password": "StrongFaculty!2026", "password_confirm": "StrongFaculty!2026",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

