from django.apps import AppConfig


class MembershipTeamConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'membership_team'
    verbose_name = 'SLQS Membership Committee'

    def ready(self):
        from . import signals  # noqa: F401
