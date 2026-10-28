"""Editable site content, read efficiently.

Every public read goes through `_cached()`: the first request after a change builds the value from the database
(1-2 queries) and stores plain, picklable data in the cache; every later request costs zero queries. Saving or deleting
any related record clears the cache immediately (core/signals.py), and CONTENT_CACHE_SECONDS is the safety net for
other worker processes when the cache is not shared (use Redis in production).

A page with no database row still renders using DEFAULTS below, so a fresh install is never blank.
"""
import json
from decimal import Decimal  # noqa: F401  (kept for template-friendly numbers if needed)

from django.conf import settings
from django.core.cache import cache
from django.templatetags.static import static

from . import pagedata

PAGE_SLUGS = ("about", "contact", "faq", "testimonials")
_KEYS = [f"page:{s}" for s in PAGE_SLUGS] + ["faqs", "testimonials", "company", "about_categories"]

DEFAULT_HEADER_IMAGE = "img/products/shea-nuts.jpg"
DEFAULT_SIDE_IMAGE = "img/products/shea-nuts-heap.jpg"

SAFETY = ("- Pay only using the details in our written confirmation.\n"
          "- We will never ask you to pay into a personal account.\n"
          "- We will never ask for your card number by email, phone or chat.\n"
          "- Unsure about a message? Call us on the number above before you pay.")

DEFAULTS = {
    "about": {
        "crumb": "About us", "title": "About AgroNGA",
        "intro": "A Lagos-based supplier of non-GMO agricultural products, raw and processed.",
        "body": ("AgroNGA Limited supplies non-GMO agricultural products, raw and processed, sourced from farms in Nigeria.\n\n"
                 "Our range covers cashew nuts, shea nuts and shea butter, sesame seeds, peanuts, and Kaju King roasted, glazed and "
                 "chocolate-coated cashew snacks. We sell to buyers in Nigeria and the United States, with prices in naira or US dollars.\n\n"
                 "For bulk and export volumes we quote each order, so you see price, availability and delivery before you pay."),
        "blocks": [],
    },
    "contact": {
        "crumb": "Contact", "title": "Contact us",
        "intro": "Ask a question, request a bulk quote or get help with an order.", "body": "",
        "blocks": [{"heading": "Staying safe when you pay", "body": SAFETY, "callout": True}],
    },
    "faq": {"crumb": "FAQ", "title": "Frequently asked questions", "intro": "Quick answers about our products, prices and ordering.", "body": "", "blocks": []},
    "testimonials": {"crumb": "Testimonials", "title": "What buyers say", "intro": "Words from customers who agreed to be quoted.", "body": "", "blocks": []},
}


# ───────── cache plumbing ─────────
def _cached(key, build):
    ttl = int(getattr(settings, "CONTENT_CACHE_SECONDS", 0))
    if ttl <= 0:
        return build()
    full = f"content:{key}"
    hit = cache.get(full)
    if hit is not None:
        return hit
    value = build()
    cache.set(full, value, ttl)
    return value


def invalidate():
    """Forget everything cached here. Called whenever editable content changes."""
    cache.delete_many([f"content:{k}" for k in _KEYS])


def _media_url(path):
    from django.core.files.storage import default_storage
    return default_storage.url(path)


# ───────── pages ─────────
def page(slug) -> pagedata.PageData:
    return _cached(f"page:{slug}", lambda: _build_page(slug))


