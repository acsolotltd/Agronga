from django.conf import settings
from django.urls import reverse_lazy

from . import content
from .currency import COOKIE, CURRENCIES, NGN, USD

NAV_LINKS = [
    {"label": "Products", "href": reverse_lazy("core:products")},
    {"label": "About us", "href": reverse_lazy("core:about")},
    {"label": "FAQ", "href": reverse_lazy("core:faq")},
    {"label": "Testimonials", "href": reverse_lazy("core:testimonials")},
    {"label": "Contact", "href": reverse_lazy("core:contact")},
]  # keep in sync with the header and footer components


def _default_currency(request):
    """Cloudflare/most CDNs pass the visitor country; fall back to language, then naira."""
    country = request.META.get("HTTP_CF_IPCOUNTRY", "").upper()
    if country:
        return NGN if country == "NG" else USD
    if "-NG" in request.META.get("HTTP_ACCEPT_LANGUAGE", "").upper():
        return NGN
    return NGN  # home market


def current_currency(request):
    """Cookie first, then country/language default. Use this everywhere, never re-derive it."""
    return CURRENCIES.get(request.COOKIES.get(COOKIE, "")) or _default_currency(request)


def site(request):
    return {
        "currency": current_currency(request),
        "currencies": CURRENCIES.values(),
        "nav_links": [{"label": l["label"], "href": str(l["href"]), "active": request.path.startswith(str(l["href"]))} for l in NAV_LINKS],
        "social_links": getattr(settings, "SOCIAL_LINKS", []),
        "company": content.company(),
    }
