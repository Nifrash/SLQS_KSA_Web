"""Add the optional Wagtail page builder without removing Phase 1 content."""
import cms_pages.blocks
from django.db import migrations, models
import wagtail.fields


class Migration(migrations.Migration):
    dependencies = [("home", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="homepage",
            name="show_standard_sections",
            field=models.BooleanField(
                default=True,
                help_text="Uncheck once your custom sections are ready to replace the original homepage content. The hero remains visible.",
                verbose_name="Show original Phase 1 homepage sections",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="sections",
            field=wagtail.fields.StreamField(
                cms_pages.blocks.PageStreamBlock(), blank=True,
                help_text="Optional custom sections, placed after the hero and before the original sections (if still enabled).",
            ),
        ),
    ]