def _build_page(slug):
    from .models import PageBlock, PageContent
    d = DEFAULTS[slug]
    row = PageContent.objects.filter(slug=slug).first()
    if row is None:
        header = pagedata.image_data(static(DEFAULT_HEADER_IMAGE), [], lambda p: p)
        side = pagedata.image_data(static(DEFAULT_SIDE_IMAGE), [], lambda p: p, alt="A heap of dried shea nuts") if slug == "about" else None
        blocks = d["blocks"]
        body = _legacy_story(slug) or d["body"]
        title, intro, eyebrow = d["title"], d["intro"], ""
    else:
        pos = row.header_position
        header = (pagedata.image_data(row.header_image.url if row.header_image else "", row.header_variants, _media_url, pos)
                  or pagedata.image_data(static(DEFAULT_HEADER_IMAGE), [], lambda p: p, pos))
        side = (pagedata.image_data(row.side_image.url if row.side_image else "", row.side_variants, _media_url, alt=row.side_alt)
                or (pagedata.image_data(static(DEFAULT_SIDE_IMAGE), [], lambda p: p, alt="A heap of dried shea nuts") if slug == "about" else None))
        blocks = list(PageBlock.objects.filter(page=row, is_active=True).values("heading", "body", "callout"))
        body = row.body or _legacy_story(slug) or d["body"]
        title, intro, eyebrow = row.title or d["title"], row.intro or d["intro"], row.eyebrow
    return pagedata.PageData(
        slug=slug, title=title, crumb=d["crumb"], intro=intro, eyebrow=eyebrow,
        paragraphs=pagedata.paragraphs(body), header=header, side=side,
        blocks=tuple(pagedata.BlockData(b["heading"], pagedata.block_items(b["body"]), bool(b["callout"])) for b in blocks))


def _legacy_story(slug):
    """Before pages were editable, the About text lived in Company profile > Story. Keep honouring it."""
    if slug != "about":
        return ""
    from .models import CompanyProfile
    p = CompanyProfile.objects.only("story").first()
    return p.story if p else ""


# ───────── company details (header, footer, contact page, call-to-actions) ─────────
def company() -> dict:
    return _cached("company", _build_company)


def _digits_href(number):
    digits = "".join(c for c in number if c.isdigit())
    return ("+" if number.strip().startswith("+") else "") + digits


def _build_company():
    from .models import CompanyProfile
    base = dict(settings.COMPANY)
    p = CompanyProfile.objects.first()
    numbers = [l.strip() for l in (p.phones if p else "").splitlines() if l.strip()]
    if not numbers:
        numbers = [base["phone"]] + ([base["phone2"]] if base.get("phone2") else [])
    phones = [{"display": n, "href": _digits_href(n)} for n in numbers]
    user, domain = base["email_user"], base["email_domain"]
    if p and "@" in p.email:
        user, domain = p.email.split("@", 1)
    return {
        "name": base["name"], "phone": phones[0]["display"], "phone_href": phones[0]["href"], "phones": phones,
        "email_user": user, "email_domain": domain,
        "address": (p.address if p and p.address else base["address"]),
        "hours": (p.opening_hours if p and p.opening_hours else base["hours"]),
        "map_url": (p.map_url if p and p.map_url else base.get("map_url", "")),
        "short_location": (p.short_location if p and p.short_location else base.get("short_location", "")),
        "rc_number": p.rc_number if p else "", "founded_year": p.founded_year if p else None,
        "certification_list": p.certification_list if p else [],
    }


# ───────── FAQ, testimonials, product categories ─────────
def faq_page():
    """(list of {question, answer}, JSON-LD string). One query, then cached."""
    return _cached("faqs", _build_faqs)


def _build_faqs():
    from .models import FAQ
    items = list(FAQ.objects.filter(is_published=True).values("question", "answer"))
    if not items:
        return items, ""
    ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": f["question"], "acceptedAnswer": {"@type": "Answer", "text": f["answer"]}} for f in items]}
    return items, json.dumps(ld).replace("<", "\\u003c")


def testimonials():
    """Published testimonials that have recorded consent, as [{name, role, quote}]."""
    return _cached("testimonials", _build_testimonials)


def _build_testimonials():
    from .models import Testimonial
    return list(Testimonial.objects.filter(is_published=True, consent_given=True).values("name", "role", "quote"))


def about_categories():
    """[{name, slug, product_names}] for the About page: two queries, then cached."""
    return _cached("about_categories", _build_categories)


def _build_categories():
    from .models import Category, Product
    cats = list(Category.objects.values("id", "name", "slug"))
    names = {}
    for cid, name in Product.objects.filter(is_active=True).order_by("sort_order", "id").values_list("category_id", "name"):
        names.setdefault(cid, []).append(name)
    return [{"name": c["name"], "slug": c["slug"], "product_names": names[c["id"]]} for c in cats if c["id"] in names]
