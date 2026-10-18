"""Permission-protected membership administration in /system-admin/."""
import csv

from django import forms
from django.contrib import admin, messages
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone

from .models import MembershipApplication, MembershipReviewLog, MembershipInformationRequest
from .notifications import status_email


class MembershipReviewForm(forms.ModelForm):
    decision_note = forms.CharField(
        label="Review message to applicant",
        max_length=3000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Required when rejecting or requesting additional information."}),
        help_text="This note is saved in the audit history and included in status emails.",
    )

    class Meta:
        model = MembershipApplication
        fields = ["status"]

    def clean(self):
        cleaned = super().clean()
        new_status = cleaned.get("status")
        note = (cleaned.get("decision_note") or "").strip()
        if new_status != self.instance.status and new_status in {
            MembershipApplication.Status.REJECTED,
            MembershipApplication.Status.MORE_INFO,
        } and not note:
            self.add_error("decision_note", "Please enter a message for the applicant.")
        return cleaned


class MembershipReviewLogInline(admin.TabularInline):
    model = MembershipReviewLog
    extra = 0
    can_delete = False
    fields = ("created_at", "from_status", "to_status", "note", "actor")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(MembershipApplication)
class MembershipApplicationAdmin(admin.ModelAdmin):
    form = MembershipReviewForm
    list_display = (
        "short_reference", "full_name", "preferred_email", "company_name",
        "job_title", "working_region", "status", "created_at",
    )
    list_filter = ("status", "working_region", "whatsapp_group_member", "created_at")
    search_fields = ("full_name", "preferred_email", "company_name", "reference", "job_title")
    ordering = ("-created_at",)
    list_per_page = 35
    list_select_related = ("reviewed_by",)
    inlines = [MembershipReviewLogInline]
    actions = ["export_selected_csv"]
    readonly_fields = (
        "reference", "full_name", "date_of_birth", "preferred_email",
        "ksa_phone", "whatsapp_phone", "whatsapp_group_member", "company_name",
        "job_title", "highest_educational_qualification", "qualifications_display",
        "overall_post_qualification_experience", "ksa_experience", "working_region",
        "suggestions", "privacy_consent_at", "reviewed_by", "reviewed_at",
        "created_at", "updated_at", "approved_member_link",
    )
    fieldsets = (
        ("Application", {"fields": (
            "reference", "full_name", "date_of_birth", "preferred_email",
            "ksa_phone", "whatsapp_phone", "whatsapp_group_member",
            "company_name", "job_title", "highest_educational_qualification",
            "qualifications_display", "overall_post_qualification_experience",
            "ksa_experience", "working_region", "suggestions",
        )}),
        ("Membership review", {"fields": ("status", "decision_note", "reviewed_by", "reviewed_at", "approved_member_link")}),
        ("Submission and privacy", {"fields": ("privacy_consent_at", "created_at", "updated_at")}),
    )

    def has_add_permission(self, request):
        return False  # public applications must arrive through validated forms

    def has_delete_permission(self, request, obj=None):
        return False  # preserve audit history; retention/deletion procedure later

    @admin.display(description="Active professional qualifications")
    def qualifications_display(self, obj):
        return obj.qualifications_display

    @admin.display(description="Approved member record")
    def approved_member_link(self, obj):
        if not obj.pk:
            return "Not yet submitted"
        member = MemberProfile.objects.filter(application=obj).first()
        if member:
            url = reverse("admin:membership_memberprofile_change", args=[member.pk])
            return format_html('<a href="{}">{}</a>', url, member.membership_number)
        return "Awaiting approval / provisioning"

    def save_model(self, request, obj, form, change):
        if not change:
            return super().save_model(request, obj, form, change)
        # Django admin wraps the change form POST in an atomic transaction.
        previous = MembershipApplication.objects.select_for_update().get(pk=obj.pk)
        old_status = previous.status
        note = form.cleaned_data.get("decision_note", "").strip()
        changed = old_status != obj.status
        if changed:
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)
        if changed and obj.status == MembershipApplication.Status.MORE_INFO:
            MembershipInformationRequest.objects.create(
                application=obj, requested_by=request.user, message=note,
            )
        if changed or note:
            MembershipReviewLog.objects.create(
                application=obj,
                from_status=old_status,
                to_status=obj.status,
                note=note,
                actor=request.user,
            )
            if changed:
                transaction.on_commit(lambda pk=obj.pk, msg=note: _notify_by_pk(pk, msg))

    @admin.action(description="Export selected membership applications to CSV")
    def export_selected_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="slqs_membership_applications.csv"'
        writer = csv.writer(response)
        writer.writerow([
            "Reference", "Full Name", "DOB", "Preferred Email", "KSA Phone", "WhatsApp Phone",
            "Already in WhatsApp Group", "Company", "Job Title", "Highest Education",
            "Active Qualifications", "Overall Post-Qualification Years", "KSA Years",
            "KSA Region", "Suggestions", "Status", "Submitted At",
        ])
        for obj in queryset.iterator():
            writer.writerow([safe_csv(value) for value in (
                obj.short_reference, obj.full_name, obj.date_of_birth,
                obj.preferred_email, obj.ksa_phone, obj.whatsapp_phone,
                obj.get_whatsapp_group_member_display(), obj.company_name,
                obj.job_title, obj.highest_educational_qualification,
                obj.qualifications_display, obj.overall_post_qualification_experience,
                obj.ksa_experience, obj.get_working_region_display(),
                obj.suggestions, obj.get_status_display(), obj.created_at,
            )])
        return response


