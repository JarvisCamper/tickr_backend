"""
URL configuration for tickr project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# tickr/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from rest_framework_simplejwt.views import TokenRefreshView, TokenObtainPairView

urlpatterns = [
    path('admin/api/', include('admin_site.urls')), 
    path('django-admin/', admin.site.urls),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/', include('user.urls')),
    path('api/', include('management.urls')),
    path('api/auth/', include('rest_framework.urls')),
]

# Always expose uploaded media files so locally captured screenshots can be previewed.
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]

# Static files can stay dev-oriented.
if settings.DEBUG or "localhost" in settings.ALLOWED_HOSTS or "127.0.0.1" in settings.ALLOWED_HOSTS:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
