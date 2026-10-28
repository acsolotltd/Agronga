from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_order_status_emails"),
    ]

    operations = [
        migrations.AddField(model_name="product", name="sku", field=models.CharField(blank=True, help_text="Your stock code, e.g. CNRUNS001. Shown on the product page and on order emails.", max_length=30, null=True, unique=True, verbose_name="SKU")),
        migrations.AddField(model_name="product", name="net_weight", field=models.CharField(blank=True, help_text="e.g. 100 g (3.5 oz).", max_length=40, verbose_name="Pack size")),
        migrations.AddField(model_name="product", name="ingredients", field=models.TextField(blank=True, help_text="As printed on the pack, e.g. 'Cashews, Honey, Sea Salt'.")),
        migrations.AddField(model_name="product", name="allergens", field=models.TextField(blank=True, help_text="As printed on the pack, e.g. 'Contains tree nuts.'. Shown prominently on the product page.", verbose_name="Allergen information")),
        migrations.AddField(model_name="product", name="domestic_only", field=models.BooleanField(default=False, help_text="Tick if this product may not be exported (for example raw shea nuts). Buyers choosing any other delivery country cannot order it.", verbose_name="Nigeria delivery only")),
        migrations.AddField(model_name="orderitem", name="sku", field=models.CharField(blank=True, max_length=30)),
        migrations.AlterField(model_name="companyprofile", name="phones", field=models.TextField(blank=True, help_text="One number per line, e.g. +234-808-250-1525. The first one is shown in the header and footer. Blank = use the default.")),
    ]
