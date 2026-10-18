from datetime import date
from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


class ImportForm(forms.Form):
    workbook=forms.FileField(label='SLQS Google Forms export (CSV / XLSX)', help_text='Maximum 3 MB, 2,000 members per file.')
    confirm_approvals=forms.BooleanField(required=False, label='I confirm approved members against the SLQS official approval list.')
    def clean_workbook(self):
        upload=self.cleaned_data['workbook']
        if upload.size>3*1024*1024 or upload.size==0:raise ValidationError('Upload a non-empty file no larger than 3 MB.')
        if not upload.name.lower().endswith(('.xlsx','.csv')):raise ValidationError('Upload .xlsx or .csv.')
        return upload


class EmailForm(forms.Form):
    email=forms.EmailField(label='Email used on your original SLQS registration',max_length=254,
                           widget=forms.EmailInput(attrs={'autocomplete':'email','placeholder':'you@example.com'}))


class CodeForm(forms.Form):
    code=forms.RegexField(r'^\d{6}$',label='Six-digit email code',min_length=6,max_length=6)


class ClaimForm(forms.Form):
    date_of_birth=forms.DateField(label='Date of birth as registered with SLQS',
                    widget=forms.DateInput(attrs={'type':'date'}),input_formats=['%Y-%m-%d'])
    password1=forms.CharField(label='Create password',widget=forms.PasswordInput(attrs={'autocomplete':'new-password'}))
    password2=forms.CharField(label='Confirm password',widget=forms.PasswordInput(attrs={'autocomplete':'new-password'}))
    privacy_consent=forms.BooleanField(required=True,label='I agree to SLQS KSA processing my imported membership details for managing my website account and membership services.')
    def clean(self):
        data=super().clean()
        if data.get('password1')!=data.get('password2'):self.add_error('password2','Passwords must match.')
        elif data.get('password1'):validate_password(data['password1'])
        return data
