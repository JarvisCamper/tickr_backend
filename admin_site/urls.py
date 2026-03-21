from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AdminUserViewSet,
    AdminTeamViewSet,
    AdminProjectViewSet,
    AdminTimeEntryViewSet,
    AdminScreenshotViewSet,
    AdminAnalyticsViewSet,
    AdminActivityLogViewSet,
    AdminUserAccessLogViewSet,
    AdminSettingsViewSet
)

router = DefaultRouter()
router.register(r'users', AdminUserViewSet, basename='admin-user')
router.register(r'teams', AdminTeamViewSet, basename='admin-team')
router.register(r'projects', AdminProjectViewSet, basename='admin-project')
router.register(r'time-entries', AdminTimeEntryViewSet, basename='admin-time-entry')
router.register(r'screenshots', AdminScreenshotViewSet, basename='admin-screenshot')
router.register(r'analytics', AdminAnalyticsViewSet, basename='admin-analytics')
router.register(r'activity-logs', AdminActivityLogViewSet, basename='admin-activity-log')
router.register(r'auth-events', AdminUserAccessLogViewSet, basename='admin-auth-event')
router.register(r'settings', AdminSettingsViewSet, basename='admin-settings')

urlpatterns = [
    path('', include(router.urls)),
]
