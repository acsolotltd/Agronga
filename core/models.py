from decimal import Decimal

from . import pagedata

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.templatetags.static import static
from django.utils import timezone
from django.urls import reverse


class Category(models.Model):
    name = models.CharField(max_length=60)
    slug = models.SlugField(unique=True)
    sort_order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ("sort_order", "name")
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Product(models.Model):
    """USD is the master price you edit. The naira price is derived from it (live rate + margin) and is read-only."""

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    blurb = models.CharField(max_length=140, help_text="One line shown on product cards.")
    description = models.TextField(blank=True)

    unit = models.CharField(max_length=40, blank=True,
                            help_text="What the price covers, e.g. 'per 500 g pack' or 'per tonne'.")
    min_order = models.CharField(max_length=60, blank=True, help_text="e.g. '1 tonne'. Leave blank if none.")
    price_usd = models.DecimalField("Price ($)", max_digits=10, decimal_places=2, null=True, blank=True,
                                    help_text="The master price. Naira is calculated from this automatically. "
                                              "Leave blank to show 'Price on request'.")
    price_ngn = models.DecimalField("Price (₦, automatic)", max_digits=12, decimal_places=2, null=True, blank=True, editable=False,
                                    help_text="Read-only. USD price x live exchange rate x (1 + margin), rounded to ₦10. "
                                              "Updated whenever the rate changes and when a naira customer checks out.")
    weight_kg = models.DecimalField("Shipping weight (kg)", max_digits=8, decimal_places=3, default=Decimal("0.500"),
                                    help_text="Weight of ONE unit, packaging included. Used to calculate shipping. Ignored for bulk (tonne) goods.")
    quote_only = models.BooleanField(default=False,
                                     help_text="Bulk goods: show 'From <price>' and sell by quote, not by cart.")

    is_bulk = models.BooleanField(default=False,
                                  help_text="Sold by the tonne or in volume: show a 'Request bulk quote' button beside Add to cart.")
    badge = models.CharField(max_length=30, blank=True, help_text="Small label on the card, e.g. 'New flavour'.")
    accent = models.CharField(max_length=7, default="#1b6b3a", help_text="Hex colour used to tint this product's card and page.")
    highlights = models.TextField(blank=True, help_text="One short selling point per line (3 works best).")
    specs = models.TextField(blank=True, help_text="One 'Label: value' per line. Only list facts that are true.")
    gallery = models.TextField(blank=True, help_text="Static image paths, one per line (e.g. img/products/cashew-nuts.jpg). "
                                                     "Used when no photo is uploaded below.")

    image = models.ImageField(upload_to="products/", blank=True, help_text="Landscape 4:3, at least 800x600.")
    image_alt = models.CharField(max_length=140, blank=True, help_text="Describe the photo. Defaults to the name.")

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text="Shown on the home page.")
    sort_order = models.PositiveSmallIntegerField(default=100)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "name")
        constraints = [
            models.CheckConstraint(condition=Q(price_ngn__isnull=True) | Q(price_ngn__gte=0), name="price_ngn_non_negative"),
            models.CheckConstraint(condition=Q(price_usd__isnull=True) | Q(price_usd__gte=0), name="price_usd_non_negative"),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("core:product_detail", args=[self.slug])

    def save(self, *args, **kwargs):
        """price_ngn is never typed in: it is always recalculated from the USD price."""
        from . import fx
        self.price_ngn = fx.usd_to_ngn(self.price_usd)
        uf = kwargs.get("update_fields")
        if uf is not None and "price_usd" in uf and "price_ngn" not in uf:
            kwargs["update_fields"] = [*uf, "price_ngn"]
        super().save(*args, **kwargs)

    def price_for(self, code):
        """Decimal, or None when no price is set for that currency."""
        return self.price_usd if code == "USD" else self.price_ngn

    # ── storefront helpers (used by templates) ──
    @property
    def image_urls(self):
        """Uploaded photo first, then the static gallery. Always a list of URLs."""
        urls = [self.image.url] if self.image else []
        urls += [static(l.strip()) for l in self.gallery.splitlines() if l.strip()]
        return urls

    @property
    def image_url(self):
        urls = self.image_urls
        return urls[0] if urls else ""

    @property
    def alt(self):
        return self.image_alt or self.name

    @property
    def highlight_list(self):
        return [l.strip() for l in self.highlights.splitlines() if l.strip()]

    @property
    def spec_rows(self):
        rows = []
        for line in self.specs.splitlines():
            label, sep, value = line.partition(":")
            if sep and label.strip() and value.strip():
                rows.append((label.strip(), value.strip()))
        return rows

    @property
    def paragraphs(self):
        return [p.strip() for p in (self.description or self.blurb).split("\n\n") if p.strip()]

    def clean(self):
        if self.is_active and (self.price_ngn or self.price_usd) and not self.unit:
            raise ValidationError({"unit": "Add a unit so buyers know what the price covers."})


class FAQ(models.Model):
    question = models.CharField(max_length=200)
    answer = models.TextField(help_text="Plain text. Blank lines start a new paragraph.")
    sort_order = models.PositiveSmallIntegerField(default=100)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"

    def __str__(self):
        return self.question


class Testimonial(models.Model):
    """Real customer words only. Publishing requires recorded consent."""

    name = models.CharField(max_length=80)
    role = models.CharField(max_length=100, blank=True, help_text="e.g. 'Buyer, Houston' or 'Chocolatier, Lagos'.")
    quote = models.TextField(max_length=600)
    consent_given = models.BooleanField(
        default=False, help_text="Tick only if this person agreed (email or message counts) to be quoted by name.")
    is_published = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ("sort_order", "id")

    def __str__(self):
        return f"{self.name}: {self.quote[:40]}"

    def clean(self):
        if self.is_published and not self.consent_given:
            raise ValidationError({"is_published": "Record the customer's consent before publishing."})


class CompanyProfile(models.Model):
    """Single row. Anything left blank is simply not shown on the About page."""

    rc_number = models.CharField("CAC registration number", max_length=40, blank=True, help_text="e.g. RC 1234567")
    founded_year = models.PositiveSmallIntegerField(null=True, blank=True)
    story = models.TextField(blank=True, help_text="Replaces the default About text. Blank lines start a new paragraph.")
    certifications = models.TextField(blank=True, help_text="One per line, e.g. 'NAFDAC registration no. ...'. Only list what you hold.")
    phones = models.TextField(blank=True, help_text="One number per line, e.g. +234 913 612 2996. The first one is shown in the header and footer. Blank = use the default.")
    email = models.EmailField(blank=True, help_text="Public contact email (shown without exposing it to spam bots). Blank = use the default.")
    address = models.CharField(max_length=300, blank=True, help_text="Blank = use the default.")
    opening_hours = models.CharField(max_length=120, blank=True, help_text="e.g. Sunday to Friday, 8:00 am to 5:00 pm (WAT). Blank = use the default.")
    map_url = models.URLField(max_length=300, blank=True, help_text="Link to your location on Google Maps. Blank = no map link.")
    short_location = models.CharField(max_length=60, blank=True, help_text="Short place name for the top bar, e.g. 'Festac Town, Lagos'. Blank = the default.")

    class Meta:
        verbose_name = verbose_name_plural = "Company profile"

    def __str__(self):
        return "Company profile"

    @classmethod
    def load(cls):
        return cls.objects.first() or cls()

    @property
    def certification_list(self):
        return [l.strip() for l in self.certifications.splitlines() if l.strip()]


class Order(models.Model):
    """One checkout. Prices are copied from the catalogue at the moment of ordering and never change after."""

    PENDING, PAID, REQUESTED, FAILED, REVIEW = "pending", "paid", "requested", "failed", "review"
    STATUS_CHOICES = [
        (PENDING, "Awaiting payment"), (PAID, "Paid"), (REQUESTED, "Invoice requested"),
        (FAILED, "Payment failed"), (REVIEW, "Needs review (amount mismatch)"),
    ]

    reference = models.CharField(max_length=24, unique=True, editable=False)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PENDING, db_index=True)
    currency = models.CharField(max_length=3)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    shipping_fee = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, help_text="Goods + shipping: the amount sent to Paystack.")
    fx_rate = models.DecimalField("Naira per $1 used", max_digits=12, decimal_places=4, null=True, blank=True,
                                  help_text="Market rate plus margin, locked at checkout. Blank for dollar orders.")
    fx_raw_rate = models.DecimalField("Market rate", max_digits=12, decimal_places=4, null=True, blank=True)
    shipping_zone = models.CharField(max_length=60, blank=True)
    shipping_note = models.CharField(max_length=300, blank=True)

    name = models.CharField(max_length=80)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    country = models.CharField(max_length=2)
    address = models.CharField(max_length=300)
    notes = models.CharField(max_length=1000, blank=True)

    paystack_access_code = models.CharField(max_length=60, blank=True)
    authorization_url = models.URLField(max_length=300, blank=True, editable=False, help_text="Paystack payment page for this order.")
    idempotency_key = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False,
                                       help_text="Stops a double-click or retry from creating two orders.")
    paid_at = models.DateTimeField(null=True, blank=True)
    channel = models.CharField(max_length=30, blank=True, help_text="card, bank_transfer, ...")
    gateway_response = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"], name="order_status_created_idx")]

    def __str__(self):
        return f"{self.reference} ({self.currency} {self.total}, {self.status})"

    @property
    def first_name(self):
        return (self.name.split() or [""])[0]

    @property
    def masked_email(self):
        """a***@example.com. The public order page shows this, never the full address."""
        local, _, domain = self.email.partition("@")
        return f"{local[:1]}***@{domain}" if domain else "***"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=120)
    unit = models.CharField(max_length=40, blank=True)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    quantity = models.PositiveIntegerField()

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.name}"


