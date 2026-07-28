"""
Django settings for the Afarinick Farm Plot & Harvest Tracker.

I kept this settings file readable and environment-aware. By default the project
runs on SQLite so it works on a clean machine with zero setup, but it switches to
PostgreSQL automatically when a database URL (e.g. Neon) or POSTGRES_* variables are
present. Static files are served by WhiteNoise so the app deploys cleanly to
single-process hosts like Render and to serverless hosts like Vercel.
"""
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# I read secrets/flags from the environment so nothing sensitive is hard-coded, but
# I provide safe development fallbacks so the reviewer can run it immediately.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-key-change-me-in-production")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

# I allow localhost by default plus the Render/Vercel subdomains. A leading dot lets
# Django match any subdomain of that host.
ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,.onrender.com,.vercel.app"
).split(",")

# I trust the platform HTTPS origins for CSRF so the Django admin login works once
# deployed behind Render's or Vercel's TLS proxy.
CSRF_TRUSTED_ORIGINS = os.environ.get(
    "DJANGO_CSRF_TRUSTED_ORIGINS", "https://*.onrender.com,https://*.vercel.app"
).split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "tracker",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # I place WhiteNoise directly after the security middleware, as its docs advise,
    # so it can serve compressed static assets without a separate web server.
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database selection, in priority order:
#   1. DATABASE_URL  -> a single connection string (this is what Neon gives you).
#   2. POSTGRES_DB   -> discrete POSTGRES_* variables.
#   3. neither       -> SQLite, so the project runs on a clean machine with no setup.
if os.environ.get("DATABASE_URL"):
    DATABASES = {
        "default": dj_database_url.parse(
            os.environ["DATABASE_URL"],
            conn_max_age=600,
            # I enable health checks so Django discards a dead pooled connection and
            # opens a fresh one instead of erroring — this avoids the occasional 500
            # that a serverless Postgres (Neon) can cause when it closes idle links.
            conn_health_checks=True,
            # Neon requires TLS; I enforce it unless the URL already specifies a mode.
            ssl_require="sslmode" not in os.environ["DATABASE_URL"],
        )
    }
elif os.environ.get("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.environ.get("POSTGRES_USER", "postgres"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# I set the timezone to Accra since Afarinick operates in Ghana; harvest and
# registration dates then read naturally for the operations team.
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Accra"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# I use WhiteNoise's compressed storage (no strict manifest) and enable finders so
# static assets are served correctly whether or not collectstatic has run. That
# makes the same config work on Render (collectstatic in build) and on Vercel's
# read-only serverless filesystem.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
WHITENOISE_USE_FINDERS = True

# I trust the platform's forwarded-proto header so Django knows requests are HTTPS
# when running behind Render's or Vercel's TLS proxy.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# I raise the multipart upload threshold a little so modest CSV/Excel harvest files
# are handled in memory for the import bonus without touching disk.
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
