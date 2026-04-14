import csv
from decimal import Decimal

from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta

# Import models from other apps
from user.models import User
from management.models import Team, Project, TimeEntry, Screenshot

# Import admin models and utilities
from .models import ActivityLog, AdminSettings, UserAccessLog
from .serializers import (
    AdminUserListSerializer,
    AdminUserDetailSerializer,
    AdminUserUpdateSerializer,
    AdminTeamListSerializer,
    AdminTeamDetailSerializer,
    AdminTeamWriteSerializer,
    AdminProjectListSerializer,
    AdminProjectWriteSerializer,
    AdminTimeEntryListSerializer,
    AdminScreenshotListSerializer,
    AdminAnalyticsOverviewSerializer,
    AdminUserGrowthSerializer,
    AdminActivitySerializer,
    AdminTopUserSerializer,
    AdminTopProjectSerializer,
    AdminTopTeamSerializer,
    ActivityLogSerializer,
    UserAccessLogSerializer,
    AdminSettingsSerializer,
    AdminPasswordChangeSerializer,
    AdminTestEmailSerializer,
)
from .permissions import IsAdminUser, IsSuperAdmin
from .utils import log_admin_action
from .admin_config import (
    calculate_overtime,
    format_admin_setting,
    get_admin_settings,
    send_test_email,
)
from rest_framework_simplejwt.authentication import JWTAuthentication


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


#  USER VIEWSET


class AdminUserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing users from admin panel
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = User.objects.annotate(
            total_time_entries=Count("time_entries"),
            teams_count=Count("team_memberships", distinct=True),
            projects_count=Count("created_projects", distinct=True),
        ).order_by("-id")

        # Filters
        status_filter = self.request.query_params.get("status", None)
        search = self.request.query_params.get("search", None)

        if status_filter == "active":
            queryset = queryset.filter(is_active=True)
        elif status_filter == "inactive":
            queryset = queryset.filter(is_active=False)
        elif status_filter == "staff":
            queryset = queryset.filter(is_staff=True)

        if search:
            queryset = queryset.filter(
                Q(email__icontains=search) | Q(username__icontains=search)
            )

        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AdminUserDetailSerializer
        elif self.action in ["update", "partial_update"]:
            return AdminUserUpdateSerializer
        return AdminUserListSerializer

    def update(self, request, *args, **kwargs):
        """Update user details"""
        response = super().update(request, *args, **kwargs)

        # Log the action
        log_admin_action(
            admin_user=request.user,
            action="user_update",
            target_type="user",
            target_id=kwargs.get("pk"),
            description=f"Updated user {self.get_object().email}",
            request=request,
        )

        return response

    def destroy(self, request, *args, **kwargs):
        """Delete user"""
        user = self.get_object()
        email = user.email

        # Log before deletion
        log_admin_action(
            admin_user=request.user,
            action="user_delete",
            target_type="user",
            target_id=user.id,
            description=f"Deleted user {email}",
            request=request,
        )

        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        """Suspend a user account"""
        user = self.get_object()
        user.is_active = False
        user.save()

        log_admin_action(
            admin_user=request.user,
            action="user_suspend",
            target_type="user",
            target_id=user.id,
            description=f"Suspended user {user.email}",
            request=request,
        )

        return Response(
            {
                "message": f"User {user.email} has been suspended",
                "user": AdminUserDetailSerializer(user).data,
            }
        )

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        """Activate a suspended user account"""
        user = self.get_object()
        user.is_active = True
        user.save()

        log_admin_action(
            admin_user=request.user,
            action="user_activate",
            target_type="user",
            target_id=user.id,
            description=f"Activated user {user.email}",
            request=request,
        )

        return Response(
            {
                "message": f"User {user.email} has been activated",
                "user": AdminUserDetailSerializer(user).data,
            }
        )


# ==================== TEAM VIEWSET ====================


