"""Email-verified website accounts; separate from the committee's membership decision."""
from django.conf import settings
from django.db import models


class MemberAccountProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="slqs_account"
    )
    full_name = models.CharField(max_length=180)
    ksa_phone = models.CharField(max_length=20, blank=True)
    whatsapp_phone = models.CharField(max_length=20, blank=True)
    company_name = models.CharField(max_length=180, blank=True)
    job_title = models.CharField(max_length=150, blank=True)
    profile_photo = models.ImageField(
        upload_to="member_photos/%Y/%m/", blank=True,
        help_text="Optional profile photo. JPEG, PNG or WebP, up to 5 MB.",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    otp_hash = models.CharField(max_length=128, blank=True)
    otp_expires_at = models.DateTimeField(null=True, blank=True)
    otp_last_sent_at = models.DateTimeField(null=True, blank=True)
    otp_attempts = models.PositiveSmallIntegerField(default=0)
    otp_window_started_at = models.DateTimeField(null=True, blank=True)
    otp_sent_in_window = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "SLQS website account"
        verbose_name_plural = "SLQS website accounts"

    def __str__(self):
        return self.user.email

    @property
    def is_verified(self):
        return bool(self.verified_at and self.user.is_active)
