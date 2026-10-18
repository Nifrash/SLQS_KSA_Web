"""Do not invent privacy consent when importing historical Google Form responses."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('membership', '0005_response_user_nullable')]
    operations = [
        migrations.AlterField(model_name='membershipapplication', name='privacy_consent_at',
                              field=models.DateTimeField(null=True, blank=True)),
    ]
