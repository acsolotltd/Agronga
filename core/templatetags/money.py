from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag(takes_context=True)
def price(context, product):
    """{% price product %} -> <span class="price" data-ngn=".." data-usd="..">₦12,500</span>

    The text is rendered for the visitor's current currency (works without JS). The data
    attributes let the browser re-render instantly when the visitor flips the ₦ / $ switch.
    Missing price in a currency shows "Price on request". Nothing is ever converted.
    """
    cur = context["currency"]
    amount = product.price_for(cur.code)
    text = "Price on request" if amount is None else cur.format(amount)
    if amount is not None and product.quote_only:
        text = f"From {text}"
    return format_html(
        '<span class="price" data-ngn="{}" data-usd="{}" data-from="{}">{}</span>',
        "" if product.price_ngn is None else product.price_ngn,
        "" if product.price_usd is None else product.price_usd,
        "1" if product.quote_only else "",
        text,
    )
