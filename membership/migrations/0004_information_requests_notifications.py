from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import membership.models


def backfill_open_requests(apps, schema_editor):
    Application = apps.get_model("membership", "MembershipApplication")
    ReviewLog = apps.get_model("membership", "MembershipReviewLog")
    InfoRequest = apps.get_model("membership", "MembershipInformationRequest")
    Notification = apps.get_model("membership", "MemberPortalNotification")
    for application in Application.objects.filter(status="more_info").iterator():
        log = ReviewLog.objects.filter(application_id=application.pk, to_status="more_info").order_by("-created_at", "-pk").first()
        message = log.note if log and log.note else "Please provide the supporting information requested by the membership team."
        info = InfoRequest.objects.create(
            application_id=application.pk, message=message, requested_by_id=(log.actor_id if log else None),
            requested_at=(log.created_at if log else django.utils.timezone.now()),
        )
        if application.user_id:
            Notification.objects.create(
                user_id=application.user_id, application_id=application.pk,
                information_request_id=info.pk, kind="info_request",
                title="Action required: membership documents",
                message=message,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("membership", "0003_application_account"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="MembershipInformationRequest",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False, auto_created=True, verbose_name="ID")),
                ("message", models.TextField(max_length=3000)),
                ("requested_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                ("application", models.ForeignKey(to="membership.membershipapplication", related_name="information_requests", on_delete=django.db.models.deletion.PROTECT)),
                ("requested_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, blank=True, null=True, related_name="slqs_information_requests_sent", on_delete=django.db.models.deletion.SET_NULL)),
            ],
            options={"ordering": ("-requested_at", "-pk")},
        ),
        migrations.CreateModel(
            name="MembershipInformationResponse",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False, auto_created=True, verbose_name="ID")),
                ("message", models.TextField(max_length=3000)),
                ("document", models.FileField(max_length=255, storage=membership.models.PrivateMembershipDocumentStorage(), upload_to=membership.models.evidence_filename)),
                ("submitted_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("request", models.OneToOneField(to="membership.membershipinformationrequest", related_name="response", on_delete=django.db.models.deletion.PROTECT)),
                ("user", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT)),
            ],
            options={"ordering": ("-submitted_at", "-pk")},
        ),
        migrations.CreateModel(
            name="MemberPortalNotification",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False, auto_created=True, verbose_name="ID")),
                ("kind", models.CharField(max_length=20, choices=[("info_request", "Information required"), ("submitted", "Application received"), ("approved", "Membership approved"), ("rejected", "Application rejected"), ("update", "Application updated")])),
                ("title", models.CharField(max_length=140)),
                ("message", models.TextField(max_length=3000)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("read_at", models.DateTimeField(null=True, blank=True)),
                ("application", models.ForeignKey(to="membership.membershipapplication", related_name="portal_notifications", on_delete=django.db.models.deletion.PROTECT)),
                ("information_request", models.ForeignKey(to="membership.membershipinformationrequest", related_name="portal_notifications", blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL)),
                ("user", models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name="slqs_portal_notifications", on_delete=django.db.models.deletion.CASCADE)),
            ],
            options={"ordering": ("-created_at", "-pk"), "indexes": [models.Index(fields=["user", "read_at", "created_at"], name="slqs_notif_inbox_idx")]},
        ),
        migrations.RunPython(backfill_open_requests, migrations.RunPython.noop),
    ]
