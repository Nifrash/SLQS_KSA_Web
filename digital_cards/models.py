"""Member-owned digital cards with opaque public verification tokens."""
import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class DigitalMembershipCard(models.Model):
    member = models.OneToOneField(
        "membership.MemberProfile", on_delete=models.PROTECT, related_name="digital_card"
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    issued_at = models.DateTimeField(default=timezone.now, editable=False)
    reissue_count = models.PositiveIntegerField(default=0, editable=False)
    revoked_at = models.DateTimeField(null=True, blank=True, editable=False)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="slqs_cards_revoked", editable=False,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Digital membership card"
        verbose_name_plural = "Digital membership cards"

    def __str__(self):
        return f"Digital card: {self.member.membership_number or self.member_id}"


class CardAuditEvent(models.Model):
    class Action(models.TextChoices):
        ISSUED = "issued", "Issued"
        REVOKED = "revoked", "Revoked"
        REISSUED = "reissued", "Reissued with new QR"

    card = models.ForeignKey(
        DigitalMembershipCard, on_delete=models.PROTECT, related_name="audit_events"
    )
    action = models.CharField(max_length=10, choices=Action.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="slqs_card_actions"
    )
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ("-created_at", "-pk")
        verbose_name = "Digital card audit event"

    def __str__(self):
        return f"{self.card.member.membership_number}: {self.get_action_display()}"
