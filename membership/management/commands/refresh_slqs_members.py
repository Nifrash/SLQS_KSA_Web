"""Intended for one scheduled run daily after a local production policy is agreed."""
from django.core.management.base import BaseCommand
from membership.services import expire_overdue_members


class Command(BaseCommand):
    help = "Mark active memberships with past renewal due dates as expired."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show count without updating statuses.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        count = expire_overdue_members(dry_run=dry_run)
        qualifier = "would be" if dry_run else "were"
        self.stdout.write(self.style.SUCCESS(f"{count} member(s) {qualifier} marked expired."))