class AdminTeamViewSet(viewsets.ModelViewSet):
    """
    ViewSet for viewing teams from admin panel
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = (
            Team.objects.select_related("owner")
            .annotate(
                members_count=Count("members", distinct=True),
                projects_count=Count("projects", distinct=True),
            )
            .order_by("-created_at")
        )

        # Filters
        search = self.request.query_params.get("search", None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(owner__email__icontains=search)
            )

        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AdminTeamDetailSerializer
        if self.action in ["create", "update", "partial_update"]:
            return AdminTeamWriteSerializer
        return AdminTeamListSerializer

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        team_id = response.data.get("id")
        team_name = response.data.get("name", "team")
        log_admin_action(
            admin_user=request.user,
            action="team_create",
            target_type="team",
            target_id=team_id,
            description=f"Created team {team_name}",
            request=request,
        )
        return response

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        team = self.get_object()
        log_admin_action(
            admin_user=request.user,
            action="team_update",
            target_type="team",
            target_id=team.id,
            description=f"Updated team {team.name}",
            request=request,
        )
        return response

    def destroy(self, request, *args, **kwargs):
        team = self.get_object()
        log_admin_action(
            admin_user=request.user,
            action="team_delete",
            target_type="team",
            target_id=team.id,
            description=f"Deleted team {team.name}",
            request=request,
        )
        return super().destroy(request, *args, **kwargs)


#  PROJECT VIEWSET 


class AdminProjectViewSet(viewsets.ModelViewSet):
    """
    ViewSet for viewing projects from admin panel
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    pagination_class = StandardResultsSetPagination
    serializer_class = AdminProjectListSerializer

    def get_queryset(self):
        queryset = (
            Project.objects.select_related("creator", "team")
            .annotate(time_entries_count=Count("time_entries"))
            .order_by("-created_at")
        )

        # Filters
        project_type = self.request.query_params.get("type", None)
        search = self.request.query_params.get("search", None)

        if project_type:
            queryset = queryset.filter(type=project_type)

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(creator__email__icontains=search)
            )

        return queryset

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return AdminProjectWriteSerializer
        return AdminProjectListSerializer

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        project_id = response.data.get("id")
        project_name = response.data.get("name", "project")
        log_admin_action(
            admin_user=request.user,
            action="project_create",
            target_type="project",
            target_id=project_id,
            description=f"Created project {project_name}",
            request=request,
        )
        return response

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        project = self.get_object()
        log_admin_action(
            admin_user=request.user,
            action="project_update",
            target_type="project",
            target_id=project.id,
            description=f"Updated project {project.name}",
            request=request,
        )
        return response

    def destroy(self, request, *args, **kwargs):
        project = self.get_object()
        log_admin_action(
            admin_user=request.user,
            action="project_delete",
            target_type="project",
            target_id=project.id,
            description=f"Deleted project {project.name}",
            request=request,
        )
        return super().destroy(request, *args, **kwargs)


# ==================== TIME ENTRY VIEWSET ====================


class AdminTimeEntryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing time entries from admin panel
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    pagination_class = StandardResultsSetPagination
    serializer_class = AdminTimeEntryListSerializer

    def get_queryset(self):
        queryset = TimeEntry.objects.select_related("user", "project").order_by(
            "-start_time"
        )

        search = self.request.query_params.get("search", None)
        project_id = self.request.query_params.get("project", None)
        status_filter = self.request.query_params.get("status", None)

        if search:
            queryset = queryset.filter(
                Q(description__icontains=search)
                | Q(user__email__icontains=search)
                | Q(user__username__icontains=search)
                | Q(project__name__icontains=search)
            )

        if project_id:
            queryset = queryset.filter(project_id=project_id)

        if status_filter == "running":
            queryset = queryset.filter(is_running=True)
        elif status_filter == "completed":
            queryset = queryset.filter(is_running=False)

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            overtime_map = calculate_overtime(page)
            serializer = self.get_serializer(
                page, many=True, context={"overtime_map": overtime_map}
            )
            return self.get_paginated_response(serializer.data)

        overtime_map = calculate_overtime(queryset)
        serializer = self.get_serializer(
            queryset, many=True, context={"overtime_map": overtime_map}
        )
        return Response(serializer.data)


class AdminScreenshotViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    pagination_class = StandardResultsSetPagination
    serializer_class = AdminScreenshotListSerializer

    def get_queryset(self):
        queryset = Screenshot.objects.select_related(
            "user", "project", "time_entry", "time_entry__project"
        ).order_by(
            "-captured_at"
        )

        search = self.request.query_params.get("search", None)
        user_id = self.request.query_params.get("user_id", None)
        project_id = self.request.query_params.get("project_id", None)
        time_entry_id = self.request.query_params.get("time_entry_id", None)
        captured_on = self.request.query_params.get("captured_on", None)

        if search:
            queryset = queryset.filter(
                Q(user__email__icontains=search)
                | Q(user__username__icontains=search)
                | Q(project__name__icontains=search)
                | Q(time_entry__description__icontains=search)
            )

        if user_id:
            queryset = queryset.filter(user_id=user_id)

        if project_id:
            queryset = queryset.filter(project_id=project_id)

        if time_entry_id:
            queryset = queryset.filter(time_entry_id=time_entry_id)

        if captured_on:
            queryset = queryset.filter(captured_at__date=captured_on)

        return queryset

    def destroy(self, request, *args, **kwargs):
        screenshot = self.get_object()
        screenshot_id = screenshot.id
        username = screenshot.user.username or screenshot.user.email

        if screenshot.image:
            screenshot.image.delete(save=False)

        log_admin_action(
            admin_user=request.user,
            action="screenshot_delete",
            target_type="screenshot",
            target_id=screenshot_id,
            description=f"Deleted screenshot {screenshot_id} for {username}",
            request=request,
        )

        screenshot.delete()
        return Response(status=204)


# ==================== ANALYTICS VIEWSETS ====================


