# SLQS Phase 6: private member records, renewal ledger and activity trail.
# Does not alter or delete the existing Phase 5 applications.
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("membership", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MemberProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("membership_number", models.CharField(blank=True, editable=False, help_text="System-issued, permanent SLQS membership identifier.", max_length=32, null=True, unique=True)),
                ("status", models.CharField(choices=[("active", "Active"), ("suspended", "Suspended"), ("inactive", "Inactive"), ("expired", "Expired")], db_index=True, default="active", max_length=12)),
                ("joined_on", models.DateField(default=django.utils.timezone.localdate)),
                ("renewal_due_on", models.DateField(blank=True, db_index=True, null=True)),
                ("internal_notes", models.TextField(blank=True, max_length=3000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("application", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="member_profile", to="membership.membershipapplication")),
            ],
            options={"ordering": ("-created_at", "-pk"), "verbose_name": "SLQS member", "verbose_name_plural": "SLQS members"},
        ),
        migrations.CreateModel(
            name="MemberActivity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[("created", "Member created"), ("status", "Status changed"), ("due_date", "Due date changed"), ("renewed", "Membership renewed"), ("notes", "Administrative notes updated"), ("joined_on", "Joining date corrected")], max_length=16)),
                ("old_status", models.CharField(blank=True, max_length=12)),
                ("new_status", models.CharField(blank=True, max_length=12)),
                ("old_due_on", models.DateField(blank=True, null=True)),
                ("new_due_on", models.DateField(blank=True, null=True)),
                ("note", models.TextField(blank=True, max_length=1500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="slqs_member_activity", to=settings.AUTH_USER_MODEL)),
                ("member", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="activity_history", to="membership.memberprofile")),
            ],
            options={"ordering": ("-created_at", "-pk"), "verbose_name": "Member activity", "verbose_name_plural": "Member activity history"},
        ),
        migrations.CreateModel(
            name="MemberRenewal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("old_due_on", models.DateField(blank=True, null=True)),
                ("new_due_on", models.DateField()),
                ("note", models.CharField(blank=True, max_length=500)),
                ("processed_at", models.DateTimeField(auto_now_add=True)),
                ("member", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="renewals", to="membership.memberprofile")),
                ("processed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="slqs_member_renewals", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-processed_at", "-pk"), "verbose_name": "Member renewal", "verbose_name_plural": "Member renewals"},
        ),
    ]
