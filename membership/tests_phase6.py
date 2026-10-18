"""Phase 6 regression tests; run: python manage.py test membership.tests_phase6"""
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import MemberActivity, MemberProfile, MemberRenewal, MembershipApplication
from .services import provision_approved_member, renew_membership


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class MemberManagementTests(TestCase):
    def make_application(self, email="member@example.com", approved=False):
        application = MembershipApplication.objects.create(
            full_name="Test Member", date_of_birth=timezone.localdate() - timedelta(days=365 * 30),
            preferred_email=email, ksa_phone="+966551234567", whatsapp_phone="+966551234567",
            whatsapp_group_member="yes", company_name="Sample QS Employer", job_title="Quantity Surveyor",
            highest_educational_qualification="BSc Quantity Surveying", professional_qualifications=["MRICS"],
            overall_post_qualification_experience="10.00", ksa_experience="6.00",
            working_region="riyadh", privacy_consent_at=timezone.now(),
        )
        if approved:
            application.status = MembershipApplication.Status.APPROVED
            application.reviewed_at = timezone.now()
            application.save(update_fields=["status", "reviewed_at"])
        return application

    def test_pending_applicants_are_not_members(self):
        application = self.make_application()
        self.assertFalse(MemberProfile.objects.filter(application=application).exists())
        with self.assertRaises(ValidationError):
            provision_approved_member(application)

    def test_approval_provisions_one_member_and_number(self):
        app = self.make_application(approved=True)
        member = MemberProfile.objects.get(application=app)
        self.assertEqual(member.membership_number, f"SLQS-KSA-{member.pk:06d}")
        self.assertEqual(member.status, MemberProfile.Status.ACTIVE)
        self.assertIsNone(member.renewal_due_on)
        self.assertEqual(MemberActivity.objects.filter(member=member, action="created").count(), 1)

    def test_repeated_approval_is_idempotent(self):
        app = self.make_application(approved=True)
        member = MemberProfile.objects.get(application=app)
        app.save()
        later, created = provision_approved_member(app)
        self.assertFalse(created)
        self.assertEqual(later.pk, member.pk)
        self.assertEqual(MemberProfile.objects.count(), 1)
        self.assertEqual(MemberActivity.objects.filter(action="created").count(), 1)

    def test_numbers_are_unique_and_not_reused(self):
        first = MemberProfile.objects.get(application=self.make_application(approved=True))
        second = MemberProfile.objects.get(application=self.make_application("member2@example.com", approved=True))
        self.assertNotEqual(first.membership_number, second.membership_number)

    def test_sync_command_backfills_older_approved_applications(self):
        app = self.make_application()
        MembershipApplication.objects.filter(pk=app.pk).update(status=MembershipApplication.Status.APPROVED)
        self.assertEqual(MemberProfile.objects.count(), 0)
        out = StringIO()
        call_command("sync_slqs_members", "--dry-run", stdout=out)
        self.assertIn("profiles missing: 1", out.getvalue())
        self.assertEqual(MemberProfile.objects.count(), 0)
        call_command("sync_slqs_members", stdout=out)
        self.assertEqual(MemberProfile.objects.count(), 1)
        call_command("sync_slqs_members", stdout=out)
        self.assertEqual(MemberProfile.objects.count(), 1)

    def test_application_revocation_deactivates_existing_member(self):
        app = self.make_application(approved=True)
        member = app.member_profile
        app.status = MembershipApplication.Status.REJECTED
        app.save(update_fields=["status"])
        member.refresh_from_db()
        self.assertEqual(member.status, MemberProfile.Status.INACTIVE)
        self.assertEqual(MemberProfile.objects.count(), 1)
        self.assertEqual(MemberActivity.objects.filter(member=member, action="status").count(), 1)

    def test_renewal_records_ledger_and_reactivates(self):
        member = self.make_application(approved=True).member_profile
        yesterday = timezone.localdate() - timedelta(days=1)
        MemberProfile.objects.filter(pk=member.pk).update(status=MemberProfile.Status.EXPIRED, renewal_due_on=yesterday)
        future = timezone.localdate() + timedelta(days=365)
        renew_membership(member.pk, future, note="Committee confirmed renewal")
        member.refresh_from_db()
        self.assertEqual(member.status, MemberProfile.Status.ACTIVE)
        self.assertEqual(member.renewal_due_on, future)
        self.assertEqual(MemberRenewal.objects.filter(member=member, new_due_on=future).count(), 1)
        self.assertEqual(MemberActivity.objects.filter(member=member, action="renewed").count(), 1)

    def test_renewal_rejects_invalid_and_nonextending_date(self):
        member = self.make_application(approved=True).member_profile
        future = timezone.localdate() + timedelta(days=90)
        renew_membership(member.pk, future)
        for invalid_date in (timezone.localdate(), future):
            with self.assertRaises(ValidationError):
                renew_membership(member.pk, invalid_date)
        self.assertEqual(MemberRenewal.objects.filter(member=member).count(), 1)

    def test_daily_expiry_command_and_suspended_preservation(self):
        active = self.make_application(approved=True).member_profile
        suspended = self.make_application("suspended@example.com", approved=True).member_profile
        past = timezone.localdate() - timedelta(days=1)
        MemberProfile.objects.filter(pk=active.pk).update(renewal_due_on=past)
        MemberProfile.objects.filter(pk=suspended.pk).update(renewal_due_on=past, status="suspended")
        call_command("refresh_slqs_members", "--dry-run", stdout=StringIO())
        active.refresh_from_db()
        self.assertEqual(active.status, "active")
        call_command("refresh_slqs_members", stdout=StringIO())
        active.refresh_from_db()
        suspended.refresh_from_db()
        self.assertEqual(active.status, "expired")
        self.assertEqual(suspended.status, "suspended")
        call_command("refresh_slqs_members", stdout=StringIO())
        self.assertEqual(MemberActivity.objects.filter(member=active, action="status").count(), 1)

    def test_member_admin_is_private(self):
        member = self.make_application(approved=True).member_profile
        overview = reverse("admin:membership_memberprofile_overview")
        renew_url = reverse("admin:membership_memberprofile_renew", args=[member.pk])
        self.assertEqual(self.client.get(overview).status_code, 302)
        ordinary = get_user_model().objects.create_user("ordinary", password="pass")
        self.client.force_login(ordinary)
        self.assertEqual(self.client.get(overview).status_code, 302)
        viewer = get_user_model().objects.create_user("viewer", password="pass", is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename="view_memberprofile"))
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(overview).status_code, 200)
        self.assertEqual(self.client.get(renew_url).status_code, 403)

    def test_staff_can_record_renewal_through_admin(self):
        member = self.make_application(approved=True).member_profile
        admin_user = get_user_model().objects.create_superuser("manager", "manager@example.com", "password")
        self.client.force_login(admin_user)
        overview = reverse("admin:membership_memberprofile_overview")
        renew_url = reverse("admin:membership_memberprofile_renew", args=[member.pk])
        self.assertContains(self.client.get(overview), "Member management")
        self.assertEqual(self.client.get(renew_url).status_code, 200)
        response = self.client.post(renew_url, {"new_due_on": (timezone.localdate() + timedelta(days=365)).isoformat(), "note": "Approved"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(MemberRenewal.objects.filter(member=member, processed_by=admin_user).count(), 1)

    def test_member_csv_escapes_formula_values(self):
        app = self.make_application(approved=True)
        app.company_name = '=HYPERLINK("https://example.org")'
        app.save(update_fields=["company_name"])
        admin_user = get_user_model().objects.create_superuser("adminer", "adminer@example.com", "password")
        self.client.force_login(admin_user)
        url = reverse("admin:membership_memberprofile_changelist")
        response = self.client.post(url, {"action": "export_member_csv", "_selected_action": [app.member_profile.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertIn("'=HYPERLINK", response.content.decode("utf-8"))
