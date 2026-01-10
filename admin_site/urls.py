from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AdminUserViewSet,
    AdminTeamViewSet,
    AdminProjectViewSet,
    AdminAnalyticsViewSet,
    AdminActivityLogViewSet,
    AdminSettingsViewSet
)

router = DefaultRouter()
router.register(r'users', AdminUserViewSet, basename='admin-user')
router.register(r'teams', AdminTeamViewSet, basename='admin-team')
router.register(r'projects', AdminProjectViewSet, basename='admin-project')
router.register(r'analytics', AdminAnalyticsViewSet, basename='admin-analytics')
router.register(r'activity-logs', AdminActivityLogViewSet, basename='admin-activity-log')
router.register(r'settings', AdminSettingsViewSet, basename='admin-settings')

urlpatterns = [
    path('', include(router.urls)),
]
