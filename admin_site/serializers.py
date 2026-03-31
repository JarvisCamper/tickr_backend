from rest_framework import serializers
from django.db.models import Sum

# Import models from other apps
from user.models import User
from management.models import Team, Project, TimeEntry, TeamMember, Screenshot

# Import admin models
from .models import ActivityLog, UserAccessLog


# USER SERIALIZERS 

class AdminUserListSerializer(serializers.ModelSerializer):
    """List view serializer for users in admin panel"""
    total_time_entries = serializers.IntegerField(read_only=True)
    teams_count = serializers.IntegerField(read_only=True)
    projects_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'is_active', 
            'is_staff', 'is_superuser', 'last_login', 'created_at',
            'total_time_entries', 'teams_count', 'projects_count'
        ]
        read_only_fields = ['id', 'last_login', 'created_at']


class AdminUserDetailSerializer(serializers.ModelSerializer):
    """Detailed view serializer for individual user"""
    total_time_entries = serializers.SerializerMethodField()
    total_time_tracked = serializers.SerializerMethodField()
    teams = serializers.SerializerMethodField()
    recent_projects = serializers.SerializerMethodField()
    owned_teams = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'is_active', 
            'is_staff', 'is_superuser', 'last_login', 'created_at',
            'total_time_entries', 'total_time_tracked',
            'teams', 'owned_teams', 'recent_projects'
        ]
        read_only_fields = ['id', 'last_login', 'created_at']
    
    def get_total_time_entries(self, obj):
        return obj.time_entries.count()
    
    def get_total_time_tracked(self, obj):
        total = obj.time_entries.filter(duration__isnull=False).aggregate(
            total=Sum('duration')
        )['total']
        if total:
            return str(total)
        return "0:00:00"
    
    def get_teams(self, obj):
        teams = Team.objects.filter(members__user=obj).distinct()
        return [{
            'id': t.id, 
            'name': t.name, 
            'role': 'member',
            'joined_at': TeamMember.objects.get(team=t, user=obj).joined_at
        } for t in teams]
    
    def get_owned_teams(self, obj):
        teams = Team.objects.filter(owner=obj)
        return [{'id': t.id, 'name': t.name, 'created_at': t.created_at} for t in teams]
    
    def get_recent_projects(self, obj):
        projects = Project.objects.filter(creator=obj).order_by('-created_at')[:5]
        return [{
            'id': p.id, 
            'name': p.name, 
            'type': p.type,
            'created_at': p.created_at
        } for p in projects]


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user details"""
    class Meta:
        model = User
        fields = ['email', 'username', 'is_active', 'is_staff', 'is_superuser']


# TEAM SERIALIZERS 

class AdminTeamListSerializer(serializers.ModelSerializer):
    """List view serializer for teams"""
    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    members_count = serializers.IntegerField(read_only=True)
    projects_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Team
        fields = [
            'id', 'name', 'description', 'owner', 'owner_email', 'owner_username',
            'created_at', 'members_count', 'projects_count'
        ]
        read_only_fields = ['id', 'created_at']


class AdminTeamDetailSerializer(serializers.ModelSerializer):
    """Detailed view serializer for individual team"""
    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    members = serializers.SerializerMethodField()
    projects = serializers.SerializerMethodField()
    
    class Meta:
        model = Team
        fields = [
            'id', 'name', 'description', 'owner', 'owner_email', 'owner_username',
            'created_at', 'members', 'projects'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_members(self, obj):
        members = obj.members.select_related('user').all()
        return [{
            'id': m.user.id,
            'email': m.user.email,
            'username': m.user.username,
            'joined_at': m.joined_at
        } for m in members]
    
    def get_projects(self, obj):
        projects = obj.projects.all().order_by('-created_at')
        return [{
            'id': p.id,
            'name': p.name,
            'type': p.type,
            'created_at': p.created_at
        } for p in projects]


class AdminTeamWriteSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating teams from admin panel"""
    owner_id = serializers.PrimaryKeyRelatedField(
        source="owner",
        queryset=User.objects.all(),
        write_only=True,
    )
    owner_email = serializers.EmailField(source="owner.email", read_only=True)
    owner_username = serializers.CharField(source="owner.username", read_only=True)

    class Meta:
        model = Team
        fields = [
            "id",
            "name",
            "description",
            "owner_id",
            "owner_email",
            "owner_username",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "owner_email", "owner_username"]


# PROJECT SERIALIZERS 

class AdminProjectListSerializer(serializers.ModelSerializer):
    """List view serializer for projects"""
    creator_email = serializers.EmailField(source='creator.email', read_only=True)
    creator_username = serializers.CharField(source='creator.username', read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True, allow_null=True)
    time_entries_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Project
        fields = [
            'id', 'name', 'description', 'type', 
            'creator', 'creator_email', 'creator_username',
            'team', 'team_name', 'created_at', 'time_entries_count'
        ]
        read_only_fields = ['id', 'created_at']


# ==================== TIME ENTRY SERIALIZERS ====================

