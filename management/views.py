# management/views.py
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.db.models import Sum
from django.utils import timezone
from django.http import Http404
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.urls import reverse
from decouple import config
import uuid

from .models import Project, Team, TeamMember, TimeEntry, TeamInvitation
from .serializers import (
    ProjectSerializer,
    TeamSerializer,
    TeamMemberSerializer,
    TimeEntrySerializer,
    TeamInvitationSerializer
)

User = get_user_model()

# Logger for debugging incoming requests
logger = logging.getLogger(__name__)

# Configuration
FRONTEND_URL = config('FRONTEND_URL', default='https://tickr-frontend.vercel.app/')


# PROJECT VIEWSET
class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return projects created by the user OR projects assigned to teams where user is a member/owner"""
        # Projects created by the user
        user_projects = Project.objects.filter(creator=self.request.user)
        
        # Teams where user is the owner
        owned_teams = Team.objects.filter(owner=self.request.user)
        
        # Teams where user is a member
        member_teams = Team.objects.filter(members__user=self.request.user)
        
        # All teams user has access to
        user_teams = (owned_teams | member_teams).distinct()
        
        # Projects assigned to those teams
        team_projects = Project.objects.filter(team__in=user_teams)
        
        # Combine both: user's own projects + team projects
        return (user_projects | team_projects).distinct()

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
        # Teams owned by the user
        owned_teams = Team.objects.filter(
            owner=self.request.user
        ).distinct()
        
        # Teams where user is a member
        member_teams = Team.objects.filter(
            members__user=self.request.user
        ).distinct()
        
        # Combine both querysets - both must have same distinct state
        return (owned_teams | member_teams).distinct()

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
        
        # Check if user is the owner
        if team.owner != request.user:
            return Response(
                {"detail": "Only team owner can generate invitations"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Create a generic invitation with unique placeholder email
            unique_placeholder = f"invite-{uuid.uuid4().hex[:12]}@pending.local"
            invitation = TeamInvitation.objects.create(
                team=team,
                email=unique_placeholder,
                invited_by=request.user,
                expires_at=timezone.now() + timedelta(days=7)
            )
            
            # Build the invitation link - Point to Next.js frontend
            invitation_link = f"{FRONTEND_URL}/teams/AcceptInvite/{invitation.token}"
            
            return Response({
                "invite_link": invitation_link,
                "invitation_link": invitation_link,
                "token": str(invitation.token),
                "expires_at": invitation.expires_at,
                "team_name": team.name
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            # Log the error for debugging
            import traceback
            traceback.print_exc()
            return Response(
                {"detail": f"Error creating invitation: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'], url_path='members')
    def list_members(self, request, pk=None):
        """List all members of a team (including owner)"""
        team = self.get_object()
        members = TeamMember.objects.filter(team=team).select_related('user')
        
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
        
        # Check if requester is the owner
        if team.owner != request.user:
            return Response(
                {'detail': 'Only team owner can remove members'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get user_id from request body
        user_id = request.data.get('user_id')
        if not user_id:
            return Response(
                {'detail': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Convert user_id to int for validation and database lookup
            user_id = int(user_id)
            
            # Cannot remove the owner
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
@method_decorator(csrf_exempt, name='dispatch')
class TimeEntryViewSet(viewsets.ModelViewSet):
    queryset = TimeEntry.objects.all()
    serializer_class = TimeEntrySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return only current user's entries"""
        return TimeEntry.objects.filter(user=self.request.user)

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
        entry = TimeEntry.objects.filter(
            user=request.user,
            is_running=True
        ).first()

        if entry:
            return Response(TimeEntrySerializer(entry, context={'request': request}).data)
        return Response({"detail": "No active timer"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'])
    @csrf_exempt
    def start(self, request):
        # Debug logging to inspect auth and cookies when requests fail
        try:
            auth_hdr = request.META.get('HTTP_AUTHORIZATION')
            cookie_hdr = request.META.get('HTTP_COOKIE')
            logger.debug("TimeEntry.start called - user=%s auth=%s cookies=%s data=%s", request.user, auth_hdr, cookie_hdr, request.data)
        except Exception:
            logger.exception("Failed reading request meta in TimeEntry.start")
        """Start a new timer (stop any running one first)"""
        # Stop any currently running timer
        TimeEntry.objects.filter(
            user=request.user,
            is_running=True
        ).update(end_time=timezone.now(), is_running=False)

        # Get data from request
        project_id = request.data.get('project_id')
        description = request.data.get('description', '')

        # Validate project exists and belongs to user
        project = None
        if project_id:
            try:
                project = Project.objects.get(id=project_id)
            except Project.DoesNotExist:
                return Response({"detail": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

            # Enforce permissions: allow if user created the project, is team owner/member, or is staff
            if not (
                project.creator == request.user or
                request.user.is_staff
            ):
                # If project has a team assigned, allow team owner or team members to start
                if project.team:
                    if project.team.owner == request.user or TeamMember.objects.filter(team=project.team, user=request.user).exists():
                        pass
                    else:
                        return Response({"detail": "You do not have permission to use this project"}, status=status.HTTP_403_FORBIDDEN)
                else:
                    return Response({"detail": "You do not have permission to use this project"}, status=status.HTTP_403_FORBIDDEN)

        # Create new entry
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
        entry = TimeEntry.objects.filter(
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
        entries = TimeEntry.objects.filter(user=request.user, end_time__isnull=False)

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
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    """Return the authenticated user's basic info"""
    user = request.user
    return Response({
        "id": user.id,
        "email": user.email,
        "username": user.username,
    })


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return the authenticated user's basic info"""
        user = request.user
        return Response({
            "id": user.id,
            "email": user.email,
            "username": user.username,
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
        
        email = invited_user.email
        
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
    
    if not email:
        unique_placeholder = f"invite-{uuid.uuid4().hex[:12]}@pending.local"
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
    
    invitation_link = f"{FRONTEND_URL}/teams/accept-invite/{invitation.token}"
    
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
    invitations = TeamInvitation.objects.filter(
        email=request.user.email,
        status='pending'
    ).select_related('team', 'invited_by')
    
    valid_invitations = [inv for inv in invitations if inv.is_valid()]
    
    return Response(TeamInvitationSerializer(valid_invitations, many=True, context={'request': request}).data)