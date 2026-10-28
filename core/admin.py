from django.contrib import admin

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order")
    list_editable = ("sort_order",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "unit", "price_usd", "price_ngn", "weight_kg", "is_bulk", "is_featured", "is_active")
    list_editable = ("price_usd", "weight_kg", "is_featured", "is_active")     # price_ngn is automatic and read-only
    readonly_fields = ("price_ngn",)
    list_filter = ("category", "is_active", "is_featured", "is_bulk", "quote_only")
    search_fields = ("name", "blurb")
    prepopulated_fields = {"slug": ("name",)}
    list_select_related = ("category",)
from .models import FAQ, CompanyProfile, Testimonial  # noqa: E402


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "sort_order", "is_published")
    list_editable = ("sort_order", "is_published")
    search_fields = ("question", "answer")
    list_filter = ("is_published",)


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "consent_given", "is_published", "sort_order")
    list_editable = ("is_published", "sort_order")
    list_filter = ("is_published", "consent_given")


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    """Contact details here feed the header, footer, Contact page and every call-to-action on the site."""
    fieldsets = (
        ("Contact details (shown across the whole site)", {"fields": ("phones", "email", "address", "short_location", "opening_hours", "map_url")}),
        ("Registration", {"fields": ("rc_number", "founded_year", "certifications")}),
        ("Old About text (used only if the About page text is blank)", {"fields": ("story",), "classes": ("collapse",)}),
    )

    def has_add_permission(self, request):
        return not CompanyProfile.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


from .models import Order, OrderItem  # noqa: E402


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("product", "name", "unit", "unit_price", "quantity")

    def has_add_permission(self, request, obj=None):
        return False


from django import forms  # noqa: E402
from django.contrib import messages  # noqa: E402
from django.utils import timezone  # noqa: E402

from . import orders as order_logic  # noqa: E402
from .models import OrderStatusChange  # noqa: E402

EDITABLE_ORDER_FIELDS = ("status", "tracking_info", "customer_message")


class OrderAdminForm(forms.ModelForm):
    notify_customer = forms.BooleanField(
        required=False, initial=True, label="Email the customer about this status change",
        help_text="Sends the matching email (paid, processing, shipped, delivered, cancelled, refunded). Untick to change the status silently. "
                  "It only applies when you actually change the status.")

    class Meta:
        model = Order
        fields = list(EDITABLE_ORDER_FIELDS)


