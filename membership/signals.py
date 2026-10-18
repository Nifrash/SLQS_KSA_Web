"""Approval creates an idempotent member profile within the save transaction."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import MembershipApplication
from .services import deactivate_revoked_application, provision_approved_member


@receiver(post_save, sender=MembershipApplication, dispatch_uid="slqs_membership_approval_provisioning")
def ensure_member_on_approval(sender, instance, raw=False, **kwargs):
    if raw:  # Fixtures must not create side effects before all data is loaded.
        return
    if instance.status == MembershipApplication.Status.APPROVED:
        provision_approved_member(instance)
    else:
        deactivate_revoked_application(instance)
