import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_editable_pages"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="status",
            field=models.CharField(choices=[("pending", "Awaiting payment"), ("requested", "Invoice requested"), ("paid", "Paid"), ("processing", "Processing"), ("shipped", "Shipped"), ("delivered", "Delivered"), ("cancelled", "Cancelled"), ("refunded", "Refunded"), ("failed", "Payment failed"), ("review", "Needs review (amount mismatch)")], db_index=True, default="pending", max_length=12),
        ),
        migrations.AddField(
            model_name="order",
            name="tracking_info",
            field=models.CharField(blank=True, help_text="Included in the 'shipped' email, e.g. 'DHL 1234567890' or a tracking link.", max_length=200, verbose_name="Courier and tracking number"),
        ),
        migrations.AddField(
            model_name="order",
            name="customer_message",
            field=models.TextField(blank=True, help_text="Added to the next status email, then cleared. Plain text.", verbose_name="Note to the customer"),
        ),
        migrations.CreateModel(
            name="OrderStatusChange",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("from_status", models.CharField(blank=True, max_length=12)),
                ("to_status", models.CharField(max_length=12)),
                ("changed_by", models.CharField(blank=True, help_text="Admin username, or 'Paystack' for automatic payments.", max_length=80)),
                ("customer_notified", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="history", to="core.order")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
    ]
