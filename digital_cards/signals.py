"""Automatic issuance when a new approved member record is created."""
from django.db.models.signals import post_save
from django.dispatch import receiver
from membership.models import MemberProfile, MembershipApplication
from .services import ensure_card


@receiver(post_save, sender=MemberProfile, dispatch_uid="slqs_issue_digital_card_on_approval")
def issue_new_member_card(sender, instance, created=False, raw=False, **kwargs):
    if raw or not created:
        return
    if instance.application.status == MembershipApplication.Status.APPROVED:
        ensure_card(instance)
