"""Staff-only administrative CLI to link a Phase 5 application after identity verification."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from member_accounts.models import MemberAccountProfile
from membership.models import MembershipApplication


class Command(BaseCommand):
    help = "Link a verified website account with a legacy application AFTER staff verify ownership."

    def add_arguments(self, parser):
        parser.add_argument("application_reference", help="Full application UUID")
        parser.add_argument("email", help="Verified account email")
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        app = MembershipApplication.objects.select_for_update().filter(reference=options["application_reference"]).first()
        account = MemberAccountProfile.objects.select_related("user").filter(user__email__iexact=email, verified_at__isnull=False, user__is_active=True).first()
        if not app or not account:
            raise CommandError("Application or verified website account does not exist.")
        if app.preferred_email.lower() != email:
            raise CommandError("Email mismatch. Do not link different identities.")
        if app.user_id and app.user_id != account.user_id:
            raise CommandError("Application already belongs to another account.")
        if MembershipApplication.objects.exclude(pk=app.pk).filter(user_id=account.user_id).exists():
            raise CommandError("This website account already owns an application.")
        if options["dry_run"]:
            self.stdout.write("DRY RUN: verified matching account; no database update.")
        else:
            app.user = account.user
            app.save(update_fields=["user", "updated_at"])
            self.stdout.write(self.style.SUCCESS("Existing application linked after staff verification."))
