"""Phase 8 access-control and workflow regression tests."""
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from membership.models import MemberProfile, MembershipApplication, MembershipReviewLog
from .models import CommitteeActionLog, CommitteeCase, CommitteeRecommendation


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class CommitteePortalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_slqs_committee_roles', stdout=StringIO())
        User = get_user_model()
        cls.head = User.objects.create_user(username='head8', password='secure-pass', is_staff=True)
        cls.head.groups.add(Group.objects.get(name='SLQS Membership Head'))
        cls.secretary = User.objects.create_user(username='secretary8', password='secure-pass', is_staff=True)
        cls.secretary.groups.add(Group.objects.get(name='SLQS Membership Secretary'))
        cls.reviewer = User.objects.create_user(username='reviewer8', password='secure-pass', is_staff=True)
        cls.reviewer.groups.add(Group.objects.get(name='SLQS Membership Reviewer'))
        cls.other_reviewer = User.objects.create_user(username='other8', password='secure-pass', is_staff=True)
        cls.other_reviewer.groups.add(Group.objects.get(name='SLQS Membership Reviewer'))
        cls.member_user = User.objects.create_user(username='regular8', password='secure-pass')

    def application(self, email='reviewcase@example.com'):
        app = MembershipApplication.objects.create(
            full_name='Example Quantity Surveyor',
            date_of_birth=timezone.localdate() - timedelta(days=365 * 30),
            preferred_email=email, ksa_phone='+966551234567',
            whatsapp_phone='+966551234567', whatsapp_group_member='yes',
            company_name='Civil Engineering Ltd', job_title='Quantity Surveyor',
            highest_educational_qualification='BSc Quantity Surveying',
            professional_qualifications=['MRICS'],
            overall_post_qualification_experience='10.00', ksa_experience='5.00',
            working_region='riyadh', privacy_consent_at=timezone.now(),
        )
        return app

    def test_login_separate_from_regular_otp_account(self):
        url = reverse('membership_team:dashboard')
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.member_user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.logout()
        response = self.client.post(reverse('membership_team:login'), {
            'username': self.member_user.username, 'password': 'secure-pass',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'committee login credentials')
        response = self.client.post(reverse('membership_team:login'), {
            'username': self.head.username, 'password': 'secure-pass',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], url)

    def test_backfill_command_idempotent(self):
        # Create without post_save: emulate an older migration/import.
        app = MembershipApplication(
            full_name='Old Member', date_of_birth=timezone.localdate() - timedelta(days=365*31),
            preferred_email='older8@example.com', ksa_phone='+966551234568',
            whatsapp_phone='+966551234568', whatsapp_group_member='no',
            company_name='Example', job_title='QS',
            highest_educational_qualification='BSc', professional_qualifications=['None'],
            overall_post_qualification_experience='9.00', ksa_experience='3.00',
            working_region='eastern', privacy_consent_at=timezone.now(),
        )
        MembershipApplication.objects.bulk_create([app])
        out = StringIO()
        call_command('sync_slqs_committee_cases', '--dry-run', stdout=out)
        self.assertIn('1', out.getvalue())
        self.assertFalse(CommitteeCase.objects.filter(application=app).exists())
        call_command('sync_slqs_committee_cases', stdout=StringIO())
        call_command('sync_slqs_committee_cases', stdout=StringIO())
        self.assertEqual(CommitteeCase.objects.filter(application=app).count(), 1)

    def test_assignment_restricts_reviewer_visibility(self):
        app = self.application()
        case = app.committee_case
        self.client.force_login(self.head)
        response = self.client.post(reverse('membership_team:assign', args=[case.pk]), {
            'assigned_to': self.reviewer.pk, 'priority': 'high',
        })
        self.assertEqual(response.status_code, 302)
        case.refresh_from_db()
        app.refresh_from_db()
        self.assertEqual(case.assigned_to, self.reviewer)
        self.assertEqual(case.priority, 'high')
        self.assertEqual(app.status, MembershipApplication.Status.IN_REVIEW)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.get(reverse('membership_team:case_detail', args=[case.pk])).status_code, 200)
        self.client.force_login(self.other_reviewer)
        self.assertEqual(self.client.get(reverse('membership_team:case_detail', args=[case.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('membership_team:applications')), app.full_name)
        self.assertEqual(self.client.post(reverse('membership_team:assign', args=[case.pk]), {'assigned_to': self.other_reviewer.pk, 'priority': 'normal'}).status_code, 403)

    def test_head_can_approve_directly_and_member_is_created_once(self):
        app = self.application()
        case = app.committee_case
        self.client.force_login(self.head)
        # Head approval needs neither assignment nor reviewer recommendation.
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('membership_team:decide', args=[case.pk]), {
                'decision': 'approved', 'note': 'Qualifications verified by Membership Head',
            })
        self.assertEqual(response.status_code, 302)
        app.refresh_from_db()
        self.assertEqual(app.status, MembershipApplication.Status.APPROVED)
        self.assertFalse(CommitteeRecommendation.objects.filter(case=case).exists())
        member = MemberProfile.objects.get(application=app)
        self.assertTrue(member.membership_number.startswith('SLQS-KSA-'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(member.membership_number, mail.outbox[0].body)
        self.assertNotIn('independent recommendation waived', mail.outbox[0].body)
        audit = CommitteeActionLog.objects.get(case=case, action='decided')
        self.assertIn('Direct Membership Head decision', audit.note)
        self.assertEqual(audit.actor, self.head)
        # Closed cases cannot be approved twice or duplicated.
        self.client.post(reverse('membership_team:decide', args=[case.pk]), {
            'decision': 'approved', 'note': 'Second attempt',
        })
        self.assertEqual(MemberProfile.objects.filter(application=app).count(), 1)
        self.assertEqual(MembershipReviewLog.objects.filter(application=app, to_status='approved').count(), 1)

    def test_head_can_reject_directly_and_reason_is_recorded(self):
        app = self.application()
        self.client.force_login(self.head)
        self.client.post(reverse('membership_team:decide', args=[app.committee_case.pk]), {
            'decision': 'rejected', 'note': 'Insufficient proof of eligibility',
        })
        app.refresh_from_db()
        self.assertEqual(app.status, MembershipApplication.Status.REJECTED)
        self.assertFalse(MemberProfile.objects.filter(application=app).exists())
        self.assertIn('Direct Membership Head decision', app.committee_case.committee_history.first().note)

    def test_secretary_requests_information_and_reviewer_cannot(self):
        app = self.application()
        case = app.committee_case
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.post(reverse('membership_team:more_info', args=[case.pk]), {'note': 'Evidence required'}).status_code, 403)
        self.client.force_login(self.secretary)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('membership_team:more_info', args=[case.pk]), {
                'note': 'Please supply a copy of your professional qualification.',
            })
        self.assertEqual(response.status_code, 302)
        app.refresh_from_db()
        self.assertEqual(app.status, MembershipApplication.Status.MORE_INFO)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/membership/', mail.outbox[0].body)
        self.assertEqual(CommitteeActionLog.objects.filter(case=case, action='more_info').count(), 1)

    def test_member_directory_and_exports_restricted(self):
        app = self.application()
        app.company_name = '=HYPERLINK("https://bad.example")'
        app.save(update_fields=['company_name'])
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.get(reverse('membership_team:members')).status_code, 403)
        self.assertEqual(self.client.get(reverse('membership_team:export')).status_code, 403)
        self.client.force_login(self.head)
        self.assertEqual(self.client.get(reverse('membership_team:members')).status_code, 200)
        result = self.client.get(reverse('membership_team:export'))
        self.assertEqual(result.status_code, 200)
        self.assertIn("'=HYPERLINK", result.content.decode('utf-8'))

    def test_post_only_and_recommendations_are_not_emailed(self):
        app = self.application()
        case = app.committee_case
        self.client.force_login(self.head)
        self.client.post(reverse('membership_team:assign', args=[case.pk]), {'assigned_to': self.reviewer.pk, 'priority': 'normal'})
        self.assertEqual(self.client.get(reverse('membership_team:decide', args=[case.pk])).status_code, 405)
        self.client.force_login(self.reviewer)
        self.client.post(reverse('membership_team:recommend', args=[case.pk]), {'outcome': 'reject', 'note': 'Private staff note'})
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(CommitteeActionLog.objects.filter(case=case, action='recommended').count(), 1)

    def test_head_can_decide_after_own_recommendation(self):
        app = self.application()
        case = app.committee_case
        self.client.force_login(self.head)
        self.client.post(reverse('membership_team:recommend', args=[case.pk]), {
            'outcome': 'approve', 'note': 'Head recommends approval',
        })
        self.client.post(reverse('membership_team:decide', args=[case.pk]), {
            'decision': 'approved', 'note': 'Head completed verification',
        })
        app.refresh_from_db()
        self.assertEqual(app.status, MembershipApplication.Status.APPROVED)
        self.assertEqual(MemberProfile.objects.filter(application=app).count(), 1)

    def test_other_approvers_still_require_independent_current_review(self):
        app = self.application()
        case = app.committee_case
        # Simulate a separately delegated final-decision permission: it must
        # not automatically grant the Head's direct-approval privilege.
        perm = Permission.objects.get(
            content_type__app_label='membership_team',
            content_type__model='committeecase',
            codename='decide_committeecase',
        )
        self.secretary.user_permissions.add(perm)
        self.client.force_login(self.secretary)
        self.client.post(reverse('membership_team:decide', args=[case.pk]), {
            'decision': 'approved', 'note': 'Attempt without review',
        })
        app.refresh_from_db()
        self.assertEqual(app.status, MembershipApplication.Status.SUBMITTED)
        self.assertFalse(MemberProfile.objects.filter(application=app).exists())
        # A current recommendation from another reviewer restores the ability
        # to record a final decision for this specially permitted account.
        self.client.force_login(self.head)
        self.client.post(reverse('membership_team:assign', args=[case.pk]), {
            'assigned_to': self.reviewer.pk, 'priority': 'normal',
        })
        self.client.force_login(self.reviewer)
        self.client.post(reverse('membership_team:recommend', args=[case.pk]), {
            'outcome': 'approve', 'note': 'Current qualification review',
        })
        self.client.force_login(self.secretary)
        self.client.post(reverse('membership_team:decide', args=[case.pk]), {
            'decision': 'approved', 'note': 'Delegated final decision after review',
        })
        app.refresh_from_db()
        self.assertEqual(app.status, MembershipApplication.Status.APPROVED)

    def test_reviewer_cannot_record_direct_decision(self):
        app = self.application()
        self.client.force_login(self.reviewer)
        response = self.client.post(reverse('membership_team:decide', args=[app.committee_case.pk]), {
            'decision': 'approved', 'note': 'Attempt unauthorized direct approval',
        })
        self.assertEqual(response.status_code, 403)
        app.refresh_from_db()
        self.assertEqual(app.status, MembershipApplication.Status.SUBMITTED)

    def test_head_still_requires_written_reason(self):
        app = self.application()
        self.client.force_login(self.head)
        self.client.post(reverse('membership_team:decide', args=[app.committee_case.pk]), {
            'decision': 'approved', 'note': '',
        })
        app.refresh_from_db()
        self.assertEqual(app.status, MembershipApplication.Status.SUBMITTED)
        self.assertFalse(MemberProfile.objects.filter(application=app).exists())

    def test_head_can_decide_on_resubmission_without_new_recommendation(self):
        app = self.application()
        case = app.committee_case
        self.client.force_login(self.head)
        self.client.post(reverse('membership_team:assign', args=[case.pk]), {
            'assigned_to': self.reviewer.pk, 'priority': 'normal',
        })
        self.client.force_login(self.reviewer)
        self.client.post(reverse('membership_team:recommend', args=[case.pk]), {
            'outcome': 'approve', 'note': 'Initial review',
        })
        app.refresh_from_db()
        app.status = MembershipApplication.Status.MORE_INFO
        app.save(update_fields=['status', 'updated_at'])
        app.status = MembershipApplication.Status.SUBMITTED
        app.save(update_fields=['status', 'updated_at'])
        self.client.force_login(self.head)
        self.client.post(reverse('membership_team:decide', args=[case.pk]), {
            'decision': 'approved', 'note': 'I reviewed the newly submitted document',
        })
        app.refresh_from_db()
        self.assertEqual(app.status, MembershipApplication.Status.APPROVED)
        self.assertIn('Direct Membership Head decision', case.committee_history.first().note)

    def test_head_cannot_approve_while_waiting_for_requested_information(self):
        app = self.application()
        case = app.committee_case
        app.status = MembershipApplication.Status.MORE_INFO
        app.save(update_fields=['status', 'updated_at'])
        self.client.force_login(self.head)
        self.client.post(reverse('membership_team:decide', args=[case.pk]), {
            'decision': 'approved', 'note': 'Attempt while awaiting documentation',
        })
        app.refresh_from_db()
        self.assertEqual(app.status, MembershipApplication.Status.MORE_INFO)
        self.assertFalse(MemberProfile.objects.filter(application=app).exists())
