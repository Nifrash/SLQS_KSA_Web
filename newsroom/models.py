"""Phase 3 editorial newsroom, backed by native Wagtail page publishing."""

from django.db import models
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import StreamField
from wagtail.models import Page
from wagtail.search import index
from wagtail.snippets.models import register_snippet

from cms_pages.blocks import PageStreamBlock


@register_snippet
class NewsCategory(models.Model):
    """Reusable taxonomy, managed in Wagtail > Snippets."""

    name = models.CharField(max_length=90, unique=True)
    slug = models.SlugField(max_length=90, unique=True)
    description = models.CharField(max_length=240, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(default=True)

    panels = [
        FieldPanel('name'), FieldPanel('slug'), FieldPanel('description'),
        FieldPanel('sort_order'), FieldPanel('is_active'),
    ]

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'News categories'

    def __str__(self):
        return self.name


class NewsIndexPage(Page):
    """Newsroom parent; creates /news/ and owns all articles."""

    parent_page_types = ['home.HomePage']
    subpage_types = ['newsroom.NewsArticlePage']
    max_count = 1
    template = 'newsroom/news_index_page.html'

    eyebrow = models.CharField(max_length=110, default='THE SLQS NEWSROOM')
    intro = models.CharField(
        max_length=320,
        default='Association announcements, professional insight and stories from our community.',
    )

    content_panels = Page.content_panels + [
        MultiFieldPanel([FieldPanel('eyebrow'), FieldPanel('intro')], heading='Newsroom header'),
    ]

    class Meta:
        verbose_name = 'SLQS Newsroom'

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        articles = (
            NewsArticlePage.objects.live().public().child_of(self)
            .select_related('category', 'featured_image')
            .order_by('-publish_date', '-first_published_at', '-pk')
        )

        # A bounded, database-escaped search of headlines, excerpts and categories.
        query = (request.GET.get('q') or '').strip()[:100]
        category_slug = (request.GET.get('category') or '').strip()[:90]
        kind = (request.GET.get('type') or '').strip()[:20]

        all_articles = articles
        if query:
            articles = articles.filter(
                Q(title__icontains=query) | Q(excerpt__icontains=query) |
                Q(category__name__icontains=query)
            )
        if category_slug:
            articles = articles.filter(category__slug=category_slug, category__is_active=True)
        if kind in NewsArticlePage.Kind.values:
            articles = articles.filter(kind=kind)
        else:
            kind = ''

        featured_article = None
        if not query and not category_slug and not kind:
            featured_article = all_articles.filter(is_featured=True).first()
            if featured_article:
                articles = articles.exclude(pk=featured_article.pk)

        paginator = Paginator(articles, 9)
        context.update({
            'active_page': 'news',
            'articles_page': paginator.get_page(request.GET.get('page')),
            'featured_article': featured_article,
            'categories': NewsCategory.objects.filter(is_active=True),
            'selected_category': category_slug,
            'selected_kind': kind,
            'search_query': query,
            'article_types': NewsArticlePage.Kind.choices,
        })
        return context


class NewsArticlePage(Page):
    """Native Wagtail article: revisions, preview, moderation and go-live scheduling."""

    class Kind(models.TextChoices):
        NEWS = 'NEWS', 'News'
        ANNOUNCEMENT = 'ANNOUNCEMENT', 'Announcement'
        INSIGHT = 'INSIGHT', 'Professional insight'

    parent_page_types = ['newsroom.NewsIndexPage']
    subpage_types = []
    template = 'newsroom/news_article_page.html'

    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.NEWS)
    category = models.ForeignKey(
        'newsroom.NewsCategory', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='articles',
    )
    publish_date = models.DateField(default=timezone.localdate)
    excerpt = models.CharField(
        max_length=420,
        help_text='A short summary for cards, search results and social sharing.',
    )
    byline = models.CharField(max_length=120, blank=True, help_text='Optional public author name.')
    featured_image = models.ForeignKey(
        'wagtailimages.Image', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    is_featured = models.BooleanField(default=False, help_text='Highlight this article on the news landing page.')
    body = StreamField(
        PageStreamBlock(), blank=True,
        help_text='Build the article using text, images, quotes, documents and other content blocks.',
    )

    content_panels = Page.content_panels + [
        MultiFieldPanel([
            FieldPanel('kind'), FieldPanel('category'), FieldPanel('publish_date'),
            FieldPanel('excerpt'), FieldPanel('byline'),
        ], heading='Article information'),
        MultiFieldPanel([
            FieldPanel('featured_image'), FieldPanel('is_featured'),
        ], heading='Featured media'),
        FieldPanel('body'),
    ]

    search_fields = Page.search_fields + [
        index.SearchField('excerpt'),
        index.SearchField('body'),
        index.FilterField('kind'),
    ]

    class Meta:
        verbose_name = 'SLQS news / announcement article'
        verbose_name_plural = 'SLQS news / announcement articles'
        ordering = ['-publish_date']

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        parent = self.get_parent()
        context['active_page'] = 'news'
        context['news_index'] = parent.specific
        context['related_articles'] = (
            NewsArticlePage.objects.live().public().child_of(parent)
            .exclude(pk=self.pk).select_related('featured_image', 'category')
            .order_by('-publish_date', '-pk')[:3]
        )
        return context
