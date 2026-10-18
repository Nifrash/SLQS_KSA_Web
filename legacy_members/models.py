"""Audited Google Forms import batches and one-time activation challenges."""
import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class LegacyImportBatch(models.Model):
    filename = models.CharField(max_length=240)
    sha256 = models.CharField(max_length=64, db_index=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    row_count = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)


class LegacyMemberRecord(models.Model):
    """One historical registration; records are never silently overwritten on re-import."""
    source_key = models.CharField(max_length=128, unique=True)
    application = models.OneToOneField('membership.MembershipApplication', on_delete=models.PROTECT,
                                       related_name='legacy_record')
    batch = models.ForeignKey(LegacyImportBatch, on_delete=models.PROTECT, related_name='records')
    imported_email = models.EmailField(max_length=254)
    imported_status = models.CharField(max_length=12)
    activated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)


class LegacyActivationChallenge(models.Model):
    record = models.ForeignKey(LegacyMemberRecord, on_delete=models.PROTECT, related_name='challenges')
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    otp_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    attempted = models.PositiveSmallIntegerField(default=0)
    identity_attempts = models.PositiveSmallIntegerField(default=0)
    verified_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ('-created_at',)
