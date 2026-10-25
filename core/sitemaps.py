from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Product


class StaticSitemap(Sitemap):
    changefreq, priority = "monthly", 0.8

    def items(self):
        return ["core:home", "core:products", "core:about", "core:faq", "core:testimonials", "core:contact", "core:privacy", "core:terms"]

    def location(self, item):
        return reverse(item)


class ProductSitemap(Sitemap):
    changefreq, priority = "weekly", 0.7

    def items(self):
        return Product.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.updated_at


sitemaps = {"static": StaticSitemap, "products": ProductSitemap}
