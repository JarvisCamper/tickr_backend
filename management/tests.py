from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from management.models import Project, TimeEntry


@override_settings(SECURE_SSL_REDIRECT=False)
class ReportsViewTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="reports@example.com",
            username="reports-user",
            password="secret123",
        )
        self.client.force_authenticate(self.user)
        self.project = Project.objects.create(
            name="P1",
            description="",
            type="individual",
            creator=self.user,
        )

    def _create_entry(self, dt, seconds, description=""):
        start = timezone.make_aware(dt)
        end = start + timedelta(seconds=seconds)
        return TimeEntry.objects.create(
            user=self.user,
            project=self.project,
            description=description or f"entry-{seconds}",
            start_time=start,
            end_time=end,
            is_running=False,
        )

    def test_reports_include_weekly_monthly_and_recent_activity(self):
        # Same ISO week (starts Monday): 2026-01-05
        self._create_entry(datetime(2026, 1, 6, 10, 0, 0), 600, "week-a")   # 00:10:00
        self._create_entry(datetime(2026, 1, 8, 11, 0, 0), 300, "week-a2")  # 00:05:00
        # Previous week (starts Monday): 2025-12-29
        self._create_entry(datetime(2025, 12, 30, 9, 0, 0), 120, "week-b")  # 00:02:00

        resp = self.client.get(reverse("reports"))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["total_time"], "00:17:00")
        self.assertIn("project_breakdown", resp.data)
        self.assertIn("weekly_summary", resp.data)
        self.assertIn("monthly_summary", resp.data)
        self.assertIn("recent_activity", resp.data)

        weekly = resp.data["weekly_summary"]
        self.assertEqual(weekly[0]["week_start"], "2026-01-05")
        self.assertEqual(weekly[0]["hours_str"], "00:15:00")
        self.assertEqual(weekly[1]["week_start"], "2025-12-29")
        self.assertEqual(weekly[1]["hours_str"], "00:02:00")

        monthly = resp.data["monthly_summary"]
        self.assertEqual(monthly[0]["month_start"], "2026-01-01")
        self.assertEqual(monthly[0]["hours_str"], "00:15:00")
        self.assertEqual(monthly[1]["month_start"], "2025-12-01")
        self.assertEqual(monthly[1]["hours_str"], "00:02:00")
