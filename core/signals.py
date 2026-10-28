"""Clear the content cache the moment anything editable changes."""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from . import content
from .models import FAQ, Category, CompanyProfile, PageBlock, PageContent, Product, Testimonial

_WATCHED = (PageContent, PageBlock, FAQ, Testimonial, CompanyProfile, Category, Product)


@receiver(post_save)
@receiver(post_delete)
def clear_content_cache(sender, **kwargs):
    if sender in _WATCHED:
        content.invalidate()
