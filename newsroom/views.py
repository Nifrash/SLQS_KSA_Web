"""Safe, backwards-compatible routing for /news/ beside Phase 1 core routes."""
from django.shortcuts import get_object_or_404, render
from django.http import Http404
from wagtail.models import Site

from .models import NewsArticlePage, NewsIndexPage


def _live_index(request):
    site = Site.find_for_request(request)
    if site is None:
        return None
    return (
        NewsIndexPage.objects.live().public()
        .child_of(site.root_page).first()
    )


def index(request):
    page = _live_index(request)
    if page is None:
        # Preserve Phase 1's public /news/ page before the index is seeded.
        return render(request, 'core/news.html', {'active_page': 'news'})
    return page.serve(request)


def detail(request, slug):
    parent = _live_index(request)
    if parent is None:
        raise Http404('Newsroom is not available.')
    article = get_object_or_404(
        NewsArticlePage.objects.live().public().child_of(parent), slug=slug,
    )
    return article.serve(request)
