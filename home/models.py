"""Editable professional SLQS homepage; preserves Phase 1-4 fields and feeds."""
from django.core.validators import RegexValidator
from django.db import models
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import StreamField
from wagtail.models import Page

from .blocks import HomeStreamBlock
from .defaults import starter_home_sections


safe_internal_path = RegexValidator(
    regex=r"^/(?!/)",
    message="Use a site-relative URL starting with a single / (for example, /membership/).",
)


class HomePage(Page):
    max_count = 1
    parent_page_types = ["wagtailcore.Page"]
    subpage_types = ["cms_pages.ContentPage", "newsroom.NewsIndexPage", "events.EventIndexPage"]

    hero_eyebrow = models.CharField(max_length=150, default="THE PROFESSIONAL COMMUNITY")
    hero_title = models.CharField(max_length=200, default="Built on expertise. Connected by purpose.")
    hero_description = models.TextField(default=(
        "Bringing Sri Lankan quantity surveying professionals across Saudi Arabia "
        "together through knowledge, collaboration and opportunity."
    ))
    hero_image = models.ForeignKey(
        "wagtailimages.Image", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", help_text="Choose a hero photograph from the Wagtail image library."
    )
    hero_image_alt = models.CharField(
        max_length=200, blank=True,
        help_text="Describe the image for accessibility. Leave blank for a purely decorative image."
    )
    hero_button_label = models.CharField(max_length=65, default="Explore membership")
    hero_button_path = models.CharField(
        max_length=255, default="/membership/", validators=[safe_internal_path],
        help_text="Internal link path beginning with / (for example /membership/)."
    )
    hero_secondary_label = models.CharField(max_length=65, default="Discover SLQS")
    hero_secondary_path = models.CharField(
        max_length=255, default="/about/", validators=[safe_internal_path],
        help_text="Internal link path beginning with / (for example /about/)."
    )

    # Retained for schema/data compatibility with Phase 1 and Phase 2.
    welcome_title = models.CharField(max_length=180, default="A connected community of professionals")
    welcome_description = models.TextField(default=(
        "SLQS Saudi Arabia is a professional community focused on building connections, "
        "sharing expertise and encouraging continuous professional development."
    ))
    show_standard_sections = models.BooleanField(
        default=True,
        verbose_name="Show starter homepage sections when editor blocks are empty",
        help_text="Show the new SLQS starter design until sections are saved. Turn off to intentionally display no sections."
    )
    sections = StreamField(
        HomeStreamBlock(), blank=True,
        help_text=(
            "Add, remove and drag sections into the required order. Hero image and hero text "
            "are edited separately above. Live news/events update automatically."
        ),
    )

    content_panels = Page.content_panels + [
        MultiFieldPanel([
            FieldPanel("hero_eyebrow"), FieldPanel("hero_title"),
            FieldPanel("hero_description"), FieldPanel("hero_image"),
            FieldPanel("hero_image_alt"), FieldPanel("hero_button_label"),
            FieldPanel("hero_button_path"), FieldPanel("hero_secondary_label"),
            FieldPanel("hero_secondary_path"),
        ], heading="Hero banner — editable image, words and buttons"),
        MultiFieldPanel([
            FieldPanel("sections"), FieldPanel("show_standard_sections"),
        ], heading="Homepage sections — add, drag and publish"),
    ]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        if self.sections:
            context["home_sections"] = self.sections
        elif self.show_standard_sections:
            # Render starter design even before the owner runs the seed command.
            # The seed command later persists these blocks for editing in Wagtail.
            context["home_sections"] = HomeStreamBlock().to_python(starter_home_sections())
        else:
            context["home_sections"] = []

        # Preserve Phase 3/4 dynamic feeds. They are never populated with fake data.
        from newsroom.models import NewsArticlePage, NewsIndexPage
        index_page = NewsIndexPage.objects.live().public().child_of(self).first()
        if index_page is not None:
            context["latest_news"] = (
                NewsArticlePage.objects.live().public().child_of(index_page)
                .select_related("featured_image", "category")
                .order_by("-publish_date", "-pk")[:3]
            )
        from events.models import EventIndexPage, EventPage
        calendar = EventIndexPage.objects.live().public().child_of(self).first()
        if calendar is not None:
            from django.utils import timezone
            context["upcoming_events"] = (
                EventPage.objects.live().public().child_of(calendar)
                .filter(end_at__gte=timezone.now(), status=EventPage.Status.SCHEDULED)
                .order_by("start_at", "pk")[:3]
            )
        return context

    class Meta:
        verbose_name = "SLQS Home Page"
