import hashlib
import json
import time
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.db import IntegrityError
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.vary import vary_on_cookie, vary_on_headers

import logging

from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

from . import content, fx, orders, paystack
from . import quote as quote_mod
from .countries import COUNTRY_NAMES
from .context_processors import current_currency
from .currency import COOKIE, CURRENCIES
from .forms import ContactForm, OrderForm, QuoteForm
from .models import FAQ, Category, CompanyProfile, Order, PaymentEvent, Product, ShippingZone, Testimonial
from .net import client_ip

logger = logging.getLogger(__name__)

STEPS = [
    {"title": "Pick your currency", "text": "Choose naira or US dollars. Every price on the site follows your choice."},
    {"title": "Add to cart or request a quote", "text": "Order standard packs and tonnes from the shop, or send a quote request for larger volumes."},
    {"title": "We confirm, then you pay", "text": "We email price, stock and delivery for you to approve before any payment."},
]


# Hero slides. `slug` must match a product; copy lives here so it is easy to edit.
HERO_SLIDES = [
    {"slug": "white-chocolate-coated-cashew-nuts", "label": "White chocolate", "tint": "#7a5a46",
     "kicker": "Kaju King cashew snacks", "title": "Crunchy cashew, dressed in white chocolate.",
     "lead": "Whole roasted cashews in a smooth white chocolate coat, packed in a resealable pouch."},
    {"slug": "honey-glazed-cashew-nuts", "label": "Honey glazed", "tint": "#d9822b",
     "kicker": "Kaju King cashew snacks", "title": "Honey glazed, roasted to a golden crunch.",
     "lead": "A light honey glaze over whole cashews. Sweet, buttery and easy to share."},
    {"slug": "shea-butter", "label": "Shea butter", "tint": "#b49c4b",
     "kicker": "Natural shea", "title": "Shea butter from Nigerian farms.",
     "lead": "Rich natural shea butter for skin, hair and the kitchen. Also sold as shea nuts for processors."},
    {"slug": "sesame-seeds", "label": "Bulk by the tonne", "tint": "#9a7440",
     "kicker": "For bulk buyers", "title": "Sesame, peanuts and shea nuts by the tonne.",
     "lead": "Order in naira or dollars. We confirm freight and the final price by email before you pay."},
]
# Kaju King flavour panels (slugs)
FLAVOURS = ["white-chocolate-coated-cashew-nuts", "honey-glazed-cashew-nuts", "roasted-unsalted-cashew-nuts", "cashew-nuts"]


def published():
    return Product.objects.filter(is_active=True).select_related("category")


def _featured():
    return list(published().filter(is_featured=True)[:8])


# ───────── Landing ─────────
def _home_ctx(request):
    fx.ensure_fresh()
    products = _featured()
    by_slug = {p.slug: p for p in products}
    return {
        "hero_products": products[:4],
        "products": products,
        "categories": list(Category.objects.filter(products__is_active=True).distinct()),
        "slides": [{**h, "product": by_slug[h["slug"]]} for h in HERO_SLIDES if h["slug"] in by_slug],
        "flavours": [by_slug[s] for s in FLAVOURS if s in by_slug],
        "bulk_products": [p for p in products if p.is_bulk],
        "testimonials": content.testimonials()[:3],
        "form": QuoteForm(initial={"product": request.GET.get("product", "")}),
        "steps": STEPS,
    }


@vary_on_cookie
def home(request):
    return render(request, "landing/home.html", _home_ctx(request))


# ───────── Catalogue ─────────
@vary_on_headers("HX-Request", "HX-Boosted", "HX-History-Restore-Request", "Cookie")
def product_list(request):
    fx.ensure_fresh()
    categories = list(Category.objects.all())
    active = next((c for c in categories if c.slug == request.GET.get("category")), None)
    products = list(published())
    # All products are rendered; the chips filter in the browser. With ?category= the rest start hidden.
    for p in products:
        p.hidden = bool(active) and p.category_id != active.id
    ctx = {"products": products, "categories": categories, "active_category": active,
           "shown": sum(1 for p in products if not p.hidden)}

    # Fragment only for in-page htmx requests (filter chips, currency refresh).
    # Boosted navigation and history restores need the full document.
    h = request.htmx
    if h and not h.boosted and not h.history_restore_request:
        return render(request, "products/partials/catalog.html", ctx)
    return render(request, "products/list.html", ctx)


