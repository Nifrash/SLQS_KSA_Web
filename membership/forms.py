"""Applicant input validation. No privileged fields are accepted from the public form."""
import re
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import MembershipApplication, PROFESSIONAL_QUALIFICATIONS


def normalize_ksa_phone(value):
    """Accept local 0XXXXXXXXX / international +966XXXXXXXXX formats."""
    value = value.strip()
    if not re.fullmatch(r"[+0-9\s().-]+", value):
        raise ValidationError("Enter a valid Saudi phone number.")
    digits = re.sub(r"\D", "", value)
    if digits.startswith("00966"):
        digits = digits[2:]
    if digits.startswith("966") and len(digits) == 12:
        return "+" + digits
    if digits.startswith("0") and len(digits) == 10:
        return "+966" + digits[1:]
    if len(digits) == 9 and not value.startswith("+"):
        return "+966" + digits
    raise ValidationError("Use a KSA phone number such as 05XXXXXXXX or +9665XXXXXXXX.")


def normalize_whatsapp_phone(value):
    value = value.strip()
    if not re.fullmatch(r"[+0-9\s().-]+", value):
        raise ValidationError("Enter a valid WhatsApp phone number with country code.")
    # Saudi local-format numbers are accepted here too.
    digits = re.sub(r"\D", "", value)
    if digits.startswith("00966"):
        digits = digits[2:]
    if digits.startswith("0") and len(digits) == 10:
        digits = "966" + digits[1:]
    if not 8 <= len(digits) <= 15 or digits.startswith("0"):
        raise ValidationError("Include a valid country code, e.g. +9665XXXXXXXX.")
    if not (value.startswith("+") or value.startswith("00") or (digits.startswith("966") and len(digits) == 12)):
        raise ValidationError("Include the international country code, e.g. +9665XXXXXXXX.")
    return "+" + digits


class MembershipApplicationForm(forms.ModelForm):
    professional_qualifications = forms.MultipleChoiceField(
        choices=PROFESSIONAL_QUALIFICATIONS,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "qualification-checkbox"}),
        label="Professional Qualifications (Active as of date)",
        help_text="Select every qualification you currently hold. Choose 'None' alone if none applies.",
    )
    privacy_consent = forms.BooleanField(
        label="I agree that SLQS KSA may collect and use my information to process this membership application and contact me about it.",
        required=True,
    )
    website = forms.CharField(required=False, widget=forms.HiddenInput, label="Leave this field blank")

    class Meta:
        model = MembershipApplication
        fields = [
            "full_name", "date_of_birth", "preferred_email", "ksa_phone",
            "whatsapp_phone", "whatsapp_group_member", "company_name", "job_title",
            "highest_educational_qualification", "professional_qualifications",
            "professional_qualifications_other", "overall_post_qualification_experience",
            "ksa_experience", "working_region", "suggestions",
        ]
        labels = {
            "full_name": "Full Name",
            "date_of_birth": "Date of Birth",
            "preferred_email": "Preferred Email",
            "ksa_phone": "KSA Phone Number",
            "whatsapp_phone": "WhatsApp Phone Number",
            "whatsapp_group_member": "Are you already a member of our WhatsApp group with this WhatsApp number?",
            "company_name": "Company Name",
            "job_title": "Job Title",
            "highest_educational_qualification": "Highest Educational Qualification (QS / Engineering Related)",
            "professional_qualifications_other": "Other Professional Qualification (if selected)",
            "overall_post_qualification_experience": "Overall Years of Post-Qualification Experience",
            "ksa_experience": "Years of KSA Experience",
            "working_region": "Working Region in KSA",
            "suggestions": "Your Suggestions to Improve SLQS KSA Services",
        }
        widgets = {
            "full_name": forms.TextInput(attrs={"autocomplete": "name", "placeholder": "As shown on your professional records"}),
            "date_of_birth": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "preferred_email": forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "you@example.com"}),
            "ksa_phone": forms.TextInput(attrs={"autocomplete": "tel", "placeholder": "+9665XXXXXXXX"}),
            "whatsapp_phone": forms.TextInput(attrs={"autocomplete": "tel", "placeholder": "+9665XXXXXXXX"}),
            "whatsapp_group_member": forms.RadioSelect,
            "company_name": forms.TextInput(attrs={"autocomplete": "organization", "placeholder": "Current employer"}),
            "job_title": forms.TextInput(attrs={"autocomplete": "organization-title", "placeholder": "e.g. Senior Quantity Surveyor"}),
            "highest_educational_qualification": forms.TextInput(attrs={"placeholder": "e.g. BSc (Hons) Quantity Surveying"}),
            "professional_qualifications_other": forms.TextInput(attrs={"placeholder": "Specify the active qualification"}),
            "overall_post_qualification_experience": forms.NumberInput(attrs={"min": 0, "max": 80, "step": "0.25", "placeholder": "e.g. 12.5"}),
            "ksa_experience": forms.NumberInput(attrs={"min": 0, "max": 80, "step": "0.25", "placeholder": "e.g. 6"}),
            "suggestions": forms.Textarea(attrs={"rows": 4, "placeholder": "How can we improve SLQS KSA services or activities?"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date_of_birth"].input_formats = ["%Y-%m-%d"]
        self.fields["date_of_birth"].widget.attrs["max"] = timezone.localdate().isoformat()
        for name, field in self.fields.items():
            if name not in {"professional_qualifications", "privacy_consent", "whatsapp_group_member", "website"}:
                field.widget.attrs["class"] = "slqs-input"
        self.fields["professional_qualifications_other"].required = False
        self.fields["suggestions"].required = False

    def clean_preferred_email(self):
        return self.cleaned_data["preferred_email"].strip().lower()

    def clean_ksa_phone(self):
        return normalize_ksa_phone(self.cleaned_data["ksa_phone"])

    def clean_whatsapp_phone(self):
        return normalize_whatsapp_phone(self.cleaned_data["whatsapp_phone"])

    def clean(self):
        cleaned = super().clean()
        selected = cleaned.get("professional_qualifications") or []
        if "None" in selected and len(selected) > 1:
            self.add_error("professional_qualifications", "'None' cannot be combined with other qualifications.")
        if "Other" in selected and not (cleaned.get("professional_qualifications_other") or "").strip():
            self.add_error("professional_qualifications_other", "Please specify the other qualification.")
        if "Other" not in selected:
            cleaned["professional_qualifications_other"] = ""
        return cleaned


class MembershipInformationResponseForm(forms.Form):
    """Supporting evidence from the verified applicant, never a public upload."""
    message = forms.CharField(
        label="Your response to the membership team", max_length=3000,
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "Explain the document and respond to the committee's request."}),
    )
    document = forms.FileField(
        label="Supporting document (PDF, JPEG or PNG)",
        help_text="Required. Maximum file size 10 MB. Only PDF, JPG and PNG files are accepted.",
    )

    def clean_document(self):
        upload = self.cleaned_data["document"]
        if upload.size == 0 or upload.size > 10 * 1024 * 1024:
            raise forms.ValidationError("Upload a non-empty file no larger than 10 MB.")
        name = upload.name.lower()
        upload.seek(0)
        head = upload.read(16)
        upload.seek(0)
        if name.endswith('.pdf') and head.startswith(b'%PDF-'):
            return upload
        if name.endswith(('.jpg', '.jpeg')) and head.startswith(b'\xff\xd8\xff'):
            return upload
        if name.endswith('.png') and head.startswith(b'\x89PNG\r\n\x1a\n'):
            return upload
        raise forms.ValidationError("Choose a genuine PDF, JPG or PNG document.")
