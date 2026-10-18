from django.urls import path
from . import views

app_name = "digital_cards"
urlpatterns = [
    path("me/", views.my_card, name="my_card"),
    path("me/qr/", views.my_qr, name="my_qr"),
    path("me/pdf/", views.my_pdf, name="my_pdf"),
    path("verify/<uuid:token>/", views.verify, name="verify"),
]