class FxRate(models.Model):
    """Naira per US dollar. The newest row is the live rate. Adding or fetching a rate reprices every product in naira.

    The market rate is stored WITHOUT margin; the margin (settings.NGN_MARGIN, 8%) is added when prices are calculated.
    To use a CBN or parallel-market quote instead of the automatic feed, add a row here and tick 'Pinned'.
    """

    AUTO, MANUAL = "auto", "manual"
    ngn_per_usd = models.DecimalField("Market rate (₦ per $1)", max_digits=12, decimal_places=4,
                                      help_text="Before the margin. Example: 1500 for ₦1,500 = $1.")
    source = models.CharField(max_length=30, default="manual", editable=False)
    pinned = models.BooleanField(default=False, help_text="Manual rates only: stop automatic updates from replacing this rate.")
    note = models.CharField(max_length=120, blank=True, help_text="e.g. 'CBN NFEM close, 22 Oct' or 'parallel market'.")
    fetched_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-fetched_at", "-id"]
        verbose_name = "FX rate"

    def __str__(self):
        return f"₦{self.ngn_per_usd:,.2f} per $1 ({self.source}, {self.fetched_at:%Y-%m-%d %H:%M})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from . import fx
        fx.reprice_products(self)


class ShippingZone(models.Model):
    """Courier rate card per group of countries, in USD. Naira shipping is converted with the live rate + margin."""

    name = models.CharField(max_length=60)
    countries = models.CharField(max_length=300, help_text="ISO codes separated by commas, e.g. 'US, CA'. Use * for every other country.")
    base_usd = models.DecimalField("Base fee ($)", max_digits=8, decimal_places=2, help_text="Charged once per order.")
    per_kg_usd = models.DecimalField("Per kg ($)", max_digits=8, decimal_places=2, help_text="Charged per 0.5 kg step of cart weight.")
    free_over_usd = models.DecimalField("Free shipping over ($)", max_digits=10, decimal_places=2, null=True, blank=True)
    eta = models.CharField("Delivery time", max_length=40, blank=True, help_text="e.g. '7-14 business days'.")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    @property
    def country_codes(self):
        return {c.strip().upper() for c in self.countries.replace(";", ",").replace(" ", ",").split(",") if c.strip()}

    @classmethod
    def for_country(cls, code):
        """The zone listing this country, else the '*' zone, else None (shipping is then quoted by email)."""
        catch_all = None
        for z in cls.objects.filter(is_active=True):
            codes = z.country_codes
            if code in codes:
                return z
            if "*" in codes and catch_all is None:
                catch_all = z
        return catch_all


