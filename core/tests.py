import time
from decimal import Decimal

from django.core import mail, signing
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from .currency import COOKIE
from unittest import mock

from .models import Category, FxRate, Product, ShippingZone


def set_rate(raw="1000", pinned=True, source="manual"):
    """Fix the market rate. With the default 8% margin the charged rate is raw x 1.08 (1000 -> 1080)."""
    return FxRate.objects.create(ngn_per_usd=Decimal(raw), source=source, pinned=pinned)


def make_product(**kw):
    """USD is the master price (default $12.50 -> N13,500 at the test rate). Naira is derived by Product.save()."""
    if not FxRate.objects.exists():
        set_rate()
    cat, _ = Category.objects.get_or_create(slug="nuts", defaults={"name": "Nuts"})
    defaults = dict(category=cat, name="Cashew Nuts", slug="cashew-nuts", blurb="Raw cashew.",
                    unit="per pack", price_usd=Decimal("12.50"), weight_kg=Decimal("1.000"))
    defaults.update(kw)
    return Product.objects.create(**defaults)


class PricingTests(TestCase):
    def test_naira_is_derived_from_usd_with_margin(self):
        p = make_product()                                   # $12.50 x (1000 x 1.08) = N13,500
        self.assertEqual(p.price_ngn, Decimal("13500.00"))
        self.assertEqual(p.price_for("NGN"), Decimal("13500.00"))
        self.assertEqual(p.price_for("USD"), Decimal("12.50"))

    def test_no_usd_price_means_no_naira_price(self):
        p = make_product(price_usd=None)
        self.assertIsNone(p.price_ngn)
        self.assertIsNone(p.price_for("NGN"))
        self.assertIsNone(p.price_for("USD"))

    def test_naira_cannot_be_set_by_hand(self):
        p = make_product(price_ngn=Decimal("1"))             # ignored: always recalculated from USD
        self.assertEqual(p.price_ngn, Decimal("13500.00"))
        p.price_ngn = Decimal("5")
        p.save()
        p.refresh_from_db()
        self.assertEqual(p.price_ngn, Decimal("13500.00"))

    def test_naira_is_read_only_in_admin(self):
        from django.contrib import admin
        self.assertIn("price_ngn", admin.site._registry[Product].readonly_fields)

    def test_new_rate_reprices_every_product_in_the_database(self):
        p = make_product()
        set_rate("2000")                                     # x 1.08 = 2160 -> $12.50 = N27,000
        p.refresh_from_db()
        self.assertEqual(p.price_ngn, Decimal("27000.00"))

    @override_settings(NGN_MARGIN=Decimal("0.10"))
    def test_margin_is_configurable(self):
        p = make_product()                                   # 1000 x 1.10 = 1100 -> N13,750
        self.assertEqual(p.price_ngn, Decimal("13750.00"))

    def test_usd_visitor_sees_price_on_request_when_no_usd_price(self):
        make_product(price_usd=None)
        r = self.client.get(reverse("core:products"), headers={"cf-ipcountry": "US"})
        self.assertContains(r, "Price on request")

    def test_naira_visitor_sees_naira(self):
        make_product()
        self.client.cookies[COOKIE] = "NGN"
        self.assertContains(self.client.get(reverse("core:products")), "₦13,500")

    def test_dollar_visitor_sees_dollars(self):
        make_product()
        self.client.cookies[COOKIE] = "USD"
        self.assertContains(self.client.get(reverse("core:products")), "$12.50")


class FxTests(TestCase):
    """Live-rate service. The network is always mocked; tests never reach the internet."""

    def setUp(self):
        cache.clear()

    def test_fallback_rate_is_used_before_any_rate_exists(self):
        from . import fx
        r = fx.current()
        self.assertEqual((r.source, r.ngn_per_usd), ("fallback", Decimal("1500")))

    def test_refresh_saves_rate_and_reprices(self):
        from . import fx
        p = make_product()
        with mock.patch("core.fx.pricing.fetch_live_rate", return_value=(Decimal("1500"), "open_er_api")):
            new = fx.refresh(force=True)
        self.assertEqual((new.ngn_per_usd, new.source), (Decimal("1500"), "open_er_api"))
        p.refresh_from_db()
        self.assertEqual(p.price_ngn, Decimal("20250.00"))   # $12.50 x 1620

    def test_feed_outage_keeps_last_good_rate(self):
        from . import fx
        from .pricing import FxError
        set_rate("1500", pinned=False, source="open_er_api")
        with mock.patch("core.fx.pricing.fetch_live_rate", side_effect=FxError("down")):
            self.assertIsNone(fx.refresh())
        self.assertEqual(FxRate.objects.count(), 1)

    def test_implausible_jump_is_rejected(self):
        from . import fx
        set_rate("1000", pinned=False, source="open_er_api")
        with mock.patch("core.fx.pricing.fetch_live_rate", return_value=(Decimal("2000"), "open_er_api")):
            self.assertIsNone(fx.refresh())
        self.assertEqual(FxRate.objects.count(), 1)

    def test_pinned_manual_rate_blocks_automatic_updates(self):
        from . import fx
        set_rate("1400", pinned=True)
        with mock.patch("core.fx.pricing.fetch_live_rate") as m:
            self.assertIsNone(fx.refresh())
        m.assert_not_called()

    @override_settings(FX_AUTO_REFRESH=True)
    def test_stale_rate_is_refreshed_on_demand(self):
        from datetime import timedelta
        from django.utils import timezone
        from . import fx
        r = set_rate("1000", pinned=False, source="open_er_api")
        FxRate.objects.filter(pk=r.pk).update(fetched_at=timezone.now() - timedelta(hours=3))
        with mock.patch("core.fx.pricing.fetch_live_rate", return_value=(Decimal("1100"), "open_er_api")) as m:
            self.assertEqual(fx.ensure_fresh().ngn_per_usd, Decimal("1100"))
        m.assert_called_once()

    @override_settings(FX_AUTO_REFRESH=True)
    def test_fresh_rate_is_not_refetched(self):
        from . import fx
        set_rate("1000", pinned=False, source="open_er_api")
        with mock.patch("core.fx.pricing.fetch_live_rate") as m:
            fx.ensure_fresh()
        m.assert_not_called()

    def test_update_rates_command_can_pin_a_manual_rate(self):
        from django.core.management import call_command
        call_command("update_rates", "--set", "1520.50", "--note", "CBN close", verbosity=0)
        r = FxRate.objects.first()
        self.assertEqual((r.ngn_per_usd, r.pinned, r.source), (Decimal("1520.50"), True, "manual"))


