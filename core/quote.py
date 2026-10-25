"""Builds a priced cart (a "quote"): line prices, shipping for the buyer's country, and the total.

Pure Python: callers pass in plain objects, so this is the single place the checkout maths lives and it can be
tested without a database. Products need: slug, name, unit, price_usd, weight_kg, is_bulk.
A zone needs: name, base_usd, per_kg_usd, free_over_usd, eta.
"""
from dataclasses import dataclass, field
from decimal import ROUND_UP, Decimal

from . import pricing
from .countries import COUNTRY_NAMES


@dataclass
class Line:
    product: object
    qty: int
    unit_price: Decimal
    line_total: Decimal


@dataclass
class Quote:
    currency: str
    country: str
    lines: list
    subtotal: Decimal
    shipping: Decimal
    total: Decimal
    subtotal_usd: Decimal
    shipping_usd: Decimal = Decimal("0.00")
    shipping_known: bool = True          # False: no courier rate for this country, quoted by email
    freight_pending: bool = False        # True: cart has tonne-priced goods; their freight is quoted by email
    zone_name: str = ""
    eta: str = ""
    weight_kg: Decimal = Decimal(0)
    rate_eff: Decimal | None = None      # naira per $1 (market x margin). Set for both currencies; only charged for NGN
    rate_raw: Decimal | None = None      # market rate before margin
    rate_source: str = ""
    rate_at: object = None
    margin: Decimal = Decimal(0)
    notes: list = field(default_factory=list)


def money(code, amount) -> str:
    amount = Decimal(amount)
    return f"₦{amount:,.0f}" if code == "NGN" else f"${amount:,.2f}"


def build(lines, currency, country, zone=None, eff=None, raw=None, source="", at=None, margin=Decimal(0)) -> Quote:
    """lines = [(product, qty)]. Raises ValueError if a product has no USD price or currency is NGN without a rate."""
    if currency == "NGN" and not eff:
        raise ValueError("NGN quote needs an exchange rate")
    built, sub_usd, sub, weight, bulk = [], Decimal(0), Decimal(0), Decimal(0), False
    for p, qty in lines:
        if p.price_usd is None:
            raise ValueError(f"{p.slug} has no USD price")
        unit = pricing.usd_to_ngn(p.price_usd, eff) if currency == "NGN" else Decimal(p.price_usd).quantize(pricing.CENT)
        built.append(Line(p, qty, unit, unit * qty))
        sub_usd += Decimal(p.price_usd) * qty
        sub += unit * qty
        if p.is_bulk:
            bulk = True
        else:
            weight += Decimal(str(p.weight_kg)) * qty

    q = Quote(currency=currency, country=country, lines=built, subtotal=sub, shipping=Decimal("0.00"), total=sub,
              subtotal_usd=sub_usd, freight_pending=bulk, weight_kg=weight,
              rate_eff=eff, rate_raw=raw,
              rate_source=source, rate_at=at, margin=Decimal(margin))
    where = COUNTRY_NAMES.get(country, country)
    if weight > 0:
        if zone is None:
            q.shipping_known = False
            q.notes.append(f"Shipping to {where} is quoted by email before you pay.")
        else:
            fee_usd = pricing.shipping_usd(zone.base_usd, zone.per_kg_usd, weight, sub_usd, zone.free_over_usd)
            q.shipping_usd = fee_usd
            q.shipping = pricing.usd_to_ngn(fee_usd, eff, ROUND_UP) if currency == "NGN" else fee_usd
            q.zone_name, q.eta = zone.name, zone.eta
    else:
        q.shipping_known = False          # nothing parcel-shippable (e.g. tonne goods only): freight quoted by email
    if bulk:
        q.notes.append("Freight for tonne-priced goods depends on volume and port, so we confirm it by email.")
    q.total = q.subtotal + q.shipping
    return q


def to_dict(q: Quote) -> dict:
    """JSON-ready, with display strings so the browser never has to do money maths."""
    c = q.currency
    rate_text = ""
    if c == "NGN" and q.rate_eff:
        rate_text = (f"$1 = ₦{q.rate_eff:,.2f}. That is the market rate (₦{q.rate_raw:,.2f}) plus "
                     f"{q.margin * 100:.0f}% to cover payment fees and currency movement.")
    if q.weight_kg > 0 and q.shipping_known:
        ship_label = f"Shipping to {COUNTRY_NAMES.get(q.country, q.country)}" + (f" ({q.eta})" if q.eta else "")
        ship_fmt = "Free" if q.shipping == 0 else money(c, q.shipping)
    else:
        ship_label = "Shipping"
        ship_fmt = "Quoted by email"
    return {
        "currency": c, "country": q.country,
        "lines": [{"slug": l.product.slug, "name": l.product.name, "unit": l.product.unit, "qty": l.qty,
                   "unit_price": str(l.unit_price), "unit_price_fmt": money(c, l.unit_price),
                   "line_total_fmt": money(c, l.line_total)} for l in q.lines],
        "subtotal_fmt": money(c, q.subtotal), "shipping_fmt": ship_fmt, "shipping_label": ship_label,
        "shipping_known": q.shipping_known, "freight_pending": q.freight_pending, "notes": q.notes,
        "total": str(q.total), "total_fmt": money(c, q.total), "rate_text": rate_text,
        "rate_at": q.rate_at.isoformat() if q.rate_at else "",
        # per-product prices in BOTH currencies so the browser's cart snapshot can refresh itself
        "prices": {l.product.slug: {"usd": str(Decimal(l.product.price_usd).quantize(pricing.CENT)),
                                    "ngn": str(pricing.usd_to_ngn(l.product.price_usd, q.rate_eff)) if q.rate_eff else ""}
                   for l in q.lines},
    }
