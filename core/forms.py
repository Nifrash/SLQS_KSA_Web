from django import forms
from .models import ContactInquiry


class ContactForm(forms.ModelForm):
    # Honeypot: automated bots often fill every field. Don't store this field.
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'tabindex': '-1', 'autocomplete': 'off', 'aria-hidden': 'true',
    }))
    privacy_consent = forms.BooleanField(required=True, label='I agree to be contacted regarding this enquiry.')

    class Meta:
        model = ContactInquiry
        fields = ('full_name', 'email', 'topic', 'message', 'privacy_consent')
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': 'Your full name', 'autocomplete': 'name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'you@example.com', 'autocomplete': 'email'}),
            'topic': forms.Select(),
            'message': forms.Textarea(attrs={'placeholder': 'Tell us how we can help...', 'rows': 6}),
        }

    def clean_website(self):
        if self.cleaned_data.get('website'):
            raise forms.ValidationError('Invalid submission.')
        return ''
