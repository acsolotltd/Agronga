"""Minimal Paystack client + webhook helpers. Standard library only (no extra dependency).

Docs: https://paystack.com/docs/api/transaction/  and  https://paystack.com/docs/payments/webhooks/
* Amounts are sent in the currency's smallest unit: kobo for NGN, cents for USD (value x 100).
* USD charges only work if USD is enabled on your Paystack business. Ask Paystack support to enable it.
* The webhook is the source of truth for "paid". The browser callback only verifies and displays.
"""
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
from decimal import ROUND_HALF_UP, Decimal

API_BASE = "https://api.paystack.co"
SUPPORTED_CURRENCIES = ("NGN", "USD")


class PaystackError(Exception):
    """Raised when Paystack is unreachable or rejects a request. The message is safe to log, not to show."""


def to_subunit(amount) -> int:
    """Decimal('12500.00') -> 1250000 (kobo). Decimal('8.50') -> 850 (cents). Never goes through float."""
    return int((Decimal(amount) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def verify_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    """x-paystack-signature is the HMAC-SHA512 of the RAW request body using your secret key."""
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())


def _call(method: str, path: str, secret: str, payload: dict | None = None, timeout: int = 20, retries: int = 0) -> dict:
    """One Paystack API call. `retries` is only safe for idempotent calls (GET). Never retry initialize."""
    if not secret:
        raise PaystackError("PAYSTACK_SECRET_KEY is not set")
    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        # Paystack sits behind Cloudflare, which blocks Python's default "Python-urllib" agent (error 1010).
        "User-Agent": "AgroNGA-Store/1.0 (+https://agronga.com)",
    }
    data = json.dumps(payload).encode() if payload is not None else None
    for attempt in range(retries + 1):
        req = urllib.request.Request(API_BASE + path, method=method, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode())
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            if e.code >= 500 and attempt < retries:        # Paystack hiccup: try again. 4xx means our request is wrong.
                time.sleep(0.5 * (attempt + 1))
                continue
            raise PaystackError(f"HTTP {e.code}: {detail}") from e
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise PaystackError(f"Request failed: {e}") from e
    if not body.get("status"):
        raise PaystackError(body.get("message", "Paystack returned status=false"))
    return body["data"]


def initialize(secret: str, *, email: str, amount, currency: str, reference: str, callback_url: str, metadata: dict | None = None) -> dict:
    """Start a transaction. Returns {"authorization_url", "access_code", "reference"}."""
    if currency not in SUPPORTED_CURRENCIES:
        raise PaystackError(f"Unsupported currency {currency}")
    return _call("POST", "/transaction/initialize", secret, {
        "email": email,
        "amount": str(to_subunit(amount)),
        "currency": currency,
        "reference": reference,
        "callback_url": callback_url,
        "metadata": metadata or {},
    })


def verify(secret: str, reference: str) -> dict:
    """Ask Paystack for the final state of a transaction (used by the browser callback)."""
    from urllib.parse import quote
    return _call("GET", f"/transaction/verify/{quote(reference, safe='')}", secret, timeout=10, retries=2)
