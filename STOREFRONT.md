> **Production:** read `REVIEW.md` (what was fixed and what you must do) and `DEPLOY.md` (step by step). Local development now needs `DJANGO_DEBUG=1` in `.env`.

# AgroNGA storefront revamp

## Run it
```
pip install -r requirements.txt
python manage.py migrate          # adds migration 0002 (new product fields)
python manage.py seed_products    # loads products + shipping zones (never overwrites USD prices or weights you edited)
python manage.py update_rates     # fetch the live rate now and reprice naira
python manage.py runserver
python manage.py test core        # includes new cart/order tests
```
No Tailwind build is needed any more: styling is `static/css/agronga.css` and behaviour is `static/js/agronga.js` (no dependencies).
`static/js/app.js` (old Alpine code) and the `theme/static` Tailwind output are no longer loaded and can be deleted.

## Landing page = components
`theme/templates/landing/home.html` just includes these, in order. Reorder or remove freely:
`components/sections/` hero (slides) · ticker · shop · pillars · kaju_king · bulk_board · process · testimonials (auto-hidden when none) · quote_cta
Shared: header, mobile_menu, footer, cart_drawer, socials, currency_switch, product_card, add_button, page_header, field.
Hero slide copy: `HERO_SLIDES` in `core/views.py`.

## Pages
Home `/` · Shop `/products/` · Product `/products/<slug>/` · Cart & order request `/cart/` · About · FAQ · Testimonials · Contact · Privacy · Terms · 404

## Paystack payments (NGN + USD) and the webhook

1. `pip install -r requirements.txt`, copy `.env.example` to `.env`, and set `PAYSTACK_SECRET_KEY` (start with `sk_test_...`) and `SITE_URL` (your https domain in production).
2. `python manage.py migrate` (adds migration 0003: `Order` and `OrderItem`).
3. In the Paystack dashboard, Settings > API Keys & Webhooks, set the **Webhook URL** to `https://YOUR-DOMAIN/paystack/webhook/`. Paystack signs each call; the site rejects anything whose `x-paystack-signature` (HMAC-SHA512 of the raw body) does not match your secret key.
4. **Dollars:** USD charges only work once Paystack has enabled USD on your business. Ask Paystack support.
5. Local testing: expose the dev server with a tunnel (for example `ngrok http 8000`), set `SITE_URL` to the tunnel URL, and use Paystack test cards.

How it works
* Checkout (`/cart/`) posts slugs and quantities to `/order/`. The server re-prices from the database, saves an `Order`, calls Paystack `transaction/initialize` (amount in kobo or cents) and sends the customer to Paystack's page.
* Paystack returns the customer to `/order/<reference>/`, which verifies with Paystack and shows the result.
* **The webhook (`charge.success`) is the source of truth.** `core/orders.py: settle()` marks an order paid only if Paystack's amount and currency equal ours, does it once even if Paystack retries, and emails you and the customer. A mismatch sets the order to "Needs review" and emails you.
* "Request an invoice instead" keeps the old email flow for buyers who want a quote first.
* Orders appear read-only in Admin > Orders.
* If `PAYSTACK_SECRET_KEY` is empty the cart falls back to the email-only order request, so the site never breaks.

## Pricing: USD is the master price, naira follows the live rate

* **You edit USD only** (Admin > Products > "Price ($)"). The naira price is **read-only** and calculated as
  `USD x market rate x 1.08`, rounded to the nearest ₦10. The 8% margin (`NGN_MARGIN` in settings.py) covers payment fees and currency movement, and it applies to goods **and** shipping.
* The calculated naira price is **saved to the database** on every product save, every time a new rate arrives, and again when a naira customer checks out.
* **Live rate:** stored in Admin > FX rates. It refreshes automatically (at most hourly, `FX_TTL_MINUTES`) when anyone views the shop or checks out, and you can also schedule `python manage.py update_rates` (Windows Task Scheduler or cron, hourly).
  Sources are tried in order: open.er-api.com, then two mirrors of the free currency-api feed. They return the **market mid-rate**. If a feed is down, the last good rate stays in force. A single jump of more than 25% is rejected as bad data.
* **CBN or parallel-market rate:** the CBN publishes no public API and no parallel market feed is official, so none is wired in automatically. To use one, add a row in Admin > FX rates with the rate and tick **Pinned** (or run `python manage.py update_rates --set 1520.50 --note "CBN close"`). Pinned rates stop automatic updates until you untick or delete them. The 8% margin is still added on top.
* **No rate yet?** `FX_FALLBACK_NGN_PER_USD` (default 1500, a placeholder) is used until the first live rate is saved.

## Shipping (by buyer's country, live in naira)

* Checkout has a country selector. Every change recalculates shipping instantly through `/cart/quote/`; the Pay button stays disabled until the new total is on screen.
* Courier rates live in **Admin > Shipping zones**, in USD: `base + per-kg x cart weight` (weight rounded up to the next 0.5 kg), optional free-shipping threshold. Naira shipping = USD fee x live rate x 1.08, rounded **up** to the next ₦10.
* Each product has a **Shipping weight (kg)** per unit. Tonne-priced goods (sesame, peanuts, shea nuts) are **not** charged parcel shipping online: freight depends on volume and port, so it is quoted by email and flagged at checkout.
* A country with no zone (and no `*` catch-all zone) shows "Quoted by email" instead of a fee.
* The buyer is always charged the total they were shown. If the rate moves between the quote and the click, the server refuses (HTTP 409), shows the new total, and asks them to press Pay again.
* Each order stores subtotal, shipping, total and the exchange rate locked at checkout (read-only in Admin > Orders).

## How the cart works
* The cart lives in the browser (localStorage). `/order/` accepts only slugs, quantities, the country and the total the buyer saw; prices, shipping and rate are always recomputed on the server.

## Responsive and accuracy checks
Verified at 320, 360, 375, 390, 414, 600, 768, 820, 1024, 1280, 1440 and 1920px across 13 pages: no horizontal scroll, no off-screen elements, no clipped button text, no text under 12px, and 44px touch targets on phones and tablets (24px+ for mouse pointers on desktop). Safe-area insets (notches), dynamic viewport height, metric-matched fallback fonts and reduced-motion are handled.

## Confirm before launch (all in the code as TODO)
1. **USD prices are placeholders** (derived from the earlier naira prices at about ₦1,500 = $1). Because USD is now the master, the naira price will no longer equal the ₦ figures you first gave me. Set the real USD prices in Admin > Products.
1a. **Shipping weights and courier rates are placeholders.** Set each product's weight and your real rates in Admin > Shipping zones before launch.
2. **Units** ("per pack", "per tub", "per tonne") are inferred from price size.
3. **Social URLs** in `SOCIAL_LINKS` (settings.py) are guesses; set the real company pages.
4. "White Chocolate Coated" uses the brown Kaju King pack photo; swap in the white-chocolate pack.
5. Roasted *Salted* cashews (photo supplied) are not in your product list, so it is not sold; add a row to `catalog_data.py` to enable it.
6. Email backend is the console backend; configure real email for production.
7. **Delivery cost is not added at checkout.** The customer pays for the goods and delivery is arranged and confirmed by email afterwards (wording on the cart page). If you want delivery charged online, it needs shipping rates.
8. Replace the dev `SECRET_KEY` and set `DEBUG = False`, `ALLOWED_HOSTS`, and `SECURE_*` cookie settings before going live.
9. Have a lawyer review the Terms for refunds and returns now that payment is online.
