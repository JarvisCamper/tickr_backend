from rest_framework import serializers
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta

# Import models from other apps
from user.models import User
from management.models import Team, Project, TimeEntry, TeamMember

# Import admin models
from .models import ActivityLog, AdminSettings


# ==================== USER SERIALIZERS ====================

class AdminUserListSerializer(serializers.ModelSerializer):
    """List view serializer for users in admin panel"""
    total_time_entries = serializers.IntegerField(read_only=True)
    teams_count = serializers.IntegerField(read_only=True)
    projects_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'avatar', 'is_active', 
            'is_staff', 'is_superuser', 'last_login',
            'total_time_entries', 'teams_count', 'projects_count'
        ]
        read_only_fields = ['id', 'last_login']


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
            'id', 'email', 'username', 'avatar', 'is_active', 
            'is_staff', 'is_superuser', 'last_login',
            'total_time_entries', 'total_time_tracked',
            'teams', 'owned_teams', 'recent_projects'
        ]
        read_only_fields = ['id', 'last_login']
    
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
        fields = ['username', 'is_active', 'is_staff', 'is_superuser']


# ==================== TEAM SERIALIZERS ====================

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


# ==================== PROJECT SERIALIZERS ====================

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


# ==================== SETTINGS SERIALIZERS ====================

class AdminSettingsSerializer(serializers.Serializer):
    """System settings configuration"""
    max_team_members = serializers.IntegerField(min_value=1, max_value=100, required=False)
    max_projects_per_user = serializers.IntegerField(min_value=1, max_value=1000, required=False)
    require_email_verification = serializers.BooleanField(required=False)
    allow_public_registration = serializers.BooleanField(required=False)
    maintenance_mode = serializers.BooleanField(required=False)
    session_timeout = serializers.IntegerField(min_value=5, max_value=1440, required=False)