class ShippingTests(TestCase):
    def setUp(self):
        cache.clear()
        make_product()                                       # $12.50, 1 kg each, N13,500 at the test rate
        ShippingZone.objects.create(name="Nigeria", countries="NG", base_usd=Decimal("2.50"), per_kg_usd=Decimal("0.90"), eta="2-5 days")
        ShippingZone.objects.create(name="USA", countries="US, CA", base_usd=Decimal("18"), per_kg_usd=Decimal("8.50"))

    def quote(self, country="NG", qty=2, cookie="NGN", cart=None):
        import json
        self.client.cookies[COOKIE] = cookie
        return self.client.post(reverse("core:cart_quote"), {"country": country, "cart": json.dumps(cart or [{"slug": "cashew-nuts", "qty": qty}])})

    def test_zone_lookup(self):
        self.assertEqual(ShippingZone.for_country("CA").name, "USA")
        self.assertIsNone(ShippingZone.for_country("BR"))    # no catch-all yet
        ShippingZone.objects.create(name="World", countries="*", base_usd=Decimal("26"), per_kg_usd=Decimal("12"))
        self.assertEqual(ShippingZone.for_country("BR").name, "World")
        ShippingZone.objects.filter(name="USA").update(is_active=False)
        self.assertEqual(ShippingZone.for_country("US").name, "World")

    def test_naira_quote_adds_margin_to_goods_and_shipping(self):
        d = self.quote().json()
        # goods 2 x N13,500 = N27,000. Shipping 2.50 + 0.90 x 2 kg = $4.30 x 1080 = N4,644 -> rounded up to N4,650
        self.assertEqual((d["subtotal_fmt"], d["shipping_fmt"], d["total"], d["total_fmt"]), ("₦27,000", "₦4,650", "31650.00", "₦31,650"))
        self.assertIn("8%", d["rate_text"])
        self.assertIn("1,080.00", d["rate_text"])

    def test_dollar_quote_has_no_margin(self):
        d = self.quote(cookie="USD").json()
        self.assertEqual((d["subtotal_fmt"], d["shipping_fmt"], d["total"]), ("$25.00", "$4.30", "29.30"))
        self.assertEqual(d["rate_text"], "")

    def test_shipping_changes_with_country(self):
        ng, us = self.quote("NG", cookie="USD").json(), self.quote("US", cookie="USD").json()
        self.assertEqual(ng["total"], "29.30")
        self.assertEqual(us["total"], "60.00")               # 18 + 8.50 x 2 kg = 35 shipping + 25 goods

    def test_country_without_courier_rate_is_quoted_by_email(self):
        d = self.quote("BR", cookie="USD").json()
        self.assertEqual(d["shipping_fmt"], "Quoted by email")
        self.assertEqual(d["total"], "25.00")

    def test_free_shipping_threshold(self):
        ShippingZone.objects.filter(name="Nigeria").update(free_over_usd=Decimal("20"))
        self.assertEqual(self.quote("NG", cookie="USD").json()["shipping_fmt"], "Free")

    def test_tonne_goods_flag_freight_and_add_no_online_shipping(self):
        make_product(name="Sesame", slug="sesame", price_usd=Decimal("1690"), is_bulk=True, weight_kg=Decimal("1000"))
        d = self.quote("NG", cookie="USD", cart=[{"slug": "sesame", "qty": 1}]).json()
        self.assertTrue(d["freight_pending"])
        self.assertEqual((d["shipping_fmt"], d["total"]), ("Quoted by email", "1690.00"))

    def test_bad_cart_and_missing_price_rejected(self):
        self.assertEqual(self.quote(cart=[{"slug": "nope", "qty": 1}]).status_code, 422)
        make_product(name="NoPrice", slug="noprice", price_usd=None)
        self.assertEqual(self.quote(cart=[{"slug": "noprice", "qty": 1}]).status_code, 422)

    def test_quote_requires_post(self):
        self.assertEqual(self.client.get(reverse("core:cart_quote")).status_code, 405)


class CurrencyTests(TestCase):
    def test_htmx_sets_cookie_and_trigger(self):
        r = self.client.post(reverse("core:set_currency"), {"currency": "usd"}, headers={"HX-Request": "true"})
        self.assertEqual(r.status_code, 204)
        self.assertIn("currency:changed", r["HX-Trigger"])
        self.assertEqual(r.cookies[COOKIE].value, "USD")

    def test_unknown_currency_rejected(self):
        self.assertEqual(self.client.post(reverse("core:set_currency"), {"currency": "EUR"}).status_code, 400)

    def test_no_open_redirect(self):
        r = self.client.post(reverse("core:set_currency"), {"currency": "NGN", "next": "https://evil.example/"})
        self.assertEqual(r["Location"], "/")


class CatalogTests(TestCase):
    def setUp(self):
        make_product()

    def test_htmx_filter_returns_fragment(self):
        r = self.client.get(reverse("core:products"), headers={"HX-Request": "true"})
        self.assertTemplateUsed(r, "products/partials/catalog.html")
        self.assertTemplateNotUsed(r, "base.html")

    def test_boosted_and_plain_get_full_page(self):
        for h in ({}, {"HX-Request": "true", "HX-Boosted": "true"}):
            self.assertTemplateUsed(self.client.get(reverse("core:products"), headers=h), "base.html")

    def test_inactive_product_404(self):
        make_product(name="Hidden", slug="hidden", is_active=False)
        self.assertEqual(self.client.get(reverse("core:product_detail", args=["hidden"])).status_code, 404)

    def test_robots_and_sitemap(self):
        self.assertContains(self.client.get("/robots.txt"), "Sitemap:")
        self.assertContains(self.client.get("/sitemap.xml"), "cashew-nuts")


