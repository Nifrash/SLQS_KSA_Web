from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("member_accounts", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="memberaccountprofile",
            name="profile_photo",
            field=models.ImageField(
                blank=True,
                help_text="Optional profile photo. JPEG, PNG or WebP, up to 5 MB.",
                upload_to="member_photos/%Y/%m/",
            ),
        ),
    ]
