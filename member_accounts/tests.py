"""Phase 7 verification, access-control and legacy-migration regression tests."""
import re
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from membership.models import MembershipApplication, MembershipReviewLog
from membership.tests import valid_application
from .models import MemberAccountProfile
from .services import OTPProblem, send_activation_otp, verify_activation_otp


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AccountTests(TestCase):
    def setUp(self):
        cache.clear()

    def create_verified(self, email="member@example.com"):
        user = get_user_model().objects.create_user(
            username=email, email=email, password="GoodStrongPass!9", is_active=True
        )
        MemberAccountProfile.objects.create(user=user, full_name="Test Member", verified_at=timezone.now())
        return user

    def register(self, email="member@example.com"):
        return self.client.post(reverse("member_accounts:register"), {
            "full_name": "Test Member", "email": email,
            "password1": "GoodStrongPass!9", "password2": "GoodStrongPass!9", "website": "",
        })

    def test_register_email_otp_then_dashboard_then_apply(self):
        self.assertEqual(self.client.get(reverse("membership:apply")).status_code, 302)
        response = self.register()
        self.assertRedirects(response, reverse("member_accounts:verify"))
        user = get_user_model().objects.get(email="member@example.com")
        self.assertFalse(user.is_active)
        self.assertFalse(self.client.login(username=user.username, password="GoodStrongPass!9"))
        account = user.slqs_account
        self.assertTrue(account.otp_hash)
        self.assertNotIn("123456", account.otp_hash)
        self.assertEqual(len(mail.outbox), 1)
        code = re.search(r"\b\d{6}\b", mail.outbox[0].body).group()
        response = self.client.post(reverse("member_accounts:verify"), {"code": code})
        self.assertRedirects(response, reverse("member_accounts:dashboard"))
        user.refresh_from_db()
        account.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertIsNotNone(account.verified_at)
        self.assertFalse(account.otp_hash)
        self.assertContains(self.client.get(reverse("member_accounts:dashboard")), "Apply for membership")
        self.assertEqual(self.client.get(reverse("membership:apply")).status_code, 200)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("membership:apply"), valid_application(preferred_email="wrong@example.com"))
        self.assertRedirects(response, reverse("membership:submitted"))
        app = MembershipApplication.objects.get()
        self.assertEqual(app.user, user)
        self.assertEqual(app.preferred_email, user.email)
        self.assertEqual(MembershipReviewLog.objects.filter(application=app).count(), 1)
        self.assertRedirects(self.client.get(reverse("membership:apply")), reverse("member_accounts:dashboard"))

    def test_bad_otp_lockout_is_persisted(self):
        self.register()
        user = get_user_model().objects.get(email="member@example.com")
        correct = re.search(r"\b\d{6}\b", mail.outbox[0].body).group()
        incorrect = "000000" if correct != "000000" else "999999"
        for attempt in range(5):
            resp = self.client.post(reverse("member_accounts:verify"), {"code": incorrect})
            self.assertEqual(resp.status_code, 200)
        user.slqs_account.refresh_from_db()
        self.assertEqual(user.slqs_account.otp_attempts, 5)
        self.assertFalse(user.slqs_account.otp_hash)
        correct = re.search(r"\b\d{6}\b", mail.outbox[0].body).group()
        self.assertEqual(self.client.post(reverse("member_accounts:verify"), {"code": correct}).status_code, 200)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_expiry_resend_cooldown_and_rate(self):
        self.register()
        user = get_user_model().objects.get(email="member@example.com")
        a = user.slqs_account
        a.otp_expires_at = timezone.now() - timedelta(seconds=1)
        a.save(update_fields=["otp_expires_at"])
        code = re.search(r"\b\d{6}\b", mail.outbox[-1].body).group()
        self.assertEqual(self.client.post(reverse("member_accounts:verify"), {"code": code}).status_code, 200)
        self.assertFalse(get_user_model().objects.get(pk=user.pk).is_active)
        self.client.post(reverse("member_accounts:resend_otp"))
        self.assertEqual(len(mail.outbox), 1)
        a.refresh_from_db()
        a.otp_last_sent_at = timezone.now() - timedelta(minutes=2)
        a.save(update_fields=["otp_last_sent_at"])
        self.client.post(reverse("member_accounts:resend_otp"))
        self.assertEqual(len(mail.outbox), 2)
        for _ in range(5):
            a.refresh_from_db()
            a.otp_last_sent_at = timezone.now() - timedelta(minutes=2)
            a.save(update_fields=["otp_last_sent_at"])
            self.client.post(reverse("member_accounts:resend_otp"))
        self.assertEqual(len(mail.outbox), 5)

    def test_recover_activation_requires_account_password(self):
        self.register()
        url = reverse("member_accounts:resume_verification")
        self.client.logout()
        self.assertContains(self.client.post(url, {"email": "member@example.com", "password": "incorrect"}), "Unable to verify")
        self.assertRedirects(self.client.post(url, {"email": "member@example.com", "password": "GoodStrongPass!9"}), reverse("member_accounts:verify"))

    def test_login_logout_post_and_password_reset(self):
        user = self.create_verified()
        login_url = reverse("member_accounts:login")
        self.assertRedirects(self.client.post(login_url, {"username": "MEMBER@EXAMPLE.COM", "password": "GoodStrongPass!9"}), reverse("member_accounts:dashboard"))
        self.assertEqual(self.client.get(reverse("member_accounts:logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("member_accounts:logout")), login_url)
        self.assertRedirects(self.client.post(reverse("member_accounts:password_reset"), {"email": user.email}), reverse("member_accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/password/reset/", mail.outbox[0].body)

    def test_dashboard_privacy_and_profile_edit(self):
        user = self.create_verified()
        self.client.force_login(user)
        dashboard = reverse("member_accounts:dashboard")
        self.assertContains(self.client.get(dashboard), "Not submitted")
        resp = self.client.post(reverse("member_accounts:profile"), {
            "full_name": "New Name", "ksa_phone": "0551234567", "whatsapp_phone": "+966551234567",
            "company_name": "Example Company", "job_title": "Quantity Surveyor",
        })
        self.assertRedirects(resp, reverse("member_accounts:profile"))
        user.slqs_account.refresh_from_db()
        self.assertEqual(user.slqs_account.full_name, "New Name")
        self.assertEqual(user.slqs_account.ksa_phone, "+966551234567")
        self.client.logout()
        self.assertRedirects(self.client.get(dashboard), reverse("member_accounts:login") + "?next=" + dashboard)

    def test_unlinked_legacy_application_requires_administrator_link(self):
        user = self.create_verified()
        app = MembershipApplication.objects.create(
            full_name="Existing Member", date_of_birth=timezone.localdate() - timedelta(days=365*30),
            preferred_email=user.email, ksa_phone="+966551234567", whatsapp_phone="+966551234567",
            whatsapp_group_member="yes", company_name="Company", job_title="Surveyor",
            highest_educational_qualification="BSc QS", professional_qualifications=["MRICS"],
            overall_post_qualification_experience=10, ksa_experience=5, working_region="riyadh",
            privacy_consent_at=timezone.now(),
        )
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("membership:apply")).status_code, 409)
        out = StringIO()
        call_command("link_slqs_legacy_application", str(app.reference), user.email, "--dry-run", stdout=out)
        app.refresh_from_db()
        self.assertIsNone(app.user_id)
        call_command("link_slqs_legacy_application", str(app.reference), user.email, stdout=out)
        app.refresh_from_db()
        self.assertEqual(app.user_id, user.pk)
        self.assertRedirects(self.client.get(reverse("membership:apply")), reverse("member_accounts:dashboard"))

    def test_another_account_cannot_see_application(self):
        user1 = self.create_verified()
        user2 = self.create_verified("second@example.com")
        self.client.force_login(user1)
        self.client.post(reverse("membership:apply"), valid_application())
        user2.slqs_account.full_name = "Second User"
        user2.slqs_account.save(update_fields=["full_name"])
        self.client.force_login(user2)
        response = self.client.get(reverse("member_accounts:dashboard"))
        self.assertNotContains(response, "member@example.com")
        self.assertNotContains(response, "SLQS-KSA-000001")
