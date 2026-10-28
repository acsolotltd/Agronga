from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
]

if settings.ANYMAIL.get("WEBHOOK_SECRET"):             # Brevo delivery events (bounces, complaints); see settings.py
    urlpatterns.insert(0, path("anymail/", include("anymail.urls")))
