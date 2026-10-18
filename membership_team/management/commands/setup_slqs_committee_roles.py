"""Create group permissions; DOES NOT assign privileges to any account."""
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError

ROLE_PERMISSIONS = {
    'SLQS Membership Head': [
        'view_committeecase', 'assign_committeecase', 'recommend_committeecase',
        'decide_committeecase', 'request_info_committeecase', 'export_committeecase',
    ],
    'SLQS Membership Secretary': [
        'view_committeecase', 'assign_committeecase', 'recommend_committeecase',
        'request_info_committeecase', 'export_committeecase',
    ],
    'SLQS Membership Reviewer': ['view_committeecase', 'recommend_committeecase'],
    'SLQS Membership Officer': ['view_committeecase', 'recommend_committeecase'],
}


class Command(BaseCommand):
    help = 'Create/update committee role groups. Does not create staff users or assign groups.'

    def handle(self, *args, **options):
        for name, codenames in ROLE_PERMISSIONS.items():
            group, _ = Group.objects.get_or_create(name=name)
            permissions = list(Permission.objects.filter(
                content_type__app_label='membership_team',
                content_type__model='committeecase',
                codename__in=codenames,
            ))
            if len(permissions) != len(codenames):
                raise CommandError('Phase 8 permissions missing; run python manage.py migrate first.')
            # Preserve any unrelated custom permissions set on this group.
            group.permissions.add(*permissions)
            if name in ('SLQS Membership Head', 'SLQS Membership Secretary'):
                extras = list(Permission.objects.filter(
                    content_type__app_label='membership',
                    codename__in=['view_memberprofile', 'view_membershipapplication'],
                ))
                group.permissions.add(*extras)
            self.stdout.write(self.style.SUCCESS(f'Role ready: {name}'))
