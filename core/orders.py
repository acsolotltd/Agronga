"""Order creation, payment settlement and notification emails.

`settle()` is the ONLY place an order becomes paid. Both the webhook and the browser callback call it,
it is idempotent, and it refuses to mark an order paid unless Paystack's amount and currency match ours.
"""
import logging
import secrets

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone

from django.urls import reverse

from . import emails, paystack
from .countries import COUNTRY_NAMES
from .models import Order, OrderItem, OrderStatusChange

log = logging.getLogger(__name__)

def new_reference() -> str:
    return "AG-" + secrets.token_hex(8).upper()          # e.g. AG-9F3A1C07B2D4E6A1 (64 bits: unguessable)

@transaction.atomic
def create_order(q, cleaned, status=Order.PENDING, idempotency_key=None) -> Order:
    """q is a quote.Quote already priced on the server (goods + shipping + locked rate)."""
    naira = q.currency == "NGN"
    order = Order.objects.create(
        reference=new_reference(), status=status, currency=q.currency, idempotency_key=idempotency_key,
        subtotal=q.subtotal, shipping_fee=q.shipping, total=q.total,
        fx_rate=q.rate_eff if naira else None, fx_raw_rate=q.rate_raw if naira else None,
        shipping_zone=q.zone_name, shipping_note=" ".join(q.notes)[:300],
        name=cleaned["name"], email=cleaned["email"], phone=cleaned["phone"], country=cleaned["country"],
        address=cleaned["address"], notes=cleaned.get("notes", ""),
    )
    OrderItem.objects.bulk_create(
        OrderItem(order=order, product=l.product, name=l.product.name, sku=l.product.sku or "", unit=l.product.unit, unit_price=l.unit_price, quantity=l.qty)
        for l in q.lines
    )
    OrderStatusChange.objects.create(order=order, from_status="", to_status=status, changed_by="Customer checkout")
    return order


def _money(order, amount):
    sym = {"NGN": "₦", "USD": "$"}.get(order.currency, order.currency + " ")
    dec = 0 if order.currency == "NGN" else 2
    return f"{sym}{amount:,.{dec}f}"


def summary_text(order) -> str:
    rows = "\n".join(
        f"  {i.quantity} x {i.name} ({i.unit}) @ {_money(order, i.unit_price)} = {_money(order, i.line_total)}"
        for i in order.items.all()
    )
    if order.shipping_zone:
        ship = f"Shipping ({order.shipping_zone} to {order.country}): {_money(order, order.shipping_fee)}"
    else:
        ship = "Shipping: to be confirmed by email"
    rate = (f"Exchange rate: N{order.fx_rate:,.2f} per $1 (market N{order.fx_raw_rate:,.2f} + margin)\n"
            if order.fx_rate else "")
    note = f"Note: {order.shipping_note}\n" if order.shipping_note else ""
    return (f"Reference: {order.reference}\nStatus: {order.get_status_display()}\nCurrency: {order.currency}\n{rate}\n{rows}\n\n"
            f"Subtotal: {_money(order, order.subtotal)}\n{ship}\n{note}"
            f"Total: {_money(order, order.total)}\n\nName: {order.name}\nEmail: {order.email}\nPhone: {order.phone}\n"
            f"Country: {order.country}\nAddress:\n{order.address}\n\nNotes: {order.notes or '-'}\n")


# What each status email says. Statuses not listed here (pending, failed, review) never email the customer.
STATUS_COPY = {
    Order.REQUESTED: {"subject": "We received your order request {ref}", "heading": "Order request received",
                      "lead": "Thank you. We will email you the final price, availability and payment details for you to approve.",
                      "next": "You do not need to pay anything yet."},
    Order.PAID: {"subject": "Payment received: order {ref}", "heading": "Payment received",
                 "lead": "Thank you! We have received your payment and your order is confirmed.",
                 "next": "We will email you again when your order is being prepared and when it ships."},
    Order.PROCESSING: {"subject": "We are preparing your order {ref}", "heading": "We are preparing your order",
                       "lead": "Good news: your payment is confirmed and we are now packing your order.",
                       "next": "You will get another email as soon as it ships."},
    Order.SHIPPED: {"subject": "Your order {ref} is on its way", "heading": "Your order is on its way",
                    "lead": "Your order has been handed to the courier.",
                    "next": "Keep the tracking details below handy. Questions? Just reply to this email."},
    Order.DELIVERED: {"subject": "Your order {ref} was delivered", "heading": "Your order was delivered",
                      "lead": "Your order has been marked as delivered. We hope you enjoy it!",
                      "next": "Something not right? Reply to this email and we will help."},
    Order.CANCELLED: {"subject": "Your order {ref} was cancelled", "heading": "Your order was cancelled",
                      "lead": "Your order has been cancelled.",
                      "next": "If you already paid, we will contact you about your refund. Questions? Reply to this email."},
    Order.REFUNDED: {"subject": "Refund for your order {ref}", "heading": "Your refund has been issued",
                     "lead": "We have refunded your order.",
                     "next": "Depending on your bank or card provider, it can take several business days to appear."},
}


