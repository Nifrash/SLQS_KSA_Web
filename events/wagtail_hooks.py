"""Convenient, permission-aware link to attendee management from Wagtail."""
from django.urls import reverse
from wagtail import hooks
from wagtail.admin.menu import MenuItem


class EventRegistrationMenuItem(MenuItem):
    def is_shown(self, request):
        return request.user.is_staff and request.user.has_perm("events.view_eventregistration")


@hooks.register("register_admin_menu_item")
def event_registration_menu():
    return EventRegistrationMenuItem(
        "Event registrations",
        reverse("admin:events_eventregistration_changelist"),
        icon_name="group",
        order=510,
    )
