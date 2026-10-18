from django.contrib import admin
from .models import MemberAccountProfile


@admin.register(MemberAccountProfile)
class MemberAccountProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "full_name", "verified_at", "created_at")
    list_filter = ("verified_at",)
    search_fields = ("user__email", "full_name")
    readonly_fields = (
        "user", "full_name", "ksa_phone", "whatsapp_phone", "company_name",
        "job_title", "profile_photo", "verified_at", "otp_last_sent_at", "created_at", "updated_at",
    )
    exclude = ("otp_hash", "otp_expires_at", "otp_attempts", "otp_sent_in_window", "otp_window_started_at")

    def has_add_permission(self, request):
        return False
