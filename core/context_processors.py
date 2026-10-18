from django.conf import settings


def site_details(request):
    return {
        'site_brand': 'SLQS',
        'site_full_name': 'Sri Lankan Quantity Surveyors – Saudi Arabia',
        'site_contact_email': settings.CONTACT_INBOX_EMAIL,
    }
