from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_usd_master_fx_shipping"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="authorization_url",
            field=models.URLField(blank=True, editable=False, help_text="Paystack payment page for this order.", max_length=300),
        ),
        migrations.AddField(
            model_name="order",
            name="idempotency_key",
            field=models.CharField(blank=True, editable=False, help_text="Stops a double-click or retry from creating two orders.", max_length=64, null=True, unique=True),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(fields=["status", "created_at"], name="order_status_created_idx"),
        ),
        migrations.CreateModel(
            name="PaymentEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("payload_hash", models.CharField(max_length=64, unique=True)),
                ("event", models.CharField(max_length=60)),
                ("reference", models.CharField(blank=True, db_index=True, max_length=60)),
                ("result", models.CharField(blank=True, help_text="Blank = received but not finished processing (Paystack will retry).", max_length=20)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-received_at"]},
        ),
    ]
