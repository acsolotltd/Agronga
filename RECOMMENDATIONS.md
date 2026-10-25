# AgroNGA: review, design strategy and build notes

## 1. What I reviewed on agronga.com

I read the text and links of the homepage and `/products/` page. I did **not** see the rendered
visuals, measure speed, inspect response headers or look up DNS, so those are listed as checks to run, not findings.

| Finding | Why it matters |
|---|---|
| Built on WordPress, Elementor and WooCommerce | Largest target for spam bots and plugin exploits; heavy pages on mobile data |
| Prices in ₦ only; header cart shows `₦0.00` | No path for US buyers |
| Top bar phone is `987-456-(1023)`, footer has the real `+234` numbers | Placeholder data on a live site undermines trust |
| Facebook and LinkedIn icons point to a personal profile, not the company | Looks like phishing to cautious buyers |
| Twitter and YouTube icons in the header have no company target | Dead or generic links |
| Nav "Contact" goes to `/?page_id=25`, the hero button goes to `/contact/` | Two URLs for one page; messy for SEO |
| Product prices have no unit: coated cashew ₦2,500, sesame ₦2,540,000 | Buyers cannot tell per pack from per tonne |
| `info@agronga.com` is a plain `mailto:` in the HTML | Harvested by scrapers; main source of inbound spam |
| Headline typo: "agro industry at it's best" | Small, but visible on the first screen |
| Product images carry alt text like "1", "5", "g1" | Poor accessibility and image SEO |

## 2. Design strategy

**Who it serves.** Two buyers with different needs: Nigerian retail and trade buyers (₦, local cards or transfer)
and American buyers (USD, international cards, often bulk). The site's job is to make the price
trustworthy in either currency and give bulk buyers a direct route to a quote.

**One idea carries the design:** the price sheet in the hero. It looks like a commodity trader's board,
and it flips between ₦ and $ in place. Everything else stays quiet.

- **Palette:** leaf green `#1b6b3a`, sesame gold `#d99a1c`, cool green-tinted neutrals. Dark mode has its own tuned values, not an inversion.
- **Type:** Bricolage Grotesque (display) with Figtree (body). Tabular numerals on every price.
- **Mobile first:** 16px gutters, 44px touch targets, `text-base` inputs (stops iOS zoom), safe-area insets, `100dvh` panels.
- **Content:** names things plainly, makes only claims the current site already makes (non-GMO, raw or processed, Lagos).

### Currency (the core decision)
1. **Store both prices per product** (`price_ngn`, `price_usd`). Do not convert live. FX movement would show customers a price you did not set, and card refunds break.
2. **Default by visitor country** (CDN header), then **remember the choice in a cookie**. The switch is always visible in the header.
3. **Charge in the currency shown**, with the right processor:
   - ₦: Paystack or Flutterwave (cards, bank transfer, USSD)
   - $: Stripe or PayPal, if your business entity and settlement account support it. Flutterwave also settles USD, so one provider is an option
4. **Bulk and export (sesame, peanuts, shea nuts, cocoa by the tonne) should be quote-based**, not cart-based. Prices move, freight varies, and buyers expect an invoice. That is why the page leads with a quote form.
5. **Shipping and duties for the US** are per order. Show them before payment and never bake a guess into the product price.

### Preventing spam and phishing
**Inbound spam (form and email)**
- Contact is a form, not a visible email. The footer address is assembled by JS, so scrapers never see a `mailto:`.
- The form has four layers: CSRF, a hidden honeypot field, a signed time trap (rejects submissions under 3 seconds), and per-IP rate limiting.
- Next step: add **Cloudflare Turnstile** (free, no puzzles) and verify the token server-side.
- Django's `EmailMessage` rejects header injection. The subject is built from a fixed list, never user text.

**Spoofing of your domain (what makes phishing against your customers possible)**
Set these DNS records at your domain host. Start DMARC at `p=none`, read the reports for two to four weeks, then move to `quarantine`, then `reject`.
```
SPF    TXT  @                 "v=spf1 include:<your-mail-provider> -all"
DKIM   TXT  <selector>._domainkey   (value supplied by your mail provider)
DMARC  TXT  _dmarc            "v=DMARC1; p=none; rua=mailto:dmarc@agronga.com; adkim=s; aspf=s"
```
- Send site mail from `no-reply@agronga.com` through a provider (Postmark, Amazon SES, Zoho). Never use a free Gmail address as sender.
- Use Google Workspace or Zoho for `info@`, with spam filtering on.

