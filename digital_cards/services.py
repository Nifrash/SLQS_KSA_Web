"""Card lifecycle and live membership eligibility checks.

QR codes encode only a random, replaceable token URL, never personal information.
"""
from datetime import date
import uuid
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from membership.models import MemberProfile, MembershipApplication
from .models import CardAuditEvent, DigitalMembershipCard


def membership_eligibility(member, today=None):
    today = today or timezone.localdate()
    if member.application.status != MembershipApplication.Status.APPROVED:
        return False, "Membership application is not approved."
    if member.status != MemberProfile.Status.ACTIVE:
        return False, f"Membership is {member.get_status_display().lower()}."
    if member.renewal_due_on and member.renewal_due_on < today:
        return False, "Membership renewal is overdue."
    if not member.membership_number:
        return False, "Membership number is being prepared."
    return True, "Membership is currently active."


def card_eligibility(card, today=None):
    if card.revoked_at:
        return False, "This digital card has been revoked."
    return membership_eligibility(card.member, today=today)


def verification_url(card):
    """Canonical domain avoids trusting arbitrary Host headers in QR payloads."""
    return settings.WAGTAILADMIN_BASE_URL.rstrip("/") + reverse(
        "digital_cards:verify", kwargs={"token": card.token}
    )


@transaction.atomic
def ensure_card(member, *, actor=None):
    """Idempotent issuance. Never restores revoked cards."""
    member = MemberProfile.objects.select_for_update().select_related("application").get(pk=member.pk)
    if member.application.status != MembershipApplication.Status.APPROVED:
        raise ValidationError("Only approved SLQS members can receive a card.")
    card, created = DigitalMembershipCard.objects.get_or_create(member=member)
    if created:
        CardAuditEvent.objects.create(card=card, action=CardAuditEvent.Action.ISSUED, actor=actor)
    return card, created


@transaction.atomic
def revoke_card(member_id, *, actor, note):
    if not note.strip():
        raise ValidationError("A reason is required to revoke a card.")
    card = DigitalMembershipCard.objects.select_for_update().select_related(
        "member", "member__application"
    ).get(member_id=member_id)
    if card.revoked_at is not None:
        raise ValidationError("This card is already revoked.")
    card.revoked_at = timezone.now()
    card.revoked_by = actor
    card.save(update_fields=("revoked_at", "revoked_by", "updated_at"))
    CardAuditEvent.objects.create(
        card=card, action=CardAuditEvent.Action.REVOKED, actor=actor, note=note.strip()[:500]
    )
    return card


@transaction.atomic
def reissue_card(member_id, *, actor, note):
    if not note.strip():
        raise ValidationError("A reason is required to replace a card.")
    member = MemberProfile.objects.select_for_update().select_related("application").get(pk=member_id)
    eligible, reason = membership_eligibility(member)
    if not eligible:
        raise ValidationError(reason)
    card, created = DigitalMembershipCard.objects.get_or_create(member=member)
    if created:
        CardAuditEvent.objects.create(
            card=card, action=CardAuditEvent.Action.ISSUED, actor=actor,
            note=note.strip()[:500],
        )
    else:
        card.token = uuid.uuid4()  # Rotating invalidates the previous QR immediately.
        card.revoked_at = None
        card.revoked_by = None
        card.issued_at = timezone.now()
        card.reissue_count += 1
        card.save(update_fields=("token", "revoked_at", "revoked_by", "issued_at", "reissue_count", "updated_at"))
        CardAuditEvent.objects.create(
            card=card, action=CardAuditEvent.Action.REISSUED, actor=actor,
            note=note.strip()[:500],
        )
    return card
