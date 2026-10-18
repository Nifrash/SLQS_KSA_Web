"""Initial CMS-managed pages, navigation and site-level brand settings."""
import django.db.models.deletion
from django.db import migrations, models
import wagtail.fields
import cms_pages.blocks


class Migration(migrations.Migration):
    initial = True
    dependencies = [("wagtailcore", "__latest__")]

    operations = [
        migrations.CreateModel(
            name="ContentPage",
            fields=[
                ("page_ptr", models.OneToOneField(
                    auto_created=True, on_delete=django.db.models.deletion.CASCADE,
                    parent_link=True, primary_key=True, serialize=False,
                    to="wagtailcore.page")),
                ("intro", models.TextField(blank=True, max_length=850,
                    help_text="Optional introduction shown under the page title")),
                ("eyebrow", models.CharField(blank=True, max_length=100,
                    help_text="Optional small label above the page title")),
                ("body", wagtail.fields.StreamField(
                    cms_pages.blocks.PageStreamBlock(), blank=True,
                    help_text="Add, reorder and remove page sections")),
            ],
            options={"verbose_name": "SLQS content page", "verbose_name_plural": "SLQS content pages"},
            bases=("wagtailcore.page",),
        ),
        migrations.CreateModel(
            name="NavigationItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.CharField(max_length=80)),
                ("location", models.CharField(max_length=12, default="header", choices=[
                    ("header", "Header navigation"), ("explore", "Footer — Explore"),
                    ("community", "Footer — Community")])),
                ("internal_path", models.CharField(blank=True, max_length=250,
                    help_text="For existing Django routes, e.g. /about/")),
                ("external_url", models.URLField(blank=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=100)),
                ("is_active", models.BooleanField(default=True)),
                ("page", models.ForeignKey(blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="wagtailcore.page")),
            ],
            options={"ordering": ["location", "sort_order", "pk"],
                     "verbose_name": "Navigation link", "verbose_name_plural": "Navigation links"},
        ),
        migrations.CreateModel(
            name="SiteBranding",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("footer_description", models.TextField(blank=True, max_length=350)),
                ("contact_email", models.EmailField(blank=True, max_length=254)),
                ("linkedin_url", models.URLField(blank=True)),
                ("facebook_url", models.URLField(blank=True)),
                ("instagram_url", models.URLField(blank=True)),
                ("site", models.OneToOneField(
                    editable=False, unique=True, db_index=True,
                    on_delete=django.db.models.deletion.CASCADE, to="wagtailcore.site")),
            ],
            options={"verbose_name": "SLQS Site Branding"},
        ),
    ]
