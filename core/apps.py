from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        from . import checks, signals  # noqa: F401  (registers the deploy checks and the cache-clearing signals)
        try:                                              # Brevo delivery events, when django-anymail's tracking webhook is switched on
            from anymail.signals import tracking
            from . import email_events
            tracking.connect(email_events.on_tracking_event, dispatch_uid="agronga-email-events")
        except ImportError:
            pass
