"""The AgroNGA catalogue: single source of truth for `seed_products`.

USD is the MASTER price. Naira is calculated automatically (live rate + 8% margin) and is read-only.

TODO(owner) before launch, confirm in Admin > Products:
  * every USD price below is a PLACEHOLDER (derived from the earlier naira prices at about N1,500 per USD). The three newest Kaju King
    pouches (raw, salted, chocolate coated) had no price supplied: they use the same placeholder as the other pouches.
  * every `weight` (kg per unit, packaging included) is a PLACEHOLDER; shipping is calculated from it (pouches: 100 g + packaging).
  * `Cashew Nuts` (raw kernels, N12,500) is kept as a separate product from the Kaju King 100g raw pouch: confirm that is right.
  * LABEL CHECK: the salted pouch lists "Peanut Oil" as an ingredient but its allergen line says "Plant oil". Peanut oil is usually
    declared as a peanut allergen. Please confirm the wording with whoever prepared the label.
Product text (titles, descriptions, ingredients, allergens, SKUs) is as supplied by the owner; the only edit is the obvious typo
"Cain Sugar" -> "cane sugar" and sentence-case for allergen lists.
"""
from decimal import Decimal as D

CATEGORIES = [
    # (name, slug, sort_order)
    ("Cashew snacks", "cashew-snacks", 10),
    ("Raw & bulk", "raw-and-bulk", 20),
    ("Shea", "shea", 30),
]

