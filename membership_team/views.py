"""Standalone committee portal; never expose private applications to public accounts."""
import csv
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator

from membership.models import MemberProfile, MembershipApplication, MembershipInformationRequest
from .forms import AssignCaseForm, CommitteeLoginForm, DecisionForm, MoreInfoForm, RecommendationForm
from .models import CommitteeCase
from .permissions import (
    PERM_ASSIGN, PERM_DECIDE, PERM_EXPORT, PERM_INFO, PERM_RECOMMEND, PERM_VIEW,
    accessible_cases, committee_required,
)
from .services import assign_case, decide_case, recommend_case, request_information


class CommitteeLoginView(LoginView):
    template_name = 'membership_team/login.html'
    authentication_form = CommitteeLoginForm
    next_page = reverse_lazy('membership_team:dashboard')
    redirect_authenticated_user = False
    extra_context = {'portal_login': True}


@require_POST
def logout_view(request):
    logout(request)
    return redirect('membership_team:login')


def _filters(request, qs):
    q = request.GET.get('q', '').strip()[:100]
    status = request.GET.get('status', '')
    region = request.GET.get('region', '')
    priority = request.GET.get('priority', '')
    if q:
        qs = qs.filter(
            Q(application__full_name__icontains=q) |
            Q(application__preferred_email__icontains=q) |
            Q(application__company_name__icontains=q) |
            Q(application__job_title__icontains=q)
        )
    if status in MembershipApplication.Status.values:
        qs = qs.filter(application__status=status)
    if region in dict(MembershipApplication._meta.get_field('working_region').choices):
        qs = qs.filter(application__working_region=region)
    if priority in CommitteeCase.Priority.values:
        qs = qs.filter(priority=priority)
    return qs, {'q': q, 'status': status, 'region': region, 'priority': priority}


@never_cache
@committee_required()
def dashboard(request):
    base = accessible_cases(request.user)
    open_states = [MembershipApplication.Status.SUBMITTED, MembershipApplication.Status.IN_REVIEW]
    recent = base.order_by('-application__created_at')[:7]
    counts = {
        'total': base.count(),
        'pending': base.filter(application__status__in=open_states).count(),
        'needs_info': base.filter(application__status=MembershipApplication.Status.MORE_INFO).count(),
        'approved': base.filter(application__status=MembershipApplication.Status.APPROVED).count(),
        'unassigned': base.filter(assigned_to__isnull=True, application__status__in=open_states).count(),
    }
    return render(request, 'membership_team/dashboard.html', {'counts': counts, 'recent': recent})


@never_cache
@committee_required()
def application_list(request):
    qs, active_filters = _filters(request, accessible_cases(request.user))
    qs = qs.order_by('-application__created_at', '-pk')
    page = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'membership_team/application_list.html', {
        'page': page, 'filters': active_filters,
        'statuses': MembershipApplication.Status.choices,
        'regions': MembershipApplication._meta.get_field('working_region').choices,
        'priorities': CommitteeCase.Priority.choices,
    })


@never_cache
@committee_required()
def case_detail(request, pk):
    case = get_object_or_404(accessible_cases(request.user), pk=pk)
    app = case.application
    history = app.review_history.select_related('actor')[:25]
    recommendations = case.recommendations.select_related('reviewer')[:20]
    committee_history = case.committee_history.select_related('actor')[:25]
    document_requests = MembershipInformationRequest.objects.filter(application=app).prefetch_related('response')
    return render(request, 'membership_team/case_detail.html', {
        'case': case, 'app': app, 'history': history, 'document_requests': document_requests,
        'recommendations': recommendations, 'committee_history': committee_history,
        'assign_form': AssignCaseForm(case=case),
        'recommend_form': RecommendationForm(),
        'decision_form': DecisionForm(), 'info_form': MoreInfoForm(),
        'open_case': app.status in (MembershipApplication.Status.SUBMITTED, MembershipApplication.Status.IN_REVIEW),
    })


