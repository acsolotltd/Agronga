"""Exchange-rate service: the live USD->NGN rate, the margin, and repricing the catalogue in naira.

USD is the master price; naira = USD x market rate x (1 + NGN_MARGIN), rounded to N10.
The rate is stored in the database (FxRate) and refreshed from the live feed when it is older than FX_TTL_MINUTES,
by `manage.py update_rates` (for a scheduler) and lazily whenever a customer views the shop or checks out.
"""
import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from . import pricing

log = logging.getLogger(__name__)
_COOLDOWN_KEY = "fx:cooldown"
_LOCK_KEY = "fx:lock"


def margin() -> Decimal:
    return Decimal(str(settings.NGN_MARGIN))


def current():
    """Newest FxRate row, or an unsaved placeholder built from FX_FALLBACK_NGN_PER_USD when none exists yet."""
    from .models import FxRate
    row = FxRate.objects.first()
    if row:
        return row
    return FxRate(ngn_per_usd=Decimal(str(settings.FX_FALLBACK_NGN_PER_USD)), source="fallback", pinned=False,
                  fetched_at=datetime(2000, 1, 1, tzinfo=dt_timezone.utc))


def effective(rate=None) -> Decimal:
    """Naira per $1 actually charged: market rate plus margin."""
    return pricing.effective_rate((rate or current()).ngn_per_usd, margin())


def usd_to_ngn(usd, rate=None):
    return pricing.usd_to_ngn(usd, effective(rate))


def is_stale(rate) -> bool:
    if rate.pinned:
        return False                      # the owner fixed this rate on purpose
    return rate.source == "fallback" or timezone.now() - rate.fetched_at > timedelta(minutes=settings.FX_TTL_MINUTES)


def reprice_products(rate=None) -> int:
    """Write the naira price of every product to the database. Returns how many rows changed."""
    from .models import Product
    eff = effective(rate)
    changed = []
    for p in Product.objects.exclude(price_usd=None):
        new = pricing.usd_to_ngn(p.price_usd, eff)
        if p.price_ngn != new:
            p.price_ngn = new
            changed.append(p)
    if changed:
        Product.objects.bulk_update(changed, ["price_ngn"])
    Product.objects.filter(price_usd=None).exclude(price_ngn=None).update(price_ngn=None)
    return len(changed)


def refresh(force=False):
    """Fetch the live rate and save it (which reprices products). Returns the new FxRate, or None if nothing changed.

    Never raises: a feed outage keeps the last good rate. A move of more than FX_MAX_JUMP in one step is treated as
    bad data and rejected; if the move is real, pin the new rate by hand in Admin > FX rates."""
    from .models import FxRate
    prev = current()
    if prev.pinned and not force:
        return None
    if not force and cache.get(_COOLDOWN_KEY):
        return None
    if not force and not cache.add(_LOCK_KEY, 1, 30):
        return None                       # another worker is already fetching: serve the current rate
    try:
        rate, source = pricing.fetch_live_rate(
            timeout=10 if force else settings.FX_TIMEOUT,
            deadline=None if force else settings.FX_REQUEST_BUDGET)
    except pricing.FxError as e:
        log.error("Live FX rate unavailable, keeping %s: %s", prev, e)
        cache.set(_COOLDOWN_KEY, 1, settings.FX_RETRY_MINUTES * 60)
        if prev.source == "fallback":
            reprice_products(prev)        # keep naira prices consistent with the fallback rate
        return None
    finally:
        cache.delete(_LOCK_KEY)
    if prev.source != "fallback" and not force:
        jump = abs(rate / prev.ngn_per_usd - 1)
        if jump > Decimal(str(settings.FX_MAX_JUMP)):
            log.error("Rejected FX rate %s (%s): %.0f%% away from %s", rate, source, jump * 100, prev.ngn_per_usd)
            cache.set(_COOLDOWN_KEY, 1, settings.FX_RETRY_MINUTES * 60)
            return None
    log.info("FX rate updated: %s via %s", rate, source)
    return FxRate.objects.create(ngn_per_usd=rate, source=source)


def ensure_fresh():
    """Call before showing or charging naira prices. Returns the rate in force. Cheap unless the rate is stale."""
    rate = current()
    if settings.FX_AUTO_REFRESH and is_stale(rate):
        refresh()
        rate = current()
    return rate
