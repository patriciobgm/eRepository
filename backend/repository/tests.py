from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Designation, User, UserDesignation
from repository.models import AuditLog, Document, Folder, Notification, Repository


class RepositoryPermissionTests(APITestCase):
    def setUp(self):
        self.superadmin = User.objects.create_superuser("superadmin", "superadmin@school.edu", "Password!2026")
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

    def test_principal_can_create_and_update_a_selected_repository_audience(self):
        self.client.force_authenticate(self.admin)
        eligible = self.client.get("/api/repositories/eligible-members/")
        eligible_ids = [member["id"] for member in eligible.data]
        self.assertEqual(eligible.status_code, status.HTTP_200_OK)
        self.assertIn(self.teacher.id, eligible_ids)
        self.assertIn(self.other.id, eligible_ids)
        self.assertNotIn(self.admin.id, eligible_ids)
        self.assertNotIn(self.superadmin.id, eligible_ids)

        created = self.client.post("/api/repositories/", {
            "name": "Selected Resources",
            "description": "For one faculty member",
            "member_ids": [self.teacher.id],
        }, format="json")
        repository_id = created.data["id"]
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data["member_ids"], [self.teacher.id])

        self.client.force_authenticate(self.teacher)
        teacher_repositories = self.client.get("/api/repositories/")
        self.assertIn(repository_id, [item["id"] for item in teacher_repositories.data["results"]])
        self.client.force_authenticate(self.other)
        other_repositories = self.client.get("/api/repositories/")
        self.assertNotIn(repository_id, [item["id"] for item in other_repositories.data["results"]])

        self.client.force_authenticate(self.admin)
        updated = self.client.patch(f"/api/repositories/{repository_id}/", {
            "name": "Updated Resources",
            "description": "Audience changed",
            "member_ids": [self.other.id],
        }, format="json")
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.data["name"], "Updated Resources")
        self.assertEqual(updated.data["description"], "Audience changed")
        self.assertEqual(updated.data["member_ids"], [self.other.id])

        self.client.force_authenticate(self.teacher)
        teacher_repositories = self.client.get("/api/repositories/")
        self.assertNotIn(repository_id, [item["id"] for item in teacher_repositories.data["results"]])
        self.client.force_authenticate(self.other)
        other_repositories = self.client.get("/api/repositories/")
        self.assertIn(repository_id, [item["id"] for item in other_repositories.data["results"]])

    def test_designated_teacher_can_initiate_and_manage_only_their_shared_repository(self):
        designation = Designation.objects.get(name="Research Coordinator")
        UserDesignation.objects.create(user=self.teacher, designation=designation, assigned_by=self.admin)
        other_shared = Repository.objects.create(owner=self.admin, kind=Repository.Kind.SHARED, name="Principal Repository")
        self.client.force_authenticate(self.teacher)

        created = self.client.post("/api/repositories/", {
            "name": "Research Repository",
            "description": "For the school research program.",
            "member_ids": [self.other.id],
        }, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        repository_id = created.data["id"]
        self.assertEqual(created.data["owner"]["id"], self.teacher.id)

        own_update = self.client.patch(f"/api/repositories/{repository_id}/", {"description": "Updated research purpose."})
        other_update = self.client.patch(f"/api/repositories/{other_shared.id}/", {"description": "Not allowed"})
        self.assertEqual(own_update.status_code, status.HTTP_200_OK)
        self.assertEqual(other_update.status_code, status.HTTP_403_FORBIDDEN)

        repository_ids = [item["id"] for item in self.client.get("/api/repositories/").data["results"]]
        self.assertIn(repository_id, repository_ids)

    def test_teacher_without_designation_cannot_initiate_shared_repository(self):
        self.client.force_authenticate(self.teacher)
        response = self.client.post("/api/repositories/", {"name": "Unauthorized", "description": "No designation"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_shared_repository_requires_a_stated_purpose(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post("/api/repositories/", {"name": "No Purpose"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("description", response.data)

    def test_principal_cannot_rename_a_private_repository(self):
        private = Repository.objects.get(owner=self.teacher, kind=Repository.Kind.PRIVATE)
        self.client.force_authenticate(self.admin)
        response = self.client.patch(f"/api/repositories/{private.id}/", {"name": "Renamed"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superadmin_can_view_assistant_principal_repository_but_cannot_manage_content(self):
        assistant_repository = Repository.objects.get(owner=self.admin, kind=Repository.Kind.PRIVATE)
        document = Document.objects.create(repository=assistant_repository, owner=self.admin, title="Assistant Principal File")
        self.client.force_authenticate(self.superadmin)

        repositories = self.client.get("/api/repositories/")
        documents = self.client.get("/api/documents/")
        create_repository = self.client.post("/api/repositories/", {"name": "Not Allowed"})
        file = SimpleUploadedFile("blocked.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        upload = self.client.post("/api/documents/", {"repository": assistant_repository.id, "title": "Blocked", "file": file}, format="multipart")
        update = self.client.patch(f"/api/documents/{document.id}/", {"title": "Blocked edit"})

        self.assertIn(assistant_repository.id, [item["id"] for item in repositories.data["results"]])
        self.assertIn(document.id, [item["id"] for item in documents.data["results"]])
        self.assertEqual(create_repository.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(upload.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(update.status_code, status.HTTP_403_FORBIDDEN)

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

    def test_private_folder_creation_is_limited_to_the_repository_owner(self):
        private = Repository.objects.get(owner=self.teacher, kind=Repository.Kind.PRIVATE)
        self.client.force_authenticate(self.teacher)
        created = self.client.post("/api/folders/", {"repository": private.id, "name": "Lesson Plans"})
        duplicate = self.client.post("/api/folders/", {"repository": private.id, "name": "lesson plans"})
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data["owner"]["id"], self.teacher.id)
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)

        self.client.force_authenticate(self.admin)
        principal_denied = self.client.post("/api/folders/", {"repository": private.id, "name": "Principal Folder"})
        self.client.force_authenticate(self.superadmin)
        superadmin_denied = self.client.post("/api/folders/", {"repository": private.id, "name": "Superadmin Folder"})
        self.assertEqual(principal_denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(superadmin_denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_shared_folder_tracks_owner_and_principal_can_manage_it(self):
        shared = Repository.objects.create(owner=self.admin, kind=Repository.Kind.SHARED, name="Shared Folders")
        self.client.force_authenticate(self.teacher)
        created = self.client.post("/api/folders/", {"repository": shared.id, "name": "Science"})
        folder_id = created.data["id"]
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data["owner"]["id"], self.teacher.id)

        self.client.force_authenticate(self.other)
        visible = self.client.get(f"/api/folders/?repository={shared.id}")
        denied = self.client.patch(f"/api/folders/{folder_id}/", {"name": "Changed by Other"})
        self.assertIn(folder_id, [folder["id"] for folder in visible.data])
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.admin)
        renamed = self.client.patch(f"/api/folders/{folder_id}/", {"name": "Science Resources"})
        self.assertEqual(renamed.status_code, status.HTTP_200_OK)
        self.assertEqual(renamed.data["name"], "Science Resources")
        self.assertEqual(renamed.data["owner"]["id"], self.teacher.id)

    def test_upload_can_target_root_or_folder_and_folder_delete_moves_documents_to_root(self):
        private = Repository.objects.get(owner=self.teacher, kind=Repository.Kind.PRIVATE)
        other_private = Repository.objects.get(owner=self.other, kind=Repository.Kind.PRIVATE)
        folder = Folder.objects.create(repository=private, owner=self.teacher, name="Modules")
        wrong_folder = Folder.objects.create(repository=other_private, owner=self.other, name="Other Modules")
        self.client.force_authenticate(self.teacher)

        folder_file = SimpleUploadedFile("module.pdf", b"%PDF-1.4 folder", content_type="application/pdf")
        folder_upload = self.client.post("/api/documents/", {"repository": private.id, "folder": folder.id, "title": "Folder Module", "file": folder_file}, format="multipart")
        root_file = SimpleUploadedFile("root.pdf", b"%PDF-1.4 root", content_type="application/pdf")
        root_upload = self.client.post("/api/documents/", {"repository": private.id, "title": "Root Module", "file": root_file}, format="multipart")
        invalid_file = SimpleUploadedFile("invalid.pdf", b"%PDF-1.4 invalid", content_type="application/pdf")
        mismatch = self.client.post("/api/documents/", {"repository": private.id, "folder": wrong_folder.id, "title": "Invalid Folder", "file": invalid_file}, format="multipart")

        self.assertEqual(folder_upload.status_code, status.HTTP_201_CREATED)
        self.assertEqual(root_upload.status_code, status.HTTP_201_CREATED)
        self.assertEqual(mismatch.status_code, status.HTTP_400_BAD_REQUEST)
        folder_document = Document.objects.get(pk=folder_upload.data["id"])
        root_document = Document.objects.get(pk=root_upload.data["id"])
        self.assertEqual(folder_document.folder, folder)
        self.assertIsNone(root_document.folder)

        removed = self.client.delete(f"/api/folders/{folder.id}/")
        folder_document.refresh_from_db()
        self.assertEqual(removed.status_code, status.HTTP_204_NO_CONTENT)
        self.assertIsNone(folder_document.folder)


class NotificationTests(APITestCase):
    def setUp(self):
        self.teacher = User.objects.create_user("notice-teacher", "notice-teacher@school.edu", "Password!2026", role=User.Role.TEACHER)
        self.other = User.objects.create_user("notice-other", "notice-other@school.edu", "Password!2026", role=User.Role.MASTER_TEACHER)
        self.teacher_notification = Notification.objects.create(
            recipient=self.teacher,
            category=Notification.Category.SYSTEM,
            title="Teacher notification",
            message="Visible only to the teacher.",
        )
        self.other_notification = Notification.objects.create(
            recipient=self.other,
            category=Notification.Category.SYSTEM,
            title="Other notification",
            message="Visible only to the other user.",
        )

    def test_notification_inbox_and_actions_are_recipient_scoped(self):
        self.client.force_authenticate(self.teacher)
        inbox = self.client.get("/api/notifications/")
        self.assertEqual([item["id"] for item in inbox.data["results"]], [self.teacher_notification.id])

        unread = self.client.get("/api/notifications/unread-count/")
        self.assertEqual(unread.data["count"], 1)
        marked = self.client.post(f"/api/notifications/{self.teacher_notification.id}/read/")
        self.assertEqual(marked.status_code, status.HTTP_200_OK)
        self.assertTrue(marked.data["is_read"])

        forbidden_read = self.client.post(f"/api/notifications/{self.other_notification.id}/read/")
        forbidden_delete = self.client.delete(f"/api/notifications/{self.other_notification.id}/")
        self.assertEqual(forbidden_read.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(forbidden_delete.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Notification.objects.filter(pk=self.other_notification.id).exists())

    def test_mark_all_read_and_clear_all_affect_only_current_user(self):
        Notification.objects.create(recipient=self.teacher, title="Second", message="Second notification")
        self.client.force_authenticate(self.teacher)
        marked = self.client.post("/api/notifications/mark-all-read/")
        cleared = self.client.delete("/api/notifications/clear-all/")
        self.assertEqual(marked.data["updated"], 2)
        self.assertEqual(cleared.status_code, status.HTTP_200_OK)
        self.assertFalse(Notification.objects.filter(recipient=self.teacher).exists())
        self.assertTrue(Notification.objects.filter(recipient=self.other).exists())
