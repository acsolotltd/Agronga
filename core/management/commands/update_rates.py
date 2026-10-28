from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError

from core import fx
from core.models import FxRate


class Command(BaseCommand):
    help = ("Refresh the live USD->NGN rate and reprice every product in naira. Run it hourly from a scheduler "
            "(Windows Task Scheduler or cron). Use --set to pin a CBN / parallel-market rate by hand.")

    def add_arguments(self, parser):
        parser.add_argument("--set", metavar="RATE", help="Pin this market rate (naira per $1, before margin). Automatic updates stop until you unpin it in Admin.")
        parser.add_argument("--note", default="", help="Label for a pinned rate, e.g. 'CBN NFEM close'.")

    def handle(self, *args, **o):
        if o["set"]:
            try:
                rate = Decimal(o["set"])
            except InvalidOperation:
                raise CommandError("--set needs a number, e.g. --set 1520.50")
            r = FxRate.objects.create(ngn_per_usd=rate, source="manual", pinned=True, note=o["note"])
            self.stdout.write(self.style.SUCCESS(f"Pinned {r}. Charged rate: N{fx.effective(r):,.2f} per $1."))
            return
        r = fx.refresh(force=True)
        if r is None:
            raise CommandError("Could not fetch a live rate; the previous rate is unchanged. See the log for details.")
        self.stdout.write(self.style.SUCCESS(f"{r}. Charged rate (+{fx.margin() * 100:.0f}% margin): N{fx.effective(r):,.2f} per $1."))
