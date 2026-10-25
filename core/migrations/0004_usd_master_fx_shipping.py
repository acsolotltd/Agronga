import decimal

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_orders"),
    ]

    operations = [
        # ── Product: USD is the master price, naira is derived and read-only ──
        migrations.AlterField(
            model_name="product",
            name="price_usd",
            field=models.DecimalField(blank=True, decimal_places=2, help_text="The master price. Naira is calculated from this automatically. Leave blank to show 'Price on request'.", max_digits=10, null=True, verbose_name="Price ($)"),
        ),
        migrations.AlterField(
            model_name="product",
            name="price_ngn",
            field=models.DecimalField(blank=True, decimal_places=2, editable=False, help_text="Read-only. USD price x live exchange rate x (1 + margin), rounded to ₦10. Updated whenever the rate changes and when a naira customer checks out.", max_digits=12, null=True, verbose_name="Price (₦, automatic)"),
        ),
        migrations.AddField(
            model_name="product",
            name="weight_kg",
            field=models.DecimalField(decimal_places=3, default=decimal.Decimal("0.500"), help_text="Weight of ONE unit, packaging included. Used to calculate shipping. Ignored for bulk (tonne) goods.", max_digits=8, verbose_name="Shipping weight (kg)"),
        ),
        # ── Order: goods + shipping + the rate that was locked at checkout ──
        migrations.AddField(model_name="order", name="subtotal", field=models.DecimalField(decimal_places=2, default=0, max_digits=14)),
        migrations.AddField(model_name="order", name="shipping_fee", field=models.DecimalField(decimal_places=2, default=0, max_digits=14)),
        migrations.AlterField(
            model_name="order",
            name="total",
            field=models.DecimalField(decimal_places=2, help_text="Goods + shipping: the amount sent to Paystack.", max_digits=14),
        ),
        migrations.AddField(
            model_name="order",
            name="fx_rate",
            field=models.DecimalField(blank=True, decimal_places=4, help_text="Market rate plus margin, locked at checkout. Blank for dollar orders.", max_digits=12, null=True, verbose_name="Naira per $1 used"),
        ),
        migrations.AddField(model_name="order", name="fx_raw_rate", field=models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True, verbose_name="Market rate")),
        migrations.AddField(model_name="order", name="shipping_zone", field=models.CharField(blank=True, max_length=60)),
        migrations.AddField(model_name="order", name="shipping_note", field=models.CharField(blank=True, max_length=300)),
        # ── New tables ──
        migrations.CreateModel(
            name="FxRate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ngn_per_usd", models.DecimalField(decimal_places=4, help_text="Before the margin. Example: 1500 for ₦1,500 = $1.", max_digits=12, verbose_name="Market rate (₦ per $1)")),
                ("source", models.CharField(default="manual", editable=False, max_length=30)),
                ("pinned", models.BooleanField(default=False, help_text="Manual rates only: stop automatic updates from replacing this rate.")),
                ("note", models.CharField(blank=True, help_text="e.g. 'CBN NFEM close, 22 Oct' or 'parallel market'.", max_length=120)),
                ("fetched_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
            ],
            options={"verbose_name": "FX rate", "ordering": ["-fetched_at", "-id"]},
        ),
        migrations.CreateModel(
            name="ShippingZone",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=60)),
                ("countries", models.CharField(help_text="ISO codes separated by commas, e.g. 'US, CA'. Use * for every other country.", max_length=300)),
                ("base_usd", models.DecimalField(decimal_places=2, help_text="Charged once per order.", max_digits=8, verbose_name="Base fee ($)")),
                ("per_kg_usd", models.DecimalField(decimal_places=2, help_text="Charged per 0.5 kg step of cart weight.", max_digits=8, verbose_name="Per kg ($)")),
                ("free_over_usd", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name="Free shipping over ($)")),
                ("eta", models.CharField(blank=True, help_text="e.g. '7-14 business days'.", max_length=40, verbose_name="Delivery time")),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=100)),
            ],
            options={"ordering": ["sort_order", "name"]},
        ),
    ]
