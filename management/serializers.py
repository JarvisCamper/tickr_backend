# management/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Project, Team, TeamMember, TimeEntry, TeamInvitation



class UserSimpleSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)


class ProjectSerializer(serializers.ModelSerializer):
    creator = UserSimpleSerializer(read_only=True)
    team_id = serializers.PrimaryKeyRelatedField(
        queryset=Team.objects.none(),  # Will be set in __init__
        source='team',
        allow_null=True,
        required=False
    )

    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'type', 'creator', 'team_id', 'created_at']
        read_only_fields = ['id', 'creator', 'created_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            # Only show teams owned by the current user
            self.fields['team_id'].queryset = Team.objects.filter(owner=request.user)

    def validate_name(self, value):
        """Ensure project name is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Project name cannot be empty")
        return value.strip()


class TeamSerializer(serializers.ModelSerializer):
    owner = UserSimpleSerializer(read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = ['id', 'name', 'description', 'owner', 'member_count', 'created_at']
        read_only_fields = ['id', 'owner', 'created_at']

    def get_member_count(self, obj):
        return obj.members.count()

    def validate_name(self, value):
        """Ensure team name is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Team name cannot be empty")
        return value.strip()


class TeamMemberSerializer(serializers.ModelSerializer):
    user = UserSimpleSerializer(read_only=True)
    team_id = serializers.PrimaryKeyRelatedField(
        queryset=Team.objects.none(), 
        source='team'
    )

    class Meta:
        model = TeamMember
        fields = ['id', 'team_id', 'user', 'joined_at']
        read_only_fields = ['id', 'user', 'joined_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            self.fields['team_id'].queryset = Team.objects.filter(owner=request.user)


class TeamInvitationSerializer(serializers.ModelSerializer):
    team = TeamSerializer(read_only=True)
    invited_by = UserSimpleSerializer(read_only=True)
    
    class Meta:
        model = TeamInvitation
        fields = ['id', 'team', 'email', 'invited_by', 'token', 'status', 
                  'created_at', 'expires_at', 'accepted_at']
        read_only_fields = ['id', 'token', 'created_at', 'expires_at']


class TimeEntrySerializer(serializers.ModelSerializer):
    user = UserSimpleSerializer(read_only=True)
    project = ProjectSerializer(read_only=True)
    project_id = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.none(), 
        source='project',
        write_only=True,
        allow_null=True,
        required=False
    )
    duration_display = serializers.SerializerMethodField()
    elapsed_time = serializers.SerializerMethodField()

    class Meta:
        model = TimeEntry
        fields = [
            'id', 'user', 'project', 'project_id', 'description',
            'start_time', 'end_time', 'duration', 'duration_display',
            'elapsed_time', 'is_running'
        ]
        read_only_fields = ['id', 'user', 'duration', 'start_time', 'end_time']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            
            self.fields['project_id'].queryset = Project.objects.filter(creator=request.user)

    def get_duration_display(self, obj):
        """Format duration as HH:MM:SS"""
        if obj.duration:
            total_seconds = int(obj.duration.total_seconds())
            h, r = divmod(total_seconds, 3600)
            m, s = divmod(r, 60)
            return f"{h:02d}:{m:02d}:{s:02d}"
        return "00:00:00"

    def get_elapsed_time(self, obj):
        """Calculate elapsed time for running timers"""
        if obj.is_running and obj.start_time:
            from django.utils import timezone
            elapsed = timezone.now() - obj.start_time
            total_seconds = int(elapsed.total_seconds())
            h, r = divmod(total_seconds, 3600)
            m, s = divmod(r, 60)
            return f"{h:02d}:{m:02d}:{s:02d}"
        return None