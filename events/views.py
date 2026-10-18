"""Read-only public event pages plus validated registration submissions."""
import logging

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from wagtail.models import Site

from .forms import EventRegistrationForm
from .models import EventIndexPage, EventPage, EventRegistration

logger = logging.getLogger(__name__)


def _live_index(request):
    site = Site.find_for_request(request)
    if site is None:
        return None
    return EventIndexPage.objects.live().public().child_of(site.root_page).first()


def _live_event(request, slug):
    parent = _live_index(request)
    if parent is None:
        raise Http404("The events calendar is not yet available.")
    return get_object_or_404(
        EventPage.objects.live().public().child_of(parent), slug=slug,
    )


def index(request):
    page = _live_index(request)
    if page is None:
        return render(request, "core/events.html", {"active_page": "events"})
    return page.serve(request)


def detail(request, slug):
    return _live_event(request, slug).serve(request)


def _send_registration_emails(registration):
    event = registration.event
    when = timezone.localtime(event.start_at).strftime("%d %B %Y, %I:%M %p %Z")
    venue = event.venue_name or event.get_venue_mode_display()
    sender = settings.DEFAULT_FROM_EMAIL
    try:
        send_mail(
            subject=f"SLQS registration confirmed: {event.title}",
            message=(f"Hello {registration.full_name},\n\n"
                     f"Your registration for '{event.title}' has been confirmed.\n"
                     f"When: {when}\nVenue: {venue}\n\n"
                     "If plans change, please contact SLQS using the website contact page.\n\n"
                     "SLQS Saudi Arabia"),
            from_email=sender,
            recipient_list=[registration.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Confirmation email failed for event registration %s", registration.pk)

    admin_email = (getattr(settings, "EVENTS_ADMIN_EMAIL", "") or
                   getattr(settings, "CONTACT_INBOX_EMAIL", "")).strip()
    if admin_email:
        try:
            send_mail(
                subject=f"New SLQS event registration: {event.title}",
                message=(f"Event: {event.title}\n"
                         f"Attendee: {registration.full_name}\n"
                         f"Email: {registration.email}\n"
                         f"Phone: {registration.phone or '-'}\n"
                         f"Status: Confirmed\n"),
                from_email=sender,
                recipient_list=[admin_email],
                fail_silently=False,
            )
        except Exception:
            logger.exception("Organizer email failed for event registration %s", registration.pk)


@require_http_methods(["GET", "POST"])
def register(request, slug):
    event = _live_event(request, slug)
    form = EventRegistrationForm(request.POST or None)
    allowed, reason = event.registration_availability()
    if request.method == "POST":
        if not allowed:
            form.add_error(None, reason)
        elif form.is_valid():
            email = form.cleaned_data["email"]
            created_registration = None
            # Serializes competing registrations on PostgreSQL by locking the
            # same event row. SQLite is suitable for local development only.
            try:
                with transaction.atomic():
                    locked = EventPage.objects.select_for_update().get(pk=event.pk)
                    count = locked.confirmed_count
                    allowed_locked, reason_locked = locked.registration_availability(
                        confirmed_count=count,
                    )
                    if not allowed_locked:
                        form.add_error(None, reason_locked)
                    elif EventRegistration.objects.filter(event=locked, email__iexact=email).exists():
                        form.add_error("email", "This email is already registered for the event. Contact SLQS if you need help.")
                    else:
                        created_registration = form.save(commit=False)
                        created_registration.event = locked
                        created_registration.privacy_consent = True
                        created_registration.consent_at = timezone.now()
                        created_registration.save()
            except IntegrityError:
                form.add_error("email", "This email is already registered for the event. Contact SLQS if you need help.")
            if created_registration is not None and not form.errors:
                _send_registration_emails(created_registration)
                messages.success(request, "Registration confirmed. Please check your email for event details (email delivery depends on configuration).")
                return redirect(reverse("events:detail", kwargs={"slug": event.slug}))

    return render(request, "events/event_registration.html", {
        "page": event,
        "form": form,
        "can_register": allowed,
        "registration_reason": reason,
        "active_page": "events",
    }, status=200)
