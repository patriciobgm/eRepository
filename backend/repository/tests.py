from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from repository.models import AuditLog, Document, Repository


class RepositoryPermissionTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", "admin@school.edu", "Password!2026", role=User.Role.ASSISTANT_PRINCIPAL)
        self.teacher = User.objects.create_user("teacher", "teacher@school.edu", "Password!2026", role=User.Role.TEACHER)
        self.other = User.objects.create_user("other", "other@school.edu", "Password!2026", role=User.Role.TEACHER)

    def test_only_assistant_principal_can_create_shared_repository(self):
        self.client.force_authenticate(self.teacher)
        denied = self.client.post("/api/repositories/", {"name": "Faculty Resources"})
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.admin)
        created = self.client.post("/api/repositories/", {"name": "Faculty Resources", "description": "Shared materials"})
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data["kind"], Repository.Kind.SHARED)

    def test_private_documents_are_not_visible_to_other_teacher(self):
        private = Repository.objects.get(owner=self.teacher, kind=Repository.Kind.PRIVATE)
        document = Document.objects.create(repository=private, owner=self.teacher, title="Private lesson plan")
        self.client.force_authenticate(self.other)
        response = self.client.get("/api/documents/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(document.id, [item["id"] for item in response.data["results"]])

    def test_upload_creates_first_version_and_audit_log(self):
        private = Repository.objects.get(owner=self.teacher, kind=Repository.Kind.PRIVATE)
        self.client.force_authenticate(self.teacher)
        file = SimpleUploadedFile("lesson-plan.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        response = self.client.post("/api/documents/", {"repository": private.id, "title": "Lesson Plan", "file": file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        document = Document.objects.get(pk=response.data["id"])
        self.assertEqual(document.versions.count(), 1)
        self.assertTrue(AuditLog.objects.filter(actor=self.teacher, target_id=str(document.id), action=AuditLog.Action.CREATED).exists())

