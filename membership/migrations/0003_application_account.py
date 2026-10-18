from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("membership", "0002_member_management"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField(
            model_name="membershipapplication",
            name="user",
            field=models.OneToOneField(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="slqs_membership_application", to=settings.AUTH_USER_MODEL,
                help_text="Verified applicant website account. Pre-Phase 7 applications can remain unlinked.",
            ),
        ),
    ]
