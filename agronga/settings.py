"""AgroNGA settings.

Secure by default: with no environment variables set, Django starts in PRODUCTION mode and refuses to run
without a real SECRET_KEY. Everything environment-specific comes from environment variables / .env
(see .env.example and DEPLOY.md).

  Local development :  DJANGO_DEBUG=1
  Production        :  DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS, SITE_URL=https://..., BREVO_API_KEY, PAYSTACK_SECRET_KEY, ...
"""
import os
import sys
from decimal import Decimal
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

try:  # read secrets from .env (optional)
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
env = os.environ
TESTING = "test" in sys.argv


def flag(name, default=False):
    return env.get(name, "1" if default else "0").strip().lower() in ("1", "true", "yes", "on")


def csv(name, default=""):
    return [v.strip() for v in env.get(name, default).split(",") if v.strip()]


# ── Mode ──
DEBUG = flag("DJANGO_DEBUG")
PRODUCTION = not DEBUG and not TESTING

SECRET_KEY = env.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if PRODUCTION:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY is not set. For local development put DJANGO_DEBUG=1 in .env. For production generate a key with: "
            "python -c \"from django.core.management.utils import get_random_secret_key as k; print(k())\"")
    SECRET_KEY = "dev-only-insecure-key-never-use-in-production"

ALLOWED_HOSTS = csv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
if PRODUCTION and not env.get("DJANGO_ALLOWED_HOSTS"):
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS is not set (comma-separated, e.g. agronga.com,www.agronga.com).")

# ── Apps / middleware ──
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'corsheaders',
    "anymail",
    "tailwind",
    "django_htmx",
    "theme",
    "core",
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    *(['whitenoise.middleware.WhiteNoiseMiddleware'] if PRODUCTION else []),   # serves /static/ when DEBUG is off
    'django.contrib.sessions.middleware.SessionMiddleware',
    "django_htmx.middleware.HtmxMiddleware",
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'agronga.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "theme/templates/"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.site',
            ],
        },
    },
]

WSGI_APPLICATION = 'agronga.wsgi.application'

# ── Database: SQLite for local work, PostgreSQL in production (set DB_NAME) ──
if env.get("DB_NAME"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env["DB_NAME"], "USER": env.get("DB_USER", ""), "PASSWORD": env.get("DB_PASSWORD", ""),
            "HOST": env.get("DB_HOST", "localhost"), "PORT": env.get("DB_PORT", "5432"),
            "CONN_MAX_AGE": 60, "CONN_HEALTH_CHECKS": True,
        }
    }
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ── Static + media ──
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static/']
STATIC_ROOT = BASE_DIR / "staticfiles"             # `python manage.py collectstatic` writes here
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage" if PRODUCTION
                    else "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
WHITENOISE_MANIFEST_STRICT = False                 # a missing file degrades to its plain URL instead of a 500
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"                    # admin uploads: serve with nginx or object storage, not Django

TAILWIND_APP_NAME = "theme"

# ── Security ──
SITE_URL = env.get("SITE_URL", "http://127.0.0.1:8000").rstrip("/")            # Paystack return URL + CSRF origin
if PRODUCTION and not env.get("SITE_URL"):
    raise ImproperlyConfigured("SITE_URL is not set (e.g. https://agronga.com). Paystack sends customers back to it.")
CSRF_TRUSTED_ORIGINS = csv("CSRF_TRUSTED_ORIGINS") + ([SITE_URL] if SITE_URL.startswith("https://") else [])
CLIENT_IP_HEADER = env.get("CLIENT_IP_HEADER", "")                               # see core/net.py
TRUSTED_PROXY_HOPS = int(env.get("TRUSTED_PROXY_HOPS", "1"))
DATA_UPLOAD_MAX_MEMORY_SIZE = 1_000_000                                          # 1 MB: no form here needs more

if PRODUCTION:
    SECURE_SSL_REDIRECT = flag("SECURE_SSL_REDIRECT", True)
    if flag("BEHIND_PROXY", True):                                               # nginx / Cloudflare / load balancer
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = True                                                  # the forms carry the token; JS never reads the cookie
    SECURE_HSTS_SECONDS = int(env.get("HSTS_SECONDS", "2592000"))                # 30 days; raise to 31536000 once everything works
    SECURE_HSTS_INCLUDE_SUBDOMAINS = flag("HSTS_INCLUDE_SUBDOMAINS")
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    X_FRAME_OPTIONS = "DENY"

# ── Email (Brevo via django-anymail) ──
# Setup checklist (details in DEPLOY.md): create an API key in Brevo (SMTP & API > API Keys), add and AUTHENTICATE your domain
# (Senders, Domains > SPF + DKIM + DMARC), then put BREVO_API_KEY in .env. Verify it with: python manage.py send_test_email you@example.com
QUOTE_INBOX = env.get("QUOTE_INBOX", "agesxpat@gmail.com") #env.get("QUOTE_INBOX", "info@agronga.com")                              # where enquiries and new-order alerts go
#DEFAULT_FROM_EMAIL = env.get("DEFAULT_FROM_EMAIL", "AgroNGA <info@agronga.com>")      # must be on your authenticated Brevo domain
DEFAULT_FROM_EMAIL="agesxpat@gmail.com"
SERVER_EMAIL = env.get("SERVER_EMAIL", "errors@agronga.net")                           # Django error emails (needs ADMIN_EMAIL). Check this domain is yours.
BREVO_API_KEY = env.get("BREVO_API_KEY", "")
if PRODUCTION and not BREVO_API_KEY:
    raise ImproperlyConfigured("BREVO_API_KEY is not set: customers would never receive receipts.")
