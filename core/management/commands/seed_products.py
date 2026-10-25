from django.core.management.base import BaseCommand

from core.catalog_data import CATEGORIES, PRODUCTS, SHIPPING_ZONES
from core.models import Category, Product, ShippingZone


class Command(BaseCommand):
    help = ("Load the AgroNGA catalogue from core/catalog_data.py. Safe to re-run: it updates content, but NEVER overwrites "
            "a USD price or weight you have already edited, and only creates shipping zones that do not exist yet.")

    def handle(self, *args, **opts):
        cats = {}
        for name, slug, order in CATEGORIES:
            cats[slug], _ = Category.objects.update_or_create(slug=slug, defaults={"name": name, "sort_order": order})

        created = 0
        for i, p in enumerate(PRODUCTS):
            content = {
                "name": p["name"], "category": cats[p["category"]], "blurb": p["blurb"], "description": p["description"],
                "unit": p["unit"], "is_bulk": p.get("bulk", False), "quote_only": False,
                "badge": p.get("badge", ""), "accent": p.get("accent", "#1b6b3a"),
                "highlights": "\n".join(p.get("highlights", [])),
                "specs": "\n".join(f"{k}: {v}" for k, v in p.get("specs", [])),
                "gallery": "\n".join(p.get("gallery", [])),
                "is_featured": True, "is_active": True, "sort_order": p.get("featured", 100 + i),
            }
            obj = Product.objects.filter(slug=p["slug"]).first()
            if obj is None:
                Product.objects.create(slug=p["slug"], price_usd=p["usd"], weight_kg=p.get("weight", 0.5), **content)
                created += 1
            else:                                   # keep the owner's edited price and weight
                for k, v in content.items():
                    setattr(obj, k, v)
                obj.save()

        zones = 0
        for z in SHIPPING_ZONES:
            _, made = ShippingZone.objects.get_or_create(name=z["name"], defaults=z)
            zones += made

        self.stdout.write(self.style.SUCCESS(f"Products: {created} new, {len(PRODUCTS) - created} updated. Shipping zones: {zones} new."))
        self.stdout.write(self.style.WARNING("USD prices, weights and shipping rates are placeholders until you confirm them in the admin."))
