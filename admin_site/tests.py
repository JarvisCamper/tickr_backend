from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from admin_site.models import ActivityLog
from management.models import Project, Screenshot, TimeEntry


@override_settings(SECURE_SSL_REDIRECT=False)
class AdminScreenshotDeleteTests(APITestCase):
    def setUp(self):
        self.temp_media = TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.temp_media.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.temp_media.cleanup)

        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            email="admin@example.com",
            password="secret123",
            username="admin",
        )
        self.employee = user_model.objects.create_user(
            email="employee@example.com",
            password="secret123",
            username="employee",
        )
        self.client.force_authenticate(self.admin)

        self.project = Project.objects.create(
            name="Evidence Review",
            description="",
            type="group",
            creator=self.employee,
        )
        self.time_entry = TimeEntry.objects.create(
            user=self.employee,
            project=self.project,
            description="Tracked task",
            start_time="2026-03-21T10:00:00Z",
            is_running=True,
        )
        self.screenshot = Screenshot.objects.create(
            user=self.employee,
            project=self.project,
            time_entry=self.time_entry,
            image=SimpleUploadedFile(
                "capture.jpg",
                b"fake-image-bytes",
                content_type="image/jpeg",
            ),
        )

    def test_admin_can_delete_screenshot(self):
        image_name = self.screenshot.image.name

        response = self.client.delete(
            reverse("admin-screenshot-detail", args=[self.screenshot.id])
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Screenshot.objects.filter(id=self.screenshot.id).exists())
        self.assertFalse(self.screenshot.image.storage.exists(image_name))
        self.assertTrue(
            ActivityLog.objects.filter(
                action="screenshot_delete",
                target_type="screenshot",
                target_id=self.screenshot.id,
            ).exists()
        )
