# Phase 9. Independent tables: no existing membership schema is altered.
import uuid
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("membership", "0003_application_account"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DigitalMembershipCard",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)),
                ("issued_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("reissue_count", models.PositiveIntegerField(default=0, editable=False)),
                ("revoked_at", models.DateTimeField(blank=True, null=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("member", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="digital_card", to="membership.memberprofile")),
                ("revoked_by", models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="slqs_cards_revoked", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Digital membership card", "verbose_name_plural": "Digital membership cards"},
        ),
        migrations.CreateModel(
            name="CardAuditEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[("issued", "Issued"), ("revoked", "Revoked"), ("reissued", "Reissued with new QR")], max_length=10)),
                ("note", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="slqs_card_actions", to=settings.AUTH_USER_MODEL)),
                ("card", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="audit_events", to="digital_cards.digitalmembershipcard")),
            ],
            options={"ordering": ("-created_at", "-pk"), "verbose_name": "Digital card audit event"},
        ),
    ]