@require_POST
@committee_required(PERM_ASSIGN)
def assign(request, pk):
    case = get_object_or_404(CommitteeCase, pk=pk)
    form = AssignCaseForm(request.POST, case=case)
    if form.is_valid():
        try:
            assign_case(case.pk, form.cleaned_data['assigned_to'], form.cleaned_data['priority'], actor=request.user)
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
        else:
            messages.success(request, 'Application assignment updated.')
    else:
        messages.error(request, 'Assignment could not be saved. Select an authorized reviewer and priority.')
    return redirect('membership_team:case_detail', pk=pk)


@require_POST
@committee_required(PERM_RECOMMEND)
def recommend(request, pk):
    case = get_object_or_404(accessible_cases(request.user), pk=pk)
    form = RecommendationForm(request.POST)
    if form.is_valid():
        try:
            recommend_case(case.pk, form.cleaned_data['outcome'], form.cleaned_data['note'], actor=request.user)
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
        else:
            messages.success(request, 'Private recommendation recorded for the final approver.')
    else:
        messages.error(request, 'Both a recommendation and a note are required.')
    return redirect('membership_team:case_detail', pk=pk)


@require_POST
@committee_required(PERM_INFO)
def more_info(request, pk):
    case = get_object_or_404(CommitteeCase, pk=pk)
    form = MoreInfoForm(request.POST)
    if form.is_valid():
        try:
            request_information(case.pk, form.cleaned_data['note'], actor=request.user)
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
        else:
            messages.success(request, 'Information request recorded; applicant notification queued.')
    else:
        messages.error(request, 'Please specify what information is required.')
    return redirect('membership_team:case_detail', pk=pk)


@require_POST
@committee_required(PERM_DECIDE)
def decide(request, pk):
    case = get_object_or_404(CommitteeCase, pk=pk)
    form = DecisionForm(request.POST)
    if form.is_valid():
        try:
            decide_case(case.pk, form.cleaned_data['decision'], form.cleaned_data['note'], actor=request.user)
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
        else:
            messages.success(request, 'Final decision recorded; membership record and applicant notification updated.')
    else:
        messages.error(request, 'Choose a final decision and provide the reason.')
    return redirect('membership_team:case_detail', pk=pk)


def _safe_csv(value):
    text = '' if value is None else str(value)
    if text.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')):
        return "'" + text
    return text


@never_cache
@committee_required(PERM_EXPORT)
def export_applications(request):
    queryset, _ = _filters(request, accessible_cases(request.user))
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="slqs_committee_applications.csv"'
    writer = csv.writer(response)
    writer.writerow(['Reference', 'Name', 'Email', 'Company', 'Job title', 'Region',
                     'Qualifications', 'Experience', 'KSA experience', 'Status',
                     'Priority', 'Assigned to', 'Submitted'])
    for case in queryset.order_by('pk').iterator():
        app = case.application
        writer.writerow([_safe_csv(v) for v in (
            app.short_reference, app.full_name, app.preferred_email, app.company_name,
            app.job_title, app.get_working_region_display(), app.qualifications_display,
            app.overall_post_qualification_experience, app.ksa_experience,
            app.get_status_display(), case.get_priority_display(),
            case.assigned_to.get_username() if case.assigned_to else '',
            app.created_at.isoformat(),
        )])
    return response


@never_cache
@committee_required()
def member_list(request):
    if not request.user.has_perm('membership.view_memberprofile'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied('Member directory permission required.')
    queryset = MemberProfile.objects.select_related('application')
    q = request.GET.get('q', '').strip()[:100]
    if q:
        queryset = queryset.filter(
            Q(membership_number__icontains=q) |
            Q(application__full_name__icontains=q) |
            Q(application__company_name__icontains=q) |
            Q(application__preferred_email__icontains=q)
        )
    state = request.GET.get('status', '')
    if state in MemberProfile.Status.values:
        queryset = queryset.filter(status=state)
    page = Paginator(queryset.order_by('-created_at'), 25).get_page(request.GET.get('page'))
    return render(request, 'membership_team/member_list.html', {
        'page': page, 'q': q, 'state': state, 'statuses': MemberProfile.Status.choices,
        'renewal_due_count': queryset.filter(
            renewal_due_on__lte=timezone.localdate() + timedelta(days=30),
            renewal_due_on__gte=timezone.localdate(),
        ).count(),
    })
