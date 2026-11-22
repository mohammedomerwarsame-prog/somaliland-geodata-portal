"""
Settings for the Somaliland GeoData Portal.

All secrets and environment-specific values come from environment variables
(see .env.example). Defaults are safe for local development only.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return str(os.environ.get(name, default)).lower() in ("1", "true", "yes", "on")


# Load a local .env file if present (simple KEY=VALUE lines, no extra dependency)
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in env("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

if DEBUG:
    # Development only: GitHub Codespaces forwards requests through an HTTPS
    # proxy, so the browser's Origin can be https://localhost:8000 or the
    # *.app.github.dev address. Trust those so forms (login, register, upload) work.
    ALLOWED_HOSTS += [".app.github.dev", "localhost", "127.0.0.1"]
    CSRF_TRUSTED_ORIGINS += [
        "https://localhost:8000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://*.app.github.dev",
    ]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Portal apps
    "accounts",
    "organizations",
    "datasets",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
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
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "datasets.context_processors.portal",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database: SQLite for development; set DATABASE_ENGINE=postgresql in production.
if env("DATABASE_ENGINE", "sqlite") == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DATABASE_NAME", "geoportal"),
            "USER": env("DATABASE_USER", "geoportal"),
            "PASSWORD": env("DATABASE_PASSWORD", ""),
            "HOST": env("DATABASE_HOST", "localhost"),
            "PORT": env("DATABASE_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "datasets:home"
LOGOUT_REDIRECT_URL = "datasets:home"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("so", "Soomaali")]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Africa/Nairobi"  # EAT, UTC+3
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Public media (thumbnails, organization logos)
MEDIA_URL = "media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", BASE_DIR / "media"))

# Dataset files are kept OUTSIDE the public media folder. They are only
# served through the download view, which checks status and access level.
PRIVATE_MEDIA_ROOT = Path(env("PRIVATE_MEDIA_ROOT", BASE_DIR / "private_media"))

# Upload limits
MAX_UPLOAD_MB = int(env("MAX_UPLOAD_MB", 2048))
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
MAX_MAP_PREVIEW_MB = 15  # GeoJSON larger than this is not drawn in the browser

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

PORTAL_NAME = env("PORTAL_NAME", "Somaliland GeoData Portal")
PORTAL_TAGLINE = env("PORTAL_TAGLINE", "Explore • Access • Share Geospatial Data")

# The organization that runs the portal. Only its staff (accounts created by an
# administrator) can upload. Everyone else downloads, and sends data to the team
# through the channels below.
PORTAL_ORGANIZATION = env("PORTAL_ORGANIZATION", "Somaliland GeoData Portal Team")
CONTRIBUTE_TELEGRAM_URL = env("CONTRIBUTE_TELEGRAM_URL", "https://t.me/your_telegram_username")
CONTRIBUTE_TELEGRAM_HANDLE = env("CONTRIBUTE_TELEGRAM_HANDLE", "@your_telegram_username")
CONTRIBUTE_EMAIL = env("CONTRIBUTE_EMAIL", "data@example.org")
CONTRIBUTE_PHONE = env("CONTRIBUTE_PHONE", "")

# Production hardening (active when DEBUG is off)
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
