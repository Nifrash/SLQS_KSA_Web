"""Wagtail handles the homepage; the core app handles Phase 1 sections."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

urlpatterns = [
    path('system-admin/', admin.site.urls),
    path('admin/', include(wagtailadmin_urls)),
    path('documents/', include(wagtaildocs_urls)),
    path('news/', include('newsroom.urls')),
    path('events/', include('events.urls')),
    path('membership/', include('membership.urls')),
    path('accounts/', include('member_accounts.urls')),
    path('existing-members/', include('legacy_members.urls')),
    path('membership-team/cards/', include('digital_cards.staff_urls')),
    path('membership-team/', include('membership_team.urls')),
    path('cards/', include('digital_cards.urls')),
    path('', include('core.urls')),
    path('', include(wagtail_urls)),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = 'SLQS System Administration'
admin.site.site_title = 'SLQS System'
admin.site.index_title = 'Backend Records'
