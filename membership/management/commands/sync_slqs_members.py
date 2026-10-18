"""Idempotent backfill for applications approved before Phase 6 installation."""
from django.core.management.base import BaseCommand
from membership.models import MemberProfile, MembershipApplication
from membership.services import provision_approved_member


class Command(BaseCommand):
    help = "Create missing member profiles for existing approved applications (safe to repeat)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report missing records without changing the database.")

    def handle(self, *args, **options):
        approved = MembershipApplication.objects.filter(status=MembershipApplication.Status.APPROVED)
        missing = approved.exclude(pk__in=MemberProfile.objects.values("application_id"))
        if options["dry_run"]:
            self.stdout.write(f"Approved applications: {approved.count()}; profiles missing: {missing.count()} (dry run)")
            return
        created = 0
        for application in missing.select_related("reviewed_by").iterator():
            _, was_created = provision_approved_member(application)
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Created {created} member profiles. Safe to rerun."))
