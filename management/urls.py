# management/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'projects', views.ProjectViewSet)
router.register(r'teams', views.TeamViewSet)
router.register(r'entries', views.TimeEntryViewSet)

urlpatterns = [
    path('', include(router.urls)),
    
    path('reports/', views.ReportView.as_view(), name='reports'),
    path('user/', views.CurrentUserView.as_view(), name='current-user'),
    
    # Invitation endpoints
    path('teams/<int:team_id>/invite/', views.send_team_invitation, name='send-invitation'),
    path('invitations/<uuid:token>/', views.get_invitation_details, name='invitation-details'),
    path('invitations/<uuid:token>/accept/', views.accept_invitation, name='accept-invitation'),
    path('invitations/<uuid:token>/decline/', views.decline_invitation, name='decline-invitation'),
    path('invitations/my/', views.my_invitations, name='my-invitations'),
]