"""Regression test: account deletion must retain the committee response and evidence."""
from datetime import timedelta
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from membership.models import (
    MembershipApplication,
    MembershipInformationRequest,
    MembershipInformationResponse,
)


class MemberAccountDeletionTests(TestCase):
    def test_deleting_user_preserves_response_and_application(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        document_field = MembershipInformationResponse._meta.get_field("document")
        original_storage = document_field.storage
        document_field.storage = FileSystemStorage(location=temp.name)
        self.addCleanup(setattr, document_field, "storage", original_storage)

        user = get_user_model().objects.create_user(
            username="delete-member@example.test",
            email="delete-member@example.test",
            password="TestPassword123!",
        )
        application = MembershipApplication.objects.create(
            user=user,
            full_name="Deletion Regression Applicant",
            date_of_birth=timezone.localdate() - timedelta(days=365 * 30),
            preferred_email="delete-member@example.test",
            ksa_phone="+966551234567",
            whatsapp_phone="+966551234567",
            whatsapp_group_member="no",
            company_name="Example Company",
            job_title="Quantity Surveyor",
            highest_educational_qualification="BSc QS",
            professional_qualifications=["MRICS"],
            overall_post_qualification_experience="5.00",
            ksa_experience="2.00",
            working_region="riyadh",
            privacy_consent_at=timezone.now(),
            status=MembershipApplication.Status.MORE_INFO,
        )
        info_request = MembershipInformationRequest.objects.create(
            application=application, message="Please provide your certificate."
        )
        response = MembershipInformationResponse.objects.create(
            request=info_request,
            user=user,
            message="Attached as requested.",
            document=SimpleUploadedFile(
                "certificate.pdf", b"%PDF-1.4\nSample membership evidence",
                content_type="application/pdf",
            ),
        )
        response_id = response.pk
        document_name = response.document.name
        user_id = user.pk

        get_user_model().objects.filter(pk=user_id).delete()

        self.assertFalse(get_user_model().objects.filter(pk=user_id).exists())
        self.assertTrue(MembershipApplication.objects.filter(pk=application.pk).exists())
        application.refresh_from_db()
        self.assertIsNone(application.user_id)
        response = MembershipInformationResponse.objects.get(pk=response_id)
        self.assertIsNone(response.user_id)
        self.assertEqual(response.request_id, info_request.pk)
        self.assertEqual(response.document.name, document_name)
        self.assertTrue(response.document.storage.exists(response.document.name))
