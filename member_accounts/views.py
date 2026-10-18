import logging

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordResetView
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods, require_POST

from membership.models import MembershipApplication, MemberPortalNotification, MembershipInformationRequest
from .forms import AccountProfileForm, EmailLoginForm, OTPForm, RecoverVerificationForm, RegisterForm
from .models import MemberAccountProfile
from .security import limited, too_many, verified_account
from .services import OTPProblem, send_activation_otp, verify_activation_otp

logger = logging.getLogger(__name__)
SESSION_PENDING_ID = "slqs_pending_account_id"


def _pending_user(request):
    pending_id = request.session.get(SESSION_PENDING_ID)
    if not pending_id:
        return None
    account = MemberAccountProfile.objects.select_related("user").filter(user_id=pending_id, verified_at__isnull=True, user__is_active=False).first()
    return account.user if account else None


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        if verified_account(request.user):
            return redirect("member_accounts:dashboard")
        return render(request, "member_accounts/verification_required.html", status=403)
    form = RegisterForm(request.POST or None)
    if request.method == "POST":
        if limited(request, "register", limit=8):
            return too_many()
        if form.is_valid():
            if form.cleaned_data["website"]:
                return redirect("member_accounts:login")
            email = form.cleaned_data["email"]
            from django.contrib.auth import get_user_model
            user_model = get_user_model()
            try:
                with transaction.atomic():
                    user = user_model.objects.create_user(
                        username=email, email=email, password=form.cleaned_data["password1"], is_active=False
                    )
                    MemberAccountProfile.objects.create(user=user, full_name=form.cleaned_data["full_name"])
                    send_activation_otp(user.pk)
            except (IntegrityError, OTPProblem):
                form.add_error("email", "Unable to register. Please check your details or contact SLQS.")
            except Exception:
                logger.exception("Could not send member activation email")
                form.add_error(None, "Activation email could not be sent. Please check your email settings and try again.")
            else:
                request.session[SESSION_PENDING_ID] = user.pk
                messages.success(request, "Check your email for a six-digit activation code.")
                return redirect("member_accounts:verify")
    return render(request, "member_accounts/register.html", {"form": form})


@require_http_methods(["GET", "POST"])
def verify(request):
    user = _pending_user(request)
    if not user:
        return redirect("member_accounts:resume_verification")
    form = OTPForm(request.POST or None)
    if request.method == "POST":
        if limited(request, "verify", limit=15):
            return too_many()
        if form.is_valid():
            try:
                user = verify_activation_otp(user.pk, form.cleaned_data["code"])
            except OTPProblem as exc:
                form.add_error("code", str(exc))
            else:
                request.session.pop(SESSION_PENDING_ID, None)
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                messages.success(request, "Email verified. Your SLQS account is now active.")
                return redirect("member_accounts:dashboard")
    return render(request, "member_accounts/verify.html", {"form": form, "email": user.email})


@require_POST
def resend_otp(request):
    if limited(request, "resend", limit=10):
        return too_many()
    user = _pending_user(request)
    if not user:
        return redirect("member_accounts:resume_verification")
    try:
        send_activation_otp(user.pk)
    except OTPProblem as exc:
        messages.error(request, str(exc))
    except Exception:
        logger.exception("Could not resend activation OTP")
        messages.error(request, "Email delivery failed. Please try again later.")
    else:
        messages.success(request, "A new verification code was sent to your email.")
    return redirect("member_accounts:verify")


@require_http_methods(["GET", "POST"])
def resume_verification(request):
    form = RecoverVerificationForm(request.POST or None)
    if request.method == "POST":
        if limited(request, "resume", limit=8):
            return too_many()
        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()
            from django.contrib.auth import get_user_model
            account = MemberAccountProfile.objects.select_related("user").filter(user__email__iexact=email, verified_at__isnull=True, user__is_active=False).first()
            if account and account.user.check_password(form.cleaned_data["password"]):
                request.session[SESSION_PENDING_ID] = account.user_id
                try:
                    send_activation_otp(account.user_id)
                except OTPProblem as exc:
                    messages.info(request, str(exc))
                except Exception:
                    logger.exception("Recovery OTP send failed")
                    messages.error(request, "Email delivery failed; try again later.")
                return redirect("member_accounts:verify")
            form.add_error(None, "Unable to verify these details. Check your email and password.")
    return render(request, "member_accounts/resume.html", {"form": form})


