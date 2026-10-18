"""Private membership applications and immutable-ish review history.

Public URLs never expose an applicant's profile. Member accounts and payments
are intentionally outside Phase 5.
"""
import uuid
from pathlib import Path

from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible
from datetime import date
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


PROFESSIONAL_QUALIFICATIONS = (
    ("FRICS", "FRICS"),
    ("FAIQS", "FAIQS"),
    ("FCIArb", "FCIArb"),
    ("FCIOB", "FCIOB"),
    ("MRICS", "MRICS"),
    ("AIQSSL", "AIQSSL"),
    ("CQS", "CQS"),
    ("MAIQS", "MAIQS"),
    ("MCIArb", "MCIArb"),
    ("MCIOB", "MCIOB"),
    ("AssoRICS", "AssoRICS"),
    ("None", "None"),
    ("Other", "Other"),
)

REGIONS = (
    ("riyadh", "Riyadh Region"),
    ("makkah", "Makkah Region"),
    ("madinah", "Madinah Region"),
    ("eastern", "Eastern Province"),
    ("qassim", "Al Qassim Region"),
    ("asir", "Asir Region"),
    ("tabuk", "Tabuk Region"),
    ("hail", "Hail Region"),
    ("northern_borders", "Northern Borders Region"),
    ("jazan", "Jazan Region"),
    ("najran", "Najran Region"),
    ("al_baha", "Al Baha Region"),
    ("al_jawf", "Al Jawf Region"),
    ("other", "Other / Not listed"),
)


class MembershipApplication(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        IN_REVIEW = "in_review", "Under review"
        MORE_INFO = "more_info", "Additional information requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class YesNo(models.TextChoices):
        YES = "yes", "Yes"
        NO = "no", "No"

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL,
        related_name="slqs_membership_application",
        help_text="Verified applicant website account. Pre-Phase 7 applications can remain unlinked.",
    )
    full_name = models.CharField(max_length=180)
    date_of_birth = models.DateField()
    preferred_email = models.EmailField(max_length=254)
    ksa_phone = models.CharField(max_length=20)
    whatsapp_phone = models.CharField(max_length=20)
    whatsapp_group_member = models.CharField(max_length=3, choices=YesNo.choices)
    company_name = models.CharField(max_length=180)
    job_title = models.CharField(max_length=150)
    highest_educational_qualification = models.CharField(max_length=250)
    professional_qualifications = models.JSONField(default=list)
    professional_qualifications_other = models.CharField(max_length=250, blank=True)
    overall_post_qualification_experience = models.DecimalField(max_digits=5, decimal_places=2)
    ksa_experience = models.DecimalField(max_digits=5, decimal_places=2)
    working_region = models.CharField(max_length=30, choices=REGIONS)
    suggestions = models.TextField(blank=True, max_length=3000)
    privacy_consent_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SUBMITTED, db_index=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="slqs_membership_reviews",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Membership application"
        verbose_name_plural = "Membership applications"
        constraints = [
            models.UniqueConstraint(Lower("preferred_email"), name="membership_unique_email_ci"),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.short_reference})"

    @property
    def short_reference(self):
        return str(self.reference).split("-")[0].upper()

    @property
    def qualifications_display(self):
        selected = self.professional_qualifications or []
        if "Other" in selected and self.professional_qualifications_other:
            return ", ".join(self.professional_qualifications_other if x == "Other" else x for x in selected)
        return ", ".join(selected) or "—"

    def clean(self):
        super().clean()
        errors = {}
        selected = self.professional_qualifications or []
        valid_codes = {code for code, _ in PROFESSIONAL_QUALIFICATIONS}
        if not isinstance(selected, list) or not selected or any(x not in valid_codes for x in selected):
            errors["professional_qualifications"] = "Select at least one valid qualification."
        elif len(selected) != len(set(selected)):
            errors["professional_qualifications"] = "Please do not repeat a qualification."
        elif "None" in selected and len(selected) > 1:
            errors["professional_qualifications"] = "'None' cannot be selected with other qualifications."
        if "Other" in selected and not self.professional_qualifications_other.strip():
            errors["professional_qualifications_other"] = "Please specify the other qualification."
        if "Other" not in selected and self.professional_qualifications_other:
            errors["professional_qualifications_other"] = "Select 'Other' to provide an additional qualification."
        if self.date_of_birth:
            today = timezone.localdate()
            if self.date_of_birth > today or self.date_of_birth.year < today.year - 110:
                errors["date_of_birth"] = "Enter a valid date of birth."
        for field in ("overall_post_qualification_experience", "ksa_experience"):
            value = getattr(self, field, None)
            if value is None:
                continue
            try:
                years = Decimal(str(value))
            except (InvalidOperation, TypeError, ValueError):
                errors[field] = "Enter a valid number of years."
                continue
            if not years.is_finite() or not (Decimal("0") <= years <= Decimal("80")):
                errors[field] = "Enter a number of years between 0 and 80."
        if errors:
            raise ValidationError(errors)


class MembershipReviewLog(models.Model):
    application = models.ForeignKey(
        MembershipApplication, on_delete=models.PROTECT, related_name="review_history",
    )
    from_status = models.CharField(max_length=12, blank=True)
    to_status = models.CharField(max_length=12, choices=MembershipApplication.Status.choices)
    note = models.TextField(blank=True, max_length=3000)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="slqs_membership_review_actions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        verbose_name = "Membership review history"
        verbose_name_plural = "Membership review history"

    def __str__(self):
        return f"{self.application.short_reference}: {self.from_status or 'new'} → {self.to_status}"


