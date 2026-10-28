# Email (Brevo) and order status emails

## Set up Brevo once
1. Brevo > SMTP & API > **API Keys**: create a key, put it in `.env` as `BREVO_API_KEY`.
2. Brevo > Senders, Domains > **Domains**: add `agronga.com` and add the SPF, DKIM and DMARC records Brevo shows you to your DNS. Wait for "authenticated". Without this, mail goes to spam.
3. Make sure `DEFAULT_FROM_EMAIL` (default `AgroNGA <info@agronga.com>`) is an address on that domain. `QUOTE_INBOX` is where enquiries and new-order alerts arrive.
4. Check it works: `python manage.py send_test_email you@example.com`.
5. Optional but recommended, bounce alerts: in Brevo > Transactional > Settings > Webhook add `https://USER:PASSWORD@agronga.com/anymail/brevo/tracking/` (events: hard bounce, soft bounce, blocked, spam, error) and set `BREVO_WEBHOOK_SECRET=USER:PASSWORD`. You are then emailed when a customer's address fails.
Brevo's free plan has a daily sending limit; check it against your volume.

## What gets emailed
| When | To | Email |
|---|---|---|
| Contact form submitted (AJAX, no page reload) | You + the visitor | HTML + plain text. You can press Reply to answer the visitor. The visitor gets a confirmation copy of their message. |
| Bulk quote form submitted | You + the visitor | Same, with product, country and quantity. |
| Order request (invoice) placed | You + the customer | New order summary with an "Open in admin" button; acknowledgement to the customer. |
| Payment confirmed by Paystack | You + the customer | New paid order; "Payment received" receipt with items, totals, address. |
| **You change an order's status in the admin** | The customer | Processing, Shipped (with tracking), Delivered, Cancelled, Refunded. |
| Bounce / spam complaint (needs step 5) | You | Alert once per address per hour. |

The visitor confirmation is limited to 2 per address per hour so the form cannot be used to mail-bomb someone. If sending to the visitor fails, the form still succeeds as long as your copy was delivered. If *your* copy cannot be sent the visitor sees a friendly "please try again or call us" message (never an error page).

## Changing an order's status (Admin > Orders)
* Open an order, pick the new **Status**, optionally fill **Courier and tracking number** and **Note to the customer**, leave **Email the customer** ticked, and press Save. The customer is emailed straight away and the change is recorded in **Status history**.
* Untick the box to change the status silently. Saving without changing the status never sends anything.
* On the orders list you can tick several orders and use **Mark as Processing / Shipped / Delivered / Cancelled / Refunded**, or **Send the status email again**.
* The note to the customer is included in that one email, then cleared.
* Pending, payment failed and needs-review never email the customer. Orders cannot be deleted from the admin.
* A late Paystack retry can never move a shipped order back to "paid", and money arriving for a cancelled order alerts you instead of changing anything.

## Changing the wording
Subjects and headings: `STATUS_COPY` in `core/orders.py`. Layout and colours: `theme/templates/emails/` (`base.html` is the shared frame; each email has an `.html` and a `.txt` version, keep both in step).
