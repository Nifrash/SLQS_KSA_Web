from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "member_accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("verify/", views.verify, name="verify"),
    path("verify/resend/", views.resend_otp, name="resend_otp"),
    path("verify/resume/", views.resume_verification, name="resume_verification"),
    path("login/", views.MemberLoginView.as_view(), name="login"),
    path("logout/", views.logout_member, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("profile/", views.profile, name="profile"),
    path("notifications/", views.notifications, name="notifications"),
    path("notifications/<int:pk>/read/", views.read_notification, name="read_notification"),
    path("password/reset/", views.ThrottledPasswordResetView.as_view(
        template_name="member_accounts/password/reset_form.html",
        email_template_name="member_accounts/password/reset_email.txt",
        subject_template_name="member_accounts/password/reset_subject.txt",
        success_url=reverse_lazy("member_accounts:password_reset_done"),
    ), name="password_reset"),
    path("password/reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="member_accounts/password/reset_done.html"
    ), name="password_reset_done"),
    path("password/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="member_accounts/password/reset_confirm.html",
        success_url=reverse_lazy("member_accounts:password_reset_complete"),
    ), name="password_reset_confirm"),
    path("password/reset/complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="member_accounts/password/reset_complete.html"
    ), name="password_reset_complete"),
]
