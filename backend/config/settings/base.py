from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(env_file)

SECRET_KEY = env("SECRET_KEY", default="django-insecure-change-me-in-production")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    # daphne must precede staticfiles: it makes `runserver` speak ASGI/WebSocket.
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "rest_framework",
    "django_filters",
    "drf_yasg",
    "apps.accounts",
    "apps.tickets",
    "apps.notifications",
    "apps.realtime",
    "apps.analytics",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "config.logging_utils.RequestIDMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Local filesystem storage for now; swapped to S3 in Phase 8 by changing
# STORAGES only — Attachment's model code does not need to change.
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    },
}

# Django's cache framework on the same Redis server, but its own database
# number: cache.clear() issues FLUSHDB, which must never be able to wipe the
# Celery queue that lives in database 0.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("CACHE_URL", default="redis://localhost:6379/1"),
        "KEY_PREFIX": "deskhive",
    },
}

# Celery — Redis doubles as both the message broker and the result backend,
# so no extra service is needed beyond what's already running.
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TIMEZONE = TIME_ZONE
# Explicitly JSON, not Celery's old pickle default: pickle deserializes
# arbitrary Python objects, which is a real remote-code-execution risk if
# anything untrusted ever reaches the broker.
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

# Celery Beat's periodic schedule. A static dict is enough for this project —
# django-celery-beat exists for teams that need to edit schedules at runtime
# via the Django admin, without a deploy, which isn't a need here.
CELERY_BEAT_SCHEDULE = {
    "check-sla-breaches": {
        "task": "apps.tickets.tasks.check_sla_breaches",
        "schedule": 300.0,  # every 5 minutes
    },
    "send-weekly-digest": {
        "task": "apps.notifications.tasks.send_weekly_digest",
        "schedule": crontab(day_of_week="monday", hour=8, minute=0),
    },
}

# EMAIL_BACKEND is deprecated as of Django 6.1 in favor of MAILERS (a
# DATABASES/CACHES-style multi-backend config) — using it directly would
# already emit a RemovedInDjango70Warning.
MAILERS = {
    "default": {
        "BACKEND": env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"),
    },
}
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@deskhive.example.com")

SWAGGER_SETTINGS = {
    "SECURITY_DEFINITIONS": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT auth for logged-in users. Example: 'Bearer {access_token}'",
        },
        "Api-Key": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "API key auth for third-party integrations. Example: 'Api-Key {key}'",
        },
    },
    "USE_SESSION_AUTH": False,
}

SWAGGER_USE_COMPAT_RENDERERS = False

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "apps.accounts.authentication.APIKeyAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {"()": "config.logging_utils.RequestIDFilter"},
    },
    "formatters": {
        "json": {"()": "config.logging_utils.JSONFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["request_id"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
