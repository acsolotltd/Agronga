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

from . import paystack
from .models import Order, OrderItem

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
        OrderItem(order=order, product=l.product, name=l.product.name, unit=l.product.unit, unit_price=l.unit_price, quantity=l.qty)
        for l in q.lines
    )
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


def notify_invoice_request(order):
    EmailMessage(subject=f"Order request {order.reference}", body=summary_text(order), from_email=settings.DEFAULT_FROM_EMAIL,
                 to=[settings.QUOTE_INBOX], reply_to=[order.email]).send(fail_silently=False)


def _notify_paid(order_id):
    order = Order.objects.get(pk=order_id)
    body = summary_text(order)
    try:
        EmailMessage(subject=f"PAID: order {order.reference} ({_money(order, order.total)})", body=body,
                     from_email=settings.DEFAULT_FROM_EMAIL, to=[settings.QUOTE_INBOX], reply_to=[order.email]).send()
        EmailMessage(
            subject=f"Payment received, order {order.reference}",
            body=(f"Hello {order.name},\n\nThank you. We have received your payment of {_money(order, order.total)}.\n\n{body}\n"
                  "We will email you about delivery shortly. Reply to this email if anything looks wrong.\n\nAgroNGA"),
            from_email=settings.DEFAULT_FROM_EMAIL, to=[order.email], reply_to=[settings.QUOTE_INBOX]).send()
    except Exception:  # a mail failure must never undo a recorded payment
        log.exception("Could not send paid-order emails for %s", order.reference)


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
        if order.status == Order.PAID:
            return "already_paid"                      # webhooks are delivered more than once

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
            order.status = Order.PAID
            order.paid_at = timezone.now()
            order.channel = (data.get("channel") or "")[:30]
            order.gateway_response = (data.get("gateway_response") or "")[:200]
            order.save(update_fields=["status", "paid_at", "channel", "gateway_response"])
            transaction.on_commit(lambda: _notify_paid(order.pk))
            return "paid"
        if state in ("failed", "abandoned", "reversed"):
            order.status = Order.FAILED
            order.gateway_response = (data.get("gateway_response") or state)[:200]
            order.save(update_fields=["status", "gateway_response"])
            return "failed"
        return "ignored"                                # "ongoing", "pending", "queued": wait for a later event
