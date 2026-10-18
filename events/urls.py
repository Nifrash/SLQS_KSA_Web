from django.urls import path
from . import views

app_name = "events"
urlpatterns = [
    path("", views.index, name="index"),
    path("<slug:slug>/register/", views.register, name="register"),
    path("<slug:slug>/", views.detail, name="detail"),
]
