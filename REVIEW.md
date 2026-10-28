# Production review: AgroNGA storefront and payment flow

Status key: **FIXED** in this code · **YOU** (needs action on your side, cannot be done in code) · **LATER** (recommended, not built)

> Honest limits: this was reviewed and tested without Django installed and without reaching Paystack. Run
> `python manage.py test core` and a full Paystack **test-mode** payment (NGN and USD) before taking live money.

## Critical

| # | Finding | Status |
|---|---------|--------|
| 1 | **Rate limits keyed on `REMOTE_ADDR`.** Behind any proxy (ngrok, Cloudflare, nginx) every visitor shares one IP, so the whole shop was limited to 10 orders per hour and 120 cart quotes per minute. | **FIXED** `core/net.py`, `CLIENT_IP_HEADER`. **YOU** set it (`CF-Connecting-IP` or `X-Forwarded-For`). |
| 2 | **`DEBUG = True` hard-coded**, `SECRET_KEY` committed in the repo, no HTTPS redirect, HSTS or secure cookies, WhiteNoise installed but not enabled (static files break when DEBUG is off), ngrok hosts in production lists, a missing `ImproperlyConfigured` import. | **FIXED** `settings.py` is now secure by default and environment-driven. Production refuses to start without a secret key, hosts, `SITE_URL` and email key. A live Paystack key with DEBUG is refused. |
| 3 | **Secrets in the project zip.** A `.env` (Brevo key, Paystack key) and the Django `SECRET_KEY` were included in the files you shared. | **YOU** rotate the Brevo API key and the Django secret key now, and use `.gitignore` (added). Treat any key that has been shared as compromised. |

## High (payment correctness)

| # | Finding | Status |
|---|---------|--------|
| 4 | **Double-click / retry could create two orders and two Paystack transactions.** | **FIXED** idempotency key per checkout page, reused payment link, unique constraint, race-safe. |
| 5 | **A missed webhook left a paid customer "pending" forever**; abandoned orders piled up. | **FIXED** `manage.py reconcile_payments` (run every 10 min) verifies pending orders with Paystack and expires unpaid ones after 48 h. Admin action "Verify selected orders with Paystack". **YOU** schedule it. |
| 6 | **Webhook had no audit trail**; refund and dispute events were silently ignored. | **FIXED** `PaymentEvent` log (hash only, no card/customer data), retries recognised, refunds/disputes email you. A crashed event is processed again on Paystack's retry. |
| 7 | **Public order page exposed name and email** to anyone with a 40-bit reference. | **FIXED** 64-bit reference, masked details (`a***@example.com`), first name only, rate-limited, `no-store`, `noindex`. |
| 8 | Amount, currency and signature checks on payment | Already correct: HMAC-SHA512 on the raw body, amount and currency must match, a mismatch goes to review and is never marked paid. Optional source-IP allowlist added (`PAYSTACK_WEBHOOK_IPS`). |

## Medium

| # | Finding | Status |
|---|---------|--------|
| 9 | Live FX refresh could hold a visitor for up to 12 s if feeds were slow; many workers could refresh at once. | **FIXED** 3 s total budget, single-flight lock. |
| 10 | Paystack `verify` had no retry on transient errors. | **FIXED** 2 retries on network/5xx for GET only. `initialize` is never retried (duplicate-reference risk). |
| 11 | A slow email provider could stall the webhook response and trigger Paystack retries. | **FIXED** (mitigated) Brevo timeout 5 s / 10 s; mail failures never undo a payment. **LATER** move emails to a queue. |
| 12 | Cache is per-process (LocMem): rate limits and the FX lock do not work across gunicorn workers. | **FIXED** `REDIS_URL` support. **YOU** run Redis. |
| 13 | SQLite has no row locking, which payment settlement relies on. | **FIXED** PostgreSQL via `DB_NAME`. **YOU** run Postgres. |
| 14 | Easy to deploy wrongly | **FIXED** `manage.py check` warns about test keys, http `SITE_URL`, LocMem, missing client-IP header, SQLite, console email. |
| 15 | Payment pages could be cached by browsers/proxies. | **FIXED** `never_cache` on cart, quote, order and status. |

## Low / housekeeping

* `ANYMAIL_BREVO_API_KEY=BREVO_API_KEY,` was a tuple (trailing comma): removed. `SERVER_EMAIL` defaults to `errors@agronga.net`: confirm that domain is yours.
* `corsheaders` is installed but has no middleware or config, so it does nothing. Remove it or configure it.
* `huey` is in requirements but never configured; `django-browser-reload` is dev-only. Removed from requirements.
* Admin passwords now need 12+ characters. **LATER** add 2FA (`django-otp`) and move `/admin/` to a non-default path.

## Recommended next (not built)

1. **Email queue** (Huey is already a dependency): receipts and alerts out of the request cycle.
2. **Content-Security-Policy** header. Needs nonces for the inline `<style>` in `page_header.html` and any inline scripts.
3. **Refund workflow:** a "refunded" order status that you set after refunding in Paystack (today you are alerted, nothing changes automatically).
4. **Stock levels** (nothing stops selling an item you do not have).
5. **Monitoring:** Sentry (or similar) and an uptime check on `/` and `/products/`. Backups of PostgreSQL, tested by restoring.
6. **Legal:** refund/returns policy in the Terms now that payment is online; Paystack business verification and USD enablement.

## Editable pages (added after the review)
About, Contact, FAQ and Testimonials content and header photos are now database-driven and cached: see `CONTENT.md`. Uploaded photos live in `media/`: serve it with nginx (`DEPLOY.md`) and include it in backups.