# Paths are relative to static/. First image in `gallery` is the card image.
PRODUCTS = [
    dict(
        slug="chocolate-coated-cashew-nuts", sku="CNRUCC001", name="Kaju King Chocolate Coated Cashew Nuts, 100g Pouch",
        category="cashew-snacks", usd=D("1.70"), unit="per 100g pouch", weight=D("0.12"), net_weight="100 g (3.5 oz)",
        blurb="Kaju King Chocolate Coated Roasted Cashews, 3.5 oz, Gluten-Free, Non-GMO, Kosher, Crunchy Nuts.",
        badge="", accent="#7a5a46", featured=1,
        gallery=["img/products/chocolate-coated-cashew-nuts.jpg"],
        description=("Kaju King Chocolate Coated Cashews 3.5 oz (100g) Resealable Pouch, Chocolate Covered Flavored Cashew, Non-GMO, "
                     "Roasted Nuts, Kosher Dairy, Individual Snack Packs for On the Go, Work, School, Travel."),
        ingredients="Cashews, Chocolate (Sugar, Cocoa Butter, Whole Milk Powder), Sea Salt, Confectioners Glaze.",
        allergens="Contains tree nuts, milk from animals, sea salt, cocoa proteins.",
        highlights=["Roasted cashews in a chocolate coating", "Gluten-Free, Non-GMO, Kosher Dairy", "Resealable pouch"],
        specs=[("Type", "Roasted, chocolate coated"), ("Brand", "Kaju King"), ("Sold", "Per 100g pouch"), ("Origin", "Nigeria")],
    ),
    dict(
        slug="honey-glazed-cashew-nuts", sku="CNRSHG001", name="Kaju King Honey Glazed Cashew Nuts, 100g Pouch",
        category="cashew-snacks", usd=D("1.70"), unit="per 100g pouch", weight=D("0.12"), net_weight="100 g (3.5 oz)",
        blurb="Kaju King Honey Glazed Roasted Cashews, 3.5 oz, Gluten-Free, Non-GMO, Kosher, Crunchy Nuts.",
        badge="", accent="#d9822b", featured=2,
        gallery=["img/products/honey-glazed-cashew-nuts.jpg"],
        description=("Kaju King Honey Glazed Cashews 3.5 oz (100g) Resealable Bag, Non-GMO, Contains No Artificial Preservatives, "
                     "Flavors or Synthetic Colors."),
        ingredients="Cashews, Honey, Sea Salt, Sugar granules, Cinnamon.",
        allergens="Contains tree nuts, pollen and proteins from bees, cane sugar, sea salt, cinnamon.",
        highlights=["Honey glazed roasted cashews", "Gluten-Free, Non-GMO, Kosher", "No artificial preservatives, flavors or colors"],
        specs=[("Type", "Roasted, honey glazed"), ("Brand", "Kaju King"), ("Sold", "Per 100g pouch"), ("Origin", "Nigeria")],
    ),
    dict(
        slug="salted-cashew-nuts", sku="CNRSLS001", name="Kaju King Roasted Salted Cashew Nuts, 100g Pouch",
        category="cashew-snacks", usd=D("1.70"), unit="per 100g pouch", weight=D("0.12"), net_weight="100 g (3.5 oz)",
        blurb="Kaju King Roasted Lightly Salted Cashews, 3.5 oz, Gluten-Free, Non-GMO, Kosher, Vegan, Crunchy Nuts.",
        badge="", accent="#4f7a2e", featured=3,
        gallery=["img/products/roasted-salted-cashew-pack.jpg"],
        description=("Kaju King Roasted Lightly Salted Cashews 3.5 oz (100g) Non-GMO, Kosher, Vegan, Resealable Pouch - Perfect for "
                     "Snacking, Baking, and On-the-Go Fuel."),
        ingredients="Cashews, Sea Salt, Peanut Oil.",
        allergens="Contains tree nuts, plant oil, sea salt.",
        highlights=["Roasted and lightly salted", "Gluten-Free, Non-GMO, Kosher, Vegan", "Resealable pouch"],
        specs=[("Type", "Roasted, lightly salted"), ("Brand", "Kaju King"), ("Sold", "Per 100g pouch"), ("Origin", "Nigeria")],
    ),
    dict(
        slug="roasted-unsalted-cashew-nuts", sku="CNRUNS001", name="Kaju King Roasted Cashew Nuts, 100g Pouch",
        category="cashew-snacks", usd=D("1.70"), unit="per 100g pouch", weight=D("0.12"), net_weight="100 g (3.5 oz)",
        blurb="Kaju King Roasted Unsalted Cashews, 3.5 oz, Gluten-Free, Non-GMO, Kosher, Vegan, Crunchy Nuts.",
        badge="", accent="#2f5f9a", featured=4,
        gallery=["img/products/roasted-unsalted-cashew-nuts.jpg"],
        description=("Kaju King Roasted Unsalted Cashews 3.5 oz (100g) Gluten-Free, Non-GMO, Kosher, Vegan, Crunchy Nuts, Lightly Roasted, "
                     "No Added Salt, Source of Protein & Iron, Savory Snacks."),
        ingredients="Cashews.",
        allergens="Contains tree nuts.",
        highlights=["Lightly roasted, no added salt", "Gluten-Free, Non-GMO, Kosher, Vegan", "Source of protein and iron"],
        specs=[("Type", "Roasted, unsalted"), ("Brand", "Kaju King"), ("Sold", "Per 100g pouch"), ("Origin", "Nigeria")],
    ),
    dict(
        slug="raw-cashew-nuts", sku="CNRWUS001", name="Kaju King Raw Cashew Nuts, 100g Pouch",
        category="cashew-snacks", usd=D("1.70"), unit="per 100g pouch", weight=D("0.12"), net_weight="100 g (3.5 oz)",
        blurb="Kaju King Raw Unsalted Cashews, 3.5 oz, Gluten-Free, Non-GMO, Kosher, Vegan, Crunchy Nuts.",
        badge="Raw", accent="#b3342c", featured=5,
        gallery=["img/products/raw-cashew-pack.jpg"],
        description=("Kaju King Raw Unsalted Cashews 3.5 oz (100g) Gluten-Free, Non-GMO, Kosher, Vegan, Crunchy Nuts, No Added Salt, "
                     "Source of Protein & Iron, Savory Snacks."),
        ingredients="Cashews.",
        allergens="Contains tree nuts.",
        highlights=["Raw, no added salt", "Gluten-Free, Non-GMO, Kosher, Vegan", "Source of protein and iron"],
        specs=[("Type", "Raw, unsalted"), ("Brand", "Kaju King"), ("Sold", "Per 100g pouch"), ("Origin", "Nigeria")],
    ),
    dict(
        slug="cashew-nuts", sku="", name="Cashew Nuts",
        category="cashew-snacks", usd=D("8.50"), unit="per pack", weight=D("1.0"),
        blurb="Raw cashew kernels, non-GMO.",
        badge="Raw", accent="#b3342c", featured=6,
        gallery=["img/products/cashew-nuts.jpg"],
        description=(
            "Raw, whole cashew kernels from Nigerian farms. Non-GMO and ready for the kitchen: "
            "roast them, blend them into cashew milk and cream, or use them in curries and baking.\n\n"
            "Looking for a ready-to-snack pouch? See the Kaju King range."),
        allergens="Contains tree nuts.",
        highlights=["Raw whole kernels", "Non-GMO", "Roast, blend or bake"],
        specs=[("Type", "Raw kernels"), ("Quality", "Non-GMO"), ("Sold", "Per pack"), ("Origin", "Nigeria")],
    ),
    dict(
        slug="shea-butter", sku="", name="Shea Butter",
        category="shea", usd=D("6.50"), unit="per tub", weight=D("1.0"),
        blurb="Natural shea butter for skin care and cooking.",
        badge="", accent="#c9b46a", featured=7,
        gallery=["img/products/shea-butter.jpg"],
        description=(
            "Natural shea butter in its traditional creamy-white form. Use it as a rich body and "
            "hair moisturiser, in homemade balms and soaps, or in cooking.\n\n"
            "Buying for a cosmetics line? Send a quote request and we will confirm volumes and "
            "delivery."),
        highlights=["Natural, unprocessed look", "Skin, hair and kitchen use", "Bulk on request"],
        specs=[("Type", "Natural shea butter"), ("Sold", "Per tub"), ("Origin", "Nigeria")],
    ),
    dict(
        slug="sesame-seeds", sku="", name="Sesame Seeds",
        category="raw-and-bulk", usd=D("1690"), unit="per tonne", weight=D("1000"), bulk=True,
        blurb="Cleaned sesame seeds, sold by the tonne.",
        badge="Bulk", accent="#b98d52", featured=8,
        gallery=["img/products/sesame-seeds.jpg"],
        description=(
            "Cleaned sesame seeds for processors, oil producers, bakers and exporters. "
            "Sold by the tonne.\n\n"
            "Freight and final price vary by destination, so we confirm your order by email "
            "before any payment."),
        allergens="Contains sesame.",
        highlights=["Cleaned seed", "Sold by the tonne", "Quote and invoice before payment"],
        specs=[("Type", "Cleaned sesame seed"), ("Sold", "Per tonne"), ("Origin", "Nigeria"),
               ("Order", "Confirmed by email before payment")],
    ),
    dict(
        slug="peanuts", sku="", name="Peanuts",
        category="raw-and-bulk", usd=D("585"), unit="per tonne", weight=D("1000"), bulk=True,
        blurb="Raw groundnuts in bulk, sold by the tonne.",
        badge="Bulk", accent="#8b4332", featured=9,
        gallery=["img/products/peanuts.jpg"],
        description=(
            "Raw peanuts (groundnuts) from Nigerian farms, for processors, snack makers and "
            "oil producers. Sold by the tonne.\n\n"
            "We confirm price, stock and delivery by email before any payment."),
        allergens="Contains peanuts.",
        highlights=["Raw groundnuts", "Sold by the tonne", "Quote and invoice before payment"],
        specs=[("Type", "Raw peanuts"), ("Sold", "Per tonne"), ("Origin", "Nigeria"),
               ("Order", "Confirmed by email before payment")],
    ),
    dict(
        slug="shea-nuts", sku="", name="Shea Nuts",
        category="raw-and-bulk", usd=D("200"), unit="per tonne", weight=D("1000"), bulk=True, domestic=True,
        blurb="Dried shea nuts for butter and oil processors. Delivery within Nigeria only.",
        badge="Bulk, Nigeria only", accent="#6b4630", featured=10,
        gallery=["img/products/shea-nuts.jpg", "img/products/shea-nuts-heap.jpg"],
        description=(
            "Dried shea nuts for processors who extract shea butter and oil. Sold by the tonne.\n\n"
            "Available for delivery within Nigeria only: the export of shea nuts is prohibited by law, so we cannot ship this product "
            "to any other country.\n\n"
            "We confirm price, stock and delivery by email before any payment."),
        highlights=["Dried whole nuts", "Sold by the tonne", "Delivery within Nigeria only"],
        specs=[("Type", "Dried shea nuts"), ("Sold", "Per tonne"), ("Origin", "Nigeria"),
               ("Delivery", "Within Nigeria only (export prohibited)"), ("Order", "Confirmed by email before payment")],
    ),
]