class PaymentEvent(models.Model):
    """One row per distinct webhook delivery (identified by a hash of the signed body). Gives you an audit trail and
    makes Paystack's retries harmless. The raw payload is deliberately NOT stored: it contains customer and card details."""

    payload_hash = models.CharField(max_length=64, unique=True)
    event = models.CharField(max_length=60)
    reference = models.CharField(max_length=60, blank=True, db_index=True)
    result = models.CharField(max_length=20, blank=True, help_text="Blank = received but not finished processing (Paystack will retry).")
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.event} {self.reference} -> {self.result or 'pending'}"


def validate_header_image(f):
    """Admin upload rules: 6 MB max and wide enough to look sharp (2000 x 800 px is ideal)."""
    from django.core.files.images import get_image_dimensions
    if f.size > 6 * 1024 * 1024:
        raise ValidationError("This image is %.1f MB. Please upload one under 6 MB." % (f.size / 1048576))
    width, _ = get_image_dimensions(f)
    if width and width < 1000:
        raise ValidationError(f"This image is only {width}px wide and would look blurry. Use at least 1200px (2000px is ideal).")


def validate_image_position(value):
    if not pagedata.POSITION_RE.match(value or ""):
        raise ValidationError("Use percentages like '50% 30%' or words like 'center top'.")


