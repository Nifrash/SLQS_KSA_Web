"""Public free event registration form with explicit privacy consent."""
from django import forms
from .models import EventRegistration


class EventRegistrationForm(forms.ModelForm):
    consent = forms.BooleanField(
        required=True,
        label="I agree that SLQS may process my information to manage this event registration.",
    )

    class Meta:
        model = EventRegistration
        fields = ["full_name", "email", "phone", "organisation", "job_title", "city"]
        widgets = {
            "full_name": forms.TextInput(attrs={"autocomplete": "name", "placeholder": "Your full name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "you@example.com"}),
            "phone": forms.TextInput(attrs={"autocomplete": "tel", "placeholder": "+966 ..."}),
            "organisation": forms.TextInput(attrs={"placeholder": "Your employer (optional)"}),
            "job_title": forms.TextInput(attrs={"placeholder": "Quantity Surveyor (optional)"}),
            "city": forms.TextInput(attrs={"placeholder": "City (optional)"}),
        }

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()