@override_settings(QUOTE_INBOX="sales@agronga.test", DEFAULT_FROM_EMAIL="no-reply@agronga.test")
class QuoteTests(TestCase):
    def setUp(self):
        cache.clear()
        make_product()

    def payload(self, age=30, **extra):
        data = {"name": "Ada", "email": "ada@example.com", "country": "US", "product": "cashew-nuts",
                "quantity": "1 tonne", "message": "Hi", "website": "",
                "ts": signing.dumps(time.time() - age, salt="quote")}
        data.update(extra)
        return data

    def test_valid_request_sends_mail_with_reply_to(self):
        r = self.client.post(reverse("core:quote"), self.payload())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].reply_to, ["ada@example.com"])

    def test_honeypot_sends_nothing(self):
        r = self.client.post(reverse("core:quote"), self.payload(website="http://spam.example"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_instant_submission_rejected(self):
        r = self.client.post(reverse("core:quote"), self.payload(age=0))
        self.assertEqual(r.status_code, 422)
        self.assertEqual(len(mail.outbox), 0)

    def test_rate_limit(self):
        for _ in range(5):
            self.client.post(reverse("core:quote"), self.payload())
        r = self.client.post(reverse("core:quote"), self.payload())
        self.assertEqual(r.status_code, 422)
        self.assertEqual(len(mail.outbox), 5)


from .models import FAQ, CompanyProfile, Testimonial  # noqa: E402


class TrustPageTests(TestCase):
    def test_all_pages_render(self):
        for name in ("about", "faq", "testimonials", "contact", "privacy", "terms"):
            self.assertEqual(self.client.get(reverse(f"core:{name}")).status_code, 200, name)

    def test_nav_has_no_dead_links(self):
        html = self.client.get(reverse("core:home")).content.decode()
        for name in ("about", "faq", "testimonials", "contact", "privacy", "terms"):
            self.assertIn(reverse(f"core:{name}"), html)

    def test_about_hides_blank_registration_number(self):
        self.assertNotContains(self.client.get(reverse("core:about")), "CAC registration")
        CompanyProfile.objects.create(rc_number="RC 123456")
        self.assertContains(self.client.get(reverse("core:about")), "RC 123456")

    def test_unpublished_faq_hidden_and_not_in_schema(self):
        FAQ.objects.create(question="Visible?", answer="Yes.")
        FAQ.objects.create(question="Hidden?", answer="No.", is_published=False)
        r = self.client.get(reverse("core:faq"))
        self.assertContains(r, "Visible?")
        self.assertNotContains(r, "Hidden?")

    def test_testimonial_needs_consent_to_publish(self):
        from django.core.exceptions import ValidationError
        t = Testimonial(name="Ada", quote="Great.", is_published=True, consent_given=False)
        with self.assertRaises(ValidationError):
            t.full_clean()

    def test_unconsented_testimonial_never_shown(self):
        Testimonial.objects.create(name="Ghost", quote="Secret.", is_published=True, consent_given=False)
        self.assertNotContains(self.client.get(reverse("core:testimonials")), "Secret.")

    def test_empty_testimonials_show_invitation_not_fakes(self):
        self.assertContains(self.client.get(reverse("core:testimonials")), "Customer reviews will appear here")


@override_settings(QUOTE_INBOX="sales@agronga.test", DEFAULT_FROM_EMAIL="no-reply@agronga.test")
class ContactTests(TestCase):
    def setUp(self):
        cache.clear()

    def payload(self, age=30, **extra):
        data = {"name": "Ada", "email": "ada@example.com", "topic": "general", "message": "Hello there",
                "website": "", "ts": signing.dumps(time.time() - age, salt="quote")}
        data.update(extra)
        return data

    def test_htmx_post_sends_mail_and_returns_fragment(self):
        r = self.client.post(reverse("core:contact"), self.payload(), headers={"HX-Request": "true"})
        self.assertEqual(r.status_code, 200)
        self.assertTemplateNotUsed(r, "base.html")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].reply_to, ["ada@example.com"])

    def test_no_js_post_returns_full_page(self):
        r = self.client.post(reverse("core:contact"), self.payload())
        self.assertTemplateUsed(r, "base.html")
        self.assertContains(r, "Message received")

    def test_honeypot_and_time_trap(self):
        self.client.post(reverse("core:contact"), self.payload(website="http://spam.example"))
        r = self.client.post(reverse("core:contact"), self.payload(age=0))
        self.assertEqual(r.status_code, 422)
        self.assertEqual(len(mail.outbox), 0)

    def test_contact_and_quote_rate_limits_are_independent(self):
        for _ in range(5):
            self.client.post(reverse("core:contact"), self.payload())
        self.assertEqual(self.client.post(reverse("core:contact"), self.payload()).status_code, 422)
        make_product()
        quote = {"name": "Ada", "email": "ada@example.com", "country": "US", "product": "cashew-nuts",
                 "quantity": "", "message": "", "website": "", "ts": signing.dumps(time.time() - 30, salt="quote")}
        self.assertEqual(self.client.post(reverse("core:quote"), quote).status_code, 200)

    def test_quote_no_js_fallback_is_full_page(self):
        make_product()
        quote = {"name": "Ada", "email": "ada@example.com", "country": "US", "product": "cashew-nuts",
                 "quantity": "", "message": "", "website": "", "ts": signing.dumps(time.time() - 30, salt="quote")}
        self.assertTemplateUsed(self.client.post(reverse("core:quote"), quote), "landing/home.html")


@override_settings(QUOTE_INBOX="sales@agronga.test", DEFAULT_FROM_EMAIL="no-reply@agronga.test")
class OrderTests(TestCase):
    """The cart lives in the browser, so the server must re-price every order itself."""

    def setUp(self):
        cache.clear()
        self.p = make_product()

    def payload(self, cart=None, age=30, **extra):
        import json
        data = {"name": "Ada", "email": "ada@example.com", "phone": "+2348000000000", "country": "NG",
                "address": "1 Test Street, Lagos", "notes": "", "website": "", "pay": "request",
                "cart": json.dumps(cart if cart is not None else [{"slug": "cashew-nuts", "qty": 2}]),
                "ts": signing.dumps(time.time() - age, salt="quote")}
        data.update(extra)
        return data

    def test_cart_page_renders(self):
        self.assertEqual(self.client.get(reverse("core:cart")).status_code, 200)

    def test_valid_order_is_priced_by_the_server(self):
        r = self.client.post(reverse("core:order"), self.payload())
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("₦27,000", mail.outbox[0].body)        # 2 x N13,500, derived from the USD price

    def test_usd_cookie_prices_in_dollars(self):
        self.client.cookies[COOKIE] = "USD"
        self.client.post(reverse("core:order"), self.payload())
        self.assertIn("$25.00", mail.outbox[0].body)

    def test_client_cannot_inject_prices_or_unknown_products(self):
        r = self.client.post(reverse("core:order"), self.payload(cart=[{"slug": "nope", "qty": 1}]))
        self.assertEqual(r.status_code, 422)
        self.assertEqual(len(mail.outbox), 0)

    def test_bad_quantity_rejected(self):
        for qty in (0, -1, 10000, "x"):
            r = self.client.post(reverse("core:order"), self.payload(cart=[{"slug": "cashew-nuts", "qty": qty}]))
            self.assertEqual(r.status_code, 422, qty)

    def test_missing_price_rejected(self):
        make_product(slug="no-usd", name="No USD", price_usd=None)
        r = self.client.post(reverse("core:order"), self.payload(cart=[{"slug": "no-usd", "qty": 1}]))
        self.assertEqual(r.status_code, 422)

    def test_unknown_country_code_is_rejected(self):
        self.assertEqual(self.client.post(reverse("core:order"), self.payload(country="ZZ")).status_code, 422)

    def test_honeypot_and_time_trap(self):
        self.client.post(reverse("core:order"), self.payload(website="http://spam.example"))
        r = self.client.post(reverse("core:order"), self.payload(age=0))
        self.assertEqual(r.status_code, 422)
        self.assertEqual(len(mail.outbox), 0)

    def test_order_stores_shipping_and_locked_rate(self):
        ShippingZone.objects.create(name="Nigeria", countries="NG", base_usd=Decimal("2.50"), per_kg_usd=Decimal("0.90"))
        self.client.cookies[COOKIE] = "NGN"
        self.client.post(reverse("core:order"), self.payload())
        o = Order.objects.get()
        self.assertEqual((o.subtotal, o.shipping_fee, o.total), (Decimal("27000.00"), Decimal("4650.00"), Decimal("31650.00")))
        self.assertEqual((o.fx_rate, o.fx_raw_rate, o.shipping_zone), (Decimal("1080.0000"), Decimal("1000.0000"), "Nigeria"))
        self.assertIn("₦31,650", mail.outbox[0].body)

    def test_stale_total_is_refused_with_the_new_quote(self):
        r = self.client.post(reverse("core:order"), self.payload(expected_total="1.00"))
        self.assertEqual(r.status_code, 409)
        self.assertIn("total", r.json()["quote"])
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_matching_total_is_accepted(self):
        r = self.client.post(reverse("core:order"), self.payload(expected_total="27000.00"))
        self.assertEqual(r.status_code, 200)


