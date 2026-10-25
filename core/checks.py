"""Deploy-time safety checks. They run with `python manage.py check` (warnings) and `check --deploy`."""
from django.conf import settings
from django.core.checks import Error, Warning, register


@register()
def payment_and_production_checks(app_configs, **kwargs):
    found = []
    key = settings.PAYSTACK_SECRET_KEY
    if key.startswith("sk_live_") and settings.DEBUG:
        found.append(Error("A LIVE Paystack key is set while DEBUG is on.",
                           hint="DEBUG pages expose settings and tracebacks. Use an sk_test_ key locally.", id="core.E001"))
    if not settings.PRODUCTION:
        return found
    if not key:
        found.append(Warning("PAYSTACK_SECRET_KEY is empty, so online payment is disabled.", id="core.W001"))
    elif key.startswith("sk_test_"):
        found.append(Warning("Production is using a Paystack TEST key: real customers cannot pay.",
                             hint="Switch to the sk_live_ key when you go live.", id="core.W002"))
    if not settings.SITE_URL.startswith("https://"):
        found.append(Warning("SITE_URL is not https, so Paystack's return URL is insecure.", hint="Set SITE_URL=https://your-domain", id="core.W003"))
    if "locmem" in settings.CACHES["default"]["BACKEND"]:
        found.append(Warning("The cache is per-process (LocMem). With several workers, rate limits and the FX lock do not work.",
                             hint="Set REDIS_URL.", id="core.W004"))
    if not settings.CLIENT_IP_HEADER:
        found.append(Warning("CLIENT_IP_HEADER is not set. Behind a proxy every visitor looks like one IP, so rate limits hit everyone at once.",
                             hint="CLIENT_IP_HEADER=CF-Connecting-IP (Cloudflare) or X-Forwarded-For (nginx).", id="core.W005"))
    if "sqlite" in settings.DATABASES["default"]["ENGINE"]:
        found.append(Warning("SQLite is not suitable for concurrent payments (no row locking).", hint="Use PostgreSQL (set DB_NAME etc).", id="core.W006"))
    if "console" in settings.EMAIL_BACKEND or "locmem" in settings.EMAIL_BACKEND:
        found.append(Warning("Emails are not being sent (console backend). Customers will not get receipts.", id="core.W007"))
    if not settings.PAYSTACK_WEBHOOK_IPS:
        found.append(Warning("PAYSTACK_WEBHOOK_IPS is empty. Signatures still protect the webhook; an IP allowlist adds a second layer.", id="core.W008"))
    return found
