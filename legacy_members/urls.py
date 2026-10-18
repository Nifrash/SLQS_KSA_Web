from django.urls import path
from . import views
app_name='legacy_members'
urlpatterns=[
  path('import/',views.import_members,name='import'),
  path('activate/',views.activate_start,name='activate'),
  path('activate/verify/',views.activate_verify,name='activate_verify'),
  path('activate/create-password/',views.activate_claim,name='activate_claim'),
]
