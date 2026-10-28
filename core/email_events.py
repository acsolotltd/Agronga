"""Brevo delivery events (via django-anymail's tracking webhook): tell the owner when an email cannot be delivered.

A customer whose address bounces will never see their receipt or shipping update, so you need to hear about it and call them.
"""
import hashlib
import logging

from django.conf import settings
from django.core.cache import cache

from . import orders

log = logging.getLogger(__name__)
BAD_EVENTS = {"bounced", "rejected", "complained", "failed"}


def on_tracking_event(sender, event, esp_name, **kwargs):
    if event.event_type not in BAD_EVENTS:
        return
    recipient = (event.recipient or "").lower()
    log.warning("Email %s for %s via %s: %s", event.event_type, recipient, esp_name, event.description or event.reject_reason or "")
    if not recipient or recipient == settings.QUOTE_INBOX.lower():
        return                                              # never alert about our own alerts: that would loop
    key = "mailalert:" + hashlib.sha1(recipient.encode()).hexdigest()
    if not cache.add(key, 1, 3600):
        return                                              # one alert per address per hour
    orders.alert_owner(
        f"Email to {recipient} could not be delivered ({event.event_type})",
        f"Brevo reports that an email to {recipient} was {event.event_type}.\n"
        f"Reason: {event.description or event.reject_reason or 'not given'}\n\n"
        "If this person is a customer, they may not have received a receipt or order update. Call them, and check the address in Admin > Orders.")
