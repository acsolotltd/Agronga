# Deploying AgroNGA

Tested layout: Ubuntu 22.04/24.04 · Python 3.11+ · PostgreSQL · Redis · gunicorn · nginx (optionally behind Cloudflare).

## 1. Environment (`/srv/agronga/.env`, chmod 600, never in git)
Copy `.env.example`, then set at least: `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `SITE_URL=https://agronga.com`,
`BREVO_API_KEY`, `PAYSTACK_SECRET_KEY`, `DB_NAME/DB_USER/DB_PASSWORD`, `REDIS_URL`, `CLIENT_IP_HEADER`, `ADMIN_EMAIL`.
Do **not** set `DJANGO_DEBUG`. Use `sk_test_` until the go-live test (section 6) passes.

## 2. Install
```
python -m venv venv && . venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py seed_products            # products + placeholder shipping zones (edit them in Admin)
python manage.py seed_pages               # editable About/Contact/FAQ/Testimonials pages (see CONTENT.md)
python manage.py createsuperuser
python manage.py check --deploy           # fix every warning it prints
```

## 3. gunicorn (systemd: `/etc/systemd/system/agronga.service`)
```
[Service]
User=www-data
WorkingDirectory=/srv/agronga
EnvironmentFile=/srv/agronga/.env
ExecStart=/srv/agronga/venv/bin/gunicorn agronga.wsgi --workers 3 --bind 127.0.0.1:8000 --timeout 30
Restart=always
```

## 4. nginx (TLS via certbot). The three header lines matter.
```
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;          # lets Django know the request was https
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;   # use CLIENT_IP_HEADER=X-Forwarded-For
}
location /media/ {                                      # photos uploaded in the admin
    alias /srv/agronga/media/;
    location ~* ^/media/pages/v/ { expires 1y; add_header Cache-Control "public, immutable"; }   # optimised page photos: the file name changes when the photo changes
    expires 7d;
}
```
Behind Cloudflare use `CLIENT_IP_HEADER=CF-Connecting-IP` instead, and block direct access to your server except from Cloudflare.

## 5. Scheduled jobs (cron: `crontab -e` as the app user; on Windows use Task Scheduler)
```
0  * * * *   cd /srv/agronga && venv/bin/python manage.py update_rates        # live USD->NGN rate
*/10 * * * * cd /srv/agronga && venv/bin/python manage.py reconcile_payments  # catches missed webhooks
```

## 6. Paystack setup and the go-live test
1. Dashboard > Settings > API Keys & Webhooks: set **Webhook URL** to `https://YOUR-DOMAIN/paystack/webhook/`.
2. (Optional) put Paystack's webhook IPs in `PAYSTACK_WEBHOOK_IPS`.
3. Ask Paystack support to enable **USD** on your business if you will charge dollars.
4. With the **test** key, on the live domain, complete these and check Admin > Orders and Admin > Payment events after each:
   * a naira card payment: order becomes **Paid**, you and the customer get emails, the status page shows "Payment received";
   * a dollar payment (once USD is enabled);
   * pay then close the tab before returning: the webhook still marks it paid;
   * double-click **Pay**: only one order is created;
   * a declined card: order stays unpaid and the cart is kept.
5. Switch `PAYSTACK_SECRET_KEY` to `sk_live_`, restart, and make one small real payment.

## 7. After launch
* Raise `HSTS_SECONDS` to `31536000` once everything works over HTTPS.
* Back up PostgreSQL **and the `media/` folder** (uploaded photos) daily and test a restore. Add uptime monitoring and Sentry.
* Review Admin > Orders for **Needs review** and Admin > Payment events for `alerted` (refunds/disputes).
