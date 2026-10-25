from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="is_bulk",
            field=models.BooleanField(default=False, help_text="Sold by the tonne or in volume: show a 'Request bulk quote' button beside Add to cart."),
        ),
        migrations.AddField(
            model_name="product",
            name="badge",
            field=models.CharField(blank=True, help_text="Small label on the card, e.g. 'New flavour'.", max_length=30),
        ),
        migrations.AddField(
            model_name="product",
            name="accent",
            field=models.CharField(default="#1b6b3a", help_text="Hex colour used to tint this product's card and page.", max_length=7),
        ),
        migrations.AddField(
            model_name="product",
            name="highlights",
            field=models.TextField(blank=True, help_text="One short selling point per line (3 works best)."),
        ),
        migrations.AddField(
            model_name="product",
            name="specs",
            field=models.TextField(blank=True, help_text="One 'Label: value' per line. Only list facts that are true."),
        ),
        migrations.AddField(
            model_name="product",
            name="gallery",
            field=models.TextField(blank=True, help_text="Static image paths, one per line (e.g. img/products/cashew-nuts.jpg). Used when no photo is uploaded below."),
        ),
    ]
