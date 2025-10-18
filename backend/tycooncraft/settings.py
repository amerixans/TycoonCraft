import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Add these 2 lines
env_path = BASE_DIR / '.env'  # Points to /var/www/tycooncraft/.env
load_dotenv(dotenv_path=env_path)


SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-change-this-in-production')

DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'game',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'tycooncraft.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'tycooncraft.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'tycooncraft'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'postgres'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/django-static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS Configuration - gate behind DEBUG flag for security
if DEBUG:
    # Allow all origins in development
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOW_CREDENTIALS = True
else:
    # In production, only allow specific origins
    cors_origins = os.environ.get('CORS_ALLOWED_ORIGINS', '')
    if cors_origins:
        CORS_ALLOWED_ORIGINS = [origin.strip() for origin in cors_origins.split(',') if origin.strip()]
    else:
        # Fallback: construct from domain if CORS_ALLOWED_ORIGINS not set
        domain = os.environ.get('DOMAIN', 'localhost')
        server_ip = os.environ.get('SERVER_IP', '')
        CORS_ALLOWED_ORIGINS = [
            f'http://{domain}',
            f'https://{domain}',
            f'http://www.{domain}',
            f'https://www.{domain}',
        ]
        if server_ip:
            CORS_ALLOWED_ORIGINS.extend([f'http://{server_ip}', f'https://{server_ip}'])

    CORS_ALLOW_CREDENTIALS = True

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# Session and CSRF Cookie Configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400 * 30  # 30 days
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG  # Only secure cookies in production (HTTPS)

CSRF_COOKIE_HTTPONLY = False  # Frontend needs to read it for the header
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = not DEBUG  # Only secure cookies in production (HTTPS)
CSRF_TRUSTED_ORIGINS = []

# Add domain to CSRF_TRUSTED_ORIGINS
if not DEBUG:
    domain = os.environ.get('DOMAIN', 'localhost')
    server_ip = os.environ.get('SERVER_IP', '')
    CSRF_TRUSTED_ORIGINS = [
        f'https://{domain}',
        f'https://www.{domain}',
    ]
    if server_ip:
        CSRF_TRUSTED_ORIGINS.append(f'https://{server_ip}')

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

# Rate limiting - per minute (legacy, kept for backward compatibility)
RATE_LIMIT_USER_DISCOVERIES = 4
RATE_LIMIT_GLOBAL_API_CALLS = 50
RATE_LIMIT_WINDOW = 60  # seconds

# Daily rate limits by tier
RATE_LIMIT_DAILY_STANDARD = 20  # Standard users
RATE_LIMIT_DAILY_PRO = 500      # Pro users (with upgrade key)
RATE_LIMIT_DAILY_ADMIN = 1000   # Admin users
RATE_LIMIT_DAILY_GLOBAL = 4000  # Total API calls per day across all users

STARTING_COINS = 500

# Image Compression Settings
# Quality level: 0-95 (higher = better quality, larger file size)
# 75-85 recommended for good quality/size tradeoff
IMAGE_COMPRESSION_QUALITY = 85
