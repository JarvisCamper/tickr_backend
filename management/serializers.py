from rest_framework import serializers
from .models import Project, Team, TeamMember, TimeEntry, TeamInvitation
from django.contrib.auth import get_user_model

User = get_user_model()


class ProjectSerializer(serializers.ModelSerializer):
    creator_username = serializers.CharField(source='creator.username', read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True, allow_null=True)
    team_id = serializers.IntegerField(source='team.id', read_only=True, allow_null=True)
    
    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'type', 'creator', 'creator_username', 'team', 'team_id', 'team_name', 'created_at']
        read_only_fields = ['creator', 'created_at']


class TeamMemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    
    class Meta:
        model = TeamMember
        fields = ['id', 'user_id', 'username', 'email', 'joined_at']


class TeamSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    owner = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = ['id', 'name', 'description', 'owner', 'owner_username', 'members', 'member_count', 'created_at']
        read_only_fields = ['created_at']
    
    def get_owner(self, obj):
        """Return full owner object with id, username, and email"""
        return {
            'id': obj.owner.id,
            'username': obj.owner.username,
            'email': obj.owner.email
        }

    def get_member_count(self, obj):
        return obj.members.count()
    
    def get_members(self, obj):
        """Return all members including the owner, with role information"""
        members = obj.members.all().select_related('user')
        member_list = []
        owner_in_members = False
        
        for member in members:
            is_owner = member.user == obj.owner
            if is_owner:
                owner_in_members = True
            member_list.append({
                'id': member.id,
                'user_id': member.user.id,
                'username': member.user.username,
                'email': member.user.email,
                'role': 'owner' if is_owner else 'member',
                'joined_at': member.joined_at if not is_owner else obj.created_at
            })
        
        if not owner_in_members:
            member_list.insert(0, {
                'id': -1,
                'user_id': obj.owner.id,
                'username': obj.owner.username,
                'email': obj.owner.email,
                'role': 'owner',
                'joined_at': obj.created_at
            })
        
        return member_list
class TimeEntrySerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True, allow_null=True)
    duration_str = serializers.SerializerMethodField()
    
    class Meta:
        model = TimeEntry
        fields = ['id', 'user', 'project', 'project_name', 'description', 'start_time', 'end_time', 'duration', 'duration_str', 'is_running']
        read_only_fields = ['user', 'duration']
    
    def get_duration_str(self, obj):
        if obj.duration:
            total_seconds = int(obj.duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return "00:00:00"


class TeamInvitationSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source='team.name', read_only=True)
    invited_by_username = serializers.CharField(source='invited_by.username', read_only=True)
    
    class Meta:
        model = TeamInvitation
        fields = ['id', 'team', 'team_name', 'email', 'invited_by', 'invited_by_username', 'token', 'status', 'created_at', 'expires_at', 'accepted_at']
        read_only_fields = ['token', 'created_at']