class PageContent(models.Model):
    """The editable parts of the About, Contact, FAQ and Testimonials pages. One row per page.
    A page with no row still works: it shows the built-in default text (see core/content.py)."""

    ABOUT, CONTACT, FAQ_PAGE, TESTIMONIALS = "about", "contact", "faq", "testimonials"
    PAGE_CHOICES = [(ABOUT, "About us"), (CONTACT, "Contact"), (FAQ_PAGE, "FAQ"), (TESTIMONIALS, "Testimonials")]

    slug = models.CharField("Page", max_length=20, unique=True, choices=PAGE_CHOICES)
    eyebrow = models.CharField("Small label above the title", max_length=60, blank=True)
    title = models.CharField(max_length=120, blank=True, help_text="Blank = the default title.")
    intro = models.CharField("Intro sentence", max_length=300, blank=True, help_text="Shown under the title. Blank = the default.")

    header_image = models.ImageField("Header photo", upload_to="pages/original/", blank=True, validators=[validate_header_image],
                                     help_text="Wide photo behind the title. 2000 x 800 px, JPG/PNG/WebP, under 6 MB. "
                                               "It is optimised automatically for phones and desktops. Blank = the default photo.")
    header_position = models.CharField("Which part of the photo to keep", max_length=20, default=pagedata.DEFAULT_POSITION,
                                        validators=[validate_image_position],
                                        help_text="Where to focus when the photo is cropped on narrow screens, e.g. '50% 30%' (horizontal, vertical) or 'center top'.")
    header_variants = models.JSONField(default=list, blank=True, editable=False)

    body = models.TextField("Main text", blank=True, help_text="Blank line = new paragraph. Blank = the default text (About page).")
    side_image = models.ImageField("Side photo", upload_to="pages/original/", blank=True, validators=[validate_header_image],
                                   help_text="Optional photo beside the main text (About page). Blank = the default.")
    side_alt = models.CharField("Side photo description", max_length=140, blank=True,
                                help_text="Describe the side photo for screen readers and search engines, e.g. 'Dried shea nuts in a heap'.")
    side_variants = models.JSONField(default=list, blank=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Page content"
        verbose_name_plural = "Page content"
        ordering = ["slug"]

    def __str__(self):
        return self.get_slug_display()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._orig_files = (self.header_image.name or "", self.side_image.name or "")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._optimise_images()

    def _optimise_images(self):
        """When a photo is added, replaced or removed: rebuild its optimised sizes and tidy up the old files."""
        from django.core.files.storage import default_storage
        from . import images
        changed = []
        specs = (("header_image", "header_variants", "header", images.HEADER_WIDTHS, 0),
                 ("side_image", "side_variants", "side", images.SIDE_WIDTHS, 1))
        for field, vfield, stem, widths, idx in specs:
            current, original = getattr(self, field).name or "", self._orig_files[idx]
            if current != original or (current and not getattr(self, vfield)):
                images.delete(getattr(self, vfield))
                if original and original != current:
                    default_storage.delete(original)
                setattr(self, vfield, images.from_field(getattr(self, field), f"{self.slug}-{stem}", widths) if current else [])
                changed.append(vfield)
        self._orig_files = (self.header_image.name or "", self.side_image.name or "")
        if changed:
            super().save(update_fields=changed)


class PageBlock(models.Model):
    """An extra section on a page: a heading plus text. Lines starting with '- ' become bullets."""

    page = models.ForeignKey(PageContent, related_name="blocks", on_delete=models.CASCADE)
    heading = models.CharField(max_length=120, blank=True)
    body = models.TextField(help_text="Blank line = new paragraph. Start a line with '- ' for a bullet point.")
    callout = models.BooleanField("Highlight box", default=False, help_text="Show in a tinted box (good for safety notices).")
    sort_order = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.heading or self.body[:40]
