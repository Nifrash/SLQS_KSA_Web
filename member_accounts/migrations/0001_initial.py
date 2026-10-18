from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="MemberAccountProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=180)),
                ("ksa_phone", models.CharField(blank=True, max_length=20)),
                ("whatsapp_phone", models.CharField(blank=True, max_length=20)),
                ("company_name", models.CharField(blank=True, max_length=180)),
                ("job_title", models.CharField(blank=True, max_length=150)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("otp_hash", models.CharField(blank=True, max_length=128)),
                ("otp_expires_at", models.DateTimeField(blank=True, null=True)),
                ("otp_last_sent_at", models.DateTimeField(blank=True, null=True)),
                ("otp_attempts", models.PositiveSmallIntegerField(default=0)),
                ("otp_window_started_at", models.DateTimeField(blank=True, null=True)),
                ("otp_sent_in_window", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="slqs_account", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "SLQS website account", "verbose_name_plural": "SLQS website accounts"},
        ),
    ]
