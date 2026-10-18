"""Create the SLQS homepage safely, even when Wagtail already has a /home/ page.

The command is idempotent: re-running it preserves an existing SLQS HomePage.
It never deletes or modifies Wagtail's placeholder pages.
"""

from django.core.management.base import BaseCommand, CommandError
from wagtail.models import Page, Site

from home.models import HomePage


class Command(BaseCommand):
    help = "Create the SLQS homepage and configure Wagtail's default site."

    def handle(self, *args, **options):
        # Wagtail's initial migration may have created a placeholder page with
        # slug='home' already. Never attempt to create a duplicate sibling.
        homepage = HomePage.objects.order_by("pk").first()

        if homepage is None:
            root = Page.get_first_root_node()
            if root is None:
                raise CommandError(
                    "Wagtail has no root page. Run 'python manage.py migrate' first."
                )

            # The slug of a Wagtail site's root_page does not appear in the
            # public homepage URL: this page will still be served at '/'.
            slug = "home"
            if root.get_children().filter(slug=slug).exists():
                slug = "slqs-home"

            suffix = 2
            while root.get_children().filter(slug=slug).exists():
                slug = f"slqs-home-{suffix}"
                suffix += 1

            homepage = root.add_child(
                instance=HomePage(
                    title="Home",
                    slug=slug,
                    show_in_menus=False,
                )
            )
            homepage.save_revision().publish()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created SLQS homepage (internal page slug: '{homepage.slug}')."
                )
            )
        else:
            self.stdout.write(
                "SLQS homepage already exists; keeping its existing content."
            )
            if not homepage.live:
                self.stdout.write(
                    self.style.WARNING(
                        "Existing homepage is not published; publish it in Wagtail Admin."
                    )
                )

        # Re-use the Wagtail default site, if it exists. Do not delete the
        # placeholder homepage; simply point the site's root to the SLQS page.
        site = Site.objects.filter(is_default_site=True).first()
        if site is None:
            site = Site.objects.order_by("pk").first()

        if site is None:
            site = Site(
                hostname="localhost",
                port=8000,
                site_name="SLQS Saudi Arabia",
                root_page=homepage,
                is_default_site=True,
            )
        else:
            site.root_page = homepage
            site.site_name = "SLQS Saudi Arabia"
            site.is_default_site = True

        site.save()

        self.stdout.write(
            self.style.SUCCESS(
                "Wagtail default site now points to the SLQS homepage."
            )
        )
        self.stdout.write("Open http://127.0.0.1:8000/ and /admin/.")
