"""Regression coverage: applicants respond, committee receives evidence, others cannot access."""
import shutil
import tempfile
from datetime import timedelta
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from member_accounts.models import MemberAccountProfile
from membership.models import (
    MemberPortalNotification, MembershipApplication, MembershipInformationRequest,
    MembershipInformationResponse, MembershipReviewLog,
)
from membership_team.services import request_information


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class DocumentResponseTests(TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        # Redirect the FileField used by this model to a per-test private folder.
        field = MembershipInformationResponse._meta.get_field('document')
        original_storage = field.storage
        field.storage = FileSystemStorage(location=self.folder.name)
        self.addCleanup(setattr, field, 'storage', original_storage)

        call_command('setup_slqs_committee_roles', stdout=StringIO())
        User = get_user_model()
        self.member_user = User.objects.create_user(username='reply@example.test', email='reply@example.test', password='P@ssword123!', is_active=True)
        MemberAccountProfile.objects.create(user=self.member_user, full_name='Reply Member', verified_at=timezone.now())
        self.stranger = User.objects.create_user(username='stranger@example.test', email='stranger@example.test', password='P@ssword123!', is_active=True)
        MemberAccountProfile.objects.create(user=self.stranger, full_name='Unrelated Member', verified_at=timezone.now())
        self.head = User.objects.create_user(username='headReply', password='P@ssword123!', is_staff=True)
        self.head.groups.add(Group.objects.get(name='SLQS Membership Head'))
        self.app = MembershipApplication.objects.create(
            user=self.member_user, full_name='Reply Member',
            date_of_birth=timezone.localdate() - timedelta(days=365 * 32),
            preferred_email='reply@example.test', ksa_phone='+966551234567',
            whatsapp_phone='+966551234567', whatsapp_group_member='yes',
            company_name='Construction Co', job_title='Quantity Surveyor',
            highest_educational_qualification='BSc QS',
            professional_qualifications=['MRICS'],
            overall_post_qualification_experience='8.00', ksa_experience='4.00',
            working_region='riyadh', privacy_consent_at=timezone.now(),
        )
        self.case = self.app.committee_case

    def request_doc(self):
        request_information(self.case.pk, 'Please supply a copy of your professional certificate.', actor=self.head)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, MembershipApplication.Status.MORE_INFO)
        return MembershipInformationRequest.objects.get(application=self.app)

    @staticmethod
    def pdf(content=b'%PDF-1.4\nminimal test document'):
        return SimpleUploadedFile('certificate.pdf', content, content_type='application/pdf')

    def test_respond_in_dashboard_and_restore_review_queue(self):
        with self.captureOnCommitCallbacks(execute=True):
            req = self.request_doc()
        self.assertEqual(MemberPortalNotification.objects.filter(user=self.member_user, kind='info_request').count(), 1)
        self.client.force_login(self.member_user)
        self.assertContains(self.client.get(reverse('member_accounts:dashboard')), 'Reply and upload document')
        self.assertContains(self.client.get(reverse('member_accounts:notifications')), 'professional certificate')
        url = reverse('membership:respond', args=[req.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url, {'message': 'Attached is my current MRICS certificate.', 'document': self.pdf()})
        self.assertRedirects(response, reverse('member_accounts:dashboard'))
        self.app.refresh_from_db()
        req.refresh_from_db()
        self.assertEqual(self.app.status, MembershipApplication.Status.SUBMITTED)
        self.assertIsNotNone(req.responded_at)
        reply = MembershipInformationResponse.objects.get(request=req)
        self.assertTrue(Path(reply.document.path).exists())
        self.assertEqual(MembershipReviewLog.objects.filter(application=self.app, to_status='submitted').count(), 1)
        self.assertEqual(self.client.post(url, {'message': 'Again', 'document': self.pdf()}).status_code, 403)
        self.assertNotContains(self.client.get(reverse('member_accounts:dashboard')), 'Reply and upload document')
        self.assertEqual(MembershipInformationResponse.objects.filter(request=req).count(), 1)

        file_url = reverse('membership:document_download', args=[reply.pk])
        self.assertEqual(self.client.get(file_url).status_code, 200)
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(file_url).status_code, 404)
        self.client.force_login(self.head)
        staff_download = self.client.get(file_url)
        self.assertEqual(staff_download.status_code, 200)
        self.assertEqual(staff_download['Cache-Control'], 'private, no-store, max-age=0')
        self.assertContains(self.client.get(reverse('membership_team:case_detail', args=[self.case.pk])), 'Download submitted evidence')

    def test_malformed_document_rejected_and_status_unchanged(self):
        req = self.request_doc()
        self.client.force_login(self.member_user)
        url = reverse('membership:respond', args=[req.pk])
        resp = self.client.post(url, {'message': 'Attached', 'document': self.pdf(b'<script>alert(1)</script>')})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'genuine PDF')
        self.assertFalse(MembershipInformationResponse.objects.filter(request=req).exists())
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, MembershipApplication.Status.MORE_INFO)

    def test_notifications_are_private_and_read_action_is_post_only(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.request_doc()
        note = MemberPortalNotification.objects.get(user=self.member_user)
        mark_url = reverse('member_accounts:read_notification', args=[note.pk])
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.post(mark_url).status_code, 404)
        self.client.force_login(self.member_user)
        self.assertEqual(self.client.get(mark_url).status_code, 405)
        self.assertRedirects(self.client.post(mark_url), reverse('member_accounts:notifications'))
        note.refresh_from_db()
        self.assertIsNotNone(note.read_at)
