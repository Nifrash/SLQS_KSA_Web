from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name='ContactInquiry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=120)),
                ('email', models.EmailField(max_length=254)),
                ('topic', models.CharField(choices=[('GENERAL', 'General enquiry'), ('MEMBERSHIP', 'Membership enquiry'), ('EVENTS', 'Events and partnerships'), ('PROFESSIONAL', 'Professional collaboration')], default='GENERAL', max_length=20)),
                ('message', models.TextField(max_length=4000)),
                ('privacy_consent', models.BooleanField(default=False)),
                ('status', models.CharField(choices=[('NEW', 'New'), ('IN_PROGRESS', 'In progress'), ('CLOSED', 'Closed')], default='NEW', max_length=20)),
                ('admin_notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'verbose_name_plural': 'Contact inquiries', 'ordering': ['-created_at']},
        ),
    ]