def safe_csv(value):
    """Avoid spreadsheet formula injection when exporting applicant-entered text."""
    text = str(value) if value is not None else ""
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + text
    return text


def _notify_by_pk(pk, note):
    try:
        application = MembershipApplication.objects.get(pk=pk)
    except MembershipApplication.DoesNotExist:
        return
    status_email(application, note)


# -----------------------------------------------------------------------------
# Phase 6 — private, permission-controlled member management
# -----------------------------------------------------------------------------
from datetime import timedelta

from django.contrib.admin.utils import quote, unquote
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from .models import MemberActivity, MemberProfile, MemberRenewal
from .services import renew_membership


class MemberEditForm(forms.ModelForm):
    class Meta:
        model = MemberProfile
        fields = ("status", "joined_on", "renewal_due_on", "internal_notes")
        widgets = {
            "joined_on": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "renewal_due_on": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "internal_notes": forms.Textarea(attrs={"rows": 4}),
        }

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk and self.instance.application.status != MembershipApplication.Status.APPROVED:
            self.add_error("status", "This member's application is no longer approved.")
        return cleaned


class MemberRenewalForm(forms.Form):
    new_due_on = forms.DateField(
        label="New renewal due date",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d"],
    )
    note = forms.CharField(
        max_length=500, required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Internal renewal note (optional)",
    )

    def __init__(self, *args, member=None, **kwargs):
        self.member = member
        super().__init__(*args, **kwargs)

    def clean_new_due_on(self):
        value = self.cleaned_data["new_due_on"]
        if value <= timezone.localdate():
            raise forms.ValidationError("Please select a future renewal date.")
        if self.member and self.member.renewal_due_on and value <= self.member.renewal_due_on:
            raise forms.ValidationError("New renewal date must extend the existing date.")
        return value