def _email_context(order):
    lines = [{"name": i.name, "sku": i.sku, "unit": i.unit, "qty": i.quantity, "unit_price": _money(order, i.unit_price),
              "line_total": _money(order, i.line_total)} for i in order.items.all()]
    tracking = (order.tracking_info or "").strip()
    return {
        "order": order, "first_name": order.first_name, "lines": lines,
        "subtotal": _money(order, order.subtotal), "shipping": _money(order, order.shipping_fee), "total": _money(order, order.total),
        "has_shipping": bool(order.shipping_zone), "shipping_zone": order.shipping_zone,
        "country_name": COUNTRY_NAMES.get(order.country, order.country),
        "address_lines": [l.strip() for l in order.address.splitlines() if l.strip()],
        "tracking": tracking, "tracking_url": tracking if tracking.lower().startswith(("http://", "https://")) else "",
        "customer_message": (order.customer_message or "").strip(),
        "status_url": settings.SITE_URL + reverse("core:order_status", args=[order.reference]),
        "admin_url": settings.SITE_URL + reverse("admin:core_order_change", args=[order.pk]),
        "rate_note": (f"$1 = N{order.fx_rate:,.2f}, locked when you placed this order." if order.fx_rate else ""),
    }


def notify_status(order, history=None) -> bool:
    """Email the customer about the order's CURRENT status. Returns True if sent. Never raises: a mail failure must never
    undo a status change or a recorded payment. The one-off note to the customer is cleared once it has been sent."""
    copy = STATUS_COPY.get(order.status)
    if not copy or not order.email:
        return False
    ctx = _email_context(order)
    ctx["copy"] = {**copy, "subject": copy["subject"].format(ref=order.reference)}
    try:
        emails.send("order_status", ctx["copy"]["subject"], [order.email], ctx, reply_to=[settings.QUOTE_INBOX],
                    tags=["order", order.status], metadata={"order": order.reference})
    except Exception:  # noqa: BLE001
        log.exception("Could not send the '%s' email for order %s", order.status, order.reference)
        return False
    if order.customer_message:
        order.customer_message = ""
        order.save(update_fields=["customer_message"])
    if history is not None:
        history.customer_notified = True
        history.save(update_fields=["customer_notified"])
    return True


def record_status(order, old, new, by="", notified=False):
    return OrderStatusChange.objects.create(order=order, from_status=old or "", to_status=new, changed_by=by[:80], customer_notified=notified)


def _notify_owner_new_order(order, kind):
    ctx = _email_context(order)
    ctx["kind"] = kind                                   # "paid" or "requested"
    try:
        emails.send("order_owner", f"{'PAID: order' if kind == 'paid' else 'Order request'} {order.reference} ({_money(order, order.total)})",
                    [settings.QUOTE_INBOX], ctx, reply_to=[order.email], tags=["order", "owner", kind], metadata={"order": order.reference})
    except Exception:  # noqa: BLE001
        log.exception("Could not email the owner about order %s", order.reference)


def notify_invoice_request(order):
    """Order saved as 'requested': tell the owner, and send the customer an acknowledgement. Never raises (the order is safe)."""
    _notify_owner_new_order(order, "requested")
    history = order.history.first()
    notify_status(order, history)


def _notify_paid(order_id, history_id=None):
    order = Order.objects.get(pk=order_id)
    _notify_owner_new_order(order, "paid")
    notify_status(order, OrderStatusChange.objects.filter(pk=history_id).first() if history_id else None)


def alert_owner(subject, body):
    """Tell the shop owner something needs a human (refund, dispute, mismatch). Never raises."""
    try:
        EmailMessage(subject=subject, body=body, from_email=settings.DEFAULT_FROM_EMAIL, to=[settings.QUOTE_INBOX]).send()
    except Exception:
        log.exception("Could not send owner alert: %s", subject)


def _alert_review(order_id, why):
    order = Order.objects.get(pk=order_id)
    try:
        EmailMessage(subject=f"REVIEW NEEDED: order {order.reference}", body=f"{why}\n\n{summary_text(order)}",
                     from_email=settings.DEFAULT_FROM_EMAIL, to=[settings.QUOTE_INBOX]).send()
    except Exception:
        log.exception("Could not send review alert for %s", order.reference)


def settle(reference: str, data: dict) -> str:
    """Apply a Paystack transaction payload (webhook `data` or verify `data`) to the matching order.

    Returns one of: "paid", "already_paid", "failed", "review", "unknown", "ignored".
    """
    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(reference=reference)
        except Order.DoesNotExist:
            log.warning("Paystack reference %s matches no order", reference)
            return "unknown"
        if order.status in Order.PAID_STATES:
            return "already_paid"                      # webhooks are delivered more than once; never roll a shipped order back to "paid"
        if order.status in (Order.CANCELLED, Order.REFUNDED):
            if data.get("status") == "success":        # money arrived for an order you cancelled: a human must decide
                transaction.on_commit(lambda: _alert_review(order.pk, f"A successful payment arrived for an order that is {order.status}."))
            return "ignored"

        state = data.get("status")
        if state == "success":
            same_amount = data.get("amount") == paystack.to_subunit(order.total)
            same_currency = data.get("currency") == order.currency
            if not (same_amount and same_currency):
                order.status = Order.REVIEW
                order.gateway_response = f"Mismatch: got {data.get('amount')} {data.get('currency')}"[:200]
                order.save(update_fields=["status", "gateway_response"])
                transaction.on_commit(lambda: _alert_review(order.pk, order.gateway_response))
                return "review"
            previous = order.status
            order.status = Order.PAID
            order.paid_at = timezone.now()
            order.channel = (data.get("channel") or "")[:30]
            order.gateway_response = (data.get("gateway_response") or "")[:200]
            order.save(update_fields=["status", "paid_at", "channel", "gateway_response"])
            history = record_status(order, previous, Order.PAID, by="Paystack")
            transaction.on_commit(lambda: _notify_paid(order.pk, history.pk))
            return "paid"
        if state in ("failed", "abandoned", "reversed"):
            order.status = Order.FAILED
            order.gateway_response = (data.get("gateway_response") or state)[:200]
            order.save(update_fields=["status", "gateway_response"])
            return "failed"
        return "ignored"                                # "ongoing", "pending", "queued": wait for a later event
