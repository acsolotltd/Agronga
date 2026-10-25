from django.core.management.base import BaseCommand

from core.models import FAQ, CompanyProfile

# Every answer below restates something agronga.com already says, or a policy stated on the new
# Contact and Terms pages. The owner must confirm the last one before launch.
FAQS = [
    ("Which currencies can I use?",
     "You can view prices and order in Nigerian naira (₦) or US dollars ($). Use the ₦ / $ switch at the top of any page. "
     "The price in the currency you choose is the price you pay."),
    ("Are your products non-GMO?", "Yes. We supply non-GMO agricultural products."),
    ("Do you sell raw and processed products?",
     "Both. Our range includes raw products such as cocoa beans and cashew nuts, and processed products such as "
     "roasted, honey glazed and chocolate coated cashew nuts, and shea butter."),
    ("How do I request a bulk quote?",
     "Use the quote form on the home page or the contact page. Tell us the product and quantity. We reply by email with "
     "price, availability and delivery details before you pay anything."),
    ("Where are you based and when are you open?",
     "We are at 722 Road, A Close, House 9, Festac Town, Lagos, Nigeria. We are open Sunday to Friday, 8:00 am to 5:00 pm (WAT)."),
    ("How can I tell a message really comes from AgroNGA?",
     "Pay only using the details in our written confirmation. We will never ask you to pay into a personal account or for "
     "your card number by email, phone or chat. If you are unsure, call +234 913 612 2996 before you pay."),
]

STILL_NEEDED = [
    "Do you ship to the United States, and how is shipping priced?",
    "Which payment methods do you accept (and from which countries)?",
    "Minimum order quantities and typical lead times",
    "Certifications and export documents you hold (NAFDAC, NEPC, phytosanitary, etc.)",
    "Your returns and damaged-goods process",
]


class Command(BaseCommand):
    help = "Create a blank Company profile and the starter FAQs. Safe to re-run; never overwrites edits."

    def handle(self, *args, **opts):
        CompanyProfile.objects.get_or_create(pk=1)
        made = 0
        for i, (q, a) in enumerate(FAQS):
            _, created = FAQ.objects.get_or_create(question=q, defaults={"answer": a, "sort_order": 10 * (i + 1)})
            made += created
        self.stdout.write(self.style.SUCCESS(f"Company profile ready, {made} FAQs added."))
        self.stdout.write(self.style.WARNING("Questions buyers will ask that only the owner can answer. Add them in Admin > FAQs:"))
        for line in STILL_NEEDED:
            self.stdout.write(f"  - {line}")