# ───────── Paystack ─────────
import hashlib  # noqa: E402
import hmac  # noqa: E402
import json as _json  # noqa: E402
from unittest import mock  # noqa: E402

from .models import Order  # noqa: E402

SECRET = "sk_test_unit"


@override_settings(PAYSTACK_SECRET_KEY=SECRET, SITE_URL="https://agronga.test")
class PaystackTests(TestCase):
    def setUp(self):
        cache.clear()
        make_product(price_usd=Decimal("8.50"))      # N9,180 at the test rate (8.50 x 1080)

    def payload(self, **extra):
        data = {"name": "Ada", "email": "ada@example.com", "phone": "+2348000000000", "country": "NG", "address": "1 Test St",
                "notes": "", "website": "", "pay": "paystack",
                "cart": _json.dumps([{"slug": "cashew-nuts", "qty": 2}]),
                "ts": signing.dumps(time.time() - 30, salt="quote")}
        data.update(extra)
        return data

    def init(self, cookie=None):
        if cookie:
            self.client.cookies[COOKIE] = cookie
        with mock.patch("core.views.paystack.initialize",
                        return_value={"authorization_url": "https://checkout.paystack.com/abc", "access_code": "abc"}) as m:
            r = self.client.post(reverse("core:order"), self.payload())
        return r, m

    def webhook(self, event, secret=SECRET, signature=None):
        raw = _json.dumps(event).encode()
        sig = signature if signature is not None else hmac.new(secret.encode(), raw, hashlib.sha512).hexdigest()
        return self.client.post(reverse("core:paystack_webhook"), raw, content_type="application/json", headers={"x-paystack-signature": sig})

    def charge(self, order, **over):
        data = {"reference": order.reference, "status": "success", "amount": int(order.total * 100), "currency": order.currency, "channel": "card"}
        data.update(over)
        return {"event": "charge.success", "data": data}

    def test_naira_order_initializes_in_kobo(self):
        r, m = self.init()
        self.assertEqual(r.json()["redirect"], "https://checkout.paystack.com/abc")
        o = Order.objects.get()
        self.assertEqual((o.status, o.currency, o.total), ("pending", "NGN", Decimal("18360.00")))
        kw = m.call_args.kwargs
        self.assertEqual((kw["currency"], kw["amount"], kw["email"]), ("NGN", Decimal("18360.00"), "ada@example.com"))
        self.assertTrue(kw["callback_url"].startswith("https://agronga.test/order/AG-"))

    def test_dollar_order_initializes_in_usd(self):
        self.init(cookie="USD")
        o = Order.objects.get()
        self.assertEqual((o.currency, o.total), ("USD", Decimal("17.00")))

    def test_paystack_outage_is_handled(self):
        from .paystack import PaystackError
        with mock.patch("core.views.paystack.initialize", side_effect=PaystackError("boom")):
            r = self.client.post(reverse("core:order"), self.payload())
        self.assertEqual(r.status_code, 502)
        self.assertEqual(Order.objects.get().status, "failed")

    def test_invoice_request_flow_still_works(self):
        r = self.client.post(reverse("core:order"), self.payload(pay="request"))
        self.assertTrue(r.json()["ok"])
        self.assertEqual(Order.objects.get().status, "requested")
        self.assertEqual(len(mail.outbox), 1)

    def test_webhook_rejects_bad_signature(self):
        self.init()
        o = Order.objects.get()
        self.assertEqual(self.webhook(self.charge(o), signature="deadbeef").status_code, 401)
        self.assertEqual(self.webhook(self.charge(o), secret="sk_test_other").status_code, 401)
        o.refresh_from_db()
        self.assertEqual(o.status, "pending")

    def test_webhook_marks_paid_once_and_emails_once(self):
        self.init()
        o = Order.objects.get()
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.webhook(self.charge(o)).status_code, 200)
            self.assertEqual(self.webhook(self.charge(o)).status_code, 200)   # Paystack retries
        o.refresh_from_db()
        self.assertEqual(o.status, "paid")
        self.assertIsNotNone(o.paid_at)
        self.assertEqual(len(mail.outbox), 2)  # owner + customer, not 4

    def test_webhook_amount_or_currency_mismatch_goes_to_review(self):
        self.init()
        o = Order.objects.get()
        with self.captureOnCommitCallbacks(execute=True):
            self.webhook(self.charge(o, amount=100))
        o.refresh_from_db()
        self.assertEqual(o.status, "review")

    def test_webhook_ignores_other_events_and_unknown_references(self):
        self.assertEqual(self.webhook({"event": "transfer.success", "data": {}}).status_code, 200)
        self.assertEqual(self.webhook({"event": "charge.success", "data": {"reference": "AG-NOPE", "status": "success"}}).status_code, 200)

    def test_webhook_is_post_only(self):
        self.assertEqual(self.client.get(reverse("core:paystack_webhook")).status_code, 405)

    def test_callback_verifies_with_paystack(self):
        self.init()
        o = Order.objects.get()
        with mock.patch("core.views.paystack.verify", return_value=self.charge(o)["data"]), self.captureOnCommitCallbacks(execute=True):
            r = self.client.get(reverse("core:order_status", args=[o.reference]) + f"?reference={o.reference}")
        self.assertContains(r, "Payment received")
        o.refresh_from_db()
        self.assertEqual(o.status, "paid")

    def test_status_page_for_pending_order_waits(self):
        self.init()
        o = Order.objects.get()
        self.assertContains(self.client.get(reverse("core:order_status", args=[o.reference])), "confirming your payment")

    def test_unknown_reference_404(self):
        self.assertEqual(self.client.get(reverse("core:order_status", args=["AG-NOPE"])).status_code, 404)


