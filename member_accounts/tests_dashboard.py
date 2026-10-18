"""Regression tests for Phase 7 member dashboard / profile photograph patch."""
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import MemberAccountProfile


def picture_bytes(size=(1200, 900), format="PNG"):
    buf = BytesIO()
    Image.new("RGB", size, (25, 80, 125)).save(buf, format=format)
    return buf.getvalue()


class MemberDashboardEnhancementTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        override = override_settings(MEDIA_ROOT=self.media.name)
        override.enable()
        self.addCleanup(override.disable)
        self.user = get_user_model().objects.create_user(
            username="member.dashboard@example.org",
            email="member.dashboard@example.org",
            password="SafePassword123!",
            is_active=True,
        )
        self.account = MemberAccountProfile.objects.create(
            user=self.user, full_name="SLQS Member", verified_at=timezone.now()
        )
        self.client.force_login(self.user)

    def profile_data(self, **kwargs):
        return dict(full_name="SLQS Member", ksa_phone="", whatsapp_phone="",
                    company_name="", job_title="", **kwargs)

    def test_apply_membership_link_on_dashboard_and_profile(self):
        response = self.client.get(reverse("member_accounts:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Apply Membership")
        self.assertContains(response, reverse("membership:apply"))
        self.assertContains(response, "Not submitted")
        profile = self.client.get(reverse("member_accounts:profile"))
        self.assertEqual(profile.status_code, 200)
        self.assertContains(profile, reverse("membership:apply"))
        self.assertContains(profile, "multipart/form-data")
        self.assertContains(profile, 'name="profile_photo"')

    def test_upload_photo_normalizes_and_displays(self):
        upload = SimpleUploadedFile("photo.png", picture_bytes(), content_type="image/png")
        response = self.client.post(reverse("member_accounts:profile"), self.profile_data(profile_photo=upload))
        self.assertRedirects(response, reverse("member_accounts:profile"))
        self.account.refresh_from_db()
        self.assertTrue(self.account.profile_photo.name.endswith(".jpg"))
        filename = self.account.profile_photo.path
        self.assertTrue(Path(filename).is_file())
        with Image.open(filename) as photo:
            self.assertEqual(photo.format, "JPEG")
            self.assertLessEqual(photo.width, 900)
            self.assertLessEqual(photo.height, 900)
            self.assertFalse(photo.getexif())
        dashboard = self.client.get(reverse("member_accounts:dashboard"))
        self.assertContains(dashboard, self.account.profile_photo.url)

    def test_rejects_disguised_invalid_image(self):
        fake = SimpleUploadedFile("fake.jpg", b"Not a valid photograph", content_type="image/jpeg")
        response = self.client.post(reverse("member_accounts:profile"), self.profile_data(profile_photo=fake))
        self.assertEqual(response.status_code, 200)
        self.assertIn("profile_photo", response.context["form"].errors)
        self.account.refresh_from_db()
        self.assertFalse(self.account.profile_photo)

    def test_rejects_oversized_photo(self):
        huge = SimpleUploadedFile("big.png", picture_bytes() + b"x" * (5 * 1024 * 1024 + 1), content_type="image/png")
        response = self.client.post(reverse("member_accounts:profile"), self.profile_data(profile_photo=huge))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "5 MB or smaller")
        self.account.refresh_from_db()
        self.assertFalse(self.account.profile_photo)

    def test_photo_can_be_cleared(self):
        upload = SimpleUploadedFile("photo.png", picture_bytes(size=(100, 100)), content_type="image/png")
        self.client.post(reverse("member_accounts:profile"), self.profile_data(profile_photo=upload))
        self.account.refresh_from_db()
        self.assertTrue(self.account.profile_photo)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("member_accounts:profile"), self.profile_data(**{"profile_photo-clear": "on"}))
        self.assertRedirects(response, reverse("member_accounts:profile"))
        self.account.refresh_from_db()
        self.assertFalse(self.account.profile_photo)

    def test_only_logged_in_accounts_access_portal(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("member_accounts:profile")).status_code, 302)
        self.assertEqual(self.client.get(reverse("member_accounts:dashboard")).status_code, 302)