EMAIL_BACKEND = "anymail.backends.brevo.EmailBackend"
#EMAIL_BACKEND = "anymail.backends.brevo.EmailBackend" if BREVO_API_KEY else "django.core.mail.backends.console.EmailBackend"
CONFIRMATION_EMAILS_PER_HOUR = 2                   # automatic replies to any ONE address: stops the contact form being used to mail-bomb someone
ANYMAIL = {
    "BREVO_API_KEY": BREVO_API_KEY,
    "REQUESTS_TIMEOUT": (5, 10),                   # connect, read seconds: a slow Brevo must not stall a form or a webhook
    "SEND_DEFAULTS": {"tags": ["agronga"]},         # every message is tagged in Brevo's reports
    # Optional delivery tracking (bounces, spam complaints). In Brevo > Transactional > Settings > Webhook add
    #   https://USER:PASSWORD@agronga.com/anymail/brevo/tracking/     and set BREVO_WEBHOOK_SECRET=USER:PASSWORD
   # **({"WEBHOOK_SECRET": env["BREVO_WEBHOOK_SECRET"]} if env.get("BREVO_WEBHOOK_SECRET") else {}),
}

COMPANY = {
    "name": "AgroNGA Limited",
    "phone": "+234-808-250-1525",
    "phone_href": "+2348082501525",
    "email_user": "info", "email_domain": "agronga.com",   # assembled in the browser, never printed as a mailto:
    "address": "722 Road, A Close, House 9, Festac Town, Lagos, Nigeria",
    "hours": "Sunday to Friday, 8:00 am to 5:00 pm (WAT)",
    "short_location": "Festac Town, Lagos",
    "map_url": "https://maps.app.goo.gl/2GuLRNvriowA8HoTA",
}   # DEFAULTS only: Admin > Company profile overrides each value that is filled in

# TODO(owner): replace each URL with the COMPANY page, not a personal profile.
SOCIAL_LINKS = [
    {"key": "facebook", "label": "Facebook", "url": "https://www.facebook.com/agronga"},
    {"key": "instagram", "label": "Instagram", "url": "https://www.instagram.com/agronga"},
    {"key": "linkedin", "label": "LinkedIn", "url": "https://www.linkedin.com/company/agronga"},
    {"key": "twitter", "label": "X (Twitter)", "url": "https://twitter.com/agronga"},
]

# ── Cache: Redis in production (shared by all workers: rate limits, FX lock) ──
if env.get("REDIS_URL"):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": env["REDIS_URL"]}}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# ── Paystack (NGN + USD) ──
PAYSTACK_SECRET_KEY = env.get("PAYSTACK_SECRET_KEY", "").strip()
PAYSTACK_WEBHOOK_IPS = csv("PAYSTACK_WEBHOOK_IPS")      # optional extra layer: copy the IPs from Paystack's webhook docs
if PAYSTACK_SECRET_KEY.startswith("sk_live_") and DEBUG:
    raise ImproperlyConfigured("A live Paystack key with DJANGO_DEBUG=1 would expose it on error pages. Use an sk_test_ key locally.")

# ── Pricing: USD is the master price; naira follows the live exchange rate ──
NGN_MARGIN = Decimal("0.08")                       # 8%: covers payment fees and currency movement. Applied to goods AND shipping.
FX_FALLBACK_NGN_PER_USD = Decimal(env.get("FX_FALLBACK_NGN_PER_USD", "1500"))   # used only until the first live rate is saved. PLACEHOLDER.
FX_TTL_MINUTES = 60                                # refresh the live rate when older than this
FX_RETRY_MINUTES = 5                               # after a failed fetch, wait this long before trying again
FX_MAX_JUMP = Decimal("0.25")                      # ignore a feed that moves the rate more than 25% in one step (bad data)
FX_TIMEOUT = 2                                     # seconds per rate source while a visitor is waiting
FX_REQUEST_BUDGET = 3                              # total seconds a visitor may ever wait for a rate refresh
FX_AUTO_REFRESH = flag("FX_AUTO_REFRESH", True) and not TESTING                 # tests never touch the network

# ── Logging: stdout (systemd/Docker collect it); emails ADMINS on server errors when ADMIN_EMAIL is set ──
ADMINS = [("Site admin", env["ADMIN_EMAIL"])] if env.get("ADMIN_EMAIL") else []
LOGGING = {
    "version": 1, "disable_existing_loggers": False,
    "filters": {"prod_only": {"()": "django.utils.log.RequireDebugFalse"}},
    "formatters": {"std": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "std"},
        "mail_admins": {"class": "django.utils.log.AdminEmailHandler", "level": "ERROR", "filters": ["prod_only"]},
    },
    "root": {"handlers": ["console"], "level": env.get("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.request": {"handlers": ["console", *(["mail_admins"] if ADMINS else [])], "level": "ERROR", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

# ── Editable page content (About, Contact, FAQ, Testimonials) ──
CONTENT_CACHE_SECONDS = 0 if TESTING else int(env.get("CONTENT_CACHE_SECONDS", "600"))   # also cleared instantly on every save
