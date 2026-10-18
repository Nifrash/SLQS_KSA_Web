"""Transactional Phase 8 workflow. Reuses membership approval/provisioning signals."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from membership.models import MembershipApplication, MembershipReviewLog, MembershipInformationRequest
from membership.notifications import status_email
from .models import CommitteeActionLog, CommitteeCase, CommitteeRecommendation
from .permissions import PERM_DECIDE

OPEN_STATUSES = {MembershipApplication.Status.SUBMITTED, MembershipApplication.Status.IN_REVIEW}
MEMBERSHIP_HEAD_GROUP = 'SLQS Membership Head'


def _is_authorized_decider(actor):
    """Service-level guard: views already check this, but services must too."""
    return (
        actor.is_authenticated
        and actor.is_active
        and actor.is_staff
        and actor.has_perm(PERM_DECIDE)
    )


def _head_can_decide_directly(actor):
    """Only the Membership Head (or superuser) may skip independent review."""
    return _is_authorized_decider(actor) and (
        actor.is_superuser
        or actor.groups.filter(name=MEMBERSHIP_HEAD_GROUP).exists()
    )


def _require_open(application):
    if application.status not in OPEN_STATUSES:
        raise ValidationError('This application is not open for committee review.')


def _lock(case_id):
    # One order for all operations: lock application, then case.
    # Read FK first, then lock rows within an atomic transaction.
    case_ref = CommitteeCase.objects.only('application_id').get(pk=case_id)
    application = MembershipApplication.objects.select_for_update().get(pk=case_ref.application_id)
    case = CommitteeCase.objects.select_for_update().get(pk=case_id)
    return case, application


def _in_review(application, actor):
    if application.status == MembershipApplication.Status.SUBMITTED:
        application.status = MembershipApplication.Status.IN_REVIEW
        application.reviewed_by = actor
        application.reviewed_at = timezone.now()
        application.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])
        MembershipReviewLog.objects.create(
            application=application, from_status=MembershipApplication.Status.SUBMITTED,
            to_status=application.status, actor=actor, note='Committee review started.',
        )


@transaction.atomic
def assign_case(case_id, assigned_to, priority, *, actor):
    case, app = _lock(case_id)
    _require_open(app)
    if not assigned_to.is_active or not assigned_to.is_staff or not assigned_to.has_perm('membership_team.view_committeecase'):
        raise ValidationError('Assign to an active, authorized committee user.')
    if priority not in CommitteeCase.Priority.values:
        raise ValidationError('Invalid priority.')
    old_assignee = str(case.assigned_to_id or '')
    old_priority = case.priority
    if case.assigned_to_id != assigned_to.pk:
        case.assigned_to = assigned_to
        case.assigned_by = actor
        case.assigned_at = timezone.now()
        CommitteeActionLog.objects.create(
            case=case, actor=actor, action=CommitteeActionLog.Action.ASSIGNED,
            before=old_assignee, after=str(assigned_to.pk),
            note=f'Assigned to {assigned_to.get_username()}.',
        )
    if old_priority != priority:
        case.priority = priority
        CommitteeActionLog.objects.create(
            case=case, actor=actor, action=CommitteeActionLog.Action.PRIORITY,
            before=old_priority, after=priority,
        )
    case.save()
    _in_review(app, actor)
    return case


@transaction.atomic
def recommend_case(case_id, outcome, note, *, actor):
    case, app = _lock(case_id)
    _require_open(app)
    if outcome not in CommitteeRecommendation.Outcome.values or not note.strip():
        raise ValidationError('Choose a recommendation and provide an explanation.')
    _in_review(app, actor)
    recommendation = CommitteeRecommendation.objects.create(
        case=case, reviewer=actor, outcome=outcome, note=note.strip(),
    )
    CommitteeActionLog.objects.create(
        case=case, actor=actor, action=CommitteeActionLog.Action.RECOMMENDED,
        after=outcome, note=note.strip(),
    )
    return recommendation


@transaction.atomic
def request_information(case_id, note, *, actor):
    case, app = _lock(case_id)
    _require_open(app)
    if not note.strip():
        raise ValidationError('Specify the information required from the applicant.')
    old_status = app.status
    app.status = MembershipApplication.Status.MORE_INFO
    app.reviewed_by = actor
    app.reviewed_at = timezone.now()
    app.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])
    MembershipReviewLog.objects.create(
        application=app, from_status=old_status, to_status=app.status, actor=actor, note=note.strip(),
    )
    # A durable, member-visible request, rather than an email-only instruction.
    MembershipInformationRequest.objects.create(
        application=app, requested_by=actor, message=note.strip(),
    )
    CommitteeActionLog.objects.create(
        case=case, actor=actor, action=CommitteeActionLog.Action.INFO,
        before=old_status, after=app.status, note=note.strip(),
    )
    transaction.on_commit(lambda pk=app.pk, msg=note.strip(): status_email(MembershipApplication.objects.get(pk=pk), msg))
    return app


@transaction.atomic
def decide_case(case_id, decision, note, *, actor):
    # Do not rely on the HTTP view decorator alone: direct callers must also
    # be authorized. Only Head/superuser can bypass an independent recommendation.
    if not _is_authorized_decider(actor):
        raise PermissionDenied('Only an authorized membership approver may record a final decision.')
    case, app = _lock(case_id)
    _require_open(app)
    if decision not in (MembershipApplication.Status.APPROVED, MembershipApplication.Status.REJECTED):
        raise ValidationError('Invalid final decision.')
    if not note or not note.strip():
        raise ValidationError('Record the reason for the final committee decision.')

    current_independent_recommendation = CommitteeRecommendation.objects.filter(
        case=case, created_at__gte=app.updated_at,
    ).exclude(reviewer=actor).exists()
    is_direct_head_decision = _head_can_decide_directly(actor) and not current_independent_recommendation
    if not current_independent_recommendation and not is_direct_head_decision:
        raise ValidationError(
            'A current recommendation from a different committee reviewer is required '
            'unless the final decision is made by the Membership Head.'
        )

    old_status = app.status
    app.status = decision
    app.reviewed_by = actor
    app.reviewed_at = timezone.now()
    app.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])
    # The existing Phase 6 signal provisions an approved MemberProfile once.
    MembershipReviewLog.objects.create(
        application=app, from_status=old_status, to_status=decision,
        actor=actor, note=note.strip(),
    )
    # Label any direct decision in the PRIVATE audit trail, not in the
    # applicant-facing email. The applicant receives the original reason only.
    audit_note = (
        '[Direct Membership Head decision; independent recommendation waived] '
        + note.strip()
        if is_direct_head_decision else note.strip()
    )
    CommitteeActionLog.objects.create(
        case=case, actor=actor, action=CommitteeActionLog.Action.DECIDED,
        before=old_status, after=decision, note=audit_note,
    )
    transaction.on_commit(
        lambda pk=app.pk, msg=note.strip():
        status_email(MembershipApplication.objects.get(pk=pk), msg)
    )
    return app
