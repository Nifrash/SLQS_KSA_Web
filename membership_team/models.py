"""Private membership-committee workflow linked to existing Phase 5/6 records."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class CommitteeCase(models.Model):
    class Priority(models.TextChoices):
        NORMAL = 'normal', 'Normal'
        HIGH = 'high', 'High'
        URGENT = 'urgent', 'Urgent'

    application = models.OneToOneField(
        'membership.MembershipApplication', on_delete=models.PROTECT,
        related_name='committee_case',
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='slqs_assigned_cases',
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='slqs_cases_assigned_by',
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-application__created_at', '-pk')
        permissions = (
            ('assign_committeecase', 'Assign committee applications'),
            ('recommend_committeecase', 'Recommend application decisions'),
            ('decide_committeecase', 'Approve or reject membership applications'),
            ('request_info_committeecase', 'Request applicant information'),
            ('export_committeecase', 'Export committee application data'),
        )

    def __str__(self):
        return f'Committee review {self.application.short_reference}'


class CommitteeRecommendation(models.Model):
    class Outcome(models.TextChoices):
        APPROVE = 'approve', 'Recommend approval'
        REJECT = 'reject', 'Recommend rejection'
        MORE_INFO = 'more_info', 'Recommend additional information'

    case = models.ForeignKey(CommitteeCase, on_delete=models.PROTECT, related_name='recommendations')
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='slqs_committee_recommendations',
    )
    outcome = models.CharField(max_length=12, choices=Outcome.choices)
    note = models.TextField(max_length=3000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-pk')

    def __str__(self):
        return f'{self.case.application.short_reference}: {self.get_outcome_display()}'


class CommitteeActionLog(models.Model):
    class Action(models.TextChoices):
        ASSIGNED = 'assigned', 'Assigned / reassigned'
        PRIORITY = 'priority', 'Priority updated'
        RECOMMENDED = 'recommended', 'Recommendation added'
        INFO = 'more_info', 'Additional information requested'
        DECIDED = 'decided', 'Final decision recorded'

    case = models.ForeignKey(CommitteeCase, on_delete=models.PROTECT, related_name='committee_history')
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='slqs_committee_actions',
    )
    action = models.CharField(max_length=16, choices=Action.choices)
    note = models.TextField(max_length=3000, blank=True)
    before = models.CharField(max_length=120, blank=True)
    after = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ('-created_at', '-pk')

    def __str__(self):
        return f'{self.case.application.short_reference}: {self.get_action_display()}'