class MemberLoginView(LoginView):
    template_name = "member_accounts/login.html"
    authentication_form = EmailLoginForm
    redirect_authenticated_user = False

    def dispatch(self, request, *args, **kwargs):
        if request.method == "POST" and limited(request, "login", limit=15):
            return too_many()
        return super().dispatch(request, *args, **kwargs)

    def get_default_redirect_url(self):
        return str(reverse_lazy("member_accounts:dashboard"))


class ThrottledPasswordResetView(PasswordResetView):
    def dispatch(self, request, *args, **kwargs):
        if request.method == "POST" and limited(request, "password-reset", limit=5):
            return too_many()
        return super().dispatch(request, *args, **kwargs)


@require_POST
def logout_member(request):
    logout(request)
    messages.info(request, "You have signed out.")
    return redirect("member_accounts:login")


@login_required
@require_http_methods(["GET"])
def dashboard(request):
    if not verified_account(request.user):
        return render(request, "member_accounts/verification_required.html", status=403)
    application = MembershipApplication.objects.select_related("member_profile").filter(user=request.user).first()
    legacy = not application and MembershipApplication.objects.filter(preferred_email__iexact=request.user.email, user__isnull=True).exists()
    member = None
    if application and application.status == MembershipApplication.Status.APPROVED:
        try:
            member = application.member_profile
        except MembershipApplication.member_profile.RelatedObjectDoesNotExist:
            pass
    notifications_qs = MemberPortalNotification.objects.filter(user=request.user)
    pending_request = (MembershipInformationRequest.objects.filter(
        application=application, responded_at__isnull=True,
    ).first() if application and application.status == MembershipApplication.Status.MORE_INFO else None)
    return render(request, "member_accounts/dashboard.html", {
        "pending_info_request": pending_request,
        "recent_notifications": notifications_qs[:4],
        "unread_notifications": notifications_qs.filter(read_at__isnull=True).count(),
        "account": request.user.slqs_account, "application": application, "member": member,
        "legacy_application_needs_linking": legacy,
        "can_apply": not application and not legacy,
        "active_page": "membership",
    })


@login_required
@require_http_methods(["GET", "POST"])
def profile(request):
    if not verified_account(request.user):
        return render(request, "member_accounts/verification_required.html", status=403)
    profile = request.user.slqs_account
    form = AccountProfileForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        # Load previous filename from DB: ModelForm validation may already
        # have replaced the in-memory ImageField value.
        old_name = MemberAccountProfile.objects.filter(pk=profile.pk).values_list(
            "profile_photo", flat=True
        ).first()
        updated = form.save()
        new_name = updated.profile_photo.name if updated.profile_photo else ""
        if old_name and old_name != new_name:
            # Delete superseded pictures only after the database write commits.
            storage = MemberAccountProfile._meta.get_field("profile_photo").storage
            transaction.on_commit(lambda name=old_name, store=storage: store.delete(name))
        messages.success(request, "Your profile has been updated. Submitted membership details remain unchanged.")
        return redirect("member_accounts:profile")
    application = MembershipApplication.objects.select_related("member_profile").filter(user=request.user).first()
    legacy = not application and MembershipApplication.objects.filter(
        preferred_email__iexact=request.user.email, user__isnull=True
    ).exists()
    member = None
    if application and application.status == MembershipApplication.Status.APPROVED:
        try:
            member = application.member_profile
        except MembershipApplication.member_profile.RelatedObjectDoesNotExist:
            pass
    return render(request, "member_accounts/profile.html", {
        "form": form, "account": profile, "application": application,
        "member": member, "legacy_application_needs_linking": legacy,
        "active_page": "membership",
    })


@login_required
@require_http_methods(["GET"])
def notifications(request):
    if not verified_account(request.user):
        return render(request, "member_accounts/verification_required.html", status=403)
    application = MembershipApplication.objects.filter(user=request.user).first()
    queryset = MemberPortalNotification.objects.filter(user=request.user).select_related("information_request")
    return render(request, "member_accounts/notifications.html", {
        "account": request.user.slqs_account, "application": application,
        "notifications": queryset[:80],
        "unread_notifications": queryset.filter(read_at__isnull=True).count(),
        "portal_section": "notifications", "active_page": "membership",
    })


@login_required
@require_POST
def read_notification(request, pk):
    if not verified_account(request.user):
        return render(request, "member_accounts/verification_required.html", status=403)
    item = MemberPortalNotification.objects.filter(pk=pk, user=request.user).first()
    if item is None:
        from django.http import Http404
        raise Http404("Notification not found")
    if item.read_at is None:
        item.read_at = timezone.now()
        item.save(update_fields=["read_at"])
    return redirect("member_accounts:notifications")
