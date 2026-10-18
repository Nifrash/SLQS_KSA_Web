from django.urls import path
from . import views

app_name = 'core'
urlpatterns = [
    path('about/', views.about, name='about'),
    path('what-we-do/', views.what_we_do, name='what_we_do'),
    path('news/', views.news, name='news'),
    path('events/', views.events, name='events'),
    path('membership/', views.membership, name='membership'),
    path('contact/', views.contact, name='contact'),
    path('privacy/', views.privacy, name='privacy'),
]
