# Phase 8 independent committee workflow (no alterations to Phase 5/6 tables).
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('membership', '0003_application_account'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CommitteeCase',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('priority', models.CharField(choices=[('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent')], default='normal', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('application', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='committee_case', to='membership.membershipapplication')),
                ('assigned_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='slqs_assigned_cases', to=settings.AUTH_USER_MODEL)),
                ('assigned_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='slqs_cases_assigned_by', to=settings.AUTH_USER_MODEL)),
                ('assigned_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'ordering': ('-application__created_at', '-pk'),
                'permissions': (
                    ('assign_committeecase', 'Assign committee applications'),
                    ('recommend_committeecase', 'Recommend application decisions'),
                    ('decide_committeecase', 'Approve or reject membership applications'),
                    ('request_info_committeecase', 'Request applicant information'),
                    ('export_committeecase', 'Export committee application data'),
                ),
            },
        ),
        migrations.CreateModel(
            name='CommitteeRecommendation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('outcome', models.CharField(choices=[('approve', 'Recommend approval'), ('reject', 'Recommend rejection'), ('more_info', 'Recommend additional information')], max_length=12)),
                ('note', models.TextField(max_length=3000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('case', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='recommendations', to='membership_team.committeecase')),
                ('reviewer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='slqs_committee_recommendations', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ('-created_at', '-pk')},
        ),
        migrations.CreateModel(
            name='CommitteeActionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('assigned', 'Assigned / reassigned'), ('priority', 'Priority updated'), ('recommended', 'Recommendation added'), ('more_info', 'Additional information requested'), ('decided', 'Final decision recorded')], max_length=16)),
                ('note', models.TextField(blank=True, max_length=3000)),
                ('before', models.CharField(blank=True, max_length=120)),
                ('after', models.CharField(blank=True, max_length=120)),
                ('created_at', models.DateTimeField(default=timezone.now, editable=False)),
                ('case', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='committee_history', to='membership_team.committeecase')),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='slqs_committee_actions', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ('-created_at', '-pk')},
        ),
    ]
