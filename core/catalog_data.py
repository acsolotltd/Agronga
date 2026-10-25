"""The AgroNGA catalogue: single source of truth for `seed_products`.

USD is the MASTER price. Naira is calculated automatically (live rate + 8% margin) and is read-only.

TODO(owner) before launch, confirm in Admin > Products:
  * every USD price below is a PLACEHOLDER (derived from the earlier naira prices at about N1,500 per USD).
  * every `weight` (kg per unit, packaging included) is a PLACEHOLDER; shipping is calculated from it.
  * every `unit` is inferred from the price scale ("per pack", "per tub", "per tonne").
  * `White Chocolate Coated Cashew Nuts` uses the brown Kaju King pack photo. Swap in the white pack shot.
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
        slug="white-chocolate-coated-cashew-nuts", name="White Chocolate Coated Cashew Nuts",
        category="cashew-snacks", usd=D("1.70"), unit="per pack", weight=D("0.25"),
        blurb="Crunchy cashews wrapped in smooth white chocolate.",
        badge="", accent="#7a5a46", featured=1,
        gallery=["img/products/white-chocolate-coated-cashew-nuts.jpg"],
        description=(
            "Whole cashew kernels roasted for crunch, then coated in smooth white chocolate. "
            "A sweet, creamy snack that is easy to share and easy to gift.\n\n"
            "Part of the Kaju King range. Packed in a resealable stand-up pouch with the full "
            "nutrition panel on the back."),
        highlights=["Whole cashew kernels", "Smooth white chocolate coating", "Resealable pouch"],
        specs=[("Type", "Roasted, chocolate-coated"), ("Brand", "Kaju King"), ("Sold", "Per pack"),
               ("Origin", "Nigeria")],
    ),
    dict(
        slug="honey-glazed-cashew-nuts", name="Honey Glazed Cashew Nuts",
        category="cashew-snacks", usd=D("1.70"), unit="per pack", weight=D("0.25"),
        blurb="Roasted cashews with a light honey glaze.",
        badge="", accent="#d9822b", featured=2,
        gallery=["img/products/honey-glazed-cashew-nuts.jpg"],
        description=(
            "Roasted cashews finished with a light honey glaze: sweet up front, with the natural "
            "buttery crunch of the nut underneath.\n\n"
            "Part of the Kaju King range. Good with tea, on yoghurt or straight from the pouch."),
        highlights=["Whole roasted cashews", "Honey glaze", "Resealable pouch"],
        specs=[("Type", "Roasted, honey-glazed"), ("Brand", "Kaju King"), ("Sold", "Per pack"),
               ("Origin", "Nigeria")],
    ),
    dict(
        slug="roasted-unsalted-cashew-nuts", name="Roasted Unsalted Cashew Nuts",
        category="cashew-snacks", usd=D("1.70"), unit="per pack", weight=D("0.25"),
        blurb="Dry roasted, nothing added. Just cashew.",
        badge="", accent="#2f5f9a", featured=3,
        gallery=["img/products/roasted-unsalted-cashew-nuts.jpg"],
        description=(
            "Cashews roasted and left unsalted, so the natural flavour comes through. "
            "A simple everyday snack that also works in cooking, baking and salads.\n\n"
            "Part of the Kaju King range."),
        highlights=["Roasted, no added salt", "Whole kernels", "Resealable pouch"],
        specs=[("Type", "Roasted, unsalted"), ("Brand", "Kaju King"), ("Sold", "Per pack"),
               ("Origin", "Nigeria")],
    ),
    dict(
        slug="cashew-nuts", name="Cashew Nuts",
        category="cashew-snacks", usd=D("8.50"), unit="per pack", weight=D("1.0"),
        blurb="Raw cashew kernels, non-GMO.",
        badge="Raw", accent="#b3342c", featured=4,
        gallery=["img/products/cashew-nuts.jpg", "img/products/raw-cashew-pack.jpg"],
        description=(
            "Raw, whole cashew kernels from Nigerian farms. Non-GMO and ready for the kitchen: "
            "roast them, blend them into cashew milk and cream, or use them in curries and baking.\n\n"
            "Also available packed under the Kaju King label."),
        highlights=["Raw whole kernels", "Non-GMO", "Roast, blend or bake"],
        specs=[("Type", "Raw kernels"), ("Quality", "Non-GMO"), ("Sold", "Per pack"),
               ("Origin", "Nigeria")],
    ),
    dict(
        slug="shea-butter", name="Shea Butter",
        category="shea", usd=D("6.50"), unit="per tub", weight=D("1.0"),
        blurb="Natural shea butter for skin care and cooking.",
        badge="", accent="#c9b46a", featured=5,
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
        slug="sesame-seeds", name="Sesame Seeds",
        category="raw-and-bulk", usd=D("1690"), unit="per tonne", weight=D("1000"), bulk=True,
        blurb="Cleaned sesame seeds, sold by the tonne.",
        badge="Bulk", accent="#b98d52", featured=6,
        gallery=["img/products/sesame-seeds.jpg"],
        description=(
            "Cleaned sesame seeds for processors, oil producers, bakers and exporters. "
            "Sold by the tonne.\n\n"
            "Freight and final price vary by destination, so we confirm your order by email "
            "before any payment."),
        highlights=["Cleaned seed", "Sold by the tonne", "Quote and invoice before payment"],
        specs=[("Type", "Cleaned sesame seed"), ("Sold", "Per tonne"), ("Origin", "Nigeria"),
               ("Order", "Confirmed by email before payment")],
    ),
    dict(
        slug="peanuts", name="Peanuts",
        category="raw-and-bulk", usd=D("585"), unit="per tonne", weight=D("1000"), bulk=True,
        blurb="Raw groundnuts in bulk, sold by the tonne.",
        badge="Bulk", accent="#8b4332", featured=7,
        gallery=["img/products/peanuts.jpg"],
        description=(
            "Raw peanuts (groundnuts) from Nigerian farms, for processors, snack makers and "
            "oil producers. Sold by the tonne.\n\n"
            "We confirm price, stock and delivery by email before any payment."),
        highlights=["Raw groundnuts", "Sold by the tonne", "Quote and invoice before payment"],
        specs=[("Type", "Raw peanuts"), ("Sold", "Per tonne"), ("Origin", "Nigeria"),
               ("Order", "Confirmed by email before payment")],
    ),
    dict(
        slug="shea-nuts", name="Shea Nuts",
        category="raw-and-bulk", usd=D("200"), unit="per tonne", weight=D("1000"), bulk=True,
        blurb="Dried shea nuts for butter and oil processors.",
        badge="Bulk", accent="#6b4630", featured=8,
        gallery=["img/products/shea-nuts.jpg", "img/products/shea-nuts-heap.jpg"],
        description=(
            "Dried shea nuts for processors who extract shea butter and oil. Sold by the tonne.\n\n"
            "We confirm price, stock and delivery by email before any payment."),
        highlights=["Dried whole nuts", "Sold by the tonne", "Quote and invoice before payment"],
        specs=[("Type", "Dried shea nuts"), ("Sold", "Per tonne"), ("Origin", "Nigeria"),
               ("Order", "Confirmed by email before payment")],
    ),
]


# Courier rate card in USD. PLACEHOLDERS: replace with your courier's real rates in Admin > Shipping zones.
# Fee = base + per_kg x (cart weight rounded up to the next 0.5 kg). Naira shipping = USD x live rate x (1 + margin).
SHIPPING_ZONES = [
    dict(name="Nigeria", countries="NG", base_usd=D("2.50"), per_kg_usd=D("0.90"), eta="2-5 business days", sort_order=10),
    dict(name="Rest of Africa", countries="GH, ZA, KE, EG, SN, CI, CM, TZ, UG, ET, MA", base_usd=D("14.00"), per_kg_usd=D("6.00"), eta="5-10 business days", sort_order=20),
    dict(name="USA & Canada", countries="US, CA", base_usd=D("18.00"), per_kg_usd=D("8.50"), eta="7-14 business days", sort_order=30),
    dict(name="UK & Europe", countries="GB, IE, DE, FR, NL, BE, ES, IT, PT, SE, NO, DK, CH, AT, PL", base_usd=D("20.00"), per_kg_usd=D("9.00"), eta="7-14 business days", sort_order=40),
    dict(name="Rest of the world", countries="*", base_usd=D("26.00"), per_kg_usd=D("12.00"), eta="10-21 business days", sort_order=90),
]
