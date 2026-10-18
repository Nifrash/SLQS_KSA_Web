"""Regression coverage for legacy import, idempotency, role guards and OTP claim."""
import csv
import io
import re
from datetime import date
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from membership.models import MembershipApplication, MemberProfile
from digital_cards.models import DigitalMembershipCard
from .importer import preview, apply_import
from .models import LegacyMemberRecord, LegacyImportBatch

HEADERS=[
 'Import Record ID','Form Submission Timestamp','Collected Email Address','Full Name','Date of Birth',
 'Preferred Email','KSA Phone Number','WhatsApp Phone Number','Already in SLQS WhatsApp Group',
 'Company Name','Job Title','Highest Educational Qualification (QS / Engineering Related)',
 'Professional Qualifications (Active as of date)','Other Professional Qualification (if selected)',
 'Overall Years of Post-Qualification Experience','Years of KSA Experience','Working Region in KSA',
 'Your Suggestions to Improve SLQS KSA Services','SLQS Approval Status (Legacy)',
 'Existing SLQS Member Number','Approved Date','Test Scenario','Import Notes'
]


def workbook_bytes(email='historical@example.org',status='Approved',member_number='SLQS-KSA-004200',date_of_birth='1991-03-14'):
    output=io.StringIO()
    writer=csv.writer(output)
    writer.writerow(HEADERS)
    writer.writerow(['TEST-001','2026-08-15 10:00',email,'Demo SLQS Member',date_of_birth,email,
                     '+966550001234','+966550001234','Yes','Example QS','Quantity Surveyor',
                     'BSc (Hons) Quantity Surveying','MRICS, MCIArb','',12,8,'Riyadh Region',
                     'Test record',status,member_number if status=='Approved' else '',
                     '2025-04-10' if status=='Approved' else '','',''])
    return output.getvalue().encode('utf-8')


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.head=get_user_model().objects.create_user(username='head',email='head@example.org',password='test-password',is_staff=True)
        group=Group.objects.create(name='SLQS Membership Head')
        permission=Permission.objects.get(codename='decide_committeecase',content_type__app_label='membership_team')
        group.permissions.add(permission)
        cls.head.groups.add(group)
        cls.officer=get_user_model().objects.create_user(username='officer',email='officer@example.org',password='test-password',is_staff=True)

    def test_preview_has_no_db_side_effect(self):
        data=preview(workbook_bytes(),'sample.csv')
        self.assertEqual(data['create'],1)
        self.assertEqual(data['errors'],0)
        self.assertEqual(MembershipApplication.objects.count(),0)

    def test_import_approved_preserves_number_and_card(self):
        result=preview(workbook_bytes(),'sample.csv')
        batch=apply_import(result,'sample.csv',self.head)
        self.assertEqual(batch.created_count,1)
        app=MembershipApplication.objects.get()
        self.assertEqual(app.status,MembershipApplication.Status.APPROVED)
        self.assertIsNone(app.privacy_consent_at)
        self.assertEqual(app.member_profile.membership_number,'SLQS-KSA-004200')
        self.assertEqual(app.member_profile.joined_on,date(2025,4,10))
        self.assertTrue(DigitalMembershipCard.objects.filter(member=app.member_profile).exists())
        self.assertEqual(preview(workbook_bytes(),'sample.csv')['skip'],1)

    def test_pending_does_not_create_card(self):
        result=preview(workbook_bytes(status='Pending'),'sample.csv')
        apply_import(result,'sample.csv',self.head)
        self.assertEqual(MembershipApplication.objects.first().status,MembershipApplication.Status.SUBMITTED)
        self.assertEqual(MemberProfile.objects.count(),0)
        self.assertEqual(DigitalMembershipCard.objects.count(),0)

    def test_import_detects_duplicate_email_and_member_number(self):
        apply_import(preview(workbook_bytes(),'sample.csv'),'sample.csv',self.head)
        result=preview(workbook_bytes(email='another@example.org',member_number='SLQS-KSA-004200'),'sample.csv')
        self.assertGreater(result['errors'],0)
        self.assertEqual(LegacyMemberRecord.objects.count(),1)

    def test_non_head_cannot_import(self):
        self.client.force_login(self.officer)
        response=self.client.get(reverse('legacy_members:import'))
        self.assertEqual(response.status_code,403)

    def test_head_preview_then_confirm_reupload(self):
        self.client.force_login(self.head)
        def payload(action,consent=''):
            return {'workbook':SimpleUploadedFile('sample.csv',workbook_bytes(),content_type='text/csv'),
                    'action':action,'confirm_approvals':consent}
        url=reverse('legacy_members:import')
        response=self.client.post(url,payload('preview'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(MembershipApplication.objects.count(),0)
        response=self.client.post(url,payload('confirm','on'))
        self.assertEqual(response.status_code,302)
        self.assertEqual(MembershipApplication.objects.count(),1)
        self.client.post(url,payload('preview'))
        self.client.post(url,payload('confirm','on'))
        self.assertEqual(MembershipApplication.objects.count(),1)
        self.assertEqual(LegacyImportBatch.objects.count(),2)

    def test_activation_requires_email_otp_and_dob(self):
        apply_import(preview(workbook_bytes(),'sample.csv'),'sample.csv',self.head)
        start=reverse('legacy_members:activate')
        response=self.client.post(start,{'email':'historical@example.org'})
        self.assertRedirects(response,reverse('legacy_members:activate_verify'))
        self.assertEqual(len(mail.outbox),1)
        code=re.search(r'\b\d{6}\b',mail.outbox[-1].body).group()
        response=self.client.post(reverse('legacy_members:activate_verify'),{'code':'111111' if code!='111111' else '000000'})
        self.assertEqual(response.status_code,200)
        response=self.client.post(reverse('legacy_members:activate_verify'),{'code':code})
        self.assertRedirects(response,reverse('legacy_members:activate_claim'))
        response=self.client.post(reverse('legacy_members:activate_claim'),{
            'date_of_birth':'1991-03-14','password1':'Secure!Password_8392','password2':'Secure!Password_8392',
            'privacy_consent':'on',})
        self.assertRedirects(response,reverse('member_accounts:dashboard'))
        app=MembershipApplication.objects.get()
        self.assertIsNotNone(app.user_id)
        self.assertIsNotNone(app.privacy_consent_at)
        self.assertTrue(app.user.slqs_account.verified_at)
        self.assertTrue(app.user.check_password('Secure!Password_8392'))
        self.assertEqual(self.client.get(reverse('member_accounts:dashboard')).status_code,200)
        self.assertTrue(LegacyMemberRecord.objects.get().activated_at)

    def test_preexisting_login_account_must_be_verified_by_staff(self):
        apply_import(preview(workbook_bytes(),'sample.csv'),'sample.csv',self.head)
        get_user_model().objects.create_user(username='historical@example.org',email='historical@example.org',password='some-password')
        self.client.post(reverse('legacy_members:activate'),{'email':'historical@example.org'})
        self.assertEqual(len(mail.outbox),0)
        self.assertIsNone(MembershipApplication.objects.get().user)

    def test_wrong_birth_date_attempts_are_limited(self):
        apply_import(preview(workbook_bytes(),'sample.csv'),'sample.csv',self.head)
        self.client.post(reverse('legacy_members:activate'),{'email':'historical@example.org'})
        code=re.search(r'\b\d{6}\b',mail.outbox[-1].body).group()
        self.client.post(reverse('legacy_members:activate_verify'),{'code':code})
        for _ in range(5):
            response=self.client.post(reverse('legacy_members:activate_claim'),{
                'date_of_birth':'1992-03-14','password1':'Secure!Password_8392',
                'password2':'Secure!Password_8392','privacy_consent':'on'})
            self.assertEqual(response.status_code,200)
        self.assertEqual(LegacyMemberRecord.objects.get().challenges.first().identity_attempts,5)
        response=self.client.post(reverse('legacy_members:activate_claim'),{
            'date_of_birth':'1991-03-14','password1':'Secure!Password_8392',
            'password2':'Secure!Password_8392','privacy_consent':'on'})
        self.assertEqual(response.status_code,200)
        self.assertIsNone(MembershipApplication.objects.get().user)
