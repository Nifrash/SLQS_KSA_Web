from functools import wraps
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.urls import reverse

PERM_VIEW = 'membership_team.view_committeecase'
PERM_ASSIGN = 'membership_team.assign_committeecase'
PERM_RECOMMEND = 'membership_team.recommend_committeecase'
PERM_DECIDE = 'membership_team.decide_committeecase'
PERM_INFO = 'membership_team.request_info_committeecase'
PERM_EXPORT = 'membership_team.export_committeecase'


def committee_required(permission=PERM_VIEW):
    def decorate(view):
        @wraps(view)
        def checked(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path(), reverse('membership_team:login'))
            if not request.user.is_active or not request.user.is_staff or not request.user.has_perm(permission):
                raise PermissionDenied('SLQS committee access required.')
            return view(request, *args, **kwargs)
        return checked
    return decorate


def can_view_all(user):
    return user.has_perm(PERM_ASSIGN) or user.has_perm(PERM_DECIDE)


def accessible_cases(user):
    from .models import CommitteeCase
    queryset = CommitteeCase.objects.select_related('application', 'assigned_to', 'assigned_by')
    if can_view_all(user):
        return queryset
    return queryset.filter(assigned_to=user)
