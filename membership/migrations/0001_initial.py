# SLQS Phase 5 — membership applications and audit trail.
import uuid
from django.conf import settings
from django.db import migrations, models
from django.db.models.functions import Lower
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="MembershipApplication",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("full_name", models.CharField(max_length=180)),
                ("date_of_birth", models.DateField()),
                ("preferred_email", models.EmailField(max_length=254)),
                ("ksa_phone", models.CharField(max_length=20)),
                ("whatsapp_phone", models.CharField(max_length=20)),
                ("whatsapp_group_member", models.CharField(choices=[("yes", "Yes"), ("no", "No")], max_length=3)),
                ("company_name", models.CharField(max_length=180)),
                ("job_title", models.CharField(max_length=150)),
                ("highest_educational_qualification", models.CharField(max_length=250)),
                ("professional_qualifications", models.JSONField(default=list)),
                ("professional_qualifications_other", models.CharField(blank=True, max_length=250)),
                ("overall_post_qualification_experience", models.DecimalField(decimal_places=2, max_digits=5)),
                ("ksa_experience", models.DecimalField(decimal_places=2, max_digits=5)),
                ("working_region", models.CharField(choices=[
                    ("riyadh", "Riyadh Region"), ("makkah", "Makkah Region"),
                    ("madinah", "Madinah Region"), ("eastern", "Eastern Province"),
                    ("qassim", "Al Qassim Region"), ("asir", "Asir Region"),
                    ("tabuk", "Tabuk Region"), ("hail", "Hail Region"),
                    ("northern_borders", "Northern Borders Region"), ("jazan", "Jazan Region"),
                    ("najran", "Najran Region"), ("al_baha", "Al Baha Region"),
                    ("al_jawf", "Al Jawf Region"), ("other", "Other / Not listed"),
                ], max_length=30)),
                ("suggestions", models.TextField(blank=True, max_length=3000)),
                ("privacy_consent_at", models.DateTimeField()),
                ("status", models.CharField(choices=[
                    ("submitted", "Submitted"), ("in_review", "Under review"),
                    ("more_info", "Additional information requested"),
                    ("approved", "Approved"), ("rejected", "Rejected"),
                ], db_index=True, default="submitted", max_length=12)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="slqs_membership_reviews", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",), "verbose_name": "Membership application", "verbose_name_plural": "Membership applications"},
        ),
        migrations.CreateModel(
            name="MembershipReviewLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("from_status", models.CharField(blank=True, max_length=12)),
                ("to_status", models.CharField(choices=[
                    ("submitted", "Submitted"), ("in_review", "Under review"),
                    ("more_info", "Additional information requested"),
                    ("approved", "Approved"), ("rejected", "Rejected"),
                ], max_length=12)),
                ("note", models.TextField(blank=True, max_length=3000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="slqs_membership_review_actions", to=settings.AUTH_USER_MODEL)),
                ("application", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="review_history", to="membership.membershipapplication")),
            ],
            options={"ordering": ("-created_at", "-pk"), "verbose_name": "Membership review history", "verbose_name_plural": "Membership review history"},
        ),
        migrations.AddConstraint(
            model_name="membershipapplication",
            constraint=models.UniqueConstraint(Lower("preferred_email"), name="membership_unique_email_ci"),
        ),
    ]
