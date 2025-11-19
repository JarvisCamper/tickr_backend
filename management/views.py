# management/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

from .models import Project, Team, TeamMember, TimeEntry, TeamInvitation
from .serializers import (
    ProjectSerializer,
    TeamSerializer,
    TeamMemberSerializer,
    TimeEntrySerializer,
    TeamInvitationSerializer
)

User = get_user_model()


# PROJECT VIEWSET
class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return only projects created by the current user"""
        return Project.objects.filter(creator=self.request.user)

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
        """Return only teams owned by the current user"""
        return Team.objects.filter(owner=self.request.user)

    def get_serializer_context(self):
        """Pass request context to serializer"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        """Automatically set the owner to the current user"""
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'])
    def invite(self, request, pk=None):
        """Invite a user to the team"""
        team = self.get_object()
        user_id = request.data.get('user_id')

        if not user_id:
            return Response(
                {"detail": "user_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            member, created = TeamMember.objects.get_or_create(
                team=team,
                user_id=user_id
            )
            message = "Invited successfully" if created else "User is already a member"
            return Response({"detail": message}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# TIME ENTRY VIEWSET
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
    def start(self, request):
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
                project = Project.objects.get(id=project_id, creator=request.user)
            except Project.DoesNotExist:
                return Response(
                    {"detail": "Project not found or you don't have permission to use it"},
                    status=status.HTTP_403_FORBIDDEN
                )

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
    
    email = request.data.get('email', '').strip()
    
    # If no email provided, create a generic invitation link
    if not email:
        # Create invitation with a placeholder email
        invitation = TeamInvitation.objects.create(
            team=team,
            email='pending@invite.link',  # Placeholder
            invited_by=request.user,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        invitation_link = f"http://localhost:3000/invitations/{invitation.token}"
        
        return Response({
            "detail": "Invitation link created successfully",
            "invitation_link": invitation_link,
            "invitation": TeamInvitationSerializer(invitation).data
        }, status=status.HTTP_201_CREATED)
    
    # If email provided, validate user exists
    try:
        invited_user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response(
            {"detail": "No user found with this email"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check if already a member
    if TeamMember.objects.filter(team=team, user=invited_user).exists():
        return Response(
            {"detail": "User is already a team member"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check for existing pending invitation
    existing = TeamInvitation.objects.filter(
        team=team,
        email=email,
        status='pending'
    ).first()
    
    if existing and existing.is_valid():
        return Response(
            {"detail": "Invitation already sent to this email"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Create new invitation
    invitation = TeamInvitation.objects.create(
        team=team,
        email=email,
        invited_by=request.user,
        expires_at=timezone.now() + timedelta(days=7)
    )
    
    invitation_link = f"http://localhost:3000/invitations/{invitation.token}"
    
    return Response({
        "detail": "Invitation sent successfully",
        "invitation_link": invitation_link,
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
    
    if request.user.email != invitation.email:
        return Response(
            {"detail": "This invitation was sent to a different email address"},
            status=status.HTTP_403_FORBIDDEN
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
    })


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
    
    if request.user.email != invitation.email:
        return Response(
            {"detail": "This invitation was sent to a different email address"},
            status=status.HTTP_403_FORBIDDEN
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