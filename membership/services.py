"""Atomic membership lifecycle services shared by admin, signals and commands."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import MemberActivity, MemberProfile, MemberRenewal, MembershipApplication


def _actor_for(application):
    return application.reviewed_by if application.reviewed_by_id else None


@transaction.atomic
def provision_approved_member(application):
    """Idempotently create one stable membership number for an approved applicant.

    The profile is linked via a unique OneToOneField; using its PK to allocate
    the display ID eliminates sequence races and prevents accidental reuse.
    """
    if application.status != MembershipApplication.Status.APPROVED:
        raise ValidationError("Only approved applications can become members.")

    member, created = MemberProfile.objects.get_or_create(
        application=application,
        defaults={
            "status": MemberProfile.Status.ACTIVE,
            "joined_on": (
                timezone.localtime(application.reviewed_at).date()
                if application.reviewed_at else timezone.localdate()
            ),
        },
    )
    if created:
        # Historical membership numbers imported in Phase 9.5 must not be reused.
        # Skip reserved identifiers, rather than failing a future approval when
        # the PK-based number happens to reach an imported legacy member number.
        next_sequence = member.pk
        while True:
            number = f"SLQS-KSA-{next_sequence:06d}"
            if not MemberProfile.objects.filter(membership_number=number).exclude(pk=member.pk).exists():
                break
            next_sequence += 1
        MemberProfile.objects.filter(pk=member.pk).update(membership_number=number)
        member.membership_number = number
        MemberActivity.objects.create(
            member=member, action=MemberActivity.Action.CREATED,
            new_status=member.status, actor=_actor_for(application),
            note="Member profile generated from approved application.",
        )
    return member, created


@transaction.atomic
def deactivate_revoked_application(application):
    """Protect membership when a previously approved application is revoked."""
    member = MemberProfile.objects.select_for_update().filter(application=application).first()
    if member and member.status != MemberProfile.Status.INACTIVE:
        old_status = member.status
        member.status = MemberProfile.Status.INACTIVE
        member.save(update_fields=["status", "updated_at"])
        MemberActivity.objects.create(
            member=member, action=MemberActivity.Action.STATUS,
            old_status=old_status, new_status=member.status,
            actor=_actor_for(application), note="Application is no longer approved.",
        )
    return member


@transaction.atomic
def renew_membership(member_id, new_due_on, *, actor=None, note=""):
    """Record an explicit renewal, extend date and activate; never alter fees."""
    member = MemberProfile.objects.select_for_update().select_related("application").get(pk=member_id)
    today = timezone.localdate()
    if member.application.status != MembershipApplication.Status.APPROVED:
        raise ValidationError("The associated membership application is not approved.")
    if not new_due_on or new_due_on <= today:
        raise ValidationError("New renewal due date must be later than today.")
    if member.renewal_due_on and new_due_on <= member.renewal_due_on:
        raise ValidationError("New renewal due date must extend the existing due date.")

    previous_status = member.status
    previous_due = member.renewal_due_on
    member.renewal_due_on = new_due_on
    member.status = MemberProfile.Status.ACTIVE
    member.full_clean()
    member.save(update_fields=["status", "renewal_due_on", "updated_at"])
    MemberRenewal.objects.create(
        member=member, old_due_on=previous_due, new_due_on=new_due_on,
        note=note[:500], processed_by=actor,
    )
    MemberActivity.objects.create(
        member=member, action=MemberActivity.Action.RENEWED,
        old_status=previous_status, new_status=member.status,
        old_due_on=previous_due, new_due_on=new_due_on,
        note=note[:1500], actor=actor,
    )
    return member


@transaction.atomic
def expire_overdue_members(*, dry_run=False):
    """Expire only active, past-due members; leave suspended/inactive untouched."""
    today = timezone.localdate()
    qs = MemberProfile.objects.filter(
        status=MemberProfile.Status.ACTIVE, renewal_due_on__lt=today,
    )
    if dry_run:
        return qs.count()
    count = 0
    for member in qs.select_for_update().iterator():
        member.status = MemberProfile.Status.EXPIRED
        member.save(update_fields=["status", "updated_at"])
        MemberActivity.objects.create(
            member=member, action=MemberActivity.Action.STATUS,
            old_status=MemberProfile.Status.ACTIVE,
            new_status=MemberProfile.Status.EXPIRED,
            note="Automatic status update after renewal due date.",
        )
        count += 1
    return count
