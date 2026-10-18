"""Create Wagtail newsroom root, articles, and categories (no existing data deleted)."""
import django.db.models.deletion
from django.db import migrations, models
import django.utils.timezone
import wagtail.fields
import cms_pages.blocks


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('home', '0002_homepage_sections'),
        ('wagtailcore', '__latest__'),
        ('wagtailimages', '__latest__'),
    ]

    operations = [
        migrations.CreateModel(
            name='NewsCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=90, unique=True)),
                ('slug', models.SlugField(max_length=90, unique=True)),
                ('description', models.CharField(blank=True, max_length=240)),
                ('sort_order', models.PositiveSmallIntegerField(default=100)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={'ordering': ['sort_order', 'name'], 'verbose_name_plural': 'News categories'},
        ),
        migrations.CreateModel(
            name='NewsIndexPage',
            fields=[
                ('page_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='wagtailcore.page')),
                ('eyebrow', models.CharField(default='THE SLQS NEWSROOM', max_length=110)),
                ('intro', models.CharField(default='Association announcements, professional insight and stories from our community.', max_length=320)),
            ],
            options={'verbose_name': 'SLQS Newsroom'},
            bases=('wagtailcore.page',),
        ),
        migrations.CreateModel(
            name='NewsArticlePage',
            fields=[
                ('page_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='wagtailcore.page')),
                ('kind', models.CharField(choices=[('NEWS', 'News'), ('ANNOUNCEMENT', 'Announcement'), ('INSIGHT', 'Professional insight')], default='NEWS', max_length=16)),
                ('publish_date', models.DateField(default=django.utils.timezone.localdate)),
                ('excerpt', models.CharField(help_text='A short summary for cards, search results and social sharing.', max_length=420)),
                ('byline', models.CharField(blank=True, help_text='Optional public author name.', max_length=120)),
                ('is_featured', models.BooleanField(default=False, help_text='Highlight this article on the news landing page.')),
                ('body', wagtail.fields.StreamField(cms_pages.blocks.PageStreamBlock(), blank=True, help_text='Build the article using text, images, quotes, documents and other content blocks.')),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='articles', to='newsroom.newscategory')),
                ('featured_image', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='wagtailimages.image')),
            ],
            options={'verbose_name': 'SLQS news / announcement article', 'verbose_name_plural': 'SLQS news / announcement articles', 'ordering': ['-publish_date']},
            bases=('wagtailcore.page',),
        ),
    ]