class MemberActivityInline(admin.TabularInline):
    model = MemberActivity
    extra = 0
    can_delete = False
    fields = ("created_at", "action", "old_status", "new_status", "old_due_on", "new_due_on", "note", "actor")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class MemberRenewalInline(admin.TabularInline):
    model = MemberRenewal
    extra = 0
    can_delete = False
    fields = ("processed_at", "old_due_on", "new_due_on", "note", "processed_by")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    form = MemberEditForm
    list_display = (
        "membership_number", "member_name", "preferred_email", "company_name",
        "working_region", "status", "joined_on", "renewal_due_on",
    )
    list_filter = ("status", "application__working_region", "joined_on", "renewal_due_on")
    search_fields = (
        "membership_number", "application__full_name", "application__preferred_email",
        "application__ksa_phone", "application__company_name", "application__job_title",
    )
    ordering = ("-created_at", "-pk")
    list_per_page = 35
    actions = ["export_member_csv"]
    list_select_related = ("application",)
    readonly_fields = (
        "membership_number", "application", "member_name", "preferred_email",
        "company_name", "job_title", "working_region", "created_at", "updated_at",
        "renew_action_link",
    )
    fieldsets = (
        ("Member identity", {"fields": (
            "membership_number", "application", "member_name", "preferred_email",
            "company_name", "job_title", "working_region",
        )}),
        ("Membership administration", {"fields": (
            "status", "joined_on", "renewal_due_on", "renew_action_link", "internal_notes",
        )}),
        ("System dates", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
    inlines = (MemberRenewalInline, MemberActivityInline)

    class Media:
        css = {"all": ("css/member_admin.css",)}

    def has_add_permission(self, request):
        return False  # members are generated only from approved applications

    def has_delete_permission(self, request, obj=None):
        return False  # retain renewal and activity audit history

    @admin.display(description="Full name", ordering="application__full_name")
    def member_name(self, obj):
        return obj.application.full_name

    @admin.display(description="Email", ordering="application__preferred_email")
    def preferred_email(self, obj):
        return obj.application.preferred_email

    @admin.display(description="Company", ordering="application__company_name")
    def company_name(self, obj):
        return obj.application.company_name

    @admin.display(description="KSA region", ordering="application__working_region")
    def working_region(self, obj):
        return obj.application.get_working_region_display()

    @admin.display(description="Job title", ordering="application__job_title")
    def job_title(self, obj):
        return obj.application.job_title

    @admin.display(description="Renew membership")
    def renew_action_link(self, obj):
        if not obj.pk:
            return "Save the member first."
        url = reverse("admin:membership_memberprofile_renew", args=[quote(obj.pk)])
        return format_html('<a class="button" href="{}">Record a membership renewal</a>', url)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("application")

    def get_urls(self):
        custom = [
            path("overview/", self.admin_site.admin_view(self.overview), name="membership_memberprofile_overview"),
            path("<path:object_id>/renew/", self.admin_site.admin_view(self.renew_view), name="membership_memberprofile_renew"),
        ]
        return custom + super().get_urls()

    def overview(self, request):
        if not self.has_view_permission(request):
            return HttpResponseForbidden("Member management permission required.")
        today = timezone.localdate()
        soon = today + timedelta(days=30)
        base = MemberProfile.objects.select_related("application")
        context = {
            **self.admin_site.each_context(request),
            "title": "SLQS member management overview",
            "opts": self.model._meta,
            "total": base.count(),
            "active": base.filter(status=MemberProfile.Status.ACTIVE).count(),
            "suspended": base.filter(status=MemberProfile.Status.SUSPENDED).count(),
            "expired": base.filter(status=MemberProfile.Status.EXPIRED).count(),
            "inactive": base.filter(status=MemberProfile.Status.INACTIVE).count(),
            "due_soon": base.filter(status=MemberProfile.Status.ACTIVE, renewal_due_on__range=(today, soon)).count(),
            "without_due": base.filter(renewal_due_on__isnull=True).count(),
            "pending_applications": MembershipApplication.objects.exclude(
                status__in=[MembershipApplication.Status.APPROVED, MembershipApplication.Status.REJECTED]
            ).count(),
            "recent_members": base.order_by("-created_at")[:8],
        }
        return render(request, "admin/membership/memberprofile/overview.html", context)

    def renew_view(self, request, object_id):
        member = get_object_or_404(self.get_queryset(request), pk=unquote(object_id))
        if not self.has_change_permission(request, member):
            return HttpResponseForbidden("Change permission required to renew a membership.")
        if request.method == "POST":
            form = MemberRenewalForm(request.POST, member=member)
            if form.is_valid():
                try:
                    renew_membership(
                        member.pk, form.cleaned_data["new_due_on"],
                        actor=request.user, note=form.cleaned_data["note"],
                    )
                except ValidationError as exc:
                    form.add_error("new_due_on", exc)
                else:
                    self.message_user(request, f"Renewal recorded for {member.membership_number}.", messages.SUCCESS)
                    return redirect("admin:membership_memberprofile_change", quote(member.pk))
        else:
            form = MemberRenewalForm(member=member)
        context = {
            **self.admin_site.each_context(request),
            "title": f"Renew {member.membership_number}", "opts": self.model._meta,
            "member": member, "form": form,
        }
        return render(request, "admin/membership/memberprofile/renew.html", context)

    def save_model(self, request, obj, form, change):
        if not change:
            return super().save_model(request, obj, form, change)
        previous = MemberProfile.objects.select_for_update().get(pk=obj.pk)
        status_changed = previous.status != obj.status
        due_changed = previous.renewal_due_on != obj.renewal_due_on
        note_changed = previous.internal_notes != obj.internal_notes
        joined_changed = previous.joined_on != obj.joined_on
        super().save_model(request, obj, form, change)
        if status_changed or due_changed:
            MemberActivity.objects.create(
                member=obj, action=(MemberActivity.Action.STATUS if status_changed else MemberActivity.Action.DUE_DATE),
                old_status=previous.status, new_status=obj.status,
                old_due_on=previous.renewal_due_on, new_due_on=obj.renewal_due_on,
                actor=request.user, note="Updated in SLQS member administration.",
            )
        if joined_changed:
            MemberActivity.objects.create(
                member=obj, action=MemberActivity.Action.JOINED_DATE,
                actor=request.user,
                note=f"Joining date corrected from {previous.joined_on} to {obj.joined_on}.",
            )
        if note_changed:
            MemberActivity.objects.create(
                member=obj, action=MemberActivity.Action.NOTES,
                actor=request.user, note="Administrative notes edited (contents omitted from audit).",
            )

    @admin.action(description="Export selected SLQS members to CSV", permissions=["view"])
    def export_member_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="slqs_members.csv"'
        writer = csv.writer(response)
        writer.writerow([
            "Membership number", "Name", "Preferred email", "KSA phone", "WhatsApp number",
            "Company", "Job title", "Region", "Qualifications", "Status", "Joined",
            "Renewal due", "Application reference",
        ])
        for member in queryset.select_related("application").iterator():
            app = member.application
            writer.writerow([safe_csv(value) for value in (
                member.membership_number, app.full_name, app.preferred_email, app.ksa_phone,
                app.whatsapp_phone, app.company_name, app.job_title,
                app.get_working_region_display(), app.qualifications_display,
                member.get_status_display(), member.joined_on, member.renewal_due_on,
                app.short_reference,
            )])
        return response


@admin.register(MemberRenewal)
class MemberRenewalAdmin(admin.ModelAdmin):
    list_display = ("member", "old_due_on", "new_due_on", "processed_by", "processed_at")
    search_fields = ("member__membership_number", "member__application__full_name")
    readonly_fields = ("member", "old_due_on", "new_due_on", "note", "processed_by", "processed_at")
    list_select_related = ("member", "processed_by")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MemberActivity)
class MemberActivityAdmin(admin.ModelAdmin):
    list_display = ("member", "action", "old_status", "new_status", "actor", "created_at")
    search_fields = ("member__membership_number", "member__application__full_name")
    list_filter = ("action", "created_at")
    readonly_fields = ("member", "action", "old_status", "new_status", "old_due_on", "new_due_on", "note", "actor", "created_at")
    list_select_related = ("member", "actor")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