class AdminTimeEntryListSerializer(serializers.ModelSerializer):
    """List view serializer for time entries in admin panel"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True, allow_null=True)
    overtime_hours = serializers.SerializerMethodField()
    overtime_pay = serializers.SerializerMethodField()

    class Meta:
        model = TimeEntry
        fields = [
            'id', 'user', 'user_email', 'username',
            'project', 'project_name', 'description',
            'start_time', 'end_time', 'duration', 'is_running',
            'overtime_hours', 'overtime_pay'
        ]
        read_only_fields = fields

    def get_overtime_hours(self, obj):
        overtime_map = self.context.get("overtime_map", {})
        value = overtime_map.get(obj.id, {}).get("overtime_hours")
        return str(value or "0.00")

    def get_overtime_pay(self, obj):
        overtime_map = self.context.get("overtime_map", {})
        value = overtime_map.get(obj.id, {}).get("overtime_pay")
        return str(value or "0.00")


class AdminScreenshotListSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True, allow_null=True)
    time_entry_description = serializers.CharField(source="time_entry.description", read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Screenshot
        fields = [
            "id",
            "user",
            "user_email",
            "username",
            "project",
            "project_name",
            "time_entry",
            "time_entry_description",
            "image",
            "image_url",
            "capture_source",
            "captured_at",
        ]
        read_only_fields = fields

    def get_image_url(self, obj):
        request = self.context.get("request")
        if not obj.image:
            return None
        if request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url


# ==================== ANALYTICS SERIALIZERS ====================

class AdminAnalyticsOverviewSerializer(serializers.Serializer):
    """Overview statistics for dashboard"""
    total_users = serializers.IntegerField()
    total_teams = serializers.IntegerField()
    total_projects = serializers.IntegerField()
    total_time_tracked = serializers.CharField()
    active_users_today = serializers.IntegerField()
    new_users_this_week = serializers.IntegerField()


class AdminUserGrowthSerializer(serializers.Serializer):
    """User growth data over time"""
    date = serializers.DateField()
    count = serializers.IntegerField()
    cumulative = serializers.IntegerField()


class AdminActivitySerializer(serializers.Serializer):
    """System activity metrics"""
    date = serializers.DateField()
    time_entries = serializers.IntegerField()
    new_projects = serializers.IntegerField()
    active_users = serializers.IntegerField()


class AdminTopUserSerializer(serializers.Serializer):
    """Top users by tracked time"""
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()
    total_entries = serializers.IntegerField()
    total_seconds = serializers.IntegerField()
    total_hours = serializers.DecimalField(max_digits=10, decimal_places=2)


class AdminTopProjectSerializer(serializers.Serializer):
    """Top projects by tracked time"""
    project_id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField()
    type = serializers.CharField(allow_blank=True, required=False)
    team_name = serializers.CharField(allow_blank=True, required=False)
    total_entries = serializers.IntegerField()
    total_seconds = serializers.IntegerField()
    total_hours = serializers.DecimalField(max_digits=10, decimal_places=2)


class AdminTopTeamSerializer(serializers.Serializer):
    """Top teams by member/project activity"""
    team_id = serializers.IntegerField()
    name = serializers.CharField()
    owner_username = serializers.CharField(allow_blank=True, required=False)
    member_count = serializers.IntegerField()
    project_count = serializers.IntegerField()


# ==================== ACTIVITY LOG SERIALIZERS ====================

class ActivityLogSerializer(serializers.ModelSerializer):
    """Serializer for activity logs"""
    admin_email = serializers.EmailField(source='admin_user.email', read_only=True)
    admin_username = serializers.CharField(source='admin_user.username', read_only=True)
    
    class Meta:
        model = ActivityLog
        fields = [
            'id', 'admin_user', 'admin_email', 'admin_username',
            'action', 'target_type', 'target_id', 'description',
            'ip_address', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class AdminProjectWriteSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating projects from admin panel"""
    creator_id = serializers.PrimaryKeyRelatedField(
        source="creator",
        queryset=User.objects.all(),
        write_only=True,
    )
    team_id = serializers.PrimaryKeyRelatedField(
        source="team",
        queryset=Team.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    creator_email = serializers.EmailField(source="creator.email", read_only=True)
    creator_username = serializers.CharField(source="creator.username", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True, allow_null=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "description",
            "type",
            "creator_id",
            "creator_email",
            "creator_username",
            "team_id",
            "team_name",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "creator_email", "creator_username", "team_name"]


class UserAccessLogSerializer(serializers.ModelSerializer):
    """Serializer for user login/logout history"""
    user_email = serializers.EmailField(source="user.email", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = UserAccessLog
        fields = [
            "id",
            "user",
            "user_email",
            "username",
            "event_type",
            "role",
            "ip_address",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


# ==================== SETTINGS SERIALIZERS ====================

class AdminSettingsSerializer(serializers.Serializer):
    """System settings configuration"""
    app_name = serializers.CharField(max_length=120, required=False, allow_blank=False)
    support_email = serializers.EmailField(required=False)
    allow_public_registration = serializers.BooleanField(required=False)
    require_email_verification = serializers.BooleanField(required=False)
    maintenance_mode = serializers.BooleanField(required=False)
    session_timeout = serializers.IntegerField(min_value=5, max_value=1440, required=False)
    max_team_members = serializers.IntegerField(min_value=1, max_value=500, required=False)
    max_projects_per_user = serializers.IntegerField(min_value=1, max_value=5000, required=False)
    team_invite_expiry_days = serializers.IntegerField(min_value=1, max_value=60, required=False)
    standard_daily_hours = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=0, max_value=24, required=False)
    overtime_hourly_rate = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False)
    overtime_multiplier = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=0, max_value=10, required=False)
    prevent_overlapping_entries = serializers.BooleanField(required=False)
    require_timer_description = serializers.BooleanField(required=False)
    invite_emails_enabled = serializers.BooleanField(required=False)
    reminder_emails_enabled = serializers.BooleanField(required=False)
    audit_log_retention_days = serializers.IntegerField(min_value=7, max_value=3650, required=False)


class AdminPasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs


class AdminTestEmailSerializer(serializers.Serializer):
    recipient_email = serializers.EmailField(required=False)
