import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('membership', '0006_historical_consent_nullable'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(name='LegacyImportBatch', fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False)),
            ('filename', models.CharField(max_length=240)),
            ('sha256', models.CharField(max_length=64, db_index=True)),
            ('row_count', models.PositiveIntegerField(default=0)),
            ('created_count', models.PositiveIntegerField(default=0)),
            ('skipped_count', models.PositiveIntegerField(default=0)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('uploaded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
        ], options={'ordering': ('-created_at',)}),
        migrations.CreateModel(name='LegacyMemberRecord', fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False)),
            ('source_key', models.CharField(max_length=128, unique=True)),
            ('imported_email', models.EmailField(max_length=254)),
            ('imported_status', models.CharField(max_length=12)),
            ('activated_at', models.DateTimeField(null=True, blank=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('application', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='legacy_record', to='membership.membershipapplication')),
            ('batch', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='records', to='legacy_members.legacyimportbatch')),
        ], options={'ordering': ('-created_at',)}),
        migrations.CreateModel(name='LegacyActivationChallenge', fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False)),
            ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
            ('otp_hash', models.CharField(max_length=128)),
            ('expires_at', models.DateTimeField()),
            ('attempted', models.PositiveSmallIntegerField(default=0)),
            ('identity_attempts', models.PositiveSmallIntegerField(default=0)),
            ('verified_at', models.DateTimeField(null=True, blank=True)),
            ('completed_at', models.DateTimeField(null=True, blank=True)),
            ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
            ('record', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='challenges', to='legacy_members.legacymemberrecord')),
        ], options={'ordering': ('-created_at',)}),
    ]