**Protecting customers**
- All payments on the processor's hosted page, so card data never touches your server.
- Never ask for card details, bank transfers to personal accounts or "payment confirmation" by WhatsApp. Say so in order emails and on the site.
- Order confirmations link back to `agronga.com`; every email states the order number and the amount in the currency shown.
- Publish **one** set of social links that belong to the company.

## 3. What's in this package

```
theme/static_src/src/styles.css      Tailwind 4 tokens, dark mode, utilities
theme/templates/base.html            Document shell: no-flash theme, SEO, htmx, skip link
theme/templates/components/
    header.html                      Sticky header, nav, currency + theme switch, cart, mobile menu
    theme_switch.html                Light / System / Dark radiogroup
    currency_switch.html             ₦ / $ radiogroup (works without JS)
    footer.html                      Contact, hours, links
    field.html                       Form field wrapper
theme/templates/landing/home.html    Hero price sheet, trust row, products, order steps, markets, quote
theme/templates/landing/partials/    hero_sheet, product_grid, quote_form (htmx fragments)
static/js/app.js                     Alpine (CSP build) stores + components: theme, menu, currency, email reveal, form state
core/                                models (Category, Product), admin, seed command, sitemaps, tests, currency, context processor, forms, views, urls, `{% price %}` tag
theme/templates/products/            list.html, detail.html, partials/catalog.html (htmx fragment)
theme/templates/pages/               about, faq, testimonials, contact, privacy, terms (+ legal.html layout)
```

### Wiring (about 10 minutes)
```python
# settings.py
INSTALLED_APPS += ["django_htmx", "tailwind", "theme", "core"]
MIDDLEWARE += ["django_htmx.middleware.HtmxMiddleware"]
TEMPLATES[0]["OPTIONS"]["context_processors"] += ["core.context_processors.site"]
TAILWIND_APP_NAME = "theme"
DEFAULT_FROM_EMAIL = "AgroNGA <no-reply@agronga.com>"
QUOTE_INBOX = "info@agronga.com"

# Production
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": "redis://..."}}  # rate limiting needs a shared cache
```
```python
# project urls.py
path("", include("core.urls")),
```
```bash
mkdir -p static/js/vendor
curl -L https://cdn.jsdelivr.net/npm/htmx.org@2/dist/htmx.min.js -o static/js/vendor/htmx.min.js
curl -L https://cdn.jsdelivr.net/npm/@alpinejs/csp@3/dist/cdn.min.js -o static/js/vendor/alpine.csp.min.js
# Pin exact versions in those URLs, or install both via npm in theme/static_src and copy the dist files.
python manage.py tailwind install && python manage.py tailwind start
```
django-tailwind expects `base.html` in `theme/templates/`. The `@source` line in `styles.css` makes Tailwind scan templates in all apps.

### Before launch
- **Replace the placeholders.** `core/catalog.py` has placeholder USD prices and inferred units. Confirm both with the owner.
- **Check the claims.** US shipping, "pay with a Nigerian card or bank transfer" and the hours are from the brief and current site; confirm each is true before launch.
- **Product photos** at 800x600 in `static/img/products/`. Export the originals from WordPress, name them descriptively and write real alt text.
- **`/cart/` still 404s** until checkout exists. Hide the cart icon in `header.html` if you launch before it's built.
- **Add a CSP** with `django-csp`. The only inline script is the theme bootstrap, and `base.html` already adds `request.csp_nonce` if present. Self-host the two fonts and drop the Google Fonts allowance.
- **Redirects.** Map every old WordPress URL (`/product/cashew_nuts/` and so on) with 301s to keep search rankings.
- **Test on:** a 360px Android, an iPhone SE, a 3G throttle, and with JS disabled. Run Lighthouse and aim for 95+ on mobile.

## 3b. Alpine.js conventions (read before adding components)
- **Use the CSP build** (`@alpinejs/csp`). The standard build evaluates attribute strings with `new Function`, which forces `'unsafe-eval'` into your CSP and weakens the injection protection the rest of this setup is for.
- **Consequence:** attributes may only reference properties and methods (`@click="toggle"`, `:aria-expanded="open"`). No inline expressions, object literals or arguments. Put logic in `Alpine.data()` in `app.js`; pass per-element values through `data-*` attributes (see `themeOption`, `currencyOption`).
- **`app.js` loads before Alpine.** Components register on `alpine:init`; reversing the order silently breaks everything.
- **Division of labour:** htmx swaps server-rendered HTML (prices, grid, form results); Alpine holds local UI state (menu open, theme, loading label). Alpine's MutationObserver initialises swapped-in markup, so no `htmx:afterSwap` glue is needed.
- **Keep one source of truth for currency:** the cookie. The Alpine `currency` store only mirrors it for instant UI feedback.
- **Don't mix Alpine and htmx on the same attribute job** (e.g. don't use `x-show` to hide something htmx also swaps).

