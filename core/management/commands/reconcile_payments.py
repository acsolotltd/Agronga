from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core import orders, paystack
from core.models import Order


class Command(BaseCommand):
    help = ("Safety net for missed webhooks. Asks Paystack about orders still 'awaiting payment', settles any that were paid, "
            "and marks long-unpaid ones as expired. Run it every 10 minutes from a scheduler.")

    def add_arguments(self, parser):
        parser.add_argument("--min-age", type=int, default=10, help="Only check orders older than this many minutes (default 10).")
        parser.add_argument("--expire-after", type=int, default=48, help="Mark unpaid orders failed after this many hours (default 48).")

    def handle(self, *args, **o):
        now = timezone.now()
        newest, oldest = now - timedelta(minutes=o["min_age"]), now - timedelta(hours=o["expire_after"])
        paid = checked = 0
        for order in Order.objects.filter(status=Order.PENDING, created_at__lt=newest, created_at__gte=oldest).exclude(paystack_access_code=""):
            checked += 1
            try:
                if orders.settle(order.reference, paystack.verify(settings.PAYSTACK_SECRET_KEY, order.reference)) == "paid":
                    paid += 1
            except paystack.PaystackError as e:        # e.g. the customer never opened the payment page
                self.stderr.write(f"{order.reference}: {e}")
        expired = Order.objects.filter(status=Order.PENDING, created_at__lt=oldest).update(
            status=Order.FAILED, gateway_response="Expired unpaid")
        self.stdout.write(self.style.SUCCESS(f"Checked {checked}, newly paid {paid}, expired {expired}."))