@vary_on_cookie
def product_detail(request, slug):
    fx.ensure_fresh()
    product = get_object_or_404(published(), slug=slug)
    related = list(published().exclude(pk=product.pk).order_by("sort_order")[:4])
    code = current_currency(request).code
    amount = product.price_for(code)

    ld = {"@context": "https://schema.org", "@type": "Product", "name": product.name,
          "description": product.blurb, "category": product.category.name,
          "brand": {"@type": "Organization", "name": "AgroNGA Limited"}}
    if product.image:
        ld["image"] = request.build_absolute_uri(product.image_url)
    elif product.image_url:
        ld["image"] = request.build_absolute_uri(product.image_url)
    if amount is not None and not product.quote_only:
        ld["offers"] = {"@type": "Offer", "priceCurrency": code, "price": str(amount)}
    return render(request, "products/detail.html", {
        "product": product, "related": related,
        "jsonld": json.dumps(ld).replace("<", "\\u003c"),  # safe inside <script>
    })


# ───────── Currency ─────────
@require_POST
def set_currency(request):
    code = request.POST.get("currency", "").upper()
    cur = CURRENCIES.get(code)
    if not cur:
        return HttpResponseBadRequest("Unsupported currency")

    if request.htmx:
        resp = HttpResponse(status=204)
        resp["HX-Trigger"] = json.dumps({"currency:changed": {"code": cur.code, "name": cur.name}})
    else:  # no-JS fallback
        nxt = request.POST.get("next", "/")
        if not url_has_allowed_host_and_scheme(nxt, {request.get_host()}, request.is_secure()):
            nxt = "/"
        resp = redirect(nxt)
    resp.set_cookie(COOKIE, cur.code, max_age=60 * 60 * 24 * 365, samesite="Lax",
                    secure=request.is_secure(), httponly=True)
    return resp


# ───────── Forms (quote + contact share one spam-protected pipeline) ─────────
def _rate_limited(request, scope, limit=5, window=3600):
    key = f"{scope}:{client_ip(request)}"
    cache.add(key, 0, window)
    try:
        return cache.incr(key) > limit
    except ValueError:
        cache.set(key, 1, window)
        return False


def _handle_submission(request, form_class, scope, send):
    """Honeypot -> rate limit -> validation (incl. time trap) -> send. Returns (context, status)."""
    if request.POST.get("website"):  # bots fill it: pretend success, send nothing, reveal nothing
        return {"sent": True}, 200
    form = form_class(request.POST)
    if _rate_limited(request, scope):
        form.add_error(None, "Too many requests from your network. Please try again later.")
    elif form.is_valid():
        send(request, form)
        return {"sent": True, "sent_name": form.cleaned_data["name"]}, 200
    return {"form": form}, 422


def _send_quote(request, form):
    cd = form.cleaned_data
    label = dict(form.fields["product"].choices)[cd["product"]]
    body = (f"Name: {cd['name']}\nEmail: {cd['email']}\nCountry: {cd['country']}\n"
            f"Currency shown: {request.COOKIES.get(COOKIE, 'default')}\n"
            f"Product: {label}\nQuantity: {cd['quantity'] or '-'}\n\n{cd['message']}")
    EmailMessage(
        subject=f"Quote request: {label}",            # built from a fixed choice, never user text
        body=body, from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.QUOTE_INBOX], reply_to=[cd["email"]],
    ).send(fail_silently=False)


def _send_contact(request, form):
    cd = form.cleaned_data
    label = dict(form.fields["topic"].choices)[cd["topic"]]
    EmailMessage(
        subject=f"Website enquiry: {label}",
        body=f"Name: {cd['name']}\nEmail: {cd['email']}\nTopic: {label}\n\n{cd['message']}",
        from_email=settings.DEFAULT_FROM_EMAIL, to=[settings.QUOTE_INBOX], reply_to=[cd["email"]],
    ).send(fail_silently=False)


@require_http_methods(["GET", "POST"])
def quote(request):
    if request.method == "GET":
        return redirect("core:home")
    ctx, status = _handle_submission(request, QuoteForm, "quote", _send_quote)
    if request.htmx:
        return render(request, "landing/partials/quote_form.html", ctx, status=status)
    # No-JS fallback: full page, so the visitor is never left on a bare fragment
    return render(request, "landing/home.html", {**_home_ctx(request), **ctx}, status=status)


@require_http_methods(["GET", "POST"])
def contact(request):
    if request.method == "GET":
        form = ContactForm(initial={"topic": request.GET.get("topic", "general")})
        return render(request, "pages/contact.html", {"form": form, "page": content.page("contact")})
    ctx, status = _handle_submission(request, ContactForm, "contact", _send_contact)
    if request.htmx:
        return render(request, "pages/partials/contact_form.html", ctx, status=status)
    return render(request, "pages/contact.html", {"form": ContactForm(), "page": content.page("contact"), **ctx}, status=status)


