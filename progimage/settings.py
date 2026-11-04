"""
ProgImage settings.

Kept to a single file for simplicity. Secrets and environment-specific
values come from environment variables, so the same code runs anywhere.

FUTURE: If I had more time I would split this into settings/base.py, dev.py, test.py, prod.py to ensure that as the
environments diverges, I don't have a growing `if DEBUG:` branches here.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"

# Never hard-code a production secret. The fallback only exists so the
# project runs out of the box in local development.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key")

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")


INSTALLED_APPS = [
    "rest_framework",
    "images",
]

MIDDLEWARE = [
    # SecurityMiddleware adds `X-Content-Type-Options: nosniff` to every
    # response, so browsers won't try to reinterpret image bytes as HTML/JS.
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    # FUTURE: request-id middleware for log correlation.
]

ROOT_URLCONF = "progimage.urls"
WSGI_APPLICATION = "progimage.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"

# SQLite keeps local setup at zero. Image *bytes* never go in the database,
# only metadata, so swapping to Postgres later is a settings-only change.
# FUTURE: read DATABASES from env (Postgres in staging/production).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Storage abstraction: all file access goes through Django's storage API,
# so moving from local disk to S3/GCS is a configuration change (e.g. the
# django-storages S3 backend), not a code change.
MEDIA_ROOT = Path(os.environ.get("PROGIMAGE_MEDIA_ROOT", BASE_DIR / "media"))
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
}

# Uploads larger than this spill from memory to a temp file on disk,
# so a big upload doesn't sit entirely in RAM.
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024

# --- ProgImage limits -------------------------------------------------------
PROGIMAGE_MAX_UPLOAD_BYTES = int(os.environ.get("PROGIMAGE_MAX_UPLOAD_BYTES", 10 * 1024 * 1024))
# Guards against "decompression bombs": tiny files that declare enormous
# dimensions and would exhaust memory if decoded.
PROGIMAGE_MAX_PIXELS = int(os.environ.get("PROGIMAGE_MAX_PIXELS", 40_000_000))


# --- CONFIG for Django REST framework ---------------------------------------------------
REST_FRAMEWORK = {
    # JSON in, JSON out. The browsable HTML API is disabled: this is a
    # machine-to-machine service.
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.MultiPartParser"],
    # No authentication yet (this is a deliberate decision at this stage, will add soon). With no session
    # authentication, DRF doesn't enforce CSRF, which only applies to cookies.
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
}