# Initial migration for SLQS Phase 1, hand-authored for portable installation.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [('wagtailcore', '__latest__')]
    operations = [
        migrations.CreateModel(
            name='HomePage',
            fields=[
                ('page_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='wagtailcore.page')),
                ('hero_eyebrow', models.CharField(default='THE PROFESSIONAL COMMUNITY', max_length=150)),
                ('hero_title', models.CharField(default='Built on expertise. Connected by purpose.', max_length=200)),
                ('hero_description', models.TextField(default='Bringing Sri Lankan quantity surveying professionals across Saudi Arabia together through knowledge, collaboration and opportunity.')),
                ('welcome_title', models.CharField(default='A connected community of professionals', max_length=180)),
                ('welcome_description', models.TextField(default='SLQS Saudi Arabia is a professional community focused on building connections, sharing expertise and encouraging continuous professional development.')),
            ],
            options={'verbose_name': 'SLQS Home Page'},
            bases=('wagtailcore.page',),
        ),
    ]
