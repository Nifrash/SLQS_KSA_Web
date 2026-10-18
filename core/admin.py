from django.contrib import admin
from .models import ContactInquiry


@admin.register(ContactInquiry)
class ContactInquiryAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'topic', 'status', 'created_at')
    list_filter = ('status', 'topic', 'created_at')
    search_fields = ('full_name', 'email', 'message')
    readonly_fields = ('full_name', 'email', 'topic', 'message', 'privacy_consent', 'created_at')
    fieldsets = (
        ('Visitor information', {'fields': ('full_name', 'email', 'topic', 'message', 'privacy_consent', 'created_at')}),
        ('Administration', {'fields': ('status', 'admin_notes')}),
    )
    list_per_page = 25
    def has_add_permission(self, request):
        return False
