"""Persist the new starter blocks so editors can change every section in Wagtail."""
from django.core.management.base import BaseCommand, CommandError
from home.defaults import starter_home_sections
from home.models import HomePage


class Command(BaseCommand):
    help = "Install editable SLQS homepage starter sections without overwriting existing blocks."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report action without saving")

    def handle(self, *args, **options):
        homepage = HomePage.objects.first()
        if homepage is None:
            raise CommandError("No SLQS homepage found. Run seed_slqs_phase1 first.")
        if homepage.sections:
            self.stdout.write("Homepage already has custom sections; no changes made.")
            return
        if options["dry_run"]:
            self.stdout.write("Would install 6 starter sections on the existing homepage.")
            return
        # Wagtail supports assigning a list of (block_type, value) tuples to StreamField.
        homepage.sections = [
            (item["type"], item["value"]) for item in starter_home_sections()
        ]
        homepage.save_revision().publish()
        self.stdout.write(self.style.SUCCESS("Installed 6 editable homepage starter sections. Open Wagtail → Pages → Home to edit them."))
