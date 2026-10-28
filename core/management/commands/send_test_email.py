from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core import emails


class Command(BaseCommand):
    help = "Send a sample HTML email to check that Brevo, your API key and your sender address work: manage.py send_test_email you@example.com"

    def add_arguments(self, parser):
        parser.add_argument("to", help="Address to send the test to")

    def handle(self, *args, to, **opts):
        ctx = {"backend": settings.EMAIL_BACKEND.rsplit(".", 2)[-2], "sender": settings.DEFAULT_FROM_EMAIL, "inbox": settings.QUOTE_INBOX}
        try:
            emails.send("test", "AgroNGA email test", [to], ctx, reply_to=[settings.QUOTE_INBOX], tags=["test"])
        except Exception as e:  # noqa: BLE001
            raise CommandError(f"Sending failed: {e}") from e
        self.stdout.write(self.style.SUCCESS(f"Sent to {to} via {ctx['backend']}."))
        if "console" in settings.EMAIL_BACKEND:
            self.stdout.write(self.style.WARNING("BREVO_API_KEY is not set, so the message was only printed above, not delivered."))
