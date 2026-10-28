"""All outgoing email: branded HTML with a plain-text alternative, sent through Brevo (django-anymail).

Rules this module enforces:
  * every message has an HTML part AND a plain-text part (spam filters and accessibility);
  * subjects are one line (header injection is impossible);
  * the shop-owner copy of an enquiry MUST be delivered, so failures raise;
  * the visitor's confirmation is best-effort and limited per address, so the form cannot be used to mail-bomb someone.
"""
import hashlib
import logging

from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from . import content

log = logging.getLogger(__name__)


def one_line(text, limit=120) -> str:
    """Collapse whitespace and newlines: user text is never allowed to break a header."""
    return " ".join(str(text or "").split())[:limit]


def send(template, subject, to, ctx=None, reply_to=None, tags=(), metadata=None):
    """Render emails/<template>.html and .txt and send them as one multipart message. Raises on failure."""
    context = {"company": content.company(), "site_url": settings.SITE_URL, "subject": one_line(subject, 200), **(ctx or {})}
    message = EmailMultiAlternatives(
        subject=context["subject"],
        body=render_to_string(f"emails/{template}.txt", context),
        from_email=settings.DEFAULT_FROM_EMAIL, to=list(to), reply_to=list(reply_to or []))
    message.attach_alternative(render_to_string(f"emails/{template}.html", context), "text/html")
    message.tags = list(tags)                       # Brevo tags (ignored by other backends)
    message.metadata = dict(metadata or {})
    message.send(fail_silently=False)


def _confirmation_allowed(email) -> bool:
    """At most CONFIRMATION_EMAILS_PER_HOUR automatic replies to any one address."""
    limit = int(getattr(settings, "CONFIRMATION_EMAILS_PER_HOUR", 2))
    key = "mailconf:" + hashlib.sha1(email.strip().lower().encode()).hexdigest()
    cache.add(key, 0, 3600)
    try:
        return cache.incr(key) <= limit
    except ValueError:
        cache.set(key, 1, 3600)
        return True


def send_enquiry(kind, cd, label, extra_rows=()):
    """kind is 'contact' or 'quote'. Sends the owner a message (Reply-To = visitor) and the visitor a confirmation copy.
    Raises only if the OWNER email fails: the visitor must never be told 'sent' when nobody received it."""
    name = one_line(cd["name"], 80)
    ctx = {"name": name, "first_name": name.split(" ")[0] if name else "", "email": cd["email"], "label": label,
           "message": cd.get("message", "") or "", "rows": [(k, v) for k, v in extra_rows if v], "kind": kind}
    subject_owner = f"{'Website enquiry' if kind == 'contact' else 'Quote request'}: {label} ({name})"
    send(f"{kind}_owner", subject_owner, [settings.QUOTE_INBOX], ctx, reply_to=[cd["email"]], tags=[kind, "owner"])
    if not _confirmation_allowed(cd["email"]):
        log.info("Confirmation to %s skipped (hourly limit)", cd["email"])
        return False
    try:
        send(f"{kind}_sender", "We have received your message" if kind == "contact" else "We have received your quote request",
             [cd["email"]], ctx, reply_to=[settings.QUOTE_INBOX], tags=[kind, "confirmation"])
    except Exception:                               # noqa: BLE001  (a bad address must not fail the whole form)
        log.exception("Could not send the confirmation to %s", cd["email"])
        return False
    return True
