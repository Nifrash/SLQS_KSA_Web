"""Restricted attendee records and spreadsheet exports in /system-admin/."""
import csv

from django.contrib import admin, messages
from django.http import HttpResponse
from .models import EventRegistration


def excel_safe(value):
    """Prevent formulas from executing when CSV is opened in Excel."""
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ("full_name", "event", "email", "city", "status", "registered_at")
    list_filter = ("status", "event", "registered_at")
    search_fields = ("full_name", "email", "phone", "organisation", "city", "event__title")
    ordering = ("-registered_at",)
    list_select_related = ("event",)
    fields = (
        "event", "full_name", "email", "phone", "organisation", "job_title", "city",
        "status", "privacy_consent", "consent_at", "registered_at",
    )
    readonly_fields = fields
    actions = ("export_csv", "cancel_selected")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Export selected registrations to CSV")
    def export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="slqs_event_registrations.csv"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(["Event", "Name", "Email", "Phone", "Organisation", "Job title", "City", "Status", "Registered at"])
        for r in queryset.select_related("event").iterator():
            writer.writerow([excel_safe(v) for v in (
                r.event.title, r.full_name, r.email, r.phone, r.organisation,
                r.job_title, r.city, r.get_status_display(), r.registered_at.isoformat(),
            )])
        return response

    @admin.action(description="Cancel selected confirmed registrations (releases their places)")
    def cancel_selected(self, request, queryset):
        number = queryset.filter(status=EventRegistration.Status.CONFIRMED).update(
            status=EventRegistration.Status.CANCELLED,
        )
        self.message_user(request, f"Cancelled {number} registration(s).", messages.SUCCESS)
