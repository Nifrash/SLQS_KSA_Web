from django.urls import path
from . import views

app_name = "membership"

urlpatterns = [
    path("", views.index, name="index"),
    path("apply/", views.apply, name="apply"),
    path("submitted/", views.submitted, name="submitted"),
    path("update/<str:token>/", views.update, name="update"),
    path("respond/<int:pk>/", views.respond_to_request, name="respond"),
    path("documents/<int:pk>/download/", views.download_supporting_document, name="document_download"),
]
