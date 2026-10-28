"""Pricing maths and live exchange-rate fetching. Standard library only (no Django), so it is easy to test.

The rules (see STOREFRONT.md):
  * USD is the master price. Naira is always derived: USD x (market rate x (1 + margin)).
  * The margin (default 8%) covers payment fees and currency movement. It applies to goods AND shipping.
  * Naira line prices round to the nearest N10; naira shipping rounds UP to the next N10.
  * Shipping is quoted in USD (courier rate card) and converted with the same rate.
"""
import json
import time
import urllib.error
import urllib.request
from decimal import ROUND_CEILING, ROUND_HALF_UP, ROUND_UP, Decimal

CENT = Decimal("0.01")
TEN = Decimal("10")
MIN_SANE_RATE, MAX_SANE_RATE = Decimal("100"), Decimal("10000")   # NGN per USD; anything outside is a bad feed


class FxError(Exception):
    """No usable exchange rate could be fetched."""


# ───────── Exchange-rate maths ─────────
def effective_rate(raw, margin) -> Decimal:
    """Market rate plus margin. effective_rate(1500, 0.08) -> 1620.0000"""
    return (Decimal(str(raw)) * (Decimal(1) + Decimal(str(margin)))).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def usd_to_ngn(usd, eff, rounding=ROUND_HALF_UP):
    """USD amount -> naira, rounded to a multiple of N10. None stays None (no USD price = no naira price)."""
    if usd is None:
        return None
    tens = (Decimal(usd) * Decimal(eff) / TEN).quantize(Decimal(1), rounding=rounding)
    return (tens * TEN).quantize(CENT)


# ───────── Shipping ─────────
def chargeable_kg(weight_kg) -> Decimal:
    """Couriers bill in 0.5 kg steps: 0.25 -> 0.5, 0.5 -> 0.5, 0.6 -> 1.0."""
    w = Decimal(str(weight_kg))
    if w <= 0:
        return Decimal(0)
    return ((w * 2).to_integral_value(rounding=ROUND_CEILING)) / 2


def shipping_usd(base, per_kg, weight_kg, subtotal_usd=None, free_over=None) -> Decimal:
    """Courier fee in USD for a parcel: base + per_kg x chargeable weight. Zero weight = zero fee."""
    if Decimal(str(weight_kg)) <= 0:
        return Decimal("0.00")
    if free_over is not None and subtotal_usd is not None and Decimal(subtotal_usd) >= Decimal(free_over):
        return Decimal("0.00")
    fee = Decimal(base) + Decimal(per_kg) * chargeable_kg(weight_kg)
    return fee.quantize(CENT, rounding=ROUND_HALF_UP)


# ───────── Live rate providers ─────────
# None of these is the CBN's own feed (the CBN publishes no public API). They return the market mid-rate, which
# tracks the official NFEM rate closely. To use a CBN or parallel-market quote, pin a manual rate in Admin > FX rates.
def parse_er_api(data) -> Decimal:
    if data.get("result") != "success":
        raise FxError("open.er-api: result != success")
    return Decimal(str(data["rates"]["NGN"]))


def parse_fawaz(data) -> Decimal:
    return Decimal(str(data["usd"]["ngn"]))


SOURCES = [
    ("open_er_api", "https://open.er-api.com/v6/latest/USD", parse_er_api),
    ("currency_api", "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json", parse_fawaz),
    ("currency_api_2", "https://latest.currency-api.pages.dev/v1/currencies/usd.json", parse_fawaz),
]


def is_sane(rate) -> bool:
    return MIN_SANE_RATE < Decimal(rate) < MAX_SANE_RATE


def fetch_live_rate(sources=None, timeout=4, urlopen=urllib.request.urlopen, deadline=None):
    """Try each source in order. Returns (Decimal NGN-per-USD, source_name). Raises FxError if all fail.
    `deadline` is the TOTAL seconds allowed across all sources (use it when a visitor is waiting)."""
    errors = []
    started = time.monotonic()
    for name, url, parse in (sources or SOURCES):
        left = timeout if deadline is None else min(timeout, deadline - (time.monotonic() - started))
        if left <= 0.2:
            errors.append(f"{name}: skipped, out of time")
            break
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "AgroNGA-Store/1.0 (+https://agronga.com)"})
            with urlopen(req, timeout=left) as resp:
                rate = parse(json.loads(resp.read().decode()))
            if not is_sane(rate):
                raise FxError(f"implausible rate {rate}")
            return rate.quantize(Decimal("0.0001")), name
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, TypeError, FxError, OSError) as e:
            errors.append(f"{name}: {e}")
    raise FxError("; ".join(errors))
