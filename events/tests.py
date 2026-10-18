"""Phase 4 acceptance tests; run: python manage.py test events.

Uses the existing Phase 1 site setup rather than a replacement database.
"""
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.db import IntegrityError, transaction

from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from wagtail.models import Site

from home.models import HomePage
from .models import EventIndexPage, EventPage, EventRegistration


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   EVENTS_ADMIN_EMAIL="organizer@slqs.test")
class EventPublicTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_slqs_phase1", stdout=StringIO())
        call_command("seed_slqs_phase4", stdout=StringIO())
        cls.calendar = EventIndexPage.objects.get()

    def make_event(self, title="Professional CPD Seminar", slug="professional-cpd-seminar",
                   *, published=True, days_from_now=14, capacity=10,
                   accept_registrations=True, status="SCHEDULED", kind="CPD"):
        start = timezone.now() + timedelta(days=days_from_now)
        page = self.calendar.add_child(instance=EventPage(
            title=title, slug=slug, live=False,
            summary="Join SLQS members for a practical technical discussion.",
            start_at=start, end_at=start + timedelta(hours=3),
            venue_name="Riyadh, Saudi Arabia", kind=kind,
            accept_registrations=accept_registrations,
            status=status, capacity=capacity,
        ))
        if published:
            page.save_revision().publish()
        else:
            page.save_revision()
        return page

    def registration_data(self, email="person@example.com", **values):
        data = {
            "full_name": "Quantity Surveyor",
            "email": email,
            "phone": "+966 555 123 000",
            "organisation": "Construction Company",
            "job_title": "QS",
            "city": "Riyadh",
            "consent": "on",
        }
        data.update(values)
        return data

    def test_phase4_calendar_and_existing_navigation(self):
        self.assertEqual(self.client.get(reverse("core:events")).status_code, 200)
        self.assertEqual(self.client.get(reverse("events:index")).status_code, 200)
        self.assertContains(self.client.get("/events/"), "Upcoming events will appear here")
        self.assertEqual(self.client.get(reverse("core:contact")).status_code, 200)
        self.assertEqual(self.client.get("/news/").status_code, 200)

    def test_published_event_visible_on_calendar_home_and_detail(self):
        event = self.make_event()
        self.assertContains(self.client.get("/events/"), event.title)
        self.assertContains(self.client.get("/"), event.title)
        self.assertContains(self.client.get(f"/events/{event.slug}/"), event.summary)

    def test_draft_event_cannot_be_viewed_or_registered(self):
        event = self.make_event("Unpublished seminar", "unpublished-seminar", published=False)
        self.assertNotContains(self.client.get("/events/"), event.title)
        self.assertNotContains(self.client.get("/"), event.title)
        self.assertEqual(self.client.get(f"/events/{event.slug}/").status_code, 404)
        self.assertEqual(self.client.post(f"/events/{event.slug}/register/", self.registration_data()).status_code, 404)

    def test_successful_registration_and_confirmation_emails(self):
        event = self.make_event()
        response = self.client.post(reverse("events:register", args=[event.slug]), self.registration_data())
        self.assertRedirects(response, reverse("events:detail", args=[event.slug]))
        item = EventRegistration.objects.get(event=event)
        self.assertTrue(item.privacy_consent)
        self.assertIsNotNone(item.consent_at)
        self.assertEqual(item.status, "CONFIRMED")
        self.assertEqual(item.email, "person@example.com")
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ["person@example.com"])
        self.assertEqual(mail.outbox[1].to, ["organizer@slqs.test"])

    def test_duplicate_email_is_rejected_case_insensitively(self):
        event = self.make_event()
        self.client.post(reverse("events:register", args=[event.slug]), self.registration_data())
        response = self.client.post(reverse("events:register", args=[event.slug]),
                                    self.registration_data("PERSON@EXAMPLE.com"))
        self.assertContains(response, "already registered")
        self.assertEqual(EventRegistration.objects.filter(event=event).count(), 1)

    def test_consent_is_required(self):
        event = self.make_event()
        response = self.client.post(reverse("events:register", args=[event.slug]),
                                    self.registration_data(consent=""))
        self.assertContains(response, "I agree")
        self.assertEqual(EventRegistration.objects.count(), 0)

    def test_capacity_and_cancelled_registrations(self):
        event = self.make_event(capacity=1)
        self.client.post(reverse("events:register", args=[event.slug]), self.registration_data())
        response = self.client.post(reverse("events:register", args=[event.slug]),
                                    self.registration_data("second@example.com"))
        self.assertContains(response, "Registration is full")
        self.assertEqual(EventRegistration.objects.filter(status="CONFIRMED").count(), 1)
        EventRegistration.objects.filter(event=event).update(status="CANCELLED")
        self.client.post(reverse("events:register", args=[event.slug]),
                         self.registration_data("second@example.com"))
        self.assertEqual(EventRegistration.objects.filter(event=event, status="CONFIRMED").count(), 1)

    def test_closed_postponed_cancelled_and_past_events(self):
        for status in ("CANCELLED", "POSTPONED"):
            event = self.make_event(status.lower(), f"sample-{status.lower()}", status=status)
            response = self.client.post(reverse("events:register", args=[event.slug]), self.registration_data())
            self.assertContains(response, "Registration unavailable")
        past = self.make_event("Past seminar", "past-seminar", days_from_now=-5)
        response = self.client.post(reverse("events:register", args=[past.slug]), self.registration_data())
        self.assertContains(response, "Registration unavailable")
        self.assertEqual(EventRegistration.objects.count(), 0)

    def test_expired_deadline_and_disabled_registration(self):
        closed = self.make_event("Closed", "closed", accept_registrations=False)
        self.assertNotContains(self.client.get(f"/events/{closed.slug}/"), "Register for this event")
        event = self.make_event("Past deadline", "past-deadline")
        event.registration_deadline = timezone.now() - timedelta(hours=1)
        event.save(update_fields=["registration_deadline"])
        self.assertContains(self.client.get(f"/events/{event.slug}/"), "deadline has passed")

    def test_search_kind_archive_and_calendar_pagination(self):
        self.make_event("Professional networking", "professional-networking", kind="NETWORKING")
        self.make_event("Measurement CPD", "measurement-cpd")
        self.make_event("Former AGM", "former-agm", days_from_now=-3, kind="AGM")
        response = self.client.get("/events/?q=Measurement")
        self.assertContains(response, "Measurement CPD")
        self.assertNotContains(response, "Professional networking")
        response = self.client.get("/events/?type=NETWORKING")
        self.assertContains(response, "Professional networking")
        self.assertNotContains(response, "Measurement CPD")
        response = self.client.get("/events/?when=past")
        self.assertContains(response, "Former AGM")
        self.assertNotContains(response, "Measurement CPD")
        for i in range(11):
            self.make_event(f"Event number {i}", f"event-number-{i}")
        self.assertContains(self.client.get("/events/"), "Page 1 of 2")
        self.assertContains(self.client.get("/events/?page=2"), "Page 2 of 2")

    def test_seed_can_run_twice_without_deleting_events(self):
        self.make_event()
        before = (EventIndexPage.objects.count(), EventPage.objects.count())
        call_command("seed_slqs_phase4", stdout=StringIO())
        self.assertEqual((EventIndexPage.objects.count(), EventPage.objects.count()), before)
        self.assertIsInstance(Site.objects.get(is_default_site=True).root_page.specific, HomePage)

    def test_email_delivery_failure_does_not_lose_registration(self):
        event = self.make_event()
        with patch("events.views.send_mail", side_effect=OSError("mail system unavailable")):
            response = self.client.post(
                reverse("events:register", args=[event.slug]), self.registration_data()
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(EventRegistration.objects.filter(event=event).count(), 1)

    def test_case_insensitive_unique_constraint_in_database(self):
        event = self.make_event()
        EventRegistration.objects.create(event=event, full_name="Person 1", email="same@example.com")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EventRegistration.objects.create(event=event, full_name="Person 2", email="SAME@example.com")
        self.assertEqual(EventRegistration.objects.filter(event=event).count(), 1)

    def test_invalid_event_dates_have_validation_errors(self):
        event = self.make_event()
        event.end_at = event.start_at - timedelta(hours=1)
        with self.assertRaises(ValidationError):
            event.clean()
