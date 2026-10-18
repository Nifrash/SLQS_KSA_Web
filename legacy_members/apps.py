from django.apps import AppConfig


class LegacyMembersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'legacy_members'
    verbose_name = 'SLQS Legacy Member Import'
