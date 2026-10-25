from django.contrib.sitemaps.views import sitemap
from datetime import date

from django.urls import path
from django.views.generic import TemplateView

from . import views
from .sitemaps import sitemaps

app_name = "core"

# Bump this date whenever the wording of either document changes.
LEGAL_UPDATED = date(2026, 10, 11)
urlpatterns = [
    path("", views.home, name="home"),
    path("products/", views.product_list, name="products"),
    path("products/<slug:slug>/", views.product_detail, name="product_detail"),
    path("currency/", views.set_currency, name="set_currency"),
    path("cart/", views.cart, name="cart"),
    path("cart/quote/", views.cart_quote, name="cart_quote"),
    path("order/", views.order, name="order"),
    path("order/<str:reference>/", views.order_status, name="order_status"),
    path("paystack/webhook/", views.paystack_webhook, name="paystack_webhook"),
    path("quote/", views.quote, name="quote"),
    path("about/", views.about, name="about"),
    path("faq/", views.faq, name="faq"),
    path("testimonials/", views.testimonials, name="testimonials"),
    path("contact/", views.contact, name="contact"),
    path("privacy/", TemplateView.as_view(template_name="pages/privacy.html", extra_context={"updated": LEGAL_UPDATED}), name="privacy"),
    path("terms/", TemplateView.as_view(template_name="pages/terms.html", extra_context={"updated": LEGAL_UPDATED}), name="terms"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
]
