"""Create the newsroom home and taxonomy without changing existing news."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from wagtail.models import Site

from home.models import HomePage
from newsroom.models import NewsCategory, NewsIndexPage


class Command(BaseCommand):
    help = 'Prepare /news/ and standard categories, without creating fictional articles.'

    @transaction.atomic
    def handle(self, *args, **options):
        site = Site.objects.filter(is_default_site=True).first()
        if site is None or not isinstance(site.root_page.specific, HomePage):
            raise CommandError('Run seed_slqs_phase1 first; the default site must point to an SLQS HomePage.')
        homepage = site.root_page.specific
        existing = homepage.get_children().filter(slug='news').first()
        if existing:
            if not isinstance(existing.specific, NewsIndexPage):
                raise CommandError(
                    "A different Wagtail page already uses 'news' beneath Home. "
                    'Rename/move it in Wagtail before rerunning (do not delete it blindly).'
                )
            self.stdout.write('Existing newsroom found; keeping its content and publication state.')
        else:
            news = homepage.add_child(instance=NewsIndexPage(
                title='News & Announcements', slug='news', show_in_menus=True, live=False,
            ))
            news.save_revision().publish()
            self.stdout.write(self.style.SUCCESS('Created and published /news/ newsroom.'))

        categories = [
            ('association-news', 'Association News', 10),
            ('announcements', 'Announcements', 20),
            ('professional-insights', 'Professional Insights', 30),
            ('community-updates', 'Community Updates', 40),
        ]
        for slug, name, order in categories:
            _, created = NewsCategory.objects.get_or_create(
                slug=slug, defaults={'name': name, 'sort_order': order},
            )
            if created:
                self.stdout.write(f'  Category created: {name}')

        self.stdout.write(self.style.SUCCESS('Phase 3 newsroom is ready. Add news under Pages > Home > News & Announcements.'))