## 3c. Catalogue (step 2): setup
```python
# settings.py
INSTALLED_APPS += ["django.contrib.sitemaps"]
MEDIA_URL = "/media/"; MEDIA_ROOT = BASE_DIR / "media"   # serve via nginx/CDN/S3 in production
# pip install pillow   (ImageField)   Requires Django 5.1+ (CheckConstraint(condition=...), request-test `headers=`)
```
```bash
python manage.py makemigrations core && python manage.py migrate
python manage.py seed_products                 # the 11 products on agronga.com, NGN only
python manage.py seed_products --dev-usd-rate 1500   # DEV ONLY: fills USD so you can test the dollar view
python manage.py test core
```
**After seeding, the owner must fill in** (Admin > Products, `list_editable` makes this one screen): a **unit** on every product, **real USD prices**, which goods are **quote-only** (I guessed none; sesame, peanuts and shea nuts look like per-tonne goods), and **photos**. The model refuses to save an active priced product without a unit.

How it behaves
- A product with no USD price shows **"Price on request"** to dollar visitors. Nothing is converted or invented.
- `quote_only` goods show **"From ₦…"** and send buyers to the quote form, not a cart.
- `/products/?category=nuts`: chips use htmx with `hx-push-url`; the view returns a fragment only for in-page requests. Boosted navigation and back-button restores get the full page (`Vary` headers set so caches don't mix them up).
- Changing currency re-fetches the current catalogue URL, so filters survive.
- Product pages emit schema.org `Product` JSON-LD. An `Offer` is included only for priced, non-quote goods, in the visitor's currency. Availability is left out because nothing here tracks stock.
- `/sitemap.xml` and `/robots.txt` are included.

## 3d. Trust pages (step 4): setup and rules
```bash
python manage.py makemigrations core && python manage.py migrate
python manage.py seed_content      # blank Company profile + 6 starter FAQs; never overwrites edits
```
**Content lives in the admin, not in code:** Company profile (CAC number, founded year, story, certifications), FAQs, Testimonials. Anything left blank is simply not shown.

**No invented content.** I could not read the old About/FAQ/Testimonials pages, so:
- **About** uses only facts already on agronga.com. Registration number, founding year and certifications appear only once the owner enters them. Never list a certification that isn't held.
- **FAQ** starts with 6 answers that restate existing claims. `seed_content` prints the five questions buyers will really ask that only the owner can answer: US shipping, payment methods, minimums and lead times, certifications, returns.
- **Testimonials** is empty until real ones are added. The model refuses to publish one without a ticked `consent_given`, and the page query double-checks. Don't add Review schema markup for your own testimonials; Google treats self-served reviews as spam.
- **Contact** has the same form protection as the quote form (shared pipeline: honeypot, signed time trap, per-form rate limit) and no email address in the HTML. Its "Staying safe when you pay" panel is a public promise: the owner must confirm every line is true. The same wording is repeated in the Terms and one FAQ.
- **Privacy and Terms are drafts written from what the site actually does today.** A Nigerian lawyer must review both before launch. Several clauses are business decisions (quote validity, claims process, liability cap, who pays duties). Update the Privacy policy the day you add analytics, a newsletter, payments or a new email provider, and bump `LEGAL_UPDATED` in `core/urls.py`.

Also fixed along the way: the quote form now degrades to a full page without JavaScript (it used to leave a bare fragment), and navigation uses `reverse()` so a renamed URL can't create a dead link.

## 4. Suggested build order
1. **This base** (landing, currency, quote form, theme). Done.
2. **Catalogue** (models, list, detail, sitemap). Done, see 3c. Still to add: pagination or search once there are more than about 30 products, and resized image variants (django-imagekit or a CDN).
3. **Cart and checkout**: session cart, Paystack for ₦, Stripe or Flutterwave for $, signed webhooks, order emails.
4. **Trust pages**: About, FAQ, Testimonials, Contact, Privacy, Terms. Built, see 3d. The owner now has to supply the real content.
5. **Operations**: Sentry, uptime monitoring, nightly database backups, DMARC report review.

## 5. Known limits of this delivery
- I could not run Django here, so the templates and views have been syntax-checked (Python and JS) but not executed. Expect a small fix or two on first run.
- Tailwind 4 class names were written from the v4 syntax (`aria-checked:`, `group-aria-expanded:`, `@utility`); the build will flag anything misspelled.
