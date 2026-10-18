"""Run with: python manage.py test home.tests_redesign"""
from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from home.models import HomePage
from home.blocks import HomeStreamBlock


class HomepageRedesignTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_slqs_phase1", stdout=StringIO())

    def test_new_homepage_renders_without_explicit_redesign_seeding(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A stronger professional community")
        self.assertContains(response, "Stories worth sharing")
        self.assertContains(response, "Where conversations become connections")

    def test_new_editorial_block_types_available(self):
        block = HomeStreamBlock()
        for kind in ("intro_story", "services_grid", "photo_gallery", "news_feed", "events_feed", "join_banner"):
            self.assertIn(kind, block.child_blocks)
        # Existing Phase 2 blocks remain usable.
        self.assertIn("image_text", block.child_blocks)
        self.assertIn("faq", block.child_blocks)

    def test_starter_seed_creates_editable_blocks_idempotently(self):
        call_command("seed_slqs_home_redesign", stdout=StringIO())
        page = HomePage.objects.get()
        self.assertEqual(len(page.sections), 6)
        call_command("seed_slqs_home_redesign", stdout=StringIO())
        page.refresh_from_db()
        self.assertEqual(len(page.sections), 6)

    def test_starter_seed_does_not_overwrite_existing_blocks(self):
        page = HomePage.objects.get()
        page.sections = [("heading", {"title": "Our own custom section"})]
        page.save_revision().publish()
        call_command("seed_slqs_home_redesign", stdout=StringIO())
        page.refresh_from_db()
        self.assertEqual(len(page.sections), 1)
        self.assertEqual(page.sections[0].block_type, "heading")
        response = self.client.get("/")
        self.assertContains(response, "Our own custom section")
        self.assertNotContains(response, "Where conversations become connections")

    def test_hero_fields_are_editable(self):
        page = HomePage.objects.get()
        page.hero_title = "An SLQS homepage managed by the committee"
        page.hero_button_label = "Join now"
        page.hero_button_path = "/membership/"
        page.save_revision().publish()
        resp = self.client.get("/")
        self.assertContains(resp, "An SLQS homepage managed by the committee")
        self.assertContains(resp, "Join now")

    def test_existing_app_urls_remain_intact(self):
        for path in ("/news/", "/events/", "/membership/", "/contact/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
