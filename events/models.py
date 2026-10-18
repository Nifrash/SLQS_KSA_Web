"""Phase 4: Wagtail-managed events and independent attendee registrations.

Only live/public pages are exposed on the website. A member portal or online
payment collection is intentionally NOT included in this phase.
"""
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, F
from django.db.models.functions import Lower
from django.core.paginator import Paginator
from django.utils import timezone
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import StreamField
from wagtail.models import Page

from cms_pages.blocks import PageStreamBlock


class EventIndexPage(Page):
    """One /events/ section, owned by the SLQS homepage."""

    parent_page_types = ["home.HomePage"]
    subpage_types = ["events.EventPage"]
    max_count = 1
    template = "events/event_index_page.html"

    eyebrow = models.CharField(max_length=120, default="MEET · LEARN · CONNECT")
    intro = models.CharField(
        max_length=340,
        default="SLQS gatherings, seminars and professional activities across Saudi Arabia.",
    )

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [FieldPanel("eyebrow"), FieldPanel("intro")],
            heading="Events landing page",
        )
    ]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        now = timezone.now()
        events = EventPage.objects.live().public().child_of(self).select_related("cover_image")
        query = (request.GET.get("q") or "").strip()[:100]
        kind = (request.GET.get("type") or "").strip()[:20]
        period = (request.GET.get("when") or "upcoming").strip()
        if period not in {"upcoming", "past"}:
            period = "upcoming"

        if query:
            events = events.filter(
                Q(title__icontains=query) | Q(summary__icontains=query)
                | Q(venue_name__icontains=query)
            )
        if kind in EventPage.Kind.values:
            events = events.filter(kind=kind)
        else:
            kind = ""
        if period == "past":
            events = events.filter(end_at__lt=now).order_by("-start_at", "-pk")
        else:
            events = events.filter(end_at__gte=now).order_by("start_at", "pk")

        context.update({
            "events_page": Paginator(events, 9).get_page(request.GET.get("page")),
            "search_query": query,
            "selected_kind": kind,
            "selected_period": period,
            "event_types": EventPage.Kind.choices,
            "active_page": "events",
        })
        return context

    class Meta:
        verbose_name = "SLQS Events Calendar"


