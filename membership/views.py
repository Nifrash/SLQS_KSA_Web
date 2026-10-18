"""Public signup; admin-only status review is handled separately."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden
from django.urls import reverse
from member_accounts.security import verified_account
from django.core import signing
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import MembershipApplicationForm
from .models import MembershipApplication, MembershipReviewLog
from .notifications import TOKEN_MAX_AGE, TOKEN_SALT, submission_emails


def index(request):
    return render(request, "membership/index.html", {"active_page": "membership"})


def submitted(request):
    # A generic acknowledgement; no personal information is exposed by URL.
    return render(request, "membership/submitted.html", {"active_page": "membership"})


@login_required(login_url="member_accounts:login")
@require_http_methods(["GET", "POST"])
def apply(request):
    if not verified_account(request.user):
        return render(request, "member_accounts/verification_required.html", status=403)
    if MembershipApplication.objects.filter(user=request.user).exists():
        return redirect("member_accounts:dashboard")
    verified_email = request.user.email.strip().lower()
    # Old Phase 5 records are not automatically claimed by matching an email.
    if MembershipApplication.objects.filter(preferred_email__iexact=verified_email).exists():
        return render(request, "membership/existing_application.html", status=409)
    initial = {"preferred_email": verified_email, "full_name": request.user.slqs_account.full_name}
    form = MembershipApplicationForm(request.POST or None, initial=initial)
    form.fields["preferred_email"].disabled = True
    if request.method == "POST":
        valid = form.is_valid()
        # Django may detect the case-insensitive email constraint during
        # ModelForm validation, before database insertion. A fully otherwise
        # valid duplicate gets the same public acknowledgement as a new one.
        cleaned_email = getattr(form, "cleaned_data", {}).get("preferred_email")
        if not valid and cleaned_email and set(form.errors).issubset({"preferred_email", "__all__"}):
            if MembershipApplication.objects.filter(preferred_email__iexact=cleaned_email).exists():
                messages.success(request, "Thank you. Any new application has been recorded for SLQS review.")
                return redirect("membership:submitted")
        if valid:
            if form.cleaned_data.get("website"):
                return redirect("membership:submitted")  # bot honeypot
            application = form.save(commit=False)
            application.user = request.user
            application.preferred_email = verified_email
            application.privacy_consent_at = timezone.now()
            try:
                with transaction.atomic():
                    application.save()
                    MembershipReviewLog.objects.create(
                        application=application, from_status="", to_status=application.status,
                        note="Application submitted online.",
                    )
                    transaction.on_commit(lambda app=application: submission_emails(app))
            except IntegrityError:
                # Generic acknowledgement prevents public email-lookup/enumeration.
                pass
            messages.success(request, "Thank you. If this is a new application, it has been recorded for SLQS review.")
            return redirect("membership:submitted")
    return render(request, "membership/form.html", {
        "form": form, "is_update": False, "active_page": "membership",
    })


def _resolve_token(token):
    try:
        payload = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
        if not isinstance(payload, dict) or set(payload) != {"ref", "email"}:
            raise Http404("Invalid link")
        app = get_object_or_404(MembershipApplication, reference=payload["ref"])
        if (app.status != MembershipApplication.Status.MORE_INFO or
                app.preferred_email != payload["email"]):
            raise Http404("This update link is no longer available")
        return app
    except (signing.BadSignature, signing.SignatureExpired, ValueError, TypeError):
        raise Http404("Invalid or expired link")


@require_http_methods(["GET", "POST"])
def update(request, token):
    app = _resolve_token(token)
    if app.user_id and not verified_account(request.user):
        return redirect_to_login(request.get_full_path(), login_url=reverse("member_accounts:login"))
    if app.user_id and request.user.pk != app.user_id:
        return HttpResponseForbidden("This application belongs to another account.")
    if app.user_id:
        outstanding = app.information_requests.filter(responded_at__isnull=True).first()
        if outstanding:
            return redirect("membership:respond", pk=outstanding.pk)
    # ModelForm validation mutates its instance. Keep the original address
    # separately so legitimate changes to Preferred Email can be accepted.
    original_email = app.preferred_email
    form = MembershipApplicationForm(request.POST or None, instance=app)
    if app.user_id:
        form.fields["preferred_email"].disabled = True
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data.get("website"):
            return redirect("membership:submitted")
        try:
            with transaction.atomic():
                locked = MembershipApplication.objects.select_for_update().get(pk=app.pk)
                if locked.status != MembershipApplication.Status.MORE_INFO or locked.preferred_email != original_email:
                    raise Http404("This update link is no longer available")
                modified = form.save(commit=False)
                # In case another reviewer modifies the application concurrently,
                # do not save a stale status or review metadata.
                modified.status = MembershipApplication.Status.SUBMITTED
                modified.reviewed_by = locked.reviewed_by
                modified.reviewed_at = locked.reviewed_at
                modified.privacy_consent_at = timezone.now()
                modified.save()
                MembershipReviewLog.objects.create(
                    application=modified, from_status=locked.status,
                    to_status=modified.status, note="Applicant resubmitted information.",
                )
                transaction.on_commit(lambda updated=modified: submission_emails(updated, resubmitted=True))
        except IntegrityError:
            form.add_error("preferred_email", "Please use a different email or contact SLQS for assistance.")
        else:
            messages.success(request, "Your updated application has been received for review.")
            return redirect("membership:submitted")
    return render(request, "membership/form.html", {
        "form": form, "is_update": True, "active_page": "membership",
    })


@login_required(login_url="member_accounts:login")
@require_http_methods(["GET", "POST"])
def respond_to_request(request, pk):
    """Verified applicant responds once, with mandatory private evidence."""
    from .forms import MembershipInformationResponseForm
    from .models import MembershipInformationRequest, MembershipInformationResponse

    if not verified_account(request.user):
        return render(request, "member_accounts/verification_required.html", status=403)
    info = get_object_or_404(
        MembershipInformationRequest.objects.select_related("application"),
        pk=pk, application__user=request.user,
    )
    previous = MembershipInformationResponse.objects.filter(request=info).first()
    open_request = info.is_open and previous is None
    form = MembershipInformationResponseForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if not open_request:
            return HttpResponseForbidden("This request has already been answered or closed.")
        if form.is_valid():
            saved_name = None
            try:
                with transaction.atomic():
                    locked = MembershipInformationRequest.objects.select_for_update().get(pk=info.pk)
                    app = MembershipApplication.objects.select_for_update().get(pk=locked.application_id)
                    if (locked.responded_at or app.status != MembershipApplication.Status.MORE_INFO
                            or app.user_id != request.user.pk):
                        return HttpResponseForbidden("This information request is no longer open.")
                    reply = MembershipInformationResponse(
                        request=locked, user=request.user,
                        message=form.cleaned_data["message"].strip(),
                        document=form.cleaned_data["document"],
                    )
                    reply.save()
                    saved_name = reply.document.name
                    locked.responded_at = timezone.now()
                    locked.save(update_fields=["responded_at"])
                    app.status = MembershipApplication.Status.SUBMITTED
                    app.save(update_fields=["status", "updated_at"])
                    MembershipReviewLog.objects.create(
                        application=app, from_status=MembershipApplication.Status.MORE_INFO,
                        to_status=app.status, note="Applicant uploaded supporting document and resubmitted information.",
                    )
                    transaction.on_commit(lambda app_id=app.pk: submission_emails(
                        MembershipApplication.objects.get(pk=app_id), resubmitted=True
                    ))
            except Exception:
                if saved_name:
                    reply.document.storage.delete(saved_name)
                raise
            messages.success(request, "Your response and supporting document were sent to the SLQS membership committee.")
            return redirect("member_accounts:dashboard")
    return render(request, "membership/respond_to_request.html", {
        "account": request.user.slqs_account,
        "application": info.application,
        "info": info, "previous": previous, "open_request": open_request,
        "form": form, "portal_section": "notifications",
        "active_page": "membership",
    })


@login_required(login_url="member_accounts:login")
@require_http_methods(["GET"])
def download_supporting_document(request, pk):
    """Files never have a public /media/ URL; authorization checked on every download."""
    from django.http import FileResponse
    from .models import MembershipInformationResponse

    reply = get_object_or_404(
        MembershipInformationResponse.objects.select_related("request__application"), pk=pk
    )
    application = reply.request.application
    is_owner = application.user_id == request.user.pk and verified_account(request.user)
    staff_allowed = False
    if request.user.is_active and request.user.is_staff:
        from membership_team.permissions import PERM_VIEW, accessible_cases
        staff_allowed = (request.user.has_perm(PERM_VIEW) and
                         accessible_cases(request.user).filter(application_id=application.pk).exists())
    if not (is_owner or staff_allowed):
        raise Http404("Document not found")
    try:
        stream = reply.document.open("rb")
    except (OSError, ValueError):
        raise Http404("Document unavailable")
    from pathlib import Path
    response = FileResponse(stream, as_attachment=True, filename=Path(reply.document.name).name,
                            content_type="application/octet-stream")
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Content-Type-Options"] = "nosniff"
    return response
