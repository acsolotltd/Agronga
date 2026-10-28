from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from core.content import DEFAULTS
from core.models import CompanyProfile, PageBlock, PageContent


class Command(BaseCommand):
    help = ("Create the editable About, Contact, FAQ and Testimonials pages (and the starter FAQs) from the current site text, "
            "and fill any blank contact details in Company profile. Safe to re-run: it never overwrites anything you edited.")

    def handle(self, *args, **opts):
        call_command("seed_content", verbosity=0)                     # Company profile row + starter FAQs

        base = settings.COMPANY
        profile, _ = CompanyProfile.objects.get_or_create(pk=1)
        defaults = {
            "phones": "\n".join(filter(None, [base["phone"], base.get("phone2", "")])),
            "email": f"{base['email_user']}@{base['email_domain']}",
            "address": base["address"], "short_location": base.get("short_location", ""), "opening_hours": base["hours"], "map_url": base.get("map_url", ""),
        }
        filled = [k for k, v in defaults.items() if not getattr(profile, k) and setattr(profile, k, v) is None]
        if filled:
            profile.save()

        created = 0
        for slug, d in DEFAULTS.items():
            page, made = PageContent.objects.get_or_create(slug=slug, defaults={"title": d["title"], "intro": d["intro"], "body": d["body"]})
            if made:
                created += 1
                for i, b in enumerate(d["blocks"]):
                    PageBlock.objects.create(page=page, heading=b["heading"], body=b["body"], callout=b["callout"], sort_order=10 * (i + 1))
        self.stdout.write(self.style.SUCCESS(f"Pages: {created} created. Company contact fields filled: {', '.join(filled) or 'none (already set)'}."))
        self.stdout.write("Next: Admin > Page content > upload a header photo for each page.")
