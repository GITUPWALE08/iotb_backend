"""
Django settings for core project.
Production-ready, Celery-free configuration.
"""

import os
from pathlib import Path
import dj_database_url
import certifi

# --------------------------------------------------
# BASE SETUP
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

# Fix SSL cert issues (Render + Windows)
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

# --------------------------------------------------
# SECURITY
# --------------------------------------------------

SECRET_KEY = os.environ.get("SECRET_KEY", "unsafe-dev-key")

DEBUG = not os.environ.get("RENDER")

ALLOWED_HOSTS = [
    ".onrender.com",
    "iot-bridge.onrender.com",
    "https://iot-bridge.onrender.com",
    "localhost",
    "127.0.0.1",
]

# Required for HTTPS behind proxy (Render)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# --------------------------------------------------
# APPLICATIONS
# --------------------------------------------------

INSTALLED_APPS = [
    'daphne',
    'channels',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'corsheaders',
    'rest_framework',

    'devices',
    'telemetry',

    'django_extensions',

    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',

    'anymail',
]

AUTH_USER_MODEL = 'devices.User'

# --------------------------------------------------
# MIDDLEWARE
# --------------------------------------------------

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',

    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',

    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# --------------------------------------------------
# CORS / CSRF
# --------------------------------------------------

FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:5173')

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "https://www.iotbridging.tech",
    FRONTEND_URL,
]

CSRF_TRUSTED_ORIGINS = [
    "https://www.iotbridging.tech",
    "https://*.onrender.com",
]

# --------------------------------------------------
# TEMPLATES
# --------------------------------------------------

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
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

# --------------------------------------------------
# ASGI / WSGI
# --------------------------------------------------

ASGI_APPLICATION = 'core.asgi.application'
WSGI_APPLICATION = 'core.wsgi.application'

# --------------------------------------------------
# DATABASE (Optimized for production)
# --------------------------------------------------

DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get(
            'DATABASE_URL',
            'postgresql://iot_user:wale%400811@127.0.0.1:5432/iot_bridge_db'
        ),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# --------------------------------------------------
# REDIS (Channels + Cache ONLY — NOT Celery)
# --------------------------------------------------

if os.environ.get('RENDER'):
    REDIS_URL = os.environ.get('REDIS_URL')

    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_URL],
                "capacity": 1500,
                "expiry": 10,
            },
        },
    }

    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            }
        }
    }

else:
    # Local dev fallback
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }

    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache"
        }
    }

# --------------------------------------------------
# REST FRAMEWORK
# --------------------------------------------------

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],

    # Throttling tuned for IoT scale
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '500/day',
        'user': '10000/day',
        'burst': '60/minute',
        'ingestion': '6000/minute',
    }
}

# --------------------------------------------------
# EMAIL (Resend via Anymail)
# --------------------------------------------------

ANYMAIL = {
    "RESEND_API_KEY": os.environ.get("RESEND_API_KEY"),
}

EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"

DEFAULT_FROM_EMAIL = "noreply@mail.iotbridging.tech"
EMAIL_HOST = os.environ.get("EMAIL_HOST")
EMAIL_TIMEOUT = 60

# --------------------------------------------------
# MQTT CONFIG
# --------------------------------------------------

MQTT_BROKER_URL = os.environ.get('MQTT_BROKER_URL', 'localhost')
MQTT_BROKER_PORT = int(os.environ.get('MQTT_BROKER_PORT', 1883))

# --------------------------------------------------
# PASSWORD VALIDATION
# --------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --------------------------------------------------
# INTERNATIONALIZATION
# --------------------------------------------------

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'

USE_I18N = True
USE_TZ = True

# --------------------------------------------------
# STATIC FILES (Production-ready)
# --------------------------------------------------

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# --------------------------------------------------
# MEDIA FILES
# --------------------------------------------------

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# --------------------------------------------------
# DEFAULT PRIMARY KEY
# --------------------------------------------------

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'