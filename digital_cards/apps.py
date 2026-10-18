from django.apps import AppConfig


class DigitalCardsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "digital_cards"
    verbose_name = "SLQS Digital Membership Cards"

    def ready(self):
        from . import signals  # noqa: F401
