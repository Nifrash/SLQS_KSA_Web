"""Create missing digital cards for already approved members, safe to repeat."""
from django.core.management.base import BaseCommand
from membership.models import MemberProfile, MembershipApplication
from digital_cards.services import ensure_card


class Command(BaseCommand):
    help = "Create missing digital cards for approved members (--dry-run previews)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        missing = MemberProfile.objects.filter(
            application__status=MembershipApplication.Status.APPROVED,
            digital_card__isnull=True,
        )
        if options["dry_run"]:
            self.stdout.write(f"Missing digital cards: {missing.count()} (dry run)")
            return
        created = 0
        for member in missing.iterator():
            _, was_created = ensure_card(member)
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Created {created} missing digital cards."))
