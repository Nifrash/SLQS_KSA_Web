"""Regression tests for homepage seeding. Run: python manage.py test core.test_seed_slqs_phase1"""
from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from wagtail.models import Page, Site
from home.models import HomePage


class SeedSLQSPhase1Tests(TestCase):
    def run_seed(self):
        call_command("seed_slqs_phase1", stdout=StringIO())

    def test_seed_reuses_homepage_on_second_run(self):
        self.run_seed()
        page_id = HomePage.objects.get().pk
        self.run_seed()
        self.assertEqual(HomePage.objects.count(), 1)
        self.assertEqual(HomePage.objects.get().pk, page_id)
        self.assertEqual(Site.objects.get(is_default_site=True).root_page_id, page_id)

    def test_seed_works_when_home_slug_is_already_taken(self):
        root = Page.get_first_root_node()
        if not root.get_children().filter(slug="home").exists():
            root.add_child(instance=Page(title="Existing Wagtail page", slug="home"))
        self.run_seed()
        page = HomePage.objects.get()
        self.assertNotEqual(page.slug, "home")
        self.assertEqual(page.get_parent().pk, root.pk)
        self.assertEqual(Site.objects.get(is_default_site=True).root_page_id, page.pk)

    def test_seed_retains_existing_homepage_content(self):
        self.run_seed()
        page = HomePage.objects.get()
        page.hero_title = "My existing custom headline"
        page.save_revision().publish()
        self.run_seed()
        page.refresh_from_db()
        self.assertEqual(page.hero_title, "My existing custom headline")