@override_settings(PAYSTACK_SECRET_KEY=SECRET, SITE_URL="https://agronga.test")
class CheckoutRepricingTests(TestCase):
    def test_naira_checkout_writes_current_naira_prices_to_the_database(self):
        cache.clear()
        p = make_product()
        Product.objects.filter(pk=p.pk).update(price_ngn=Decimal("1.00"))     # simulate a stale database value
        data = {"name": "Ada", "email": "ada@example.com", "phone": "+2348000000000", "country": "NG", "address": "1 Test St",
                "notes": "", "website": "", "pay": "paystack", "cart": _json.dumps([{"slug": "cashew-nuts", "qty": 1}]),
                "ts": signing.dumps(time.time() - 30, salt="quote")}
        with mock.patch("core.views.paystack.initialize", return_value={"authorization_url": "https://x", "access_code": "a"}):
            self.assertEqual(self.client.post(reverse("core:order"), data).status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.price_ngn, Decimal("13500.00"))


# ───────── Production hardening ─────────
from django.core.management import call_command  # noqa: E402
from django.db import IntegrityError  # noqa: E402

from .models import PaymentEvent  # noqa: E402


class ClientIpTests(TestCase):
    """Behind a proxy, REMOTE_ADDR is the proxy. Rate limits must still be per visitor."""

    def setUp(self):
        cache.clear()
        make_product()

    def post_quote(self, ip_header=None, **extra):
        import json
        return self.client.post(reverse("core:cart_quote"), {"country": "NG", "cart": json.dumps([{"slug": "cashew-nuts", "qty": 1}])}, **extra)

    @override_settings(CLIENT_IP_HEADER="")
    def test_without_a_configured_header_the_forwarded_value_is_ignored(self):
        from .net import client_ip
        r = self.client.get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="6.6.6.6")
        self.assertEqual(client_ip(r.wsgi_request), "10.0.0.1")

    @override_settings(CLIENT_IP_HEADER="X-Forwarded-For", TRUSTED_PROXY_HOPS=1)
    def test_forged_left_hand_values_are_ignored(self):
        from .net import client_ip
        r = self.client.get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="6.6.6.6, 41.58.1.2")
        self.assertEqual(client_ip(r.wsgi_request), "41.58.1.2")

    @override_settings(CLIENT_IP_HEADER="CF-Connecting-IP")
    def test_each_visitor_behind_the_proxy_gets_their_own_rate_limit(self):
        for i in range(125):                                  # one visitor exhausts their 120/minute quote budget
            r = self.post_quote(REMOTE_ADDR="172.70.0.2", HTTP_CF_CONNECTING_IP="41.58.1.2")
        self.assertEqual(r.status_code, 429)
        other = self.post_quote(REMOTE_ADDR="172.70.0.2", HTTP_CF_CONNECTING_IP="41.58.9.9")     # same proxy, different person
        self.assertEqual(other.status_code, 200)


@override_settings(PAYSTACK_SECRET_KEY=SECRET, SITE_URL="https://agronga.test", QUOTE_INBOX="sales@agronga.test")
class IdempotencyTests(TestCase):
    def setUp(self):
        cache.clear()
        make_product(price_usd=Decimal("8.50"))

    def pay(self, **extra):
        data = {"name": "Ada", "email": "ada@example.com", "phone": "+2348000000000", "country": "NG", "address": "1 Test St",
                "notes": "", "website": "", "pay": "paystack", "cart": _json.dumps([{"slug": "cashew-nuts", "qty": 1}]),
                "ts": signing.dumps(time.time() - 30, salt="quote")}
        data.update(extra)
        with mock.patch("core.views.paystack.initialize",
                        return_value={"authorization_url": "https://checkout.paystack.com/one", "access_code": "one"}) as m:
            return self.client.post(reverse("core:order"), data), m

    def test_double_click_creates_one_order_and_one_paystack_transaction(self):
        r1, m1 = self.pay(idem="key-123")
        r2, m2 = self.pay(idem="key-123")
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(r1.json()["redirect"], r2.json()["redirect"])
        self.assertTrue(r2.json().get("reused"))
        m1.assert_called_once()
        m2.assert_not_called()

    def test_without_a_key_each_request_is_a_new_order(self):
        self.pay()
        self.pay()
        self.assertEqual(Order.objects.count(), 2)

    def test_a_failed_attempt_does_not_block_a_retry_with_the_same_key(self):
        from .paystack import PaystackError
        data = {"name": "Ada", "email": "ada@example.com", "phone": "+2348000000000", "country": "NG", "address": "1 Test St",
                "notes": "", "website": "", "pay": "paystack", "idem": "k1", "cart": _json.dumps([{"slug": "cashew-nuts", "qty": 1}]),
                "ts": signing.dumps(time.time() - 30, salt="quote")}
        with mock.patch("core.views.paystack.initialize", side_effect=PaystackError("down")):
            self.assertEqual(self.client.post(reverse("core:order"), data).status_code, 502)
        r, _ = self.pay(idem="k1")
        self.assertTrue(r.json()["ok"])
        self.assertEqual(Order.objects.filter(status="pending").count(), 1)

    def test_changed_cart_with_the_same_key_is_a_new_order(self):
        self.pay(idem="k2")
        r, m = self.pay(idem="k2", cart=_json.dumps([{"slug": "cashew-nuts", "qty": 3}]))
        self.assertFalse(r.json().get("reused", False))
        self.assertEqual(Order.objects.count(), 2)

    def test_references_are_long_and_unique(self):
        self.pay()
        self.pay()
        refs = list(Order.objects.values_list("reference", flat=True))
        self.assertEqual(len(set(refs)), 2)
        self.assertTrue(all(len(r) == 19 and r.startswith("AG-") for r in refs))


@override_settings(PAYSTACK_SECRET_KEY=SECRET, SITE_URL="https://agronga.test", QUOTE_INBOX="sales@agronga.test",
                   DEFAULT_FROM_EMAIL="no-reply@agronga.test")
