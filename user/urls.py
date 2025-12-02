
from django.urls import path
from .views import *
from rest_framework.routers import DefaultRouter
from .views import UserAPIViewSet, LoginView, SignupView, CurrentUserView

router = DefaultRouter()
router.register(r'users', UserAPIViewSet, basename='user')
urlpatterns = [
    path('login/', LoginView.as_view() , name='login'),
    path('signup/', UserAPIViewSet.as_view({'post': 'create'}), name='signup'),
    path('user/', CurrentUserView.as_view(), name='current_user'),
 
    
]


# Include router-generated URLs
urlpatterns += router.urls