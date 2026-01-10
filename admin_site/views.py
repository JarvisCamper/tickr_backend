from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Count, Sum, Q, Prefetch
from django.utils import timezone
from datetime import timedelta

# Import models from other apps
from user.models import User
from management.models import Team, Project, TimeEntry, TeamMember

# Import admin models and utilities
from .models import ActivityLog, AdminSettings
from .serializers import (
    AdminUserListSerializer, AdminUserDetailSerializer, AdminUserUpdateSerializer,
    AdminTeamListSerializer, AdminTeamDetailSerializer,
    AdminProjectListSerializer,
    AdminAnalyticsOverviewSerializer, AdminUserGrowthSerializer, AdminActivitySerializer,
    ActivityLogSerializer, AdminSettingsSerializer
)
from .permissions import IsAdminUser, IsSuperAdmin
from .utils import log_admin_action, get_client_ip


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ==================== USER VIEWSET ====================

class AdminUserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing users from admin panel
    """
    permission_classes = [IsAdminUser]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        queryset = User.objects.annotate(
            total_time_entries=Count('time_entries'),
            teams_count=Count('team_memberships', distinct=True),
            projects_count=Count('created_projects', distinct=True)
        ).order_by('-created_at')
        
        # Filters
        status_filter = self.request.query_params.get('status', None)
        search = self.request.query_params.get('search', None)
        
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
        elif status_filter == 'staff':
            queryset = queryset.filter(is_staff=True)
        
        if search:
            queryset = queryset.filter(
                Q(email__icontains=search) | Q(username__icontains=search)
            )
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AdminUserDetailSerializer
        elif self.action in ['update', 'partial_update']:
            return AdminUserUpdateSerializer
        return AdminUserListSerializer
    
    def update(self, request, *args, **kwargs):
        """Update user details"""
        response = super().update(request, *args, **kwargs)
        
        # Log the action
        log_admin_action(
            admin_user=request.user,
            action='user_update',
            target_type='user',
            target_id=kwargs.get('pk'),
            description=f"Updated user {self.get_object().email}",
            request=request
        )
        
        return response
    
    def destroy(self, request, *args, **kwargs):
        """Delete user"""
        user = self.get_object()
        email = user.email
        
        # Log before deletion
        log_admin_action(
            admin_user=request.user,
            action='user_delete',
            target_type='user',
            target_id=user.id,
            description=f"Deleted user {email}",
            request=request
        )
        
        return super().destroy(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        """Suspend a user account"""
        user = self.get_object()
        user.is_active = False
        user.save()
        
        log_admin_action(
            admin_user=request.user,
            action='user_suspend',
            target_type='user',
            target_id=user.id,
            description=f"Suspended user {user.email}",
            request=request
        )
        
        return Response({
            'message': f'User {user.email} has been suspended',
            'user': AdminUserDetailSerializer(user).data
        })
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a suspended user account"""
        user = self.get_object()
        user.is_active = True
        user.save()
        
        log_admin_action(
            admin_user=request.user,
            action='user_activate',
            target_type='user',
            target_id=user.id,
            description=f"Activated user {user.email}",
            request=request
        )
        
        return Response({
            'message': f'User {user.email} has been activated',
            'user': AdminUserDetailSerializer(user).data
        })


# ==================== TEAM VIEWSET ====================

class AdminTeamViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing teams from admin panel
    """
    permission_classes = [IsAdminUser]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        queryset = Team.objects.select_related('owner').annotate(
            members_count=Count('members', distinct=True),
            projects_count=Count('projects', distinct=True)
        ).order_by('-created_at')
        
        # Filters
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(owner__email__icontains=search)
            )
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AdminTeamDetailSerializer
        return AdminTeamListSerializer


# ==================== PROJECT VIEWSET ====================

class AdminProjectViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing projects from admin panel
    """
    permission_classes = [IsAdminUser]
    pagination_class = StandardResultsSetPagination
    serializer_class = AdminProjectListSerializer
    
    def get_queryset(self):
        queryset = Project.objects.select_related('creator', 'team').annotate(
            time_entries_count=Count('time_entries')
        ).order_by('-created_at')
        
        # Filters
        project_type = self.request.query_params.get('type', None)
        search = self.request.query_params.get('search', None)
        
        if project_type:
            queryset = queryset.filter(type=project_type)
        
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(creator__email__icontains=search)
            )
        
        return queryset