class WebhookHardeningTests(TestCase):
    def setUp(self):
        cache.clear()
        make_product(price_usd=Decimal("8.50"))
        data = {"name": "Ada Obi", "email": "ada@example.com", "phone": "+2348000000000", "country": "NG", "address": "1 Test St",
                "notes": "", "website": "", "pay": "paystack", "cart": _json.dumps([{"slug": "cashew-nuts", "qty": 1}]),
                "ts": signing.dumps(time.time() - 30, salt="quote")}
        with mock.patch("core.views.paystack.initialize", return_value={"authorization_url": "https://x", "access_code": "a"}):
            self.client.post(reverse("core:order"), data)
        self.order = Order.objects.get()
        mail.outbox.clear()

    def send(self, event, **kw):
        raw = _json.dumps(event).encode()
        sig = hmac.new(SECRET.encode(), raw, hashlib.sha512).hexdigest()
        return self.client.post(reverse("core:paystack_webhook"), raw, content_type="application/json", headers={"x-paystack-signature": sig}, **kw)

    def success(self):
        o = self.order
        return {"event": "charge.success", "data": {"reference": o.reference, "status": "success", "amount": int(o.total * 100), "currency": o.currency}}

    def test_every_delivery_is_recorded_and_a_retry_is_recognised(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.send(self.success()).status_code, 200)
            self.assertEqual(self.send(self.success()).status_code, 200)         # byte-identical retry
        self.assertEqual(PaymentEvent.objects.count(), 1)
        ev = PaymentEvent.objects.get()
        self.assertEqual((ev.event, ev.reference, ev.result), ("charge.success", self.order.reference, "paid"))
        self.assertEqual(len(mail.outbox), 2)                                    # one owner mail + one receipt, not four

    def test_an_event_that_crashed_midway_is_processed_again_on_retry(self):
        raw_event = self.success()
        with mock.patch("core.views.orders.settle", side_effect=RuntimeError("database blip")):
            with self.assertRaises(RuntimeError):
                self.send(raw_event)
        self.assertEqual(PaymentEvent.objects.get().result, "")                  # recorded but unfinished
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.send(raw_event).status_code, 200)              # Paystack's retry completes it
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "paid")

    def test_refunds_and_disputes_alert_the_owner_without_changing_the_order(self):
        r = self.send({"event": "charge.dispute.create", "data": {"transaction": {"reference": self.order.reference}}})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("dispute", mail.outbox[0].subject)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "pending")
        self.assertEqual(PaymentEvent.objects.get().result, "alerted")

    def test_unknown_events_are_acknowledged_and_ignored(self):
        self.assertEqual(self.send({"event": "transfer.success", "data": {}}).status_code, 200)
        self.assertEqual(PaymentEvent.objects.get().result, "ignored")

    @override_settings(PAYSTACK_WEBHOOK_IPS=["52.31.139.75"])
    def test_optional_ip_allowlist(self):
        self.assertEqual(self.send(self.success(), REMOTE_ADDR="203.0.113.9").status_code, 403)
        self.assertEqual(PaymentEvent.objects.count(), 0)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.send(self.success(), REMOTE_ADDR="52.31.139.75").status_code, 200)

    def test_bad_signature_is_rejected_and_not_recorded(self):
        raw = _json.dumps(self.success()).encode()
        r = self.client.post(reverse("core:paystack_webhook"), raw, content_type="application/json", headers={"x-paystack-signature": "nope"})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(PaymentEvent.objects.count(), 0)


@override_settings(PAYSTACK_SECRET_KEY=SECRET, SITE_URL="https://agronga.test")
class OrderPageSafetyTests(TestCase):
    def setUp(self):
        cache.clear()
        make_product(price_usd=Decimal("8.50"))
        data = {"name": "Ada Obi", "email": "ada@example.com", "phone": "+2348000000000", "country": "NG", "address": "1 Secret Street",
                "notes": "", "website": "", "pay": "paystack", "cart": _json.dumps([{"slug": "cashew-nuts", "qty": 1}]),
                "ts": signing.dumps(time.time() - 30, salt="quote")}
        with mock.patch("core.views.paystack.initialize", return_value={"authorization_url": "https://x", "access_code": "a"}):
            self.client.post(reverse("core:order"), data)
        self.order = Order.objects.get()

    def test_public_order_page_hides_personal_details(self):
        self.order.status = "paid"
        self.order.save()
        r = self.client.get(reverse("core:order_status", args=[self.order.reference]))
        self.assertContains(r, "Ada")
        self.assertContains(r, "a***@example.com")
        for secret in ("ada@example.com", "Ada Obi", "1 Secret Street", "+2348000000000"):
            self.assertNotContains(r, secret)

    def test_payment_pages_are_never_cached_or_indexed(self):
        r = self.client.get(reverse("core:order_status", args=[self.order.reference]))
        self.assertIn("no-store", r["Cache-Control"])
        self.assertContains(r, 'content="noindex, nofollow"')
        self.assertIn("no-store", self.client.get(reverse("core:cart"))["Cache-Control"])

    def test_order_page_lookups_are_rate_limited(self):
        url = reverse("core:order_status", args=["AG-0000000000000000"])
        codes = {self.client.get(url).status_code for _ in range(65)}
        self.assertIn(429, codes)


@override_settings(PAYSTACK_SECRET_KEY=SECRET, SITE_URL="https://agronga.test")
class ReconcileTests(TestCase):
    def setUp(self):
        cache.clear()
        make_product(price_usd=Decimal("8.50"))
        self.make = lambda ref, minutes: self._order(ref, minutes)

    def _order(self, ref, minutes_old):
        from datetime import timedelta
        from django.utils import timezone
        o = Order.objects.create(reference=ref, status="pending", currency="NGN", subtotal=Decimal("9180"), total=Decimal("9180"),
                                 name="A", email="a@b.co", phone="1", country="NG", address="x", paystack_access_code="ac")
        Order.objects.filter(pk=o.pk).update(created_at=timezone.now() - timedelta(minutes=minutes_old))
        return o

    def test_missed_webhook_is_recovered_old_orders_expire_and_fresh_ones_are_left_alone(self):
        paid_late = self.make("AG-PAIDLATE00000001", 30)
        too_old = self.make("AG-TOOOLD0000000002", 60 * 49)
        fresh = self.make("AG-FRESH00000000003", 2)
        ok = {"status": "success", "amount": 918000, "currency": "NGN", "channel": "card"}
        with mock.patch("core.management.commands.reconcile_payments.paystack.verify", return_value=ok) as v, self.captureOnCommitCallbacks(execute=True):
            call_command("reconcile_payments", verbosity=0)
        for o in (paid_late, too_old, fresh):
            o.refresh_from_db()
        self.assertEqual(paid_late.status, "paid")
        self.assertEqual(too_old.status, "failed")
        self.assertEqual(too_old.gateway_response, "Expired unpaid")
        self.assertEqual(fresh.status, "pending")
        self.assertEqual(v.call_count, 1)                                        # only the 30-minute-old order was worth asking about

    def test_late_payment_still_settles_an_expired_order(self):
        o = self.make("AG-LATEPAY000000004", 60 * 49)
        call_command("reconcile_payments", verbosity=0)
        o.refresh_from_db()
        self.assertEqual(o.status, "failed")
        from . import orders as logic
        with self.captureOnCommitCallbacks(execute=True):
            result = logic.settle(o.reference, {"status": "success", "amount": 918000, "currency": "NGN"})
        self.assertEqual(result, "paid")


