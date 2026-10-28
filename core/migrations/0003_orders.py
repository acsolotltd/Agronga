import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_storefront_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(editable=False, max_length=24, unique=True)),
                ("status", models.CharField(choices=[("pending", "Awaiting payment"), ("paid", "Paid"), ("requested", "Invoice requested"), ("failed", "Payment failed"), ("review", "Needs review (amount mismatch)")], db_index=True, default="pending", max_length=12)),
                ("currency", models.CharField(max_length=3)),
                ("total", models.DecimalField(decimal_places=2, max_digits=14)),
                ("name", models.CharField(max_length=80)),
                ("email", models.EmailField(max_length=254)),
                ("phone", models.CharField(max_length=30)),
                ("country", models.CharField(max_length=2)),
                ("address", models.CharField(max_length=300)),
                ("notes", models.CharField(blank=True, max_length=1000)),
                ("paystack_access_code", models.CharField(blank=True, max_length=60)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("channel", models.CharField(blank=True, help_text="card, bank_transfer, ...", max_length=30)),
                ("gateway_response", models.CharField(blank=True, max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("unit", models.CharField(blank=True, max_length=40)),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=14)),
                ("quantity", models.PositiveIntegerField()),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="core.order")),
                ("product", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="core.product")),
            ],
        ),
    ]
