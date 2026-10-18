"""Automatically attach a committee case to new (and subsequently saved) applications."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from membership.models import MembershipApplication
from .models import CommitteeCase


@receiver(post_save, sender=MembershipApplication, dispatch_uid='slqs_committee_case_ensure')
def ensure_committee_case(sender, instance, raw=False, **kwargs):
    if raw:
        return
    CommitteeCase.objects.get_or_create(application=instance)
