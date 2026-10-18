from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import CommitteeCase, CommitteeRecommendation
from .permissions import PERM_VIEW


class CommitteeLoginForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff or not user.has_perm(PERM_VIEW):
            raise forms.ValidationError('Please enter valid committee login credentials.', code='invalid_login')


class AssignCaseForm(forms.Form):
    assigned_to = forms.ModelChoiceField(label='Assign to', queryset=get_user_model().objects.none())
    priority = forms.ChoiceField(choices=CommitteeCase.Priority.choices)

    def __init__(self, *args, case=None, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()
        self.fields['assigned_to'].queryset = User.objects.filter(
            Q(is_superuser=True) | Q(groups__permissions__content_type__app_label='membership_team',
                                  groups__permissions__codename='view_committeecase') |
            Q(user_permissions__content_type__app_label='membership_team',
              user_permissions__codename='view_committeecase'),
            is_staff=True, is_active=True,
        ).distinct().order_by(User.USERNAME_FIELD)
        if case:
            self.initial.setdefault('assigned_to', case.assigned_to_id)
            self.initial.setdefault('priority', case.priority)


class RecommendationForm(forms.Form):
    outcome = forms.ChoiceField(choices=CommitteeRecommendation.Outcome.choices)
    note = forms.CharField(label='Private committee recommendation', max_length=3000,
                           widget=forms.Textarea(attrs={'rows': 4}))


class DecisionForm(forms.Form):
    decision = forms.ChoiceField(choices=(('approved', 'Approve membership'), ('rejected', 'Reject application')))
    note = forms.CharField(label='Decision reason / applicant message', max_length=3000,
                           widget=forms.Textarea(attrs={'rows': 4}),
                           help_text='Sent to the applicant. Do not include private committee notes.')


class MoreInfoForm(forms.Form):
    note = forms.CharField(label='Information required from applicant', max_length=3000,
                           widget=forms.Textarea(attrs={'rows': 4}),
                           help_text='Included in the applicant email along with their update link.')
