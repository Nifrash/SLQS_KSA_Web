"""Backfill cases for all Phase 5 applications, safely repeatable."""
from django.core.management.base import BaseCommand
from membership.models import MembershipApplication
from membership_team.models import CommitteeCase


class Command(BaseCommand):
    help = 'Create missing private committee cases for existing applications (--dry-run previews).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        missing = MembershipApplication.objects.filter(committee_case__isnull=True)
        total = missing.count()
        if options['dry_run']:
            self.stdout.write(f'Committee cases missing: {total} (dry run; unchanged)')
            return
        created = 0
        for application in missing.iterator():
            _, was_created = CommitteeCase.objects.get_or_create(application=application)
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f'Created {created} missing committee cases.'))
