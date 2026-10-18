from django import forms
from io import BytesIO
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError
from django.core.files.uploadedfile import SimpleUploadedFile, UploadedFile
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from membership.forms import normalize_ksa_phone, normalize_whatsapp_phone
from .models import MemberAccountProfile


def canonical_email(email):
    return (email or "").strip().lower()


class RegisterForm(forms.Form):
    full_name = forms.CharField(max_length=180, label="Full name")
    email = forms.EmailField(label="Email address", max_length=150)
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}), label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}), label="Confirm password")
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_email(self):
        email = canonical_email(self.cleaned_data["email"])
        user_model = get_user_model()
        if user_model.objects.filter(email__iexact=email).exists() or user_model.objects.filter(username__iexact=email).exists():
            raise ValidationError("An account already exists for this email. Please log in or contact SLQS.")
        return email

    def clean(self):
        data = super().clean()
        if data.get("password1") and data.get("password1") != data.get("password2"):
            self.add_error("password2", "Passwords must match.")
        elif data.get("password1"):
            validate_password(data["password1"])
        return data


class EmailLoginForm(AuthenticationForm):
    username = forms.CharField(label="Email address", widget=forms.TextInput(attrs={"autocomplete": "username"}))

    def clean(self):
        if "username" in self.cleaned_data and "@" in self.cleaned_data["username"]:
            self.cleaned_data["username"] = canonical_email(self.cleaned_data["username"])
        return super().clean()


class OTPForm(forms.Form):
    code = forms.RegexField(r"^[0-9]{6}$", max_length=6, min_length=6, label="6-digit verification code")


class RecoverVerificationForm(forms.Form):
    email = forms.EmailField(label="Email address")
    password = forms.CharField(label="Password", widget=forms.PasswordInput)


class AccountProfileForm(forms.ModelForm):
    class Meta:
        model = MemberAccountProfile
        fields = ("full_name", "ksa_phone", "whatsapp_phone", "company_name", "job_title", "profile_photo")
        labels = {
            "full_name": "Full name", "ksa_phone": "KSA phone number",
            "whatsapp_phone": "WhatsApp phone", "company_name": "Company name",
            "job_title": "Job title", "profile_photo": "Profile picture",
        }
        widgets = {"profile_photo": forms.ClearableFileInput(attrs={
            "accept": "image/jpeg,image/png,image/webp", "class": "slqs-member-photo-input",
        })}

    def clean_ksa_phone(self):
        value = self.cleaned_data["ksa_phone"]
        return normalize_ksa_phone(value) if value else ""

    def clean_whatsapp_phone(self):
        value = self.cleaned_data["whatsapp_phone"]
        return normalize_whatsapp_phone(value) if value else ""

    def clean_profile_photo(self):
        """Accept image uploads only, normalize to a small EXIF-free JPEG.

        Do not touch an existing stored image when no new upload is submitted.
        The built-in forms.ImageField also checks that the file is an image.
        """
        uploaded = self.cleaned_data.get("profile_photo")
        if uploaded is False or not uploaded or not isinstance(uploaded, UploadedFile):
            return uploaded

        if uploaded.size > 5 * 1024 * 1024:
            raise ValidationError("The profile picture must be 5 MB or smaller.")

        try:
            uploaded.seek(0)
            with Image.open(uploaded) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValidationError("Upload a JPEG, PNG or WebP photograph.")
                width, height = image.size
                if width < 64 or height < 64:
                    raise ValidationError("Please choose an image at least 64 × 64 pixels.")
                if width > 4096 or height > 4096:
                    raise ValidationError("Please choose an image no larger than 4096 × 4096 pixels.")
                image = ImageOps.exif_transpose(image)
                image.thumbnail((900, 900), Image.Resampling.LANCZOS)
                if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
                    rgba = image.convert("RGBA")
                    background = Image.new("RGB", rgba.size, (255, 255, 255))
                    background.paste(rgba, mask=rgba.getchannel("A"))
                    image = background
                else:
                    image = image.convert("RGB")
                output = BytesIO()
                image.save(output, format="JPEG", quality=85, optimize=True)
        except (OSError, UnidentifiedImageError, ValueError, Image.DecompressionBombError) as exc:
            raise ValidationError("This image could not be processed. Choose a valid JPEG, PNG or WebP file.") from exc
        finally:
            uploaded.seek(0)

        return SimpleUploadedFile(
            f"avatar-{uuid4().hex}.jpg", output.getvalue(), content_type="image/jpeg"
        )
