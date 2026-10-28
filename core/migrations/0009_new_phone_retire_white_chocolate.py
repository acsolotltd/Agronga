"""Data migration: (1) the website phone is now +234-808-250-1525; (2) the White Chocolate Coated product is retired.

Only values that still hold the OLD default numbers are replaced: a phone list you customised is left alone.
Retiring (not deleting) keeps old orders intact.
"""
import re

from django.db import migrations

NEW_PHONE = "+234-808-250-1525"
OLD_DIGITS = {"2349136122996", "2348160685030"}
OLD_IN_TEXT = re.compile(
    r"\+234[ -]?913[ -]?612[ -]?2996(?:\s*(?:,|/|and|or)\s*\+234[ -]?816[ -]?068[ -]?5030)?|\+234[ -]?816[ -]?068[ -]?5030")


def update_phone(apps, schema_editor):
    CompanyProfile = apps.get_model("core", "CompanyProfile")
    for profile in CompanyProfile.objects.all():
        numbers = [l.strip() for l in profile.phones.splitlines() if l.strip()]
        if numbers and all("".join(c for c in n if c.isdigit()) in OLD_DIGITS for n in numbers):
            profile.phones = NEW_PHONE
            profile.save(update_fields=["phones"])
    for model, fields in (("FAQ", ["answer"]), ("PageBlock", ["body"]), ("PageContent", ["body", "intro"]), ("CompanyProfile", ["story"])):
        Model = apps.get_model("core", model)
        for obj in Model.objects.all():
            changed = []
            for field in fields:
                value = getattr(obj, field) or ""
                new_value = OLD_IN_TEXT.sub(NEW_PHONE, value)
                if new_value != value:
                    setattr(obj, field, new_value)
                    changed.append(field)
            if changed:
                obj.save(update_fields=changed)


def retire_white_chocolate(apps, schema_editor):
    Product = apps.get_model("core", "Product")
    Product.objects.filter(slug="white-chocolate-coated-cashew-nuts").update(is_active=False, is_featured=False)


def forwards(apps, schema_editor):
    update_phone(apps, schema_editor)
    retire_white_chocolate(apps, schema_editor)
    try:
        from core import content
        content.invalidate()                       # pages cache the old phone for up to 10 minutes otherwise
    except Exception:                              # noqa: BLE001  (never block a migration on a cache problem)
        pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_catalogue_details"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