class MemberProfile(models.Model):
    """Private member record created only from an approved Phase 5 application.

    Member identifiers are allocated once using the database primary key; they
    are not editable or reused. A missing renewal date means not yet set by SLQS.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        INACTIVE = "inactive", "Inactive"
        EXPIRED = "expired", "Expired"

    application = models.OneToOneField(
        MembershipApplication,
        on_delete=models.PROTECT,
        related_name="member_profile",
    )
    membership_number = models.CharField(
        max_length=32, unique=True, null=True, blank=True, editable=False,
        help_text="System-issued, permanent SLQS membership identifier.",
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.ACTIVE, db_index=True,
    )
    joined_on = models.DateField(default=timezone.localdate)
    renewal_due_on = models.DateField(null=True, blank=True, db_index=True)
    internal_notes = models.TextField(blank=True, max_length=3000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        verbose_name = "SLQS member"
        verbose_name_plural = "SLQS members"

    def __str__(self):
        return f"{self.membership_number or 'Pending ID'} — {self.application.full_name}"

    @property
    def is_past_due(self):
        return bool(self.renewal_due_on and self.renewal_due_on < timezone.localdate())

    def clean(self):
        super().clean()
        if self.renewal_due_on and self.joined_on and self.renewal_due_on < self.joined_on:
            raise ValidationError({"renewal_due_on": "Renewal due date cannot precede the joining date."})
        if self.status == self.Status.ACTIVE and self.is_past_due:
            raise ValidationError({"status": "An overdue member must be renewed before being marked active."})


class MemberActivity(models.Model):
    """Read-only audit trail for member lifecycle changes."""

    class Action(models.TextChoices):
        CREATED = "created", "Member created"
        STATUS = "status", "Status changed"
        DUE_DATE = "due_date", "Due date changed"
        RENEWED = "renewed", "Membership renewed"
        NOTES = "notes", "Administrative notes updated"
        JOINED_DATE = "joined_on", "Joining date corrected"

    member = models.ForeignKey(MemberProfile, on_delete=models.PROTECT, related_name="activity_history")
    action = models.CharField(max_length=16, choices=Action.choices)
    old_status = models.CharField(max_length=12, blank=True)
    new_status = models.CharField(max_length=12, blank=True)
    old_due_on = models.DateField(null=True, blank=True)
    new_due_on = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True, max_length=1500)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="slqs_member_activity",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        verbose_name = "Member activity"
        verbose_name_plural = "Member activity history"

    def __str__(self):
        return f"{self.member.membership_number}: {self.get_action_display()}"


class MemberRenewal(models.Model):
    """A recorded administrative renewal. Phase 6 does not process payments."""

    member = models.ForeignKey(MemberProfile, on_delete=models.PROTECT, related_name="renewals")
    old_due_on = models.DateField(null=True, blank=True)
    new_due_on = models.DateField()
    note = models.CharField(max_length=500, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="slqs_member_renewals",
    )
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-processed_at", "-pk")
        verbose_name = "Member renewal"
        verbose_name_plural = "Member renewals"

    def __str__(self):
        return f"{self.member.membership_number} renewed to {self.new_due_on}"


# Evidence is stored outside MEDIA_ROOT and STATIC_ROOT; it is never published
# through Django's development-media URL or the site's web server.
@deconstructible
class PrivateMembershipDocumentStorage(FileSystemStorage):
    """Storage deconstructs portably in migrations, resolving root at runtime."""
    def __init__(self):
        root = getattr(settings, "SLQS_PRIVATE_DOCUMENTS_ROOT", settings.BASE_DIR / "private_membership_docs")
        super().__init__(location=Path(root))


private_documents_storage = PrivateMembershipDocumentStorage()


def evidence_filename(instance, filename):
    # Never use a user-provided path or name in private storage.
    extension = Path(filename).suffix.lower()
    return f"supporting/{instance.request.application_id}/{uuid.uuid4().hex}{extension}"


class MembershipInformationRequest(models.Model):
    """An actionable committee request, retained for subsequent audit."""
    application = models.ForeignKey(
        MembershipApplication, on_delete=models.PROTECT, related_name="information_requests",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="slqs_information_requests_sent",
    )
    message = models.TextField(max_length=3000)
    requested_at = models.DateTimeField(default=timezone.now)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-requested_at", "-pk")

    @property
    def is_open(self):
        return self.responded_at is None and self.application.status == MembershipApplication.Status.MORE_INFO


class MembershipInformationResponse(models.Model):
    """Exactly one submitted response and document per committee request."""
    request = models.OneToOneField(
        MembershipInformationRequest, on_delete=models.PROTECT, related_name="response",
    )
    # Keep the response and its evidence when an account is deleted.
    # The linked application remains the source of historical submission details.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    message = models.TextField(max_length=3000)
    document = models.FileField(upload_to=evidence_filename, storage=private_documents_storage, max_length=255)
    submitted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-submitted_at", "-pk")


class MemberPortalNotification(models.Model):
    class Kind(models.TextChoices):
        INFO_REQUEST = "info_request", "Information required"
        SUBMITTED = "submitted", "Application received"
        APPROVED = "approved", "Membership approved"
        REJECTED = "rejected", "Application rejected"
        UPDATE = "update", "Application updated"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="slqs_portal_notifications",
    )
    application = models.ForeignKey(
        MembershipApplication, on_delete=models.PROTECT, related_name="portal_notifications",
    )
    information_request = models.ForeignKey(
        MembershipInformationRequest, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="portal_notifications",
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    title = models.CharField(max_length=140)
    message = models.TextField(max_length=3000)
    created_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        indexes = [models.Index(fields=["user", "read_at", "created_at"], name="slqs_notif_inbox_idx")]
