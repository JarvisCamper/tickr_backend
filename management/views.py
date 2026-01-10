# management/views.py
import logging
from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.http import Http404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from decouple import config

from .models import Project, Team, TeamMember, TimeEntry, TeamInvitation
from .serializers import (
    ProjectSerializer,
    TeamSerializer,
    TimeEntrySerializer,
    TeamInvitationSerializer
)

User = get_user_model()

logger = logging.getLogger(__name__)
FRONTEND_URL = config('FRONTEND_URL', default='https://tickr-frontend.vercel.app/')


# PROJECT VIEWSET
class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return projects created by the user OR projects assigned to teams where user is a member/owner"""
        from django.db.models import Q
        
        # Optimize with select_related to avoid N+1 queries
        # Get all projects in a single query with proper joins
        return Project.objects.select_related('creator', 'team').filter(
            Q(creator=self.request.user) |  # User's own projects
            Q(team__owner=self.request.user) |  # Projects from teams user owns
            Q(team__members__user=self.request.user)  # Projects from teams user is member of
        ).distinct()

    def get_serializer_context(self):
        """Pass request context to serializer"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        """Automatically set the creator to the current user"""
        serializer.save(creator=self.request.user)


# TEAM VIEWSET
class TeamViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return teams owned by the current user or teams they are a member of"""
        from django.db.models import Q
        
        # Optimize with single query and prefetch members
        return Team.objects.select_related('owner').prefetch_related(
            'members__user'
        ).filter(
            Q(owner=self.request.user) | Q(members__user=self.request.user)
        ).distinct()

    def get_serializer_context(self):
        """Pass request context to serializer"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        """Automatically set the owner to the current user"""
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'], url_path='invite')
    def invite(self, request, pk=None):
        """Generate invitation link for the team"""
        team = self.get_object()
        
        if team.owner != request.user:
            return Response(
                {"detail": "Only team owner can generate invitations"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            unique_placeholder = f"invite-{uuid4().hex[:12]}@pending.local"
            invitation = TeamInvitation.objects.create(
                team=team,
                email=unique_placeholder,
                invited_by=request.user,
                expires_at=timezone.now() + timedelta(days=7)
            )
            
            invitation_link = f"{FRONTEND_URL}/teams/AcceptInvite/{invitation.token}"
            
            return Response({
                "invite_link": invitation_link,
                "token": str(invitation.token),
                "expires_at": invitation.expires_at,
                "team_name": team.name
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.exception("Error creating invitation")
            return Response(
                {"detail": f"Error creating invitation: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'], url_path='members')
    def list_members(self, request, pk=None):
        """List all members of a team (including owner)"""
        team = Team.objects.select_related('owner').prefetch_related('members__user').get(pk=pk)
        members = team.members.all()
        
        # Build member list with role information
        member_data = []
        
        # Always include the owner first
        owner_in_members = False
        for member in members:
            if member.user == team.owner:
                owner_in_members = True
                member_data.append({
                    'id': member.id,
                    'user_id': team.owner.id,
                    'username': team.owner.username,
                    'email': team.owner.email,
                    'role': 'owner',
                    'joined_at': team.created_at  # Use team creation date for owner
                })
            else:
                member_data.append({
                    'id': member.id,
                    'user_id': member.user.id,
                    'username': member.user.username,
                    'email': member.user.email,
                    'role': 'member',
                    'joined_at': member.joined_at
                })
        
        # If owner is not in TeamMember table, add them manually
        if not owner_in_members:
            member_data.insert(0, {
                'id': -1,  # Special ID for owner not in TeamMember table
                'user_id': team.owner.id,
                'username': team.owner.username,
                'email': team.owner.email,
                'role': 'owner',
                'joined_at': team.created_at
            })
        
        return Response(member_data)

    @action(detail=True, methods=['delete'], url_path='remove-member')
    def remove_member(self, request, pk=None):
        """Remove a member from the team"""
        team = self.get_object()
        
        if team.owner != request.user:
            return Response(
                {'detail': 'Only team owner can remove members'},
                status=status.HTTP_403_FORBIDDEN
            )

        user_id = request.data.get('user_id')
        if not user_id:
            return Response(
                {'detail': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user_id = int(user_id)
            
            if user_id == team.owner.id:
                return Response(
                    {'detail': 'Cannot remove the team owner'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            member_to_remove = TeamMember.objects.get(team=team, user_id=user_id)
            member_to_remove.delete()
            return Response(
                {'detail': 'Member removed successfully'},
                status=status.HTTP_200_OK
            )
        except (ValueError, TypeError):
            return Response(
                {'detail': 'Invalid user_id format'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except TeamMember.DoesNotExist:
            return Response(
                {'detail': 'User is not a member of this team'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'], url_path='assign-project')
    def assign_project(self, request, pk=None):
        """Assign a project to this team"""
        # Try to get the team - get_object() uses get_queryset() which filters by user access
        try:
            team = self.get_object()
        except Http404:
            # Try to get more information about why it failed
            try:
                # Check if team exists at all
                team_exists = Team.objects.filter(id=pk).exists()
                if not team_exists:
                    return Response(
                        {"detail": f"Team with ID {pk} does not exist"},
                        status=status.HTTP_404_NOT_FOUND
                    )
                # Team exists but user doesn't have access
                return Response(
                    {"detail": f"You don't have access to team {pk}. You must be the owner or a member."},
                    status=status.HTTP_403_FORBIDDEN
                )
            except (ValueError, TypeError):
                return Response(
                    {"detail": f"Invalid team ID: {pk}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Check if user is the owner
        if team.owner != request.user:
            return Response(
                {"detail": "Only team owner can assign projects"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        project_id = request.data.get('project_id')
        if not project_id:
            return Response(
                {"detail": "project_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get the project and check ownership
            project = Project.objects.get(id=project_id, creator=request.user)
            
            # Assign project to team
            project.team = team
            project.save()
            
            return Response({
                "detail": "Project assigned successfully",
                "project": ProjectSerializer(project, context={'request': request}).data
            }, status=status.HTTP_200_OK)
            
        except Project.DoesNotExist:
            return Response(
                {"detail": "Project not found or you don't have permission"},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'], url_path='unassign-project')
    def unassign_project(self, request, pk=None):
        """Unassign a project from this team"""
        team = self.get_object()
        
        # Check if user is the owner
        if team.owner != request.user:
            return Response(
                {"detail": "Only team owner can unassign projects"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        project_id = request.data.get('project_id')
        if not project_id:
            return Response(
                {"detail": "project_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get the project
            project = Project.objects.get(id=project_id, team=team, creator=request.user)
            
            # Unassign project from team
            project.team = None
            project.save()
            
            return Response({
                "detail": "Project unassigned successfully",
                "project": ProjectSerializer(project, context={'request': request}).data
            }, status=status.HTTP_200_OK)
            
        except Project.DoesNotExist:
            return Response(
                {"detail": "Project not found or not assigned to this team"},
                status=status.HTTP_404_NOT_FOUND
            )


# TIME ENTRY VIEWSET
class TimeEntryViewSet(viewsets.ModelViewSet):
    queryset = TimeEntry.objects.all()
    serializer_class = TimeEntrySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return only current user's entries"""
        return TimeEntry.objects.select_related('project', 'user').filter(user=self.request.user)

    def get_serializer_context(self):
        """Pass request context to serializer"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        """Automatically set the user to the current user"""
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get the currently running timer if any"""
        entry = TimeEntry.objects.select_related('project').filter(
            user=request.user,
            is_running=True
        ).first()

        if entry:
            return Response(TimeEntrySerializer(entry, context={'request': request}).data)
        return Response({"detail": "No active timer"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'])
    def start(self, request):
        """Start a new timer (stop any running one first)"""
        TimeEntry.objects.filter(
            user=request.user,
            is_running=True
        ).update(end_time=timezone.now(), is_running=False)

        project_id = request.data.get('project_id')
        description = request.data.get('description', '')

        project = None
        if project_id:
            try:
                project = Project.objects.get(id=project_id)
            except Project.DoesNotExist:
                return Response({"detail": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

            if not (project.creator == request.user or request.user.is_staff):
                if project.team:
                    if not (project.team.owner == request.user or TeamMember.objects.filter(team=project.team, user=request.user).exists()):
                        return Response({"detail": "You do not have permission to use this project"}, status=status.HTTP_403_FORBIDDEN)
                else:
                    return Response({"detail": "You do not have permission to use this project"}, status=status.HTTP_403_FORBIDDEN)

        entry = TimeEntry.objects.create(
            user=request.user,
            project=project,
            description=description,
            start_time=timezone.now(),
            is_running=True
        )
        return Response(
            TimeEntrySerializer(entry, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['post'])
    def stop(self, request):
        """Stop the currently running timer"""
        entry = TimeEntry.objects.select_related('project').filter(
            user=request.user,
            is_running=True
        ).first()

        if not entry:
            return Response(
                {"detail": "No active timer to stop"},
                status=status.HTTP_400_BAD_REQUEST
            )

        entry.end_time = timezone.now()
        entry.is_running = False
        entry.save()

        return Response(TimeEntrySerializer(entry, context={'request': request}).data)


# REPORTS VIEW
class ReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Generate time tracking reports for the current user"""
        entries = TimeEntry.objects.select_related('project').filter(user=request.user, end_time__isnull=False)

        # Total time
        total_duration = entries.aggregate(total=Sum('duration'))['total']
        total_seconds = int(total_duration.total_seconds()) if total_duration else 0
        h, r = divmod(total_seconds, 3600)
        m, s = divmod(r, 60)
        total_str = f"{h:02d}:{m:02d}:{s:02d}"

        # Per-project breakdown
        project_stats = (
            entries.values('project__name')
            .annotate(hours=Sum('duration'))
            .order_by('-hours')
        )

        breakdown = []
        for stat in project_stats:
            secs = int(stat['hours'].total_seconds()) if stat['hours'] else 0
            hh, rr = divmod(secs, 3600)
            mm, ss = divmod(rr, 60)
            breakdown.append({
                'project_name': stat['project__name'] or 'No Project',
                'hours_str': f"{hh:02d}:{mm:02d}:{ss:02d}",
                'total_seconds': secs
            })

        return Response({
            "total_time": total_str,
            "project_breakdown": breakdown
        })


# USER INFO ENDPOINT
class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return the authenticated user's basic info"""
        return Response({
            "id": request.user.id,
            "email": request.user.email,
            "username": request.user.username,
        })


# INVITATION ENDPOINTS

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_team_invitation(request, team_id):
    """Send invitation to join a team"""
    try:
        team = Team.objects.get(id=team_id, owner=request.user)
    except Team.DoesNotExist:
        return Response(
            {"detail": "Team not found or you don't have permission"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    user_id = request.data.get('user_id')
    email = request.data.get('email', '').strip()
    
    if user_id:
        try:
            invited_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if TeamMember.objects.filter(team=team, user=invited_user).exists():
            return Response(
                {"detail": "User is already a team member"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        email = invited_user.email
        invitation = TeamInvitation.objects.create(
            team=team,
            email=email,
            invited_by=request.user,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        invitation_link = f"{FRONTEND_URL}/teams/AcceptInvite/{invitation.token}"
        
        return Response({
            "detail": "Invitation sent successfully",
            "invitation_link": invitation_link,
            "invitation_code": str(invitation.token),
            "invitation": TeamInvitationSerializer(invitation).data
        }, status=status.HTTP_201_CREATED)
    
    if not email:
        unique_placeholder = f"invite-{uuid4().hex[:12]}@pending.local"
        invitation = TeamInvitation.objects.create(
            team=team,
            email=unique_placeholder,
            invited_by=request.user,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        invitation_link = f"{FRONTEND_URL}/teams/AcceptInvite/{invitation.token}"
        
        return Response({
            "detail": "Invitation link created successfully",
            "invitation_link": invitation_link,
            "invitation_code": str(invitation.token),
            "invitation": TeamInvitationSerializer(invitation).data
        }, status=status.HTTP_201_CREATED)
    
    try:
        invited_user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response(
            {"detail": "No user found with this email"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if TeamMember.objects.filter(team=team, user=invited_user).exists():
        return Response(
            {"detail": "User is already a team member"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    invitation = TeamInvitation.objects.create(
        team=team,
        email=email,
        invited_by=request.user,
        expires_at=timezone.now() + timedelta(days=7)
    )
    
    invitation_link = f"{FRONTEND_URL}/teams/AcceptInvite/{invitation.token}"
    
    return Response({
        "detail": "Invitation sent successfully",
        "invitation_link": invitation_link,
        "invitation_code": str(invitation.token),
        "invitation": TeamInvitationSerializer(invitation).data
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_invitation_details(request, token):
    """Get invitation details by token"""
    try:
        invitation = TeamInvitation.objects.select_related('team', 'invited_by').get(token=token)
    except TeamInvitation.DoesNotExist:
        return Response(
            {"detail": "Invitation not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if not invitation.is_valid():
        return Response(
            {"detail": "Invitation has expired or is no longer valid"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    return Response(TeamInvitationSerializer(invitation).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_invitation(request, token):
    """Accept a team invitation"""
    try:
        invitation = TeamInvitation.objects.get(token=token)
    except TeamInvitation.DoesNotExist:
        return Response(
            {"detail": "Invitation not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if not invitation.is_valid():
        return Response(
            {"detail": "Invitation has expired or is no longer valid"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if TeamMember.objects.filter(team=invitation.team, user=request.user).exists():
        return Response(
            {"detail": "You are already a member of this team"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    member, created = TeamMember.objects.get_or_create(
        team=invitation.team,
        user=request.user
    )
    
    invitation.status = 'accepted'
    invitation.accepted_at = timezone.now()
    invitation.save()
    
    return Response({
        "detail": "Successfully joined the team!",
        "team": TeamSerializer(invitation.team, context={'request': request}).data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def decline_invitation(request, token):
    """Decline a team invitation"""
    try:
        invitation = TeamInvitation.objects.get(token=token)
    except TeamInvitation.DoesNotExist:
        return Response(
            {"detail": "Invitation not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    invitation.status = 'declined'
    invitation.save()
    
    return Response({"detail": "Invitation declined"})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_invitations(request):
    """Get all pending invitations for the logged-in user"""
    invitations = TeamInvitation.objects.select_related('team__owner', 'invited_by').filter(
        email=request.user.email,
        status='pending'
    )
    
    valid_invitations = [inv for inv in invitations if inv.is_valid()]
    
    return Response(TeamInvitationSerializer(valid_invitations, many=True, context={'request': request}).data)