# ───────── Cart and order request ─────────
# The cart lives in the browser (localStorage). The server never trusts prices from it:
# an order request carries only slugs and quantities, and totals are recomputed here.
def _parse_cart(raw):
    try:
        items = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(items, list) or not 0 < len(items) <= 50:
        return None
    wanted = {}
    for it in items:
        try:
            slug, qty = str(it["slug"]), int(it["qty"])
        except (KeyError, TypeError, ValueError):
            return None
        if not 1 <= qty <= 9999:
            return None
        wanted[slug] = wanted.get(slug, 0) + qty
    products = {p.slug: p for p in published().filter(slug__in=wanted)}
    if len(products) != len(wanted):
        return None
    return [(products[s], q) for s, q in wanted.items()]


def _default_country(cur):
    return "NG" if cur.code == "NGN" else "US"


@never_cache
def cart(request):
    fx.ensure_fresh()
    cur = current_currency(request)
    return render(request, "pages/cart.html", {
        "form": OrderForm(initial={"country": _default_country(cur)}),
        "paystack_enabled": bool(settings.PAYSTACK_SECRET_KEY),
    })


def _fail(msg, status=422, field="__all__", **extra):
    return JsonResponse({"ok": False, "errors": {field: [msg]}, **extra}, status=status)


def _price_cart(request, lines, country):
    """Price a parsed cart for the visitor's currency and country. One place, used by the preview AND the real order.
    Returns (Quote, Currency). Raises ValueError if an item has no USD price."""
    cur = current_currency(request)
    rate = fx.ensure_fresh()
    if country not in COUNTRY_NAMES:
        country = "OT"
    q = quote_mod.build(lines, cur.code, country, ShippingZone.for_country(country), eff=fx.effective(rate),
                        raw=rate.ngn_per_usd, source=rate.source, at=rate.fetched_at, margin=fx.margin())
    return q, cur


@never_cache
@require_POST
def cart_quote(request):
    """Live checkout totals. Called by the cart page whenever the cart, currency or destination country changes."""
    if _rate_limited(request, "cartquote", limit=120, window=60):
        return _fail("Too many requests. Please wait a moment.", 429)
    lines = _parse_cart(request.POST.get("cart"))
    if lines is None:
        return _fail("Your cart could not be read. Reload the page.")
    try:
        q, _ = _price_cart(request, lines, request.POST.get("country", "NG"))
    except ValueError:
        return _fail("Some items have no price. Please contact us.")
    return JsonResponse({"ok": True, **quote_mod.to_dict(q)})


@never_cache
@require_POST
def order(request):
    """JSON endpoint for the cart page. pay=paystack -> create order + Paystack transaction; pay=request -> email an invoice request."""
    if request.POST.get("website"):  # honeypot
        return JsonResponse({"ok": True, "ref": "AG-0000000000"})
    if _rate_limited(request, "order", limit=10):
        return _fail("Too many requests from your network. Please try again later.", 429)
    form = OrderForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": {k: [str(e) for e in v] for k, v in form.errors.items()}}, status=422)

    lines = _parse_cart(form.cleaned_data["cart"])
    if lines is None:
        return _fail("Some items in your cart are no longer available. Reload the page and check your cart.")
    try:
        q, cur = _price_cart(request, lines, form.cleaned_data["country"])
    except ValueError:
        return _fail("Some items in your cart have no price. Please contact us.")

    # The buyer must pay the total they were shown. If the exchange rate moved since, show the new total and let them confirm.
    try:
        seen = Decimal(form.cleaned_data.get("expected_total") or q.total)
    except InvalidOperation:
        seen = q.total
    if seen != q.total:
        return _fail("The exchange rate has just been updated, so your total changed. Please check it and press Pay again.",
                     status=409, quote=quote_mod.to_dict(q))

    pay = request.POST.get("pay", "paystack")
    if pay == "request":
        o = orders.create_order(q, form.cleaned_data, status=Order.REQUESTED)
        orders.notify_invoice_request(o)
        return JsonResponse({"ok": True, "ref": o.reference, "redirect": reverse("core:order_status", args=[o.reference])})

    if not settings.PAYSTACK_SECRET_KEY:
        return _fail("Online payment is not switched on yet. Please send an order request instead.", 503)

    # A double-click, a retry or a flaky connection must never create two orders or two charges.
    idem = (request.POST.get("idem") or "")[:64] or None
    if idem:
        prior = Order.objects.filter(idempotency_key=idem).first()
        if prior is not None:
            if prior.status == Order.PENDING and prior.authorization_url and prior.total == q.total and prior.currency == q.currency:
                return JsonResponse({"ok": True, "ref": prior.reference, "redirect": prior.authorization_url, "reused": True})
            idem = None                      # that attempt is finished or different: this is a genuinely new order
    try:
        o = orders.create_order(q, form.cleaned_data, idempotency_key=idem)
    except IntegrityError:                   # two identical requests raced and the other one won
        prior = Order.objects.filter(idempotency_key=idem).first()
        if prior is not None and prior.authorization_url:
            return JsonResponse({"ok": True, "ref": prior.reference, "redirect": prior.authorization_url, "reused": True})
        return _fail("Your payment is already being set up. Please wait a moment and press Pay again.", 409)
    if cur.code == "NGN":
        fx.reprice_products()          # naira catalogue prices in the database follow the rate this buyer paid at
    try:
        init = paystack.initialize(
            settings.PAYSTACK_SECRET_KEY, email=o.email, amount=o.total, currency=o.currency, reference=o.reference,
            callback_url=settings.SITE_URL + reverse("core:order_status", args=[o.reference]),
            metadata={"order": o.reference, "customer": o.name, "phone": o.phone, "country": o.country,
                      "subtotal": str(o.subtotal), "shipping": str(o.shipping_fee),
                      "fx_rate": str(o.fx_rate) if o.fx_rate else "",
                      "custom_fields": [{"display_name": "Order", "variable_name": "order", "value": o.reference}]},
        )
    except paystack.PaystackError:
        logger.exception("Paystack initialize failed for %s", o.reference)
        o.status = Order.FAILED
        o.gateway_response = "Could not start payment"
        o.save(update_fields=["status", "gateway_response"])
        return _fail("We could not reach the payment service. Please try again, or send an order request instead.", 502)
    o.paystack_access_code = init.get("access_code", "")
    o.authorization_url = init["authorization_url"]
    o.save(update_fields=["paystack_access_code", "authorization_url"])
    return JsonResponse({"ok": True, "ref": o.reference, "redirect": init["authorization_url"]})


@never_cache
def order_status(request, reference):
    """Where Paystack sends the customer back. Verifies with Paystack, then shows the result.
    The webhook is the source of truth, so a 'pending' page simply waits and refreshes."""
    if _rate_limited(request, "orderstatus", limit=60, window=60):
        return HttpResponse("Too many requests. Please wait a moment.", status=429)
    o = get_object_or_404(Order, reference=reference)
    if o.status == Order.PENDING and settings.PAYSTACK_SECRET_KEY and request.GET.get("reference") == o.reference:
        try:
            orders.settle(o.reference, paystack.verify(settings.PAYSTACK_SECRET_KEY, o.reference))
            o.refresh_from_db()
        except paystack.PaystackError:
            logger.exception("Paystack verify failed for %s", o.reference)
    return render(request, "pages/order_status.html", {"order": o, "items": o.items.all()})


def _event_reference(data):
    """Paystack puts the transaction reference in different places depending on the event type."""
    ref = data.get("reference") or data.get("transaction_reference") or (data.get("transaction") or {}).get("reference") or ""
    return str(ref)[:60]


@csrf_exempt
@require_POST
def paystack_webhook(request):
    """Paystack -> us. Set this URL in Paystack Dashboard > Settings > API Keys & Webhooks.

    Order of checks: (optional) source IP, signature, JSON, then a hash of the signed body so a retried delivery is
    recognised. Any exception here returns 500 on purpose: Paystack retries, and settle() is idempotent."""
    allow = settings.PAYSTACK_WEBHOOK_IPS
    if allow and client_ip(request) not in allow:
        return HttpResponse(status=403)
    raw = request.body
    if not paystack.verify_signature(raw, request.headers.get("x-paystack-signature", ""), settings.PAYSTACK_SECRET_KEY):
        return HttpResponse(status=401)
    try:
        event = json.loads(raw.decode())
    except ValueError:
        return HttpResponse(status=400)
    name = str(event.get("event", ""))[:60]
    data = event.get("data") or {}
    ref = _event_reference(data)

    record, created = PaymentEvent.objects.get_or_create(
        payload_hash=hashlib.sha256(raw).hexdigest(), defaults={"event": name, "reference": ref})
    if not created and record.result:
        return HttpResponse(status=200)                     # a retry of something already handled

    if name == "charge.success" and ref:
        result = orders.settle(ref, data)
    elif name.startswith(("refund.", "charge.dispute")):
        orders.alert_owner(f"Paystack: {name} for {ref or 'unknown reference'}",
                           f"Paystack reported '{name}' for reference {ref or '(none)'}.\n"
                           f"Review it in the Paystack dashboard and in Admin > Orders. Nothing was changed automatically.")
        result = "alerted"
    else:
        result = "ignored"
    record.result = result[:20]
    record.save(update_fields=["result"])
    logger.info("Paystack webhook %s %s -> %s", name, ref, result)
    return HttpResponse(status=200)          # 200 once the signature is valid and the event is handled


# ───────── Trust pages ─────────
def about(request):
    return render(request, "pages/about.html", {"page": content.page("about"), "categories": content.about_categories()})


def faq(request):
    items, jsonld = content.faq_page()
    return render(request, "pages/faq.html", {"page": content.page("faq"), "faqs": items, "jsonld": jsonld})


def testimonials(request):
    return render(request, "pages/testimonials.html", {"page": content.page("testimonials"), "testimonials": content.testimonials()})