# Products that no longer exist. `seed_products` switches them off (kept, not deleted, so old orders stay intact).
RETIRED_SLUGS = ["white-chocolate-coated-cashew-nuts"]

# Addresses from the OLD agronga.com shop -> the new product slug. Used for permanent (301) redirects so old links,
# bookmarks and search results keep working. Old URL shape: /product/<key>/
LEGACY_PRODUCT_URLS = {
    "roasted_cashew_nuts": "roasted-unsalted-cashew-nuts",
    "raw_cashew_nuts": "raw-cashew-nuts",
    "salted_cashew_nuts": "salted-cashew-nuts",
    "honey_glazed_cashew_nuts": "honey-glazed-cashew-nuts",
    "chocolate_coated_cashew_nuts": "chocolate-coated-cashew-nuts",
    "white_chocolate_coated_cashew_nuts": "chocolate-coated-cashew-nuts",
    "cashew_nuts": "cashew-nuts",
    "shea_butter": "shea-butter",
    "peanuts": "peanuts",
    "sesame-seeds": "sesame-seeds",
    "sesame_seeds": "sesame-seeds",
    "shea_nuts": "shea-nuts",
}


# Courier rate card in USD. PLACEHOLDERS: replace with your courier's real rates in Admin > Shipping zones.
# Fee = base + per_kg x (cart weight rounded up to the next 0.5 kg). Naira shipping = USD x live rate x (1 + margin).
SHIPPING_ZONES = [
    dict(name="Nigeria", countries="NG", base_usd=D("2.50"), per_kg_usd=D("0.90"), eta="2-5 business days", sort_order=10),
    dict(name="Rest of Africa", countries="GH, ZA, KE, EG, SN, CI, CM, TZ, UG, ET, MA", base_usd=D("14.00"), per_kg_usd=D("6.00"), eta="5-10 business days", sort_order=20),
    dict(name="USA & Canada", countries="US, CA", base_usd=D("18.00"), per_kg_usd=D("8.50"), eta="7-14 business days", sort_order=30),
    dict(name="UK & Europe", countries="GB, IE, DE, FR, NL, BE, ES, IT, PT, SE, NO, DK, CH, AT, PL", base_usd=D("20.00"), per_kg_usd=D("9.00"), eta="7-14 business days", sort_order=40),
    dict(name="Rest of the world", countries="*", base_usd=D("26.00"), per_kg_usd=D("12.00"), eta="10-21 business days", sort_order=90),
]
