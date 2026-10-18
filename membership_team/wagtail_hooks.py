from django.urls import reverse
from wagtail import hooks
from wagtail.admin.menu import MenuItem

from .permissions import PERM_VIEW


class CommitteePortalMenuItem(MenuItem):
    def is_shown(self, request):
        return request.user.is_authenticated and request.user.is_staff and request.user.has_perm(PERM_VIEW)


@hooks.register('register_admin_menu_item')
def register_committee_portal_menu():
    return CommitteePortalMenuItem(
        'Membership Committee Portal', reverse('membership_team:dashboard'),
        icon_name='group', order=265,
    )
