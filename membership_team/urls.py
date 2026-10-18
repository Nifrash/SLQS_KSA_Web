from django.urls import path
from . import views

app_name = 'membership_team'

urlpatterns = [
    path('login/', views.CommitteeLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.dashboard, name='dashboard'),
    path('applications/', views.application_list, name='applications'),
    path('applications/export/', views.export_applications, name='export'),
    path('applications/<int:pk>/', views.case_detail, name='case_detail'),
    path('applications/<int:pk>/assign/', views.assign, name='assign'),
    path('applications/<int:pk>/recommend/', views.recommend, name='recommend'),
    path('applications/<int:pk>/request-info/', views.more_info, name='more_info'),
    path('applications/<int:pk>/decide/', views.decide, name='decide'),
    path('members/', views.member_list, name='members'),
]
