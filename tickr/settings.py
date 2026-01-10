"""
Django settings for tickr project
"""
from pathlib import Path
from decouple import config, Csv
from datetime import timedelta
from urllib.parse import urlparse

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*', cast=Csv())

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',

    'user',
    'management',
    'admin_site',
]

# Use the custom user model defined in the `user` app
AUTH_USER_MODEL = 'user.User'

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',        
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # 'tickr.middleware.EnsureCORSHeadersMiddleware',  # ← COMMENTED OUT – it was breaking things
]

ROOT_URLCONF = 'tickr.urls'
WSGI_APPLICATION = 'tickr.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Database – Aiven + Vercel needs SSL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT'),
        'OPTIONS': {
            'sslmode': 'require',   
        },
    }
}

# CORS – ALLOW EVERYTHING FOR NOW (you can tighten later)
CORS_ALLOW_ALL_ORIGINS = config('CORS_ALLOW_ALL_ORIGINS', default=True, cast=bool)
CORS_ALLOW_CREDENTIALS = True

# Optional strict lists (ignored when CORS_ALLOW_ALL_ORIGINS=True)
# Normalize origins: django-cors-headers requires scheme://host[:port] with no path or trailing slash
def _normalize_origins(raw_origins):
    if not raw_origins:
        return []
    normalized = []
    for origin in raw_origins:
        if not origin:
            continue
        # Trim whitespace
        origin = origin.strip()
        # Parse the origin and rebuild scheme://netloc
        parsed = urlparse(origin)
        if parsed.scheme and parsed.netloc:
            normalized.append(f"{parsed.scheme}://{parsed.netloc}")
            continue
        # If no scheme provided, try assuming https
        if '://' not in origin:
            attempt = urlparse('https://' + origin.rstrip('/'))
            if attempt.scheme and attempt.netloc:
                normalized.append(f"{attempt.scheme}://{attempt.netloc}")
                continue
        # As a last resort, strip any trailing slash
        cleaned = origin.rstrip('/')
        normalized.append(cleaned)
    return normalized

_raw_cors = config(
    'CORS_ALLOWED_ORIGINS',
    default='https://localhost:3000,https://tickr-frontend.vercel.app',
    cast=Csv()
)
_raw_csrf = config(
    'CSRF_TRUSTED_ORIGINS',
    default='https://localhost:3000,https://tickr-frontend.vercel.app',
    cast=Csv()
)

CORS_ALLOWED_ORIGINS = _normalize_origins(_raw_cors)
CSRF_TRUSTED_ORIGINS = _normalize_origins(_raw_csrf)

# REST Framework & JWT
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': ('rest_framework.renderers.JSONRenderer',),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=7),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# Static & Media
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles_build'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'