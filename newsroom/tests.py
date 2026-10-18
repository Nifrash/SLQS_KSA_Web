"""Phase 3 regressions; execute: python manage.py test newsroom."""
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from wagtail.models import Site

from home.models import HomePage
from .models import NewsIndexPage, NewsArticlePage, NewsCategory


class NewsroomPublicTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_slqs_phase1', stdout=StringIO())
        call_command('seed_slqs_phase3', stdout=StringIO())
        cls.index = NewsIndexPage.objects.get()
        cls.category = NewsCategory.objects.get(slug='association-news')

    def add_article(self, title='Professional gathering', slug='professional-gathering', *, published=True, category=None, kind='NEWS', is_featured=False, days_ago=0):
        article = self.index.add_child(instance=NewsArticlePage(
            title=title, slug=slug, live=False, excerpt='A practical update about SLQS activities.',
            category=category or self.category, kind=kind, is_featured=is_featured,
            publish_date=timezone.localdate() - timedelta(days=days_ago),
        ))
        if published:
            article.save_revision().publish()
        else:
            article.save_revision()
        return article

    def test_phase3_index_loads_without_any_articles(self):
        response = self.client.get(reverse('core:news'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'NO ARTICLES PUBLISHED YET')
        self.assertContains(response, 'Find stories')

    def test_article_publishes_with_detail_page_and_homepage_card(self):
        article = self.add_article()
        response = self.client.get('/news/')
        self.assertContains(response, article.title)
        self.assertContains(self.client.get('/news/professional-gathering/'), article.excerpt)
        self.assertContains(self.client.get('/'), article.title)

    def test_draft_is_invisible_in_list_detail_and_home(self):
        self.add_article('Private draft', 'private-draft', published=False)
        self.assertNotContains(self.client.get('/news/'), 'Private draft')
        self.assertEqual(self.client.get('/news/private-draft/').status_code, 404)
        self.assertNotContains(self.client.get('/'), 'Private draft')

    def test_category_type_and_search_filter(self):
        self.add_article('Association announcement', 'association-announcement', kind='ANNOUNCEMENT')
        self.add_article('Engineering knowledge', 'engineering-knowledge', kind='INSIGHT')
        resp = self.client.get('/news/?q=Engineering')
        self.assertContains(resp, 'Engineering knowledge')
        self.assertNotContains(resp, '/news/association-announcement/')
        resp = self.client.get('/news/?type=ANNOUNCEMENT')
        self.assertContains(resp, 'Association announcement')
        self.assertNotContains(resp, 'Engineering knowledge')
        resp = self.client.get('/news/?category=association-news')
        self.assertContains(resp, 'Engineering knowledge')
        self.assertContains(resp, 'Association announcement')
        resp = self.client.get('/news/?category=missing')
        self.assertContains(resp, 'No matching articles found')

    def test_featured_article_does_not_duplicate_in_grid(self):
        article = self.add_article('Featured announcement', 'featured-announcement', is_featured=True)
        self.add_article('Other story', 'other-story')
        response = self.client.get('/news/')
        self.assertContains(response, 'FEATURED STORY')
        self.assertContains(response, article.title)
        self.assertContains(response, 'Other story')

    def test_news_pagination_nine_stories_per_page(self):
        for i in range(12):
            self.add_article(f'News entry number {i}', f'news-entry-{i}', days_ago=i)
        first = self.client.get('/news/')
        second = self.client.get('/news/?page=2')
        self.assertContains(first, 'Page 1 of 2')
        self.assertContains(second, 'Page 2 of 2')
        self.assertNotContains(first, 'News entry number 11')
        self.assertContains(second, 'News entry number 11')

    def test_repeat_seed_keeps_existing_article(self):
        self.add_article()
        before = (NewsIndexPage.objects.count(), NewsCategory.objects.count(), NewsArticlePage.objects.count())
        call_command('seed_slqs_phase3', stdout=StringIO())
        after = (NewsIndexPage.objects.count(), NewsCategory.objects.count(), NewsArticlePage.objects.count())
        self.assertEqual(before, after)

    def test_other_site_articles_not_leaked(self):
        self.add_article()
        home = HomePage.objects.get()
        self.assertEqual(Site.objects.get(is_default_site=True).root_page_id, home.pk)
        # Query/slug routes must stay rooted at the public site's NewsIndexPage.
        self.assertEqual(self.client.get('/news/nonexistent/').status_code, 404)

    def test_legacy_event_and_contact_routes_are_unaffected(self):
        self.assertEqual(self.client.get(reverse('core:events')).status_code, 200)
        self.assertEqual(self.client.get(reverse('core:contact')).status_code, 200)