class AdminAnalyticsViewSet(viewsets.ViewSet):
    """
    ViewSet for admin analytics and statistics
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=["get"], url_path="dashboard")
    def dashboard(self, request):
        """Get dashboard payload in a single response"""
        now = timezone.now()
        week_ago = now - timedelta(days=7)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        total_duration = TimeEntry.objects.aggregate(total=Sum("duration"))["total"]
        if total_duration:
            total_seconds = int(total_duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            total_time_tracked = f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            total_time_tracked = "0:00:00"

        overview = {
            "total_users": User.objects.count(),
            "total_teams": Team.objects.count(),
            "total_projects": Project.objects.count(),
            "total_time_tracked": total_time_tracked,
            "active_users_today": User.objects.filter(
                time_entries__start_time__gte=today_start
            )
            .distinct()
            .count(),
            "new_users_this_week": User.objects.filter(created_at__gte=week_ago).count(),
        }

        users = AdminUserListSerializer(
            User.objects.annotate(
                total_time_entries=Count("time_entries"),
                teams_count=Count("team_memberships", distinct=True),
                projects_count=Count("created_projects", distinct=True),
            ).order_by("-id")[:8],
            many=True,
        ).data
        teams = AdminTeamListSerializer(
            Team.objects.select_related("owner")
            .annotate(
                members_count=Count("members", distinct=True),
                projects_count=Count("projects", distinct=True),
            )
            .order_by("-created_at")[:8],
            many=True,
        ).data
        projects = AdminProjectListSerializer(
            Project.objects.select_related("creator", "team")
            .annotate(time_entries_count=Count("time_entries"))
            .order_by("-created_at")[:8],
            many=True,
        ).data
        activity_logs = ActivityLogSerializer(
            ActivityLog.objects.select_related("admin_user").order_by("-created_at")[:8],
            many=True,
        ).data

        return Response(
            {
                "overview": overview,
                "users": users,
                "teams": teams,
                "projects": projects,
                "activity_logs": activity_logs,
            }
        )

    @action(detail=False, methods=["get"])
    def overview(self, request):
        """Get overview statistics for admin dashboard"""
        now = timezone.now()
        week_ago = now - timedelta(days=7)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Calculate total time tracked (DurationField returns timedelta)
        total_duration = TimeEntry.objects.aggregate(total=Sum("duration"))["total"]
        if total_duration:
            total_seconds = int(total_duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            total_time_tracked = f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            total_time_tracked = "0:00:00"

        data = {
            "total_users": User.objects.count(),
            "total_teams": Team.objects.count(),
            "total_projects": Project.objects.count(),
            "total_time_tracked": total_time_tracked,
            "active_users_today": User.objects.filter(
                time_entries__start_time__gte=today_start
            )
            .distinct()
            .count(),
            "new_users_this_week": User.objects.filter(
                created_at__gte=week_ago
            ).count(),
        }

        serializer = AdminAnalyticsOverviewSerializer(data)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="users/growth")
    def user_growth(self, request):
        """Get user growth data over time"""
        days = int(request.query_params.get("days", 30))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        growth_data = []
        cumulative = User.objects.filter(created_at__date__lt=start_date).count()

        for i in range(days + 1):
            current_date = start_date + timedelta(days=i)
            daily_count = User.objects.filter(created_at__date=current_date).count()
            cumulative += daily_count

            growth_data.append(
                {"date": current_date, "count": daily_count, "cumulative": cumulative}
            )

        serializer = AdminUserGrowthSerializer(growth_data, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def activity(self, request):
        """Get system activity metrics"""
        days = int(request.query_params.get("days", 7))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        activity_data = []

        for i in range(days + 1):
            current_date = start_date + timedelta(days=i)

            time_entries = TimeEntry.objects.filter(
                start_time__date=current_date
            ).count()

            new_projects = Project.objects.filter(created_at__date=current_date).count()

            active_users = (
                TimeEntry.objects.filter(start_time__date=current_date)
                .values("user")
                .distinct()
                .count()
            )

            activity_data.append(
                {
                    "date": current_date,
                    "time_entries": time_entries,
                    "new_projects": new_projects,
                    "active_users": active_users,
                }
            )

        serializer = AdminActivitySerializer(activity_data, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="users/top")
    def top_users(self, request):
        """Get top users by tracked duration"""
        limit = int(request.query_params.get("limit", 5))
        queryset = (
            User.objects.filter(time_entries__duration__isnull=False)
            .annotate(
                total_duration=Sum("time_entries__duration"),
                total_entries=Count("time_entries"),
            )
            .order_by("-total_duration")[:limit]
        )

        data = []
        for user in queryset:
            total_seconds = (
                int(user.total_duration.total_seconds()) if user.total_duration else 0
            )
            data.append(
                {
                    "user_id": user.id,
                    "username": user.username or user.email,
                    "email": user.email,
                    "total_entries": user.total_entries,
                    "total_seconds": total_seconds,
                    "total_hours": Decimal(total_seconds / 3600).quantize(Decimal("0.01")),
                }
            )

        serializer = AdminTopUserSerializer(data, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="projects/top")
    def top_projects(self, request):
        """Get top projects by tracked duration"""
        limit = int(request.query_params.get("limit", 5))
        queryset = (
            Project.objects.select_related("team")
            .filter(time_entries__duration__isnull=False)
            .annotate(
                total_duration=Sum("time_entries__duration"),
                total_entries=Count("time_entries"),
            )
            .order_by("-total_duration")[:limit]
        )

        data = []
        for project in queryset:
            total_seconds = (
                int(project.total_duration.total_seconds()) if project.total_duration else 0
            )
            data.append(
                {
                    "project_id": project.id,
                    "name": project.name,
                    "type": project.type,
                    "team_name": project.team.name if project.team else "",
                    "total_entries": project.total_entries,
                    "total_seconds": total_seconds,
                    "total_hours": Decimal(total_seconds / 3600).quantize(Decimal("0.01")),
                }
            )

        serializer = AdminTopProjectSerializer(data, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="teams/top")
    def top_teams(self, request):
        """Get top teams by size and project footprint"""
        limit = int(request.query_params.get("limit", 5))
        queryset = (
            Team.objects.select_related("owner")
            .annotate(
                member_count=Count("members", distinct=True),
                project_count=Count("projects", distinct=True),
            )
            .order_by("-project_count", "-member_count", "name")[:limit]
        )

        data = [
            {
                "team_id": team.id,
                "name": team.name,
                "owner_username": team.owner.username or team.owner.email,
                "member_count": team.member_count,
                "project_count": team.project_count,
            }
            for team in queryset
        ]

        serializer = AdminTopTeamSerializer(data, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="bundle")
    def bundle(self, request):
        """Get analytics payload in a single response"""
        days = int(request.query_params.get("days", 14))
        limit = int(request.query_params.get("limit", 6))
        now = timezone.now()
        week_ago = now - timedelta(days=7)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now.date()
        start_date = end_date - timedelta(days=days)

        total_duration = TimeEntry.objects.aggregate(total=Sum("duration"))["total"]
        if total_duration:
            total_seconds = int(total_duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            total_time_tracked = f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            total_time_tracked = "0:00:00"

        overview = {
            "total_users": User.objects.count(),
            "total_teams": Team.objects.count(),
            "total_projects": Project.objects.count(),
            "total_time_tracked": total_time_tracked,
            "active_users_today": User.objects.filter(
                time_entries__start_time__gte=today_start
            )
            .distinct()
            .count(),
            "new_users_this_week": User.objects.filter(created_at__gte=week_ago).count(),
        }

        growth_data = []
        cumulative = User.objects.filter(created_at__date__lt=start_date).count()
        for i in range(days + 1):
            current_date = start_date + timedelta(days=i)
            daily_count = User.objects.filter(created_at__date=current_date).count()
            cumulative += daily_count
            growth_data.append(
                {"date": current_date, "count": daily_count, "cumulative": cumulative}
            )

        activity_data = []
        for i in range(days + 1):
            current_date = start_date + timedelta(days=i)
            activity_data.append(
                {
                    "date": current_date,
                    "time_entries": TimeEntry.objects.filter(start_time__date=current_date).count(),
                    "new_projects": Project.objects.filter(created_at__date=current_date).count(),
                    "active_users": (
                        TimeEntry.objects.filter(start_time__date=current_date)
                        .values("user")
                        .distinct()
                        .count()
                    ),
                }
            )

        users_queryset = (
            User.objects.filter(time_entries__duration__isnull=False)
            .annotate(
                total_duration=Sum("time_entries__duration"),
                total_entries=Count("time_entries"),
            )
            .order_by("-total_duration")[:limit]
        )
        top_users = []
        for user in users_queryset:
            total_seconds = int(user.total_duration.total_seconds()) if user.total_duration else 0
            top_users.append(
                {
                    "user_id": user.id,
                    "username": user.username or user.email,
                    "email": user.email,
                    "total_entries": user.total_entries,
                    "total_seconds": total_seconds,
                    "total_hours": Decimal(total_seconds / 3600).quantize(Decimal("0.01")),
                }
            )

        projects_queryset = (
            Project.objects.select_related("team")
            .filter(time_entries__duration__isnull=False)
            .annotate(
                total_duration=Sum("time_entries__duration"),
                total_entries=Count("time_entries"),
            )
            .order_by("-total_duration")[:limit]
        )
        top_projects = []
        for project in projects_queryset:
            total_seconds = int(project.total_duration.total_seconds()) if project.total_duration else 0
            top_projects.append(
                {
                    "project_id": project.id,
                    "name": project.name,
                    "type": project.type,
                    "team_name": project.team.name if project.team else "",
                    "total_entries": project.total_entries,
                    "total_seconds": total_seconds,
                    "total_hours": Decimal(total_seconds / 3600).quantize(Decimal("0.01")),
                }
            )

        teams_queryset = (
            Team.objects.select_related("owner")
            .annotate(
                member_count=Count("members", distinct=True),
                project_count=Count("projects", distinct=True),
            )
            .order_by("-project_count", "-member_count", "name")[:limit]
        )
        top_teams = [
            {
                "team_id": team.id,
                "name": team.name,
                "owner_username": team.owner.username or team.owner.email,
                "member_count": team.member_count,
                "project_count": team.project_count,
            }
            for team in teams_queryset
        ]

        return Response(
            {
                "overview": overview,
                "user_growth": AdminUserGrowthSerializer(growth_data, many=True).data,
                "activity": AdminActivitySerializer(activity_data, many=True).data,
                "top_users": AdminTopUserSerializer(top_users, many=True).data,
                "top_projects": AdminTopProjectSerializer(top_projects, many=True).data,
                "top_teams": AdminTopTeamSerializer(top_teams, many=True).data,
            }
        )


# ==================== ACTIVITY LOG VIEWSET ====================


class AdminActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing activity logs
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    serializer_class = ActivityLogSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = ActivityLog.objects.select_related("admin_user").order_by(
            "-created_at"
        )

        # Filters
        action = self.request.query_params.get("action", None)
        admin_id = self.request.query_params.get("admin_id", None)

        if action:
            queryset = queryset.filter(action=action)

        if admin_id:
            queryset = queryset.filter(admin_user_id=admin_id)

        return queryset


class AdminUserAccessLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing user login/logout history
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    serializer_class = UserAccessLogSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = UserAccessLog.objects.select_related("user").order_by("-created_at")

        event_type = self.request.query_params.get("event_type", None)
        search = self.request.query_params.get("search", None)

        if event_type:
            queryset = queryset.filter(event_type=event_type)

        if search:
            queryset = queryset.filter(
                Q(user__email__icontains=search)
                | Q(user__username__icontains=search)
                | Q(ip_address__icontains=search)
            )

        return queryset


# ==================== SETTINGS VIEWSET ====================


class AdminSettingsViewSet(viewsets.ViewSet):
    """
    ViewSet for managing admin settings
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsSuperAdmin]

    def list(self, request):
        """Get all admin settings"""
        serializer = AdminSettingsSerializer(get_admin_settings())
        return Response(serializer.data)

    def create(self, request):
        """Update admin settings"""
        serializer = AdminSettingsSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        for key, value in serializer.validated_data.items():
            AdminSettings.objects.update_or_create(
                key=key,
                defaults={
                    "value": format_admin_setting(key, value),
                    "updated_by": request.user,
                },
            )

        log_admin_action(
            admin_user=request.user,
            action="settings_update",
            target_type="settings",
            target_id=None,
            description="Updated system settings",
            request=request,
        )

        return Response(
            {"message": "Settings updated successfully", "settings": serializer.data}
        )

    @action(detail=False, methods=["post"], url_path="change-password")
    def change_password(self, request):
        serializer = AdminPasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        current_password = serializer.validated_data["current_password"]
        new_password = serializer.validated_data["new_password"]

        if not request.user.check_password(current_password):
            raise ValidationError({"current_password": "Current password is incorrect."})

        request.user.set_password(new_password)
        request.user.save(update_fields=["password"])

        log_admin_action(
            admin_user=request.user,
            action="settings_update",
            target_type="security",
            target_id=request.user.id,
            description="Changed admin password",
            request=request,
        )

        return Response({"message": "Password updated successfully."})

    @action(detail=False, methods=["post"], url_path="test-email")
    def test_email(self, request):
        serializer = AdminTestEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        recipient_email = serializer.validated_data.get(
            "recipient_email", request.user.email
        )

        try:
            send_test_email(recipient_email)
        except Exception as exc:
            raise ValidationError({"recipient_email": f"Failed to send email: {exc}"})

        log_admin_action(
            admin_user=request.user,
            action="settings_update",
            target_type="email",
            target_id=None,
            description=f"Sent SMTP test email to {recipient_email}",
            request=request,
        )

        return Response({"message": f"Test email sent to {recipient_email}."})

    @action(detail=False, methods=["get"], url_path="export/activity-logs")
    def export_activity_logs(self, request):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="tickr-activity-logs.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            [
                "id",
                "admin_username",
                "admin_email",
                "action",
                "target_type",
                "target_id",
                "description",
                "ip_address",
                "created_at",
            ]
        )

        for log in ActivityLog.objects.select_related("admin_user").order_by("-created_at"):
            writer.writerow(
                [
                    log.id,
                    getattr(log.admin_user, "username", "") or "",
                    getattr(log.admin_user, "email", "") or "",
                    log.action,
                    log.target_type,
                    log.target_id or "",
                    log.description,
                    log.ip_address or "",
                    log.created_at.isoformat(),
                ]
            )

        log_admin_action(
            admin_user=request.user,
            action="settings_update",
            target_type="export",
            target_id=None,
            description="Exported activity logs CSV",
            request=request,
        )
        return response

    @action(detail=False, methods=["get"], url_path="export/reports")
    def export_reports(self, request):
        settings = get_admin_settings()
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="tickr-time-report.csv"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "date",
                "user_id",
                "user_email",
                "project",
                "description",
                "duration_hours",
                "overtime_hours",
                "overtime_pay",
            ]
        )

        entries = list(
            TimeEntry.objects.select_related("user", "project")
            .filter(duration__isnull=False)
            .order_by("user_id", "start_time", "id")
        )
        overtime_map = calculate_overtime(entries)

        for entry in entries:
            duration_hours = (
                Decimal(entry.duration.total_seconds()) / Decimal("3600")
            ).quantize(Decimal("0.01"))
            overtime = overtime_map.get(entry.id, {})
            writer.writerow(
                [
                    entry.start_time.date().isoformat(),
                    entry.user_id,
                    entry.user.email,
                    entry.project.name if entry.project else "",
                    entry.description,
                    str(duration_hours),
                    str(overtime.get("overtime_hours", Decimal("0.00"))),
                    str(overtime.get("overtime_pay", Decimal("0.00"))),
                ]
            )

        log_admin_action(
            admin_user=request.user,
            action="settings_update",
            target_type="export",
            target_id=None,
            description=(
                "Exported time report CSV with overtime using "
                f"{settings['standard_daily_hours']}h/day and rate {settings['overtime_hourly_rate']}"
            ),
            request=request,
        )
        return response