class DeployCheckTests(TestCase):
    def ids(self):
        from .checks import payment_and_production_checks
        return {m.id for m in payment_and_production_checks(None)}

    @override_settings(PRODUCTION=True, PAYSTACK_SECRET_KEY="sk_test_abc", SITE_URL="http://agronga.com", CLIENT_IP_HEADER="", PAYSTACK_WEBHOOK_IPS=[])
    def test_production_with_risky_settings_is_flagged(self):
        found = self.ids()
        for expected in ("core.W002", "core.W003", "core.W004", "core.W005", "core.W006", "core.W007", "core.W008"):
            self.assertIn(expected, found)

    @override_settings(PRODUCTION=False)
    def test_development_is_not_nagged(self):
        self.assertEqual(self.ids(), set())

    @override_settings(DEBUG=True, PAYSTACK_SECRET_KEY="sk_live_abc")
    def test_live_key_with_debug_is_an_error(self):
        self.assertIn("core.E001", self.ids())


# ───────── Editable pages (About, Contact, FAQ, Testimonials) ─────────
import io  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402

from django.contrib.auth import get_user_model  # noqa: E402
from django.core.exceptions import ValidationError  # noqa: E402
from django.core.files.storage import default_storage  # noqa: E402
from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from django.db import connection  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402
from PIL import Image  # noqa: E402

from .models import FAQ, CompanyProfile, PageBlock, PageContent, Testimonial  # noqa: E402

PAGE_URLS = {"about": "core:about", "contact": "core:contact", "faq": "core:faq", "testimonials": "core:testimonials"}


def jpeg(w, h, color=(40, 120, 70)):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "JPEG")
    return buf.getvalue()


def upload(name, w, h, color=(40, 120, 70)):
    return SimpleUploadedFile(name, jpeg(w, h, color), content_type="image/jpeg")


class EditablePageDefaultsTests(TestCase):
    """With no records in the database every page still works and shows the built-in text."""

    def get(self, key):
        return self.client.get(reverse(PAGE_URLS[key]))

    def test_every_page_renders_with_default_title_and_photo(self):
        for key, title in (("about", "About AgroNGA"), ("contact", "Contact us"), ("faq", "Frequently asked questions"), ("testimonials", "What buyers say")):
            r = self.get(key)
            self.assertContains(r, title)
            self.assertContains(r, "shea-nuts.jpg")                     # default header photo

    def test_contact_shows_default_details_and_safety_notice(self):
        r = self.get("contact")
        for text in ("+234 913 612 2996", "+234 816 068 5030", "Festac Town", "Sunday to Friday", "Staying safe when you pay",
                     "We will never ask you to pay into a personal account."):
            self.assertContains(r, text)

    def test_legacy_company_story_still_shows_on_about(self):
        CompanyProfile.objects.create(pk=1, story="Our old story text.")
        self.assertContains(self.get("about"), "Our old story text.")


class EditablePageContentTests(TestCase):
    def test_database_text_replaces_defaults(self):
        PageContent.objects.create(slug="about", eyebrow="Since day one", title="Our story", intro="Grown in Nigeria.", body="First paragraph.\n\nSecond paragraph.")
        r = self.client.get(reverse("core:about"))
        for text in ("Our story", "Since day one", "Grown in Nigeria.", "First paragraph.", "Second paragraph."):
            self.assertContains(r, text)
        self.assertNotContains(r, "About AgroNGA")

    def test_blank_fields_fall_back_to_defaults(self):
        PageContent.objects.create(slug="faq")
        r = self.client.get(reverse("core:faq"))
        self.assertContains(r, "Frequently asked questions")

    def test_sections_support_paragraphs_bullets_callouts_and_hiding(self):
        page = PageContent.objects.create(slug="contact", title="Reach us")
        PageBlock.objects.create(page=page, heading="Visiting us", body="Come any time.\n\n- Free parking\n- Ask for Ada", callout=False, sort_order=1)
        PageBlock.objects.create(page=page, heading="Beware", body="- Never pay a stranger", callout=True, sort_order=2)
        PageBlock.objects.create(page=page, heading="Hidden", body="You should not see this.", is_active=False)
        r = self.client.get(reverse("core:contact"))
        self.assertContains(r, "Visiting us")
        self.assertContains(r, "<li>Free parking</li>", html=True)
        self.assertContains(r, 'class="safe reveal"')                    # the callout styling
        self.assertNotContains(r, "You should not see this.")
        self.assertNotContains(r, "Staying safe when you pay")           # a saved page's sections replace the built-in ones

    def test_contact_details_come_from_company_profile_everywhere(self):
        CompanyProfile.objects.create(pk=1, phones="+234 700 111 2222\n+234 700 333 4444", email="hello@agronga.test",
                                      address="1 New Road, Lagos", opening_hours="Mon-Fri 9-5", map_url="https://maps.example/x")
        contact = self.client.get(reverse("core:contact"))
        for text in ("+234 700 111 2222", "+234 700 333 4444", "1 New Road, Lagos", "Mon-Fri 9-5", 'data-user="hello"', "https://maps.example/x"):
            self.assertContains(contact, text)
        self.assertNotContains(contact, "+234 913 612 2996")
        footer_page = self.client.get(reverse("core:about"))              # the footer and header share the same source
        self.assertContains(footer_page, "tel:+2347001112222")
        self.assertContains(footer_page, "1 New Road, Lagos")

    def test_unsafe_image_position_is_never_rendered(self):
        PageContent.objects.create(slug="about", header_position='50%;a:url(//evil)')
        r = self.client.get(reverse("core:about"))
        self.assertContains(r, "object-position: 50% 45%")
        self.assertNotContains(r, "evil")

    def test_position_and_image_validation_in_admin_forms(self):
        with self.assertRaises(ValidationError):
            PageContent(slug="about", header_position="50%; x").full_clean()
        from .models import validate_header_image
        with self.assertRaises(ValidationError):
            validate_header_image(upload("tiny.jpg", 500, 200))                           # too narrow: would look blurry
        with self.assertRaises(ValidationError):
            validate_header_image(SimpleUploadedFile("big.jpg", b"x" * (7 * 1024 * 1024)))   # over 6 MB
        validate_header_image(upload("fine.jpg", 2000, 800))                              # a good one passes

    def test_faq_and_testimonials_show_only_published_content(self):
        make_product()
        FAQ.objects.create(question="Shown?", answer="Yes.\n\nReally.", is_published=True)
        FAQ.objects.create(question="Hidden?", answer="No.", is_published=False)
        Testimonial.objects.create(name="Ada", quote="Great beans.", consent_given=True, is_published=True)
        Testimonial.objects.create(name="Bola", quote="Secret.", consent_given=True, is_published=False)
        faq, tm = self.client.get(reverse("core:faq")), self.client.get(reverse("core:testimonials"))
        self.assertContains(faq, "Shown?")
        self.assertNotContains(faq, "Hidden?")
        self.assertContains(faq, "FAQPage")
        self.assertContains(tm, "Great beans.")
        self.assertNotContains(tm, "Secret.")
        self.assertContains(self.client.get(reverse("core:home")), "Great beans.")


class PageImageTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)

    def test_upload_creates_small_responsive_webp_sizes(self):
        page = PageContent.objects.create(slug="about", header_image=upload("hero.jpg", 2400, 900))
        self.assertEqual([v["w"] for v in page.header_variants], [640, 1280, 1920])
        for v in page.header_variants:
            self.assertTrue(default_storage.exists(v["path"]))
            self.assertTrue(v["path"].endswith(".webp"))
        html = self.client.get(reverse("core:about")).content.decode()
        self.assertIn("srcset=", html)
        self.assertIn("640w", html)
        self.assertIn("1920w", html)
        self.assertIn('sizes="100vw"', html)

    def test_replacing_a_photo_deletes_the_old_files(self):
        page = PageContent.objects.create(slug="about", header_image=upload("one.jpg", 2000, 800))
        old_original, old_variants = page.header_image.name, [v["path"] for v in page.header_variants]
        page.header_image = upload("two.jpg", 2000, 800, color=(200, 50, 50))
        page.save()
        self.assertFalse(default_storage.exists(old_original))
        for p in old_variants:
            self.assertFalse(default_storage.exists(p))
        self.assertTrue(all(default_storage.exists(v["path"]) for v in page.header_variants))

    def test_removing_a_photo_restores_the_default(self):
        page = PageContent.objects.create(slug="about", header_image=upload("one.jpg", 2000, 800))
        page.header_image = ""
        page.save()
        page.refresh_from_db()
        self.assertEqual(page.header_variants, [])
        self.assertContains(self.client.get(reverse("core:about")), "shea-nuts.jpg")

    def test_side_photo_has_alt_text(self):
        PageContent.objects.create(slug="about", side_image=upload("side.jpg", 1200, 900), side_alt="Farmers drying cashew")
        r = self.client.get(reverse("core:about"))
        self.assertContains(r, 'alt="Farmers drying cashew"')
        self.assertContains(r, "480w")

    def test_a_corrupt_image_does_not_break_the_page(self):
        bad = SimpleUploadedFile("bad.jpg", b"not really an image", content_type="image/jpeg")
        page = PageContent.objects.create(slug="about", header_image=bad)
        self.assertEqual(page.header_variants, [])                       # optimiser failed quietly
        r = self.client.get(reverse("core:about"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, page.header_image.url)                    # falls back to the original upload


@override_settings(CONTENT_CACHE_SECONDS=300)
class ContentCacheTests(TestCase):
    """Reading page content must be cheap: zero queries once warm, and edits show up immediately."""

    def setUp(self):
        cache.clear()
        PageContent.objects.create(slug="about", title="Our story")
        FAQ.objects.create(question="Cached?", answer="Yes.")
        Testimonial.objects.create(name="Ada", quote="Lovely.", consent_given=True, is_published=True)

    def queries(self, url):
        with CaptureQueriesContext(connection) as ctx:
            r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        return [q["sql"] for q in ctx.captured_queries]

    def test_warm_pages_cost_zero_queries(self):
        for key, name in PAGE_URLS.items():
            url = reverse(name)
            self.client.get(url)                                          # warm
            self.assertEqual(self.queries(url), [], key)

    def test_cold_pages_use_a_handful_of_queries(self):
        for key, name in PAGE_URLS.items():
            cache.clear()
            self.assertLessEqual(len(self.queries(reverse(name))), 7, key)

    def test_editing_a_page_clears_the_cache_immediately(self):
        url = reverse("core:about")
        self.assertContains(self.client.get(url), "Our story")
        page = PageContent.objects.get(slug="about")
        page.title = "A better story"
        page.save()
        self.assertContains(self.client.get(url), "A better story")

    def test_editing_sections_faqs_testimonials_and_company_clears_the_cache(self):
        about, faq, tm, contact = (reverse(PAGE_URLS[k]) for k in ("about", "faq", "testimonials", "contact"))
        for u in (about, faq, tm, contact):
            self.client.get(u)
        PageBlock.objects.create(page=PageContent.objects.get(slug="about"), heading="New section", body="Fresh words.")
        self.assertContains(self.client.get(about), "New section")
        f = FAQ.objects.get()
        f.answer = "Absolutely."
        f.save()
        self.assertContains(self.client.get(faq), "Absolutely.")
        Testimonial.objects.get().delete()
        self.assertNotContains(self.client.get(tm), "Lovely.")
        CompanyProfile.objects.create(pk=1, phones="+234 700 999 8888")
        self.assertContains(self.client.get(contact), "+234 700 999 8888")

    def test_unpublishing_removes_content_at_once(self):
        faq = reverse("core:faq")
        self.assertContains(self.client.get(faq), "Cached?")
        f = FAQ.objects.get()
        f.is_published = False
        f.save()
        self.assertNotContains(self.client.get(faq), "Cached?")


class PageAdminTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser("boss", "boss@example.com", "a-long-password-123"))

    def test_changelist_add_and_change_pages_load(self):
        self.assertEqual(self.client.get(reverse("admin:core_pagecontent_changelist")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:core_pagecontent_add")).status_code, 200)
        page = PageContent.objects.create(slug="contact", title="Contact")
        r = self.client.get(reverse("admin:core_pagecontent_change", args=[page.pk]))
        self.assertContains(r, "Header (the banner at the top)")
        self.assertContains(r, "Extra sections")

    def test_only_pages_without_a_record_can_be_added(self):
        PageContent.objects.create(slug="about")
        self.assertNotContains(self.client.get(reverse("admin:core_pagecontent_add")), 'value="about"')
        for slug in ("contact", "faq", "testimonials"):
            PageContent.objects.create(slug=slug)
        self.assertEqual(self.client.get(reverse("admin:core_pagecontent_add")).status_code, 403)       # all four exist

    def test_company_profile_admin_shows_contact_fields(self):
        CompanyProfile.objects.create(pk=1)
        r = self.client.get(reverse("admin:core_companyprofile_change", args=[1]))
        self.assertContains(r, "Contact details (shown across the whole site)")


class SeedPagesTests(TestCase):
    def test_seed_creates_pages_and_fills_blank_company_details_without_overwriting_edits(self):
        from django.core.management import call_command
        CompanyProfile.objects.create(pk=1, address="My own address")
        call_command("seed_pages", verbosity=0)
        self.assertEqual(PageContent.objects.count(), 4)
        self.assertEqual(PageBlock.objects.filter(page__slug="contact").count(), 1)
        profile = CompanyProfile.objects.get()
        self.assertEqual(profile.address, "My own address")             # edited value kept
        self.assertIn("+234 913 612 2996", profile.phones)              # blank value filled
        PageContent.objects.filter(slug="about").update(title="Edited title")
        call_command("seed_pages", verbosity=0)
        self.assertEqual(PageContent.objects.get(slug="about").title, "Edited title")
        self.assertEqual(PageContent.objects.count(), 4)
        self.assertEqual(PageBlock.objects.count(), 1)
