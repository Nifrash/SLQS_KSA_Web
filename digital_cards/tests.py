"""Phase 9 regression tests for verified membership cards and QR revocation."""
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from membership.models import MembershipApplication, MemberProfile
from member_accounts.models import MemberAccountProfile
from .models import DigitalMembershipCard, CardAuditEvent
from .services import ensure_card, reissue_card, revoke_card


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", WAGTAILADMIN_BASE_URL="https://slqs.example.org")
class DigitalCardTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="verified@example.org", email="verified@example.org",
            password="SecretPass321!", is_active=True,
        )
        self.account = MemberAccountProfile.objects.create(
            user=self.user, full_name="SLQS Test Member", verified_at=timezone.now()
        )
        self.staff = user_model.objects.create_user(
            username="committee-member", email="staff@example.org",
            password="SecretPass321!", is_active=True, is_staff=True,
        )
        self.staff.user_permissions.add(Permission.objects.get(
            content_type__app_label="membership_team", codename="assign_committeecase"
        ))

    def application(self, approved=False):
        application = MembershipApplication.objects.create(
            user=self.user,
            full_name="SLQS Test Member", date_of_birth=timezone.localdate() - timedelta(days=365*30),
            preferred_email=self.user.email,
            ksa_phone="+966551234567", whatsapp_phone="+966551234567",
            whatsapp_group_member="no", company_name="QS Consultants", job_title="Quantity Surveyor",
            highest_educational_qualification="BSc Quantity Surveying",
            professional_qualifications=["MRICS"], overall_post_qualification_experience="10",
            ksa_experience="5", working_region="riyadh", privacy_consent_at=timezone.now(),
        )
        if approved:
            application.status = MembershipApplication.Status.APPROVED
            application.reviewed_at = timezone.now()
            application.save(update_fields=["status", "reviewed_at"])
        return application

    def approved_card(self):
        app = self.application(approved=True)
        member = MemberProfile.objects.get(application=app)
        return member, DigitalMembershipCard.objects.get(member=member)

    def test_new_approval_issues_card_and_repeat_is_idempotent(self):
        member, card = self.approved_card()
        self.assertEqual(CardAuditEvent.objects.filter(card=card, action="issued").count(), 1)
        duplicate, created = ensure_card(member)
        self.assertFalse(created)
        self.assertEqual(card.token, duplicate.token)
        self.assertEqual(DigitalMembershipCard.objects.count(), 1)

    def test_unapproved_applicant_has_no_card(self):
        app = self.application()
        self.assertFalse(MemberProfile.objects.filter(application=app).exists())
        self.client.force_login(self.user)
        result = self.client.get(reverse("digital_cards:my_card"))
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, "Digital cards are available after approval")
        self.assertEqual(self.client.get(reverse("digital_cards:my_qr")).status_code, 403)
        self.assertEqual(self.client.get(reverse("digital_cards:my_pdf")).status_code, 403)

    def test_verified_owner_gets_qr_pdf_and_live_public_validation(self):
        member, card = self.approved_card()
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("digital_cards:my_card")), member.membership_number)
        qr = self.client.get(reverse("digital_cards:my_qr"))
        self.assertEqual(qr.status_code, 200)
        self.assertEqual(qr["Content-Type"], "image/png")
        self.assertTrue(qr.content.startswith(b"\x89PNG"))
        pdf = self.client.get(reverse("digital_cards:my_pdf"))
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        self.client.logout()
        verification = self.client.get(reverse("digital_cards:verify", args=[card.token]))
        self.assertContains(verification, "Membership verified")
        self.assertContains(verification, member.membership_number)
        self.assertNotContains(verification, self.user.email)
        self.assertNotContains(verification, "551234567")
        self.assertIn("no-store", verification["Cache-Control"])

    def test_unrelated_user_cannot_download_card(self):
        member, card = self.approved_card()
        other = get_user_model().objects.create_user("other", "other@example.org", "SafePassword")
        MemberAccountProfile.objects.create(user=other, full_name="Other", verified_at=timezone.now())
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("digital_cards:my_qr")).status_code, 403)
        self.assertEqual(self.client.get(reverse("digital_cards:my_pdf")).status_code, 403)
        self.assertNotContains(self.client.get(reverse("digital_cards:my_card")), member.membership_number)

    def test_revocation_and_rotation_kill_old_qr(self):
        member, card = self.approved_card()
        original = card.token
        revoke_card(member.pk, actor=self.staff, note="Lost printed card")
        self.assertContains(self.client.get(reverse("digital_cards:verify", args=[original])), "Card not verified")
        updated = reissue_card(member.pk, actor=self.staff, note="Replacement requested")
        self.assertNotEqual(updated.token, original)
        self.assertEqual(updated.reissue_count, 1)
        self.assertContains(self.client.get(reverse("digital_cards:verify", args=[original])), "Card not verified")
        self.assertContains(self.client.get(reverse("digital_cards:verify", args=[updated.token])), "Membership verified")
        self.assertEqual(CardAuditEvent.objects.filter(card=card).count(), 3)

    def test_suspended_expired_or_revoked_application_invalidates_live_qr(self):
        member, card = self.approved_card()
        verify_url = reverse("digital_cards:verify", args=[card.token])
        MemberProfile.objects.filter(pk=member.pk).update(status=MemberProfile.Status.SUSPENDED)
        self.assertContains(self.client.get(verify_url), "Card not verified")
        MemberProfile.objects.filter(pk=member.pk).update(status=MemberProfile.Status.ACTIVE, renewal_due_on=timezone.localdate()-timedelta(days=1))
        self.assertContains(self.client.get(verify_url), "Card not verified")
        MemberProfile.objects.filter(pk=member.pk).update(renewal_due_on=None)
        app = member.application
        app.status = MembershipApplication.Status.REJECTED
        app.save(update_fields=["status"])
        self.assertContains(self.client.get(verify_url), "Card not verified")

    def test_old_token_unknown_and_public_result_nonidentifying(self):
        self.assertContains(self.client.get(reverse("digital_cards:verify", args=["00000000-0000-4000-8000-000000000000"])), "Card not verified")
        self.assertNotContains(self.client.get(reverse("digital_cards:verify", args=["00000000-0000-4000-8000-000000000000"])), "SLQS Test Member")

    def test_member_only_route_redirects_anonymous(self):
        self.assertEqual(self.client.get(reverse("digital_cards:my_card")).status_code, 302)
        self.assertEqual(self.client.get(reverse("digital_cards:my_pdf")).status_code, 302)

    def test_staff_card_actions_are_post_only_and_permission_protected(self):
        member, card = self.approved_card()
        list_url = reverse("digital_card_staff:cards")
        revoke_url = reverse("digital_card_staff:revoke", args=[member.pk])
        self.assertEqual(self.client.get(list_url).status_code, 302)
        self.assertEqual(self.client.post(revoke_url, {"reason": "lost"}).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(list_url).status_code, 403)
        self.assertEqual(self.client.post(revoke_url, {"reason": "lost"}).status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(list_url).status_code, 200)
        self.assertEqual(self.client.get(revoke_url).status_code, 405)
        self.assertEqual(self.client.post(revoke_url, {"reason": ""}).status_code, 302)
        card.refresh_from_db()
        self.assertIsNone(card.revoked_at)
        self.assertEqual(self.client.post(revoke_url, {"reason": "Printed card lost"}).status_code, 302)
        card.refresh_from_db()
        self.assertIsNotNone(card.revoked_at)

    def test_staff_cannot_reissue_suspended_member(self):
        member, card = self.approved_card()
        MemberProfile.objects.filter(pk=member.pk).update(status=MemberProfile.Status.SUSPENDED)
        with self.assertRaises(ValidationError):
            reissue_card(member.pk, actor=self.staff, note="Replacement")

    def test_repeat_sync_preserves_existing_card_token(self):
        member, card = self.approved_card()
        first_token = card.token
        call_command("sync_slqs_cards", "--dry-run", stdout=StringIO())
        call_command("sync_slqs_cards", stdout=StringIO())
        card.refresh_from_db()
        self.assertEqual(card.token, first_token)
        self.assertEqual(DigitalMembershipCard.objects.count(), 1)

    def test_public_uses_canonical_url(self):
        from .services import verification_url
        _, card = self.approved_card()
        self.assertEqual(verification_url(card), f"https://slqs.example.org/cards/verify/{card.token}/")