# ==================== ANALYTICS VIEWSETS ====================

class AdminAnalyticsViewSet(viewsets.ViewSet):
    """
    ViewSet for admin analytics and statistics
    """
    permission_classes = [IsAdminUser]
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get overview statistics for admin dashboard"""
        now = timezone.now()
        month_ago = now - timedelta(days=30)
        
        data = {
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'total_teams': Team.objects.count(),
            'total_projects': Project.objects.count(),
            'total_time_entries': TimeEntry.objects.count(),
            'new_users_this_month': User.objects.filter(created_at__gte=month_ago).count(),
            'new_teams_this_month': Team.objects.filter(created_at__gte=month_ago).count(),
            'new_projects_this_month': Project.objects.filter(created_at__gte=month_ago).count(),
        }
        
        serializer = AdminAnalyticsOverviewSerializer(data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='users/growth')
    def user_growth(self, request):
        """Get user growth data over time"""
        days = int(request.query_params.get('days', 30))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        growth_data = []
        cumulative = User.objects.filter(created_at__date__lt=start_date).count()
        
        for i in range(days + 1):
            current_date = start_date + timedelta(days=i)
            daily_count = User.objects.filter(created_at__date=current_date).count()
            cumulative += daily_count
            
            growth_data.append({
                'date': current_date,
                'count': daily_count,
                'cumulative': cumulative
            })
        
        serializer = AdminUserGrowthSerializer(growth_data, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def activity(self, request):
        """Get system activity metrics"""
        days = int(request.query_params.get('days', 7))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        activity_data = []
        
        for i in range(days + 1):
            current_date = start_date + timedelta(days=i)
            next_date = current_date + timedelta(days=1)
            
            time_entries = TimeEntry.objects.filter(
                start_time__date=current_date
            ).count()
            
            new_projects = Project.objects.filter(
                created_at__date=current_date
            ).count()
            
            active_users = TimeEntry.objects.filter(
                start_time__date=current_date
            ).values('user').distinct().count()
            
            activity_data.append({
                'date': current_date,
                'time_entries': time_entries,
                'new_projects': new_projects,
                'active_users': active_users
            })
        
        serializer = AdminActivitySerializer(activity_data, many=True)
        return Response(serializer.data)


# ==================== ACTIVITY LOG VIEWSET ====================

class AdminActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing activity logs
    """
    permission_classes = [IsAdminUser]
    serializer_class = ActivityLogSerializer
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        queryset = ActivityLog.objects.select_related('admin_user').order_by('-created_at')
        
        # Filters
        action = self.request.query_params.get('action', None)
        admin_id = self.request.query_params.get('admin_id', None)
        
        if action:
            queryset = queryset.filter(action=action)
        
        if admin_id:
            queryset = queryset.filter(admin_user_id=admin_id)
        
        return queryset


# ==================== SETTINGS VIEWSET ====================

class AdminSettingsViewSet(viewsets.ViewSet):
    """
    ViewSet for managing admin settings
    """
    permission_classes = [IsSuperAdmin]
    
    def list(self, request):
        """Get all admin settings"""
        settings = {}
        for setting in AdminSettings.objects.all():
            settings[setting.key] = setting.value
        
        serializer = AdminSettingsSerializer(settings)
        return Response(serializer.data)
    
    def create(self, request):
        """Update admin settings"""
        serializer = AdminSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        for key, value in serializer.validated_data.items():
            AdminSettings.objects.update_or_create(
                key=key,
                defaults={
                    'value': str(value),
                    'updated_by': request.user
                }
            )
        
        log_admin_action(
            admin_user=request.user,
            action='settings_update',
            target_type='settings',
            target_id=None,
            description=f"Updated system settings",
            request=request
        )
        
        return Response({
            'message': 'Settings updated successfully',
            'settings': serializer.data
        })
