"""Who is really calling? Behind a proxy (Cloudflare, nginx, a load balancer) REMOTE_ADDR is the PROXY, so
rate limits keyed on it would treat every visitor as one person. Configure the header your proxy sets.

  CLIENT_IP_HEADER=CF-Connecting-IP        Cloudflare (one value, set by Cloudflare, cannot be forged by visitors)
  CLIENT_IP_HEADER=X-Forwarded-For         nginx / load balancer; also set TRUSTED_PROXY_HOPS (default 1)

Only set this when ALL traffic really passes through that proxy; otherwise a visitor can forge the header.
"""
import ipaddress

from django.conf import settings


def client_ip(request) -> str:
    peer = request.META.get("REMOTE_ADDR", "")
    header = (getattr(settings, "CLIENT_IP_HEADER", "") or "").strip()
    if not header:
        return peer
    raw = request.META.get("HTTP_" + header.upper().replace("-", "_"), "")
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return peer
    hops = max(1, int(getattr(settings, "TRUSTED_PROXY_HOPS", 1)))
    candidate = parts[-hops] if len(parts) >= hops else parts[0]     # count from the right: the left side is forgeable
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return peer
