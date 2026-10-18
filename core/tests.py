from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from home.models import HomePage
from .models import ContactInquiry


class PublicWebsiteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_slqs_phase1', stdout=StringIO())

    def test_homepage_is_public_and_uses_slqs_design(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Built on expertise')
        self.assertContains(response, 'Explore membership')
        self.assertContains(response, 'SLQS')

    def test_phase_one_pages(self):
        for page in ['about', 'what_we_do', 'news', 'events', 'membership', 'contact', 'privacy']:
            with self.subTest(page=page):
                response = self.client.get(reverse(f'core:{page}'))
                self.assertEqual(response.status_code, 200)

    def test_news_and_event_pages_do_not_claim_unpublished_articles(self):
        self.assertContains(self.client.get(reverse('core:news')), 'NO ARTICLES PUBLISHED YET')
        self.assertContains(self.client.get(reverse('core:events')), 'NO EVENTS PUBLISHED YET')

    def test_contact_form_persists_to_database(self):
        data = {
            'full_name': 'Test Member',
            'email': 'member@example.com',
            'topic': 'MEMBERSHIP',
            'message': 'I would like to learn about SLQS membership.',
            'privacy_consent': 'on',
            'website': '',
        }
        response = self.client.post(reverse('core:contact'), data)
        self.assertRedirects(response, reverse('core:contact'))
        self.assertEqual(ContactInquiry.objects.count(), 1)
        self.assertEqual(ContactInquiry.objects.first().topic, 'MEMBERSHIP')

    def test_contact_form_rejects_invalid_or_bot_data(self):
        invalid = {
            'full_name': 'Bot', 'email': 'invalid-email', 'topic': 'GENERAL',
            'message': 'Hello', 'website': 'https://spam.example',
        }
        response = self.client.post(reverse('core:contact'), invalid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactInquiry.objects.count(), 0)

    def test_seed_is_idempotent(self):
        original_count = HomePage.objects.count()
        call_command('seed_slqs_phase1', stdout=StringIO())
        self.assertEqual(HomePage.objects.count(), original_count)

    def test_admin_requires_authentication(self):
        response = self.client.get('/admin/')
        self.assertIn(response.status_code, [302, 301])
