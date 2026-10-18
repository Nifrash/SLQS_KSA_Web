"""CMS-managed public pages, navigation snippets and site settings."""
from django.core.exceptions import ValidationError
from django.db import models
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.fields import StreamField
from wagtail.models import Page
from wagtail.snippets.models import register_snippet

from .blocks import PageStreamBlock

# Do not allow the CMS to shadow routes that belong to dedicated applications.
# 'about', 'what-we-do', 'privacy' are intentionally allowed: Phase 2 makes
# those specific Phase 1 sections editable after publishing a Wagtail page.
RESERVED_FIRST_LEVEL_SLUGS = {
    "admin", "system-admin", "documents", "static", "media",
    "news", "events", "membership", "contact",
}


class ContentPage(Page):
    """General-purpose page assembled through Wagtail's StreamField editor."""

    parent_page_types = ["home.HomePage", "cms_pages.ContentPage"]
    subpage_types = ["cms_pages.ContentPage"]
    template = "cms_pages/content_page.html"

    intro = models.TextField(blank=True, max_length=850, help_text="Optional introduction shown under the page title")
    eyebrow = models.CharField(blank=True, max_length=100, help_text="Optional small label above the page title")
    body = StreamField(PageStreamBlock(), blank=True, help_text="Add, reorder and remove page sections")

    content_panels = Page.content_panels + [
        FieldPanel("eyebrow"),
        FieldPanel("intro"),
        FieldPanel("body"),
    ]

    class Meta:
        verbose_name = "SLQS content page"
        verbose_name_plural = "SLQS content pages"

    def clean(self):
        super().clean()
        # Protect existing Phase 1 application URLs. Wagtail route resolution
        # sits after Django's core routes, so a conflicting page would be hidden.
        if self.slug in RESERVED_FIRST_LEVEL_SLUGS:
            # Only reserve directly under the homepage; nested pages can use
            # those slugs without colliding with first-level app routes.
            parent = self.get_parent() if self.pk and self.depth > 1 else None
            if parent is not None and parent.specific_class.__name__ == "HomePage":
                raise ValidationError({"slug": "This URL is reserved for a dedicated SLQS module."})

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["active_page"] = self.slug
        return context


@register_snippet
class NavigationItem(models.Model):
    """Orderable header/footer links, edited without source-code changes."""

    class Locations(models.TextChoices):
        HEADER = "header", "Header navigation"
        EXPLORE = "explore", "Footer — Explore"
        COMMUNITY = "community", "Footer — Community"

    label = models.CharField(max_length=80)
    location = models.CharField(max_length=12, choices=Locations.choices, default=Locations.HEADER)
    page = models.ForeignKey("wagtailcore.Page", blank=True, null=True, on_delete=models.SET_NULL, related_name="+")
    internal_path = models.CharField(max_length=250, blank=True, help_text="For existing Django routes, e.g. /about/")
    external_url = models.URLField(blank=True)
    sort_order = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(default=True)

    panels = [
        FieldPanel("label"), FieldPanel("location"), FieldPanel("page"),
        FieldPanel("internal_path"), FieldPanel("external_url"),
        FieldPanel("sort_order"), FieldPanel("is_active"),
    ]

    class Meta:
        ordering = ["location", "sort_order", "pk"]
        verbose_name = "Navigation link"
        verbose_name_plural = "Navigation links"

    def clean(self):
        super().clean()
        count = sum(bool(value) for value in (self.page_id, self.internal_path, self.external_url))
        if count != 1:
            raise ValidationError("Choose exactly one destination: Wagtail page, internal path or external URL.")
        if self.internal_path and (not self.internal_path.startswith("/") or self.internal_path.startswith("//") or "\\" in self.internal_path or any(ord(c) < 32 for c in self.internal_path)):
            raise ValidationError({"internal_path": "Use a safe root-relative path, such as /about/."})

    @property
    def url(self):
        if self.page_id:
            # Live pages only are exposed by the context processor.
            return self.page.url or ""
        return self.internal_path or self.external_url

    def __str__(self):
        return f"{self.label} · {self.get_location_display()}"


@register_setting(icon="cog")
class SiteBranding(BaseSiteSetting):
    """Per-site brand and social information in Settings > SLQS Site Branding."""

    footer_description = models.TextField(blank=True, max_length=350)
    contact_email = models.EmailField(blank=True)
    linkedin_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)

    panels = [
        FieldPanel("footer_description"),
        MultiFieldPanel([
            FieldPanel("contact_email"),
            FieldPanel("linkedin_url"), FieldPanel("facebook_url"),
            FieldPanel("instagram_url"),
        ], heading="Contact and social media"),
    ]

    class Meta:
        verbose_name = "SLQS Site Branding"
