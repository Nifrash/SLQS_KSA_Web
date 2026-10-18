from django.urls import path
from . import staff_views

app_name = "digital_card_staff"
urlpatterns = [
    path("", staff_views.cards, name="cards"),
    path("<int:member_id>/revoke/", staff_views.revoke, name="revoke"),
    path("<int:member_id>/reissue/", staff_views.reissue, name="reissue"),
]