class StatusHistoryInline(admin.TabularInline):
    model = OrderStatusChange
    extra = 0
    can_delete = False
    fields = readonly_fields = ("created_at", "from_status", "to_status", "changed_by", "customer_notified")
    verbose_name_plural = "Status history"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Orders are financial records: nothing can be deleted or hand-edited except the status, tracking and a note to the customer.
    Changing the status emails the customer automatically."""
    form = OrderAdminForm
    list_display = ("reference", "status", "currency", "total", "name", "email", "paid_at", "created_at")
    list_filter = ("status", "currency")
    search_fields = ("reference", "name", "email", "phone")
    date_hierarchy = "created_at"
    inlines = [OrderItemInline, StatusHistoryInline]
    fieldsets = (
        ("Status and customer email", {
            "fields": ("status", "notify_customer", "tracking_info", "customer_message"),
            "description": "Change the status and press Save: the customer is emailed. For 'Shipped', fill in the tracking field first. "
                           "The note to the customer is added to that one email and then cleared."}),
        ("Order", {"fields": ("reference", "currency", "subtotal", "shipping_fee", "total", "fx_rate", "fx_raw_rate", "shipping_zone", "shipping_note", "created_at", "paid_at")}),
        ("Customer", {"fields": ("name", "email", "phone", "country", "address", "notes")}),
        ("Payment", {"fields": ("channel", "gateway_response", "paystack_access_code", "authorization_url", "idempotency_key")}),
    )
    readonly_fields = [f.name for f in Order._meta.fields if f.name not in EDITABLE_ORDER_FIELDS]
    actions = ["mark_processing", "mark_shipped", "mark_delivered", "mark_cancelled", "mark_refunded", "resend_status_email", "verify_with_paystack"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    # ── single order: the Save button on the change page ──
    def save_model(self, request, obj, form, change):
        status_changed = change and "status" in form.changed_data
        old = form.initial.get("status") if change else None
        if status_changed and obj.status in Order.PAID_STATES and not obj.paid_at:
            obj.paid_at = timezone.now()                     # e.g. an invoice order paid by bank transfer
        super().save_model(request, obj, form, change)
        if not status_changed:
            return
        history = order_logic.record_status(obj, old, obj.status, by=request.user.get_username())
        label = obj.get_status_display()
        if not form.cleaned_data.get("notify_customer"):
            self.message_user(request, f"Status is now '{label}'. The customer was not emailed (box unticked).", messages.INFO)
        elif obj.status not in order_logic.STATUS_COPY:
            self.message_user(request, f"Status is now '{label}'. No email is sent for this status.", messages.INFO)
        elif order_logic.notify_status(obj, history):
            self.message_user(request, f"Status is now '{label}'. {obj.email} was emailed.", messages.SUCCESS)
        else:
            self.message_user(request, f"Status saved, but the email to {obj.email} could not be sent. Check Brevo and the server log, then use 'Send the status email again'.", messages.WARNING)

    # ── many orders: list page actions ──
    def _change_status(self, request, queryset, new):
        label = dict(Order.STATUS_CHOICES)[new]
        changed = emailed = 0
        for o in queryset:
            if o.status == new:
                continue
            old, o.status, fields = o.status, new, ["status"]
            if new in Order.PAID_STATES and not o.paid_at:
                o.paid_at = timezone.now()
                fields.append("paid_at")
            o.save(update_fields=fields)
            history = order_logic.record_status(o, old, new, by=request.user.get_username())
            changed += 1
            emailed += bool(order_logic.notify_status(o, history))
        level = messages.SUCCESS if emailed == changed else messages.WARNING
        self.message_user(request, f"{changed} order(s) set to '{label}'. {emailed} customer(s) emailed." + ("" if emailed == changed else " Check the others in the server log."), level)

    @admin.action(description="Mark as Processing and email the customer")
    def mark_processing(self, request, queryset):
        self._change_status(request, queryset, Order.PROCESSING)

    @admin.action(description="Mark as Shipped and email the customer")
    def mark_shipped(self, request, queryset):
        self._change_status(request, queryset, Order.SHIPPED)

    @admin.action(description="Mark as Delivered and email the customer")
    def mark_delivered(self, request, queryset):
        self._change_status(request, queryset, Order.DELIVERED)

    @admin.action(description="Mark as Cancelled and email the customer")
    def mark_cancelled(self, request, queryset):
        self._change_status(request, queryset, Order.CANCELLED)

    @admin.action(description="Mark as Refunded and email the customer")
    def mark_refunded(self, request, queryset):
        self._change_status(request, queryset, Order.REFUNDED)

    @admin.action(description="Send the status email again (current status)")
    def resend_status_email(self, request, queryset):
        sent = sum(bool(order_logic.notify_status(o)) for o in queryset)
        self.message_user(request, f"{sent} of {queryset.count()} email(s) sent.", messages.SUCCESS if sent else messages.WARNING)

    @admin.action(description="Verify selected orders with Paystack")
    def verify_with_paystack(self, request, queryset):
        from django.conf import settings
        from . import paystack
        done = 0
        for o in queryset.exclude(status__in=Order.PAID_STATES):
            try:
                result = order_logic.settle(o.reference, paystack.verify(settings.PAYSTACK_SECRET_KEY, o.reference))
            except paystack.PaystackError as e:
                self.message_user(request, f"{o.reference}: {e}", level="warning")
                continue
            done += 1
            self.message_user(request, f"{o.reference}: {result}")
        if not done:
            self.message_user(request, "Nothing to verify.", level="warning")


from . import fx  # noqa: E402
from .models import FxRate, ShippingZone  # noqa: E402


@admin.register(FxRate)
class FxRateAdmin(admin.ModelAdmin):
    """The newest row is the live rate. Adding one (e.g. a CBN or parallel-market quote) reprices every naira price at once."""
    list_display = ("fetched_at", "ngn_per_usd", "charged_rate", "source", "pinned", "note")
    fields = ("ngn_per_usd", "pinned", "note", "source", "fetched_at")
    readonly_fields = ("source", "fetched_at")

    @admin.display(description="Charged rate (market + margin)")
    def charged_rate(self, obj):
        return f"₦{fx.effective(obj):,.2f} per $1"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.source = "manual"
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        return obj is None or obj.source == "manual"       # automatic rows are history: do not edit


@admin.register(ShippingZone)
class ShippingZoneAdmin(admin.ModelAdmin):
    list_display = ("name", "countries", "base_usd", "per_kg_usd", "free_over_usd", "eta", "is_active", "sort_order")
    list_editable = ("base_usd", "per_kg_usd", "free_over_usd", "eta", "is_active", "sort_order")


from .models import PaymentEvent  # noqa: E402


@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    """Read-only audit trail of every Paystack webhook delivery (no raw payloads are kept)."""
    list_display = ("received_at", "event", "reference", "result")
    list_filter = ("event", "result")
    search_fields = ("reference",)
    readonly_fields = [f.name for f in PaymentEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


from django.utils.html import format_html  # noqa: E402

from .models import PageBlock, PageContent  # noqa: E402


class PageBlockInline(admin.StackedInline):
    model = PageBlock
    extra = 0
    fields = ("heading", "body", "callout", "sort_order", "is_active")
    verbose_name = "Extra section"
    verbose_name_plural = "Extra sections (shown below the main text)"


@admin.register(PageContent)
class PageContentAdmin(admin.ModelAdmin):
    """Edit the header photo, title, intro and text of the About, Contact, FAQ and Testimonials pages."""
    list_display = ("__str__", "title", "has_photo", "updated_at")
    inlines = [PageBlockInline]
    readonly_fields = ("header_preview", "side_preview", "updated_at")
    fieldsets = (
        ("Which page", {"fields": ("slug",)}),
        ("Header (the banner at the top)", {"fields": ("eyebrow", "title", "intro", "header_image", "header_preview", "header_position")}),
        ("Page text", {"fields": ("body", "side_image", "side_alt", "side_preview")}),
        (None, {"fields": ("updated_at",)}),
    )

    def has_add_permission(self, request):
        return PageContent.objects.count() < len(PageContent.PAGE_CHOICES)

    def get_readonly_fields(self, request, obj=None):
        return (*self.readonly_fields, "slug") if obj else self.readonly_fields

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == "slug":                       # only offer pages that do not have a record yet
            used = set(PageContent.objects.values_list("slug", flat=True))
            kwargs["choices"] = [c for c in PageContent.PAGE_CHOICES if c[0] not in used]
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    @admin.display(boolean=True, description="Own photo")
    def has_photo(self, obj):
        return bool(obj.header_image)

    def _preview(self, image, variants):
        from django.core.files.storage import default_storage
        if variants:
            url = default_storage.url(sorted(variants, key=lambda v: v["w"])[0]["path"])
        elif image:
            url = image.url
        else:
            return "No photo yet: the default photo is shown."
        return format_html('<img src="{}" style="max-width:360px;max-height:140px;border-radius:8px;border:1px solid #ccc">', url)

    @admin.display(description="Preview")
    def header_preview(self, obj):
        return self._preview(obj.header_image, obj.header_variants) if obj and obj.pk else "Save first to see a preview."

    @admin.display(description="Preview")
    def side_preview(self, obj):
        return self._preview(obj.side_image, obj.side_variants) if obj and obj.pk else "Save first to see a preview."
