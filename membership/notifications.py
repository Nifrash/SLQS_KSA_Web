"""Email notifications; failures are logged and never undo saved decisions."""
import logging
from urllib.parse import urljoin

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.urls import reverse

from .models import MembershipApplication, MemberPortalNotification

logger = logging.getLogger(__name__)
TOKEN_SALT = "slqs.membership.additional-information.v1"
TOKEN_MAX_AGE = 7 * 24 * 60 * 60


def update_token(application):
    return signing.dumps({"ref": str(application.reference), "email": application.preferred_email}, salt=TOKEN_SALT)


def update_link(application):
    base = (getattr(settings, "WAGTAILADMIN_BASE_URL", "") or "http://127.0.0.1:8000").rstrip("/") + "/"
    return urljoin(base, reverse("membership:update", kwargs={"token": update_token(application)}).lstrip("/"))


def _deliver(subject, body, recipient):
    if not recipient:
        return
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=False)
    except Exception:
        logger.exception("Membership notification delivery failed")


def submission_emails(application, resubmitted=False):
    verb = "updated" if resubmitted else "received"
    if application.user_id:
        MemberPortalNotification.objects.create(
            user_id=application.user_id, application=application,
            kind=MemberPortalNotification.Kind.SUBMITTED,
            title="Membership application received" if not resubmitted else "Additional information received",
            message="Your membership application is in the committee review queue." if not resubmitted else "Your response was submitted to the membership committee.",
        )
    _deliver(
        f"SLQS KSA membership application {verb} — {application.short_reference}",
        f"Dear {application.full_name},\n\nYour membership application has been {verb}.\n"
        f"Reference: {application.short_reference}\n"
        "The SLQS KSA membership team will review it. Submission does not mean membership approval.\n\n"
        "SLQS Saudi Arabia",
        application.preferred_email,
    )
    admin_email = getattr(settings, "MEMBERSHIP_ADMIN_EMAIL", "").strip()
    if admin_email:
        _deliver(
            f"SLQS membership application {verb}: {application.short_reference}",
            f"Application {application.short_reference} has been {verb}. Review it in SLQS System Administration.",
            admin_email,
        )


def status_email(application, note=""):
    status = application.get_status_display()
    subject = f"SLQS KSA membership application update — {application.short_reference}"
    body = (f"Dear {application.full_name},\n\n"
            f"Your membership application status is: {status}.\n"
            f"Reference: {application.short_reference}\n")
    if application.status == MembershipApplication.Status.APPROVED:
        member = getattr(application, "member_profile", None)
        if member and member.membership_number:
            body += f"Membership number: {member.membership_number}\n"
    if note:
        body += "\nMessage from the SLQS membership team:\n" + note.strip() + "\n"
    if application.user_id:
        request_obj = (application.information_requests.filter(responded_at__isnull=True).first()
                       if application.status == MembershipApplication.Status.MORE_INFO else None)
        kind = {
            MembershipApplication.Status.MORE_INFO: MemberPortalNotification.Kind.INFO_REQUEST,
            MembershipApplication.Status.APPROVED: MemberPortalNotification.Kind.APPROVED,
            MembershipApplication.Status.REJECTED: MemberPortalNotification.Kind.REJECTED,
        }.get(application.status, MemberPortalNotification.Kind.UPDATE)
        MemberPortalNotification.objects.create(
            user_id=application.user_id, application=application,
            information_request=request_obj,
            kind=kind,
            title="Action required: upload a supporting document" if request_obj else f"Membership status: {status}",
            message=note.strip() or f"Your application status changed to {status}.",
        )
    if application.status == MembershipApplication.Status.MORE_INFO:
        if application.user_id:
            outstanding = application.information_requests.filter(responded_at__isnull=True).first()
            if outstanding:
                base = (getattr(settings, "SITE_BASE_URL", "") or getattr(settings, "WAGTAILADMIN_BASE_URL", "") or "http://127.0.0.1:8000").rstrip("/") + "/"
                secure_url = urljoin(base, reverse("membership:respond", kwargs={"pk": outstanding.pk}).lstrip("/"))
                body += f"\nLog into your SLQS dashboard to respond and upload a document:\n{secure_url}\n"
            else:
                body += "\nPlease log in to your SLQS member dashboard to review the request.\n"
        else:
            body += ("\nPlease update your application using this private link within 7 days:\n"
                     f"{update_link(application)}\n"
                     "Do not forward this link; it grants access to your application.\n")
    body += "\nSLQS Saudi Arabia"
    _deliver(subject, body, application.preferred_email)
