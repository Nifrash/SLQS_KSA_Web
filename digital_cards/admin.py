"""System Admin provides read-only card audit oversight; changes use committee UI."""
from django.contrib import admin
from .models import DigitalMembershipCard, CardAuditEvent


@admin.register(DigitalMembershipCard)
class DigitalMembershipCardAdmin(admin.ModelAdmin):
    list_display = ("member", "issued_at", "revoked_at", "reissue_count")
    search_fields = ("member__membership_number", "member__application__full_name")
    list_filter = ("revoked_at",)
    readonly_fields = ("member", "issued_at", "updated_at", "revoked_at", "revoked_by", "reissue_count")
    exclude = ("token",)  # Treat public QR tokens as bearer credentials.

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CardAuditEvent)
class CardAuditEventAdmin(admin.ModelAdmin):
    list_display = ("card", "action", "actor", "created_at")
    list_filter = ("action",)
    search_fields = ("card__member__membership_number", "card__member__application__full_name")
    readonly_fields = ("card", "action", "actor", "note", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
