from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'projects', views.ProjectViewSet, basename='project')
router.register(r'teams', views.TeamViewSet, basename='team')
router.register(r'entries', views.TimeEntryViewSet, basename='timeentry')

urlpatterns = [
    path('', include(router.urls)),
    
    # Reports and User
    path('reports/', views.ReportView.as_view(), name='reports'),
    path('user/', views.CurrentUserView.as_view(), name='current-user'),
    
    # Team Invitation endpoints
    path('teams/<int:team_id>/invite/', views.send_team_invitation, name='send-invitation'),
    path('teams/invitations/<uuid:token>/', views.get_invitation_details, name='invitation-details'),
    path('teams/invitations/<uuid:token>/accept/', views.accept_invitation, name='accept-invitation'),
    path('teams/invitations/<uuid:token>/decline/', views.decline_invitation, name='decline-invitation'),
    path('teams/invitations/my/', views.my_invitations, name='my-invitations'),
]
