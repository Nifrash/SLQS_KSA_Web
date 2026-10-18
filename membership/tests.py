"""Phase 5 regression tests; run with: python manage.py test membership"""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core import mail, signing
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .admin import MembershipApplicationAdmin, MembershipReviewForm, safe_csv
from .forms import MembershipApplicationForm, normalize_ksa_phone, normalize_whatsapp_phone
from .models import MembershipApplication, MembershipReviewLog
from .notifications import TOKEN_MAX_AGE, TOKEN_SALT, update_token


def valid_application(**kwargs):
    data = {
        "full_name": "Test Member",
        "date_of_birth": "1990-03-12",
        "preferred_email": "Member@Example.com",
        "ksa_phone": "0551234567",
        "whatsapp_phone": "+966551234567",
        "whatsapp_group_member": "yes",
        "company_name": "Example Construction Ltd",
        "job_title": "Senior Quantity Surveyor",
        "highest_educational_qualification": "BSc (Hons) Quantity Surveying",
        "professional_qualifications": ["MRICS", "AIQSSL"],
        "professional_qualifications_other": "",
        "overall_post_qualification_experience": "12.50",
        "ksa_experience": "6.00",
        "working_region": "riyadh",
        "suggestions": "Introduce more online CPD sessions.",
        "privacy_consent": "on",
        "website": "",
    }
    data.update(kwargs)
    return data


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    MEMBERSHIP_ADMIN_EMAIL="review@slqs.example",
)
class MembershipTests(TestCase):
    def login_verified_account(self, email="member@example.com"):
        from member_accounts.models import MemberAccountProfile
        user = get_user_model().objects.create_user(username=email, email=email, password="SecurePassword!7", is_active=True)
        MemberAccountProfile.objects.create(user=user, full_name="Test Member", verified_at=timezone.now())
        self.client.force_login(user)
        return user

    def create_application(self, email="member@example.com"):
        return MembershipApplication.objects.create(
            full_name="Test Member",
            date_of_birth=timezone.localdate() - timedelta(days=365 * 30),
            preferred_email=email,
            ksa_phone="+966551234567",
            whatsapp_phone="+966551234567",
            whatsapp_group_member="yes",
            company_name="Example Construction",
            job_title="Quantity Surveyor",
            highest_educational_qualification="BSc Quantity Surveying",
            professional_qualifications=["MRICS"],
            overall_post_qualification_experience="10.00",
            ksa_experience="6.00",
            working_region="riyadh",
            privacy_consent_at=timezone.now(),
        )

    def test_public_landing_and_registration_form(self):
        self.assertEqual(self.client.get(reverse("membership:index")).status_code, 200)
        self.assertEqual(self.client.get(reverse("membership:apply")).status_code, 302)
        self.login_verified_account()
        response = self.client.get(reverse("membership:apply"))
        self.assertEqual(response.status_code, 200)
        for name in ("date_of_birth", "whatsapp_group_member", "professional_qualifications", "suggestions"):
            self.assertContains(response, f'name="{name}', html=False)

    def test_successful_registration_and_notifications(self):
        self.login_verified_account()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("membership:apply"), valid_application())
        self.assertRedirects(response, reverse("membership:submitted"))
        app = MembershipApplication.objects.get()
        self.assertEqual(app.preferred_email, "member@example.com")
        self.assertEqual(app.ksa_phone, "+966551234567")
        self.assertEqual(app.status, "submitted")
        self.assertEqual(app.professional_qualifications, ["MRICS", "AIQSSL"])
        self.assertEqual(MembershipReviewLog.objects.filter(application=app).count(), 1)
        self.assertEqual(len(mail.outbox), 2)  # applicant + optional review inbox

    def test_duplicate_email_is_not_added(self):
        self.create_application()
        self.login_verified_account()
        response = self.client.post(reverse("membership:apply"), valid_application(preferred_email="MEMBER@EXAMPLE.COM"))
        self.assertEqual(response.status_code, 409)  # legacy record awaits staff verification
        self.assertEqual(MembershipApplication.objects.count(), 1)

    def test_none_cannot_mix_with_qualifications(self):
        form = MembershipApplicationForm(valid_application(professional_qualifications=["None", "MRICS"]))
        self.assertFalse(form.is_valid())
        self.assertIn("professional_qualifications", form.errors)

    def test_other_requires_description(self):
        form = MembershipApplicationForm(valid_application(professional_qualifications=["Other"]))
        self.assertFalse(form.is_valid())
        self.assertIn("professional_qualifications_other", form.errors)
        form = MembershipApplicationForm(valid_application(
            professional_qualifications=["Other"],
            professional_qualifications_other="PQS Membership",
        ))
        self.assertTrue(form.is_valid(), form.errors)

    def test_privacy_consent_and_future_dob_are_rejected(self):
        data = valid_application()
        data.pop("privacy_consent")
        self.assertFalse(MembershipApplicationForm(data).is_valid())
        form = MembershipApplicationForm(valid_application(date_of_birth="2099-01-01"))
        self.assertFalse(form.is_valid())
        self.assertIn("date_of_birth", form.errors)

    def test_invalid_phones_rejected(self):
        form = MembershipApplicationForm(valid_application(ksa_phone="somewords"))
        self.assertFalse(form.is_valid())
        self.assertIn("ksa_phone", form.errors)
        self.assertEqual(normalize_whatsapp_phone("+94771234567"), "+94771234567")
        self.assertEqual(normalize_ksa_phone("0551234567"), "+966551234567")

    def test_honeypot_does_not_store_application(self):
        self.login_verified_account()
        response = self.client.post(reverse("membership:apply"), valid_application(website="bot value"))
        self.assertRedirects(response, reverse("membership:submitted"))
        self.assertEqual(MembershipApplication.objects.count(), 0)

    def test_bad_and_expired_edit_links_fail(self):
        url = reverse("membership:update", kwargs={"token": "invalid-token"})
        self.assertEqual(self.client.get(url).status_code, 404)
        app = self.create_application()
        app.status = MembershipApplication.Status.MORE_INFO
        app.save(update_fields=["status"])
        token = update_token(app)
        with patch("membership.views.signing.loads", side_effect=signing.SignatureExpired("expired")):
            self.assertEqual(self.client.get(reverse("membership:update", kwargs={"token": token})).status_code, 404)

    def test_secure_resubmission_revokes_link(self):
        app = self.create_application()
        app.status = MembershipApplication.Status.MORE_INFO
        app.save(update_fields=["status"])
        url = reverse("membership:update", kwargs={"token": update_token(app)})
        self.assertEqual(self.client.get(url).status_code, 200)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url, valid_application(suggestions="Updated suggestions"))
        self.assertRedirects(response, reverse("membership:submitted"))
        app.refresh_from_db()
        self.assertEqual(app.status, "submitted")
        self.assertEqual(app.suggestions, "Updated suggestions")
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertTrue(MembershipReviewLog.objects.filter(application=app, from_status="more_info", to_status="submitted").exists())

    def test_update_can_change_preferred_email_and_invalidates_old_link(self):
        app = self.create_application()
        app.status = MembershipApplication.Status.MORE_INFO
        app.save(update_fields=["status"])
        url = reverse("membership:update", kwargs={"token": update_token(app)})
        response = self.client.post(url, valid_application(preferred_email="updated@example.com"))
        self.assertRedirects(response, reverse("membership:submitted"))
        app.refresh_from_db()
        self.assertEqual(app.preferred_email, "updated@example.com")
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_system_admin_requires_login(self):
        app = self.create_application()
        url = reverse("admin:membership_membershipapplication_change", args=[app.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(get_user_model().objects.create_superuser("super", "super@example.com", "test-pw"))
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_model_experience_validation_accepts_numeric_strings(self):
        app = self.create_application()
        app.overall_post_qualification_experience = "10.00"
        app.ksa_experience = "6.00"
        app.clean()  # admin forms may provide a raw model instance with strings

        app.ksa_experience = "invalid"
        with self.assertRaises(ValidationError) as error:
            app.clean()
        self.assertIn("ksa_experience", error.exception.message_dict)

        app.ksa_experience = "NaN"
        with self.assertRaises(ValidationError) as error:
            app.clean()
        self.assertIn("ksa_experience", error.exception.message_dict)

    def test_admin_review_requires_note_and_sends_email(self):
        app = self.create_application()
        reviewer = get_user_model().objects.create_superuser("reviewer", "reviewer@example.com", "test-pw")
        # Form validation prevents decisions without a review explanation.
        form = MembershipReviewForm(data={"status": MembershipApplication.Status.MORE_INFO}, instance=app)
        self.assertFalse(form.is_valid())
        self.assertIn("decision_note", form.errors)
        obj = MembershipApplication.objects.get(pk=app.pk)
        obj.status = MembershipApplication.Status.APPROVED
        model_admin = MembershipApplicationAdmin(MembershipApplication, admin.site)
        with self.captureOnCommitCallbacks(execute=True):
            model_admin.save_model(
                SimpleNamespace(user=reviewer), obj,
                SimpleNamespace(cleaned_data={"decision_note": "Welcome to SLQS."}),
                change=True,
            )
        obj.refresh_from_db()
        self.assertEqual(obj.reviewed_by, reviewer)
        self.assertEqual(obj.status, "approved")
        self.assertTrue(MembershipReviewLog.objects.filter(application=obj, actor=reviewer, to_status="approved").exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Approved", mail.outbox[0].body)

    def test_csv_formula_escape(self):
        self.assertEqual(safe_csv("=1+1"), "'=1+1")
        self.assertEqual(safe_csv("+cmd"), "'+cmd")
        self.assertEqual(safe_csv("Normal Company"), "Normal Company")
