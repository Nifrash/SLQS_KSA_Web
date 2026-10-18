import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean from environment variables."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_csv(name: str, default: str = "") -> list[str]:
    """Read a comma-separated environment setting as a list."""
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


# -----------------------------------------------------------------------------
# Core settings
# -----------------------------------------------------------------------------
DEBUG = env_bool("DJANGO_DEBUG", True)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "").strip()
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY in .env for production.")
    # Development-only fallback. Set a unique value in your local .env as well.
    SECRET_KEY = "django-insecure-SLQS-LOCAL-DEVELOPMENT-ONLY-change-before-deploying"

ALLOWED_HOSTS = env_csv(
    "DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost" if DEBUG else ""
)
if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured("Set DJANGO_ALLOWED_HOSTS in .env for production.")

CSRF_TRUSTED_ORIGINS = env_csv("DJANGO_CSRF_TRUSTED_ORIGINS")


# -----------------------------------------------------------------------------
# Applications
# -----------------------------------------------------------------------------
INSTALLED_APPS = [
    "home",
    "core",
    "cms_pages",
    "newsroom",
    "events",
    "membership",
    "member_accounts",
    "legacy_members.apps.LegacyMembersConfig",
    "membership_team.apps.MembershipTeamConfig",
    "digital_cards.apps.DigitalCardsConfig",
    "wagtail.contrib.settings",
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.embeds",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    "modelcluster",
    "taggit",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
]

# Python package from YOUR uploaded project: SLQS_KSA_Web.
# Keep ROOT_URLCONF, WSGI_APPLICATION, ASGI_APPLICATION, manage.py,
# wsgi.py and asgi.py consistent with this exact package name.
ROOT_URLCONF = "SLQS_KSA_Web.urls"
WSGI_APPLICATION = "SLQS_KSA_Web.wsgi.application"
ASGI_APPLICATION = "SLQS_KSA_Web.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site_details",
                "cms_pages.context_processors.global_content",
            ]
        },
    }
]


# -----------------------------------------------------------------------------
# Database: SQLite for development; optional PostgreSQL for production
# -----------------------------------------------------------------------------
DB_ENGINE = os.getenv("DB_ENGINE", "sqlite").strip().lower()

if DB_ENGINE == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
elif DB_ENGINE in {"postgres", "postgresql"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "slqs_ksa"),
            "USER": os.getenv("DB_USER", ""),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    raise ImproperlyConfigured("DB_ENGINE must be 'sqlite' or 'postgresql'.")


# -----------------------------------------------------------------------------
# Authentication and localization
# -----------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
TIME_ZONE = "Asia/Riyadh"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# -----------------------------------------------------------------------------
# Static files and uploaded media
# -----------------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# The manifest storage requires a prebuilt staticfiles.json from collectstatic.
# Development and test runs should not depend on that production artifact.
# Django's test runner sets settings.DEBUG=False while tests execute, so
# explicitly recognize the `manage.py test` command as well as local DEBUG.
RUNNING_TESTS = "test" in sys.argv[1:]

STORAGES = {
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG or RUNNING_TESTS
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
}


# -----------------------------------------------------------------------------
# Wagtail CMS
# -----------------------------------------------------------------------------
WAGTAIL_SITE_NAME = "SLQS | Sri Lankan Quantity Surveyors Saudi Arabia"
WAGTAILADMIN_BASE_URL = os.getenv(
    "SITE_BASE_URL", "http://127.0.0.1:8000"
).rstrip("/")
WAGTAILIMAGES_EXTENSIONS = ["gif", "jpg", "jpeg", "png", "webp"]


# -----------------------------------------------------------------------------
# Email / contact enquiries
# -----------------------------------------------------------------------------
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL", "SLQS Website <noreply@example.invalid>"
)
CONTACT_INBOX_EMAIL = os.getenv("CONTACT_INBOX_EMAIL", "").strip()
# Optional organizer notifications for Phase 4 event registrations.
EVENTS_ADMIN_EMAIL = os.getenv("EVENTS_ADMIN_EMAIL", "").strip()
MEMBERSHIP_ADMIN_EMAIL = os.getenv("MEMBERSHIP_ADMIN_EMAIL", "").strip()


# -----------------------------------------------------------------------------
# Security / production (HTTPS required for production)
# -----------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
        "SECURE_HSTS_INCLUDE_SUBDOMAINS", False
    )
    SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)

    # Enable only when a trusted reverse proxy sets/overwrites X-Forwarded-Proto.
    if env_bool("DJANGO_TRUST_PROXY_SSL_HEADER", False):
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Phase 7 — member authentication (not Wagtail/System Admin accounts).
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/accounts/dashboard/"
LOGOUT_REDIRECT_URL = "/accounts/login/"
# When using multiple workers in production, configure a shared Redis cache
# for the application throttling keys; LocMemCache is process-local.
