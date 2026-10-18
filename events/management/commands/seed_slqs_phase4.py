"""Idempotently create an events section, without publishing imaginary events."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from wagtail.models import Site

from home.models import HomePage
from events.models import EventIndexPage


class Command(BaseCommand):
    help = "Prepare /events/ in Wagtail. Safe to run repeatedly."

    @transaction.atomic
    def handle(self, *args, **options):
        site = Site.objects.filter(is_default_site=True).first()
        if not site or not isinstance(site.root_page.specific, HomePage):
            raise CommandError("Run seed_slqs_phase1 first; the default site must point to an SLQS HomePage.")
        homepage = site.root_page.specific
        existing = homepage.get_children().filter(slug="events").first()
        if existing:
            if not isinstance(existing.specific, EventIndexPage):
                raise CommandError(
                    "An existing Wagtail page is using the 'events' slug. "
                    "Please rename or move that page in Wagtail; nothing has been deleted."
                )
            self.stdout.write("Events index already exists; preserving all content and publication settings.")
        else:
            page = homepage.add_child(instance=EventIndexPage(
                title="Our Events", slug="events", live=False, show_in_menus=True,
            ))
            page.save_revision().publish()
            self.stdout.write(self.style.SUCCESS("Created /events/ calendar."))
        self.stdout.write(self.style.SUCCESS("Phase 4 ready. Add Event pages under Pages > Home > Our Events."))
