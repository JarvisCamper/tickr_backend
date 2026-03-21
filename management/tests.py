from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from management.models import Project, Team, TimeEntry


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


@override_settings(SECURE_SSL_REDIRECT=False)
class TeamAssignProjectTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="owner@example.com",
            username="team-owner",
            password="secret123",
        )
        self.client.force_authenticate(self.user)
        self.team = Team.objects.create(
            name="Alpha Team",
            description="",
            owner=self.user,
        )

    def test_assign_project_requires_project_id(self):
        response = self.client.post(
            reverse("team-assign-project", args=[self.team.id]),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "project_id is required")

    def test_assign_project_rejects_invalid_project_id(self):
        response = self.client.post(
            reverse("team-assign-project", args=[self.team.id]),
            {"project_id": "abc"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Invalid project_id format")

    def test_assign_project_returns_assigned_project(self):
        project = Project.objects.create(
            name="Inbox Cleanup",
            description="",
            type="individual",
            creator=self.user,
        )

        response = self.client.post(
            reverse("team-assign-project", args=[self.team.id]),
            {"project_id": project.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], "Project assigned successfully")
        self.assertEqual(response.data["project"]["id"], project.id)
        self.assertEqual(response.data["project"]["team_id"], self.team.id)

        project.refresh_from_db()
        self.assertEqual(project.team_id, self.team.id)

    def test_assign_project_returns_existing_assignment(self):
        project = Project.objects.create(
            name="Inbox Cleanup",
            description="",
            type="individual",
            creator=self.user,
            team=self.team,
        )

        response = self.client.post(
            reverse("team-assign-project", args=[self.team.id]),
            {"project_id": project.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], "Project is already assigned to this team")
        self.assertEqual(response.data["project"]["id"], project.id)
        self.assertEqual(response.data["project"]["team_id"], self.team.id)
