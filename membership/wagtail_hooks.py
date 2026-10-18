"""Expose the secure System Admin review queue from the Wagtail main menu."""
from django.urls import reverse
from wagtail import hooks
from wagtail.admin.menu import MenuItem


class MembershipAdminMenuItem(MenuItem):
    def is_shown(self, request):
        user = request.user
        return user.is_authenticated and user.is_staff and (
            user.has_perm("membership.view_membershipapplication") or
            user.has_perm("membership.change_membershipapplication")
        )


@hooks.register("register_admin_menu_item")
def register_membership_admin_menu_item():
    return MembershipAdminMenuItem(
        "Membership Applications",
        reverse("admin:membership_membershipapplication_changelist"),
        icon_name="group", order=270,
    )


class MembersAdminMenuItem(MenuItem):
    def is_shown(self, request):
        user = request.user
        return user.is_authenticated and user.is_staff and (
            user.has_perm("membership.view_memberprofile") or
            user.has_perm("membership.change_memberprofile")
        )


@hooks.register("register_admin_menu_item")
def register_member_management_menu_item():
    return MembersAdminMenuItem(
        "SLQS Members",
        reverse("admin:membership_memberprofile_overview"),
        icon_name="group", order=275,
    )
