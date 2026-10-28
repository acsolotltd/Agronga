import django.db.models.deletion
from django.db import migrations, models

import core.models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_payment_hardening"),
    ]

    operations = [
        migrations.AddField(model_name="companyprofile", name="phones", field=models.TextField(blank=True, help_text="One number per line, e.g. +234 913 612 2996. The first one is shown in the header and footer. Blank = use the default.")),
        migrations.AddField(model_name="companyprofile", name="email", field=models.EmailField(blank=True, help_text="Public contact email (shown without exposing it to spam bots). Blank = use the default.", max_length=254)),
        migrations.AddField(model_name="companyprofile", name="address", field=models.CharField(blank=True, help_text="Blank = use the default.", max_length=300)),
        migrations.AddField(model_name="companyprofile", name="opening_hours", field=models.CharField(blank=True, help_text="e.g. Sunday to Friday, 8:00 am to 5:00 pm (WAT). Blank = use the default.", max_length=120)),
        migrations.AddField(model_name="companyprofile", name="map_url", field=models.URLField(blank=True, help_text="Link to your location on Google Maps. Blank = no map link.", max_length=300)),
        migrations.AddField(model_name="companyprofile", name="short_location", field=models.CharField(blank=True, help_text="Short place name for the top bar, e.g. 'Festac Town, Lagos'. Blank = the default.", max_length=60)),
        migrations.CreateModel(
            name="PageContent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.CharField(choices=[("about", "About us"), ("contact", "Contact"), ("faq", "FAQ"), ("testimonials", "Testimonials")], max_length=20, unique=True, verbose_name="Page")),
                ("eyebrow", models.CharField(blank=True, max_length=60, verbose_name="Small label above the title")),
                ("title", models.CharField(blank=True, help_text="Blank = the default title.", max_length=120)),
                ("intro", models.CharField(blank=True, help_text="Shown under the title. Blank = the default.", max_length=300, verbose_name="Intro sentence")),
                ("header_image", models.ImageField(blank=True, help_text="Wide photo behind the title. 2000 x 800 px, JPG/PNG/WebP, under 6 MB. It is optimised automatically for phones and desktops. Blank = the default photo.", upload_to="pages/original/", validators=[core.models.validate_header_image], verbose_name="Header photo")),
                ("header_position", models.CharField(default="50% 45%", help_text="Where to focus when the photo is cropped on narrow screens, e.g. '50% 30%' (horizontal, vertical) or 'center top'.", max_length=20, validators=[core.models.validate_image_position], verbose_name="Which part of the photo to keep")),
                ("header_variants", models.JSONField(blank=True, default=list, editable=False)),
                ("body", models.TextField(blank=True, help_text="Blank line = new paragraph. Blank = the default text (About page).", verbose_name="Main text")),
                ("side_image", models.ImageField(blank=True, help_text="Optional photo beside the main text (About page). Blank = the default.", upload_to="pages/original/", validators=[core.models.validate_header_image], verbose_name="Side photo")),
                ("side_alt", models.CharField(blank=True, help_text="Describe the side photo for screen readers and search engines, e.g. 'Dried shea nuts in a heap'.", max_length=140, verbose_name="Side photo description")),
                ("side_variants", models.JSONField(blank=True, default=list, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "Page content", "verbose_name_plural": "Page content", "ordering": ["slug"]},
        ),
        migrations.CreateModel(
            name="PageBlock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("heading", models.CharField(blank=True, max_length=120)),
                ("body", models.TextField(help_text="Blank line = new paragraph. Start a line with '- ' for a bullet point.")),
                ("callout", models.BooleanField(default=False, help_text="Show in a tinted box (good for safety notices).", verbose_name="Highlight box")),
                ("sort_order", models.PositiveSmallIntegerField(default=100)),
                ("is_active", models.BooleanField(default=True)),
                ("page", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="blocks", to="core.pagecontent")),
            ],
            options={"ordering": ["sort_order", "id"]},
        ),
    ]
