"""Phase 4 schema: published event pages and private registration records."""
import django.db.models.deletion
from django.db import migrations, models
from django.db.models.functions import Lower
from django.db.models import F
from django.core.validators import MinValueValidator
import cms_pages.blocks
import wagtail.fields


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("home", "0002_homepage_sections"),
        ("wagtailcore", "__latest__"),
        ("wagtailimages", "__latest__"),
    ]

    operations = [
        migrations.CreateModel(
            name="EventIndexPage",
            fields=[
                ("page_ptr", models.OneToOneField(
                    auto_created=True, on_delete=django.db.models.deletion.CASCADE,
                    parent_link=True, primary_key=True, serialize=False, to="wagtailcore.page")),
                ("eyebrow", models.CharField(default="MEET · LEARN · CONNECT", max_length=120)),
                ("intro", models.CharField(default="SLQS gatherings, seminars and professional activities across Saudi Arabia.", max_length=340)),
            ],
            options={"verbose_name": "SLQS Events Calendar"},
            bases=("wagtailcore.page",),
        ),
        migrations.CreateModel(
            name="EventPage",
            fields=[
                ("page_ptr", models.OneToOneField(
                    auto_created=True, on_delete=django.db.models.deletion.CASCADE,
                    parent_link=True, primary_key=True, serialize=False, to="wagtailcore.page")),
                ("kind", models.CharField(default="CPD", max_length=20, choices=[
                    ("CPD", "CPD / Technical Seminar"), ("NETWORKING", "Networking"),
                    ("AGM", "Annual General Meeting"), ("COMMUNITY", "Community / Social"), ("OTHER", "Other"),
                ])),
                ("status", models.CharField(default="SCHEDULED", max_length=12, choices=[
                    ("SCHEDULED", "Scheduled"), ("POSTPONED", "Postponed"), ("CANCELLED", "Cancelled"),
                ])),
                ("summary", models.CharField(max_length=440, help_text="Short introduction shown in the event calendar.")),
                ("start_at", models.DateTimeField(help_text="Date and time in your site time zone (Asia/Riyadh).")),
                ("end_at", models.DateTimeField(help_text="Must be after the start date and time.")),
                ("venue_mode", models.CharField(default="IN_PERSON", max_length=12, choices=[
                    ("IN_PERSON", "In person"), ("ONLINE", "Online"), ("HYBRID", "Hybrid"),
                ])),
                ("venue_name", models.CharField(blank=True, max_length=180)),
                ("venue_address", models.CharField(blank=True, max_length=420)),
                ("details", wagtail.fields.StreamField(
                    cms_pages.blocks.PageStreamBlock(), blank=True,
                    help_text="Agenda, speakers, photos, sponsor logos, downloads and other content blocks.")),
                ("accept_registrations", models.BooleanField(
                    default=False, help_text="Enable public registration for this event (free registration only).")),
                ("registration_deadline", models.DateTimeField(
                    blank=True, null=True, help_text="Optional. Must be on or before the event start.")),
                ("capacity", models.PositiveIntegerField(
                    blank=True, null=True, validators=[MinValueValidator(1)],
                    help_text="Maximum confirmed participants. Leave blank for no fixed capacity.")),
                ("contact_email", models.EmailField(blank=True, max_length=254, help_text="Public enquiries about this event.")),
                ("cover_image", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+", to="wagtailimages.image")),
            ],
            options={"verbose_name": "SLQS Event"},
            bases=("wagtailcore.page",),
        ),
        migrations.CreateModel(
            name="EventRegistration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=160)),
                ("email", models.EmailField(max_length=254)),
                ("phone", models.CharField(blank=True, max_length=32)),
                ("organisation", models.CharField(blank=True, max_length=170)),
                ("job_title", models.CharField(blank=True, max_length=140)),
                ("city", models.CharField(blank=True, max_length=110)),
                ("status", models.CharField(default="CONFIRMED", max_length=12, choices=[
                    ("CONFIRMED", "Confirmed"), ("CANCELLED", "Cancelled by admin"),
                ])),
                ("privacy_consent", models.BooleanField(default=False)),
                ("consent_at", models.DateTimeField(blank=True, null=True)),
                ("registered_at", models.DateTimeField(auto_now_add=True)),
                ("event", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="registrations", to="events.eventpage")),
            ],
            options={
                "ordering": ["-registered_at", "-pk"],
                "verbose_name": "Event registration",
                "verbose_name_plural": "Event registrations",
                "constraints": [models.UniqueConstraint(
                    Lower("email"), F("event"), name="events_unique_event_email_ci")],
            },
        ),
    ]
