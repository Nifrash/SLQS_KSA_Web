"""Phase 2 safety/functional tests. Run: python manage.py test cms_pages"""
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from wagtail.models import Site

from home.models import HomePage
from .models import ContentPage, NavigationItem, SiteBranding


class CMSPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_slqs_phase1", stdout=StringIO())
        cls.home = HomePage.objects.get()

    def _make_page(self, title, slug, *, published=True):
        page = self.home.add_child(instance=ContentPage(
            title=title, slug=slug, intro="A CMS-managed SLQS page", live=False,
        ))
        if published:
            page.save_revision().publish()
        else:
            page.save_revision()
        return page

    def test_new_page_is_routed_by_wagtail(self):
        self._make_page("Professional Resources", "professional-resources")
        response = self.client.get("/professional-resources/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Professional Resources")
        self.assertContains(response, "A CMS-managed SLQS page")

    def test_unpublished_page_is_not_public(self):
        self._make_page("Hidden Draft", "hidden-draft", published=False)
        self.assertEqual(self.client.get("/hidden-draft/").status_code, 404)

    def test_about_page_overrides_only_after_publication(self):
        draft = self._make_page("CMS About", "about", published=False)
        self.assertNotContains(self.client.get("/about/"), "CMS About")
        draft.save_revision().publish()
        self.assertContains(self.client.get("/about/"), "CMS About")

    def test_homepage_preserved_when_dynamic_sections_empty(self):
        response = self.client.get("/")
        self.assertContains(response, "Built on expertise")
        self.assertContains(response, "One community")

    def test_seed_phase2_drafts_are_repeatable(self):
        call_command("seed_slqs_phase2", stdout=StringIO())
        created = ContentPage.objects.count()
        call_command("seed_slqs_phase2", stdout=StringIO())
        self.assertEqual(created, ContentPage.objects.count())
        self.assertFalse(ContentPage.objects.get(slug="about").live)

    def test_existing_phase1_application_routes_still_work(self):
        for path in ("/news/", "/events/", "/membership/", "/contact/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)


class NavigationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_slqs_phase1", stdout=StringIO())

    def test_header_link_is_editable(self):
        NavigationItem.objects.create(
            label="Our People", location="header", internal_path="/about/", sort_order=10,
        )
        self.assertContains(self.client.get("/"), "Our People")

    def test_navigation_requires_one_safe_target(self):
        bad = NavigationItem(label="Bad", internal_path="//attacker.example", location="header")
        with self.assertRaises(ValidationError):
            bad.full_clean()
        both = NavigationItem(label="Bad", internal_path="/about/", external_url="https://example.com")
        with self.assertRaises(ValidationError):
            both.full_clean()

    def test_site_branding_footer_is_editable(self):
        site = Site.objects.get(is_default_site=True)
        branding = SiteBranding.for_site(site)
        branding.footer_description = "Custom editorial footer for SLQS."
        branding.save()
        self.assertContains(self.client.get("/"), "Custom editorial footer for SLQS.")
