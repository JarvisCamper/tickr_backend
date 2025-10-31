
from django.urls import path
from .views import *
from rest_framework.routers import DefaultRouter
from .views import UserAPIViewSet, LoginView

router = DefaultRouter()
router.register(r'user', UserAPIViewSet, basename='user')
urlpatterns = [
    path('login/', LoginView.as_view() , name='login'),
]