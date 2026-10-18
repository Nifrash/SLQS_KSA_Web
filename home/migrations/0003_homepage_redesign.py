"""Add editable hero imagery/actions and new home-specific Wagtail blocks."""
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models
import home.blocks
import wagtail.fields


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0002_homepage_sections"),
        ("wagtailimages", "__latest__"),
    ]
    operations = [
        migrations.AddField(
            model_name="homepage", name="hero_image",
            field=models.ForeignKey(
                to="wagtailimages.image", null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                help_text="Choose a hero photograph from the Wagtail image library."
            )
        ),
        migrations.AddField(
            model_name="homepage", name="hero_image_alt",
            field=models.CharField(blank=True, max_length=200,
                help_text="Describe the image for accessibility. Leave blank for a purely decorative image.")
        ),
        migrations.AddField(
            model_name="homepage", name="hero_button_label",
            field=models.CharField(default="Explore membership", max_length=65)
        ),
        migrations.AddField(
            model_name="homepage", name="hero_button_path",
            field=models.CharField(default="/membership/", max_length=255,
                validators=[django.core.validators.RegexValidator(
                    regex=r"^/(?!/)",
                    message="Use a site-relative URL starting with a single / (for example, /membership/).")],
                help_text="Internal link path beginning with / (for example /membership/).")
        ),
        migrations.AddField(
            model_name="homepage", name="hero_secondary_label",
            field=models.CharField(default="Discover SLQS", max_length=65)
        ),
        migrations.AddField(
            model_name="homepage", name="hero_secondary_path",
            field=models.CharField(default="/about/", max_length=255,
                validators=[django.core.validators.RegexValidator(
                    regex=r"^/(?!/)",
                    message="Use a site-relative URL starting with a single / (for example, /membership/).")],
                help_text="Internal link path beginning with / (for example /about/).")
        ),
        migrations.AlterField(
            model_name="homepage", name="show_standard_sections",
            field=models.BooleanField(default=True,
                verbose_name="Show starter homepage sections when editor blocks are empty",
                help_text="Show the new SLQS starter design until sections are saved. Turn off to intentionally display no sections.")
        ),
        migrations.AlterField(
            model_name="homepage", name="sections",
            field=wagtail.fields.StreamField(home.blocks.HomeStreamBlock(), blank=True,
                help_text="Add, remove and drag sections into the required order. Hero image and hero text are edited separately above. Live news/events update automatically.")
        ),
    ]