class EventPage(Page):
    """Publishable event. A page is never itself an attendee registration."""

    class Kind(models.TextChoices):
        CPD = "CPD", "CPD / Technical Seminar"
        NETWORKING = "NETWORKING", "Networking"
        AGM = "AGM", "Annual General Meeting"
        COMMUNITY = "COMMUNITY", "Community / Social"
        OTHER = "OTHER", "Other"

    class VenueMode(models.TextChoices):
        IN_PERSON = "IN_PERSON", "In person"
        ONLINE = "ONLINE", "Online"
        HYBRID = "HYBRID", "Hybrid"

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        POSTPONED = "POSTPONED", "Postponed"
        CANCELLED = "CANCELLED", "Cancelled"

    parent_page_types = ["events.EventIndexPage"]
    subpage_types = []
    template = "events/event_page.html"

    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.CPD)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SCHEDULED)
    summary = models.CharField(max_length=440, help_text="Short introduction shown in the event calendar.")
    start_at = models.DateTimeField(help_text="Date and time in your site time zone (Asia/Riyadh).")
    end_at = models.DateTimeField(help_text="Must be after the start date and time.")
    venue_mode = models.CharField(max_length=12, choices=VenueMode.choices, default=VenueMode.IN_PERSON)
    venue_name = models.CharField(max_length=180, blank=True)
    venue_address = models.CharField(max_length=420, blank=True)
    cover_image = models.ForeignKey(
        "wagtailimages.Image", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )
    details = StreamField(
        PageStreamBlock(), blank=True,
        help_text="Agenda, speakers, photos, sponsor logos, downloads and other content blocks.",
    )
    accept_registrations = models.BooleanField(
        default=False, help_text="Enable public registration for this event (free registration only).",
    )
    registration_deadline = models.DateTimeField(
        null=True, blank=True, help_text="Optional. Must be on or before the event start.",
    )
    capacity = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1)],
        help_text="Maximum confirmed participants. Leave blank for no fixed capacity.",
    )
    contact_email = models.EmailField(blank=True, help_text="Public enquiries about this event.")

    content_panels = Page.content_panels + [
        MultiFieldPanel([
            FieldPanel("kind"), FieldPanel("status"), FieldPanel("summary"),
            FieldPanel("cover_image"),
        ], heading="Event overview"),
        MultiFieldPanel([
            FieldPanel("start_at"), FieldPanel("end_at"),
            FieldPanel("venue_mode"), FieldPanel("venue_name"), FieldPanel("venue_address"),
            FieldPanel("contact_email"),
        ], heading="Date, time and location"),
        MultiFieldPanel([FieldPanel("details")], heading="Programme / page builder"),
        MultiFieldPanel([
            FieldPanel("accept_registrations"), FieldPanel("registration_deadline"),
            FieldPanel("capacity"),
        ], heading="Registration settings"),
    ]

    def clean(self):
        super().clean()
        errors = {}
        if self.start_at and self.end_at and self.end_at <= self.start_at:
            errors["end_at"] = "End time must be later than the start time."
        if self.start_at and self.registration_deadline and self.registration_deadline > self.start_at:
            errors["registration_deadline"] = "Registration deadline cannot follow the event start."
        if self.capacity is not None and self.capacity < 1:
            errors["capacity"] = "Capacity must be at least 1 or left blank."
        if errors:
            raise ValidationError(errors)

    @property
    def confirmed_count(self):
        return self.registrations.filter(status=EventRegistration.Status.CONFIRMED).count()

    def registration_availability(self, *, now=None, confirmed_count=None):
        """Return (can_register, human-readable explanation)."""
        now = now or timezone.now()
        if self.status == self.Status.CANCELLED:
            return False, "This event has been cancelled."
        if self.status == self.Status.POSTPONED:
            return False, "Registration is paused while the event is postponed."
        if not self.accept_registrations:
            return False, "Online registration is not available for this event."
        if self.start_at <= now:
            return False, "Registration has closed because the event has started."
        if self.registration_deadline and self.registration_deadline <= now:
            return False, "The registration deadline has passed."
        if self.capacity is not None:
            count = self.confirmed_count if confirmed_count is None else confirmed_count
            if count >= self.capacity:
                return False, "Registration is full. All places have been taken."
        return True, "Registration is open."

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        can_register, reason = self.registration_availability()
        context.update({
            "can_register": can_register,
            "registration_reason": reason,
            "available_seats": max(self.capacity - self.confirmed_count, 0) if self.capacity else None,
            "active_page": "events",
        })
        return context

    class Meta:
        verbose_name = "SLQS Event"


class EventRegistration(models.Model):
    """One registration per email and event; staff can cancel and export records."""

    class Status(models.TextChoices):
        CONFIRMED = "CONFIRMED", "Confirmed"
        CANCELLED = "CANCELLED", "Cancelled by admin"

    event = models.ForeignKey(EventPage, on_delete=models.CASCADE, related_name="registrations")
    full_name = models.CharField(max_length=160)
    email = models.EmailField()
    phone = models.CharField(max_length=32, blank=True)
    organisation = models.CharField(max_length=170, blank=True)
    job_title = models.CharField(max_length=140, blank=True)
    city = models.CharField(max_length=110, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CONFIRMED)
    privacy_consent = models.BooleanField(default=False)
    consent_at = models.DateTimeField(null=True, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-registered_at", "-pk"]
        verbose_name = "Event registration"
        verbose_name_plural = "Event registrations"
        constraints = [
            models.UniqueConstraint(Lower("email"), F("event"), name="events_unique_event_email_ci"),
        ]

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} — {self.event.title}"
