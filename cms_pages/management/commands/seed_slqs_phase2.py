"""Optional, repeatable Phase 2 preparation. Never overwrites published pages."""
from django.core.management.base import BaseCommand, CommandError
from wagtail.models import Site
from cms_pages.models import ContentPage
from home.models import HomePage


class Command(BaseCommand):
    help = "Create draft CMS versions of the SLQS About / What We Do / Privacy pages."

    def handle(self, *args, **options):
        site = Site.objects.filter(is_default_site=True).first()
        if not site or not isinstance(site.root_page.specific, HomePage):
            raise CommandError("Run 'python manage.py seed_slqs_phase1' before preparing Phase 2.")
        home = site.root_page.specific
        pages = [
            ("about", "About Us", "ABOUT THE ASSOCIATION", "Learn about the SLQS professional community in Saudi Arabia."),
            ("what-we-do", "What We Do", "OUR PROFESSIONAL FOCUS", "Professional development, networking and shared expertise."),
            ("privacy", "Privacy Information", "YOUR PRIVACY", "Information about how SLQS handles website enquiries."),
        ]
        for slug, title, eyebrow, intro in pages:
            if home.get_children().filter(slug=slug).exists():
                self.stdout.write(f"Skipping {slug}: a page already uses this slug.")
                continue
            page = home.add_child(instance=ContentPage(
                title=title, slug=slug, eyebrow=eyebrow, intro=intro,
                show_in_menus=True, live=False,
            ))
            page.save_revision()
            self.stdout.write(self.style.SUCCESS(f"Created draft '/{slug}/' (not published)."))
        self.stdout.write("Edit drafts in /admin/ > Pages > Home. The Phase 1 public pages remain visible until publication.")
