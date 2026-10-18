"""Member-only card and QR endpoints, plus minimal public verification."""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from membership.models import MembershipApplication, MemberProfile
from member_accounts.security import verified_account
from .models import DigitalMembershipCard
from .pdf import card_pdf_bytes
from .qr import qr_png_bytes
from .services import card_eligibility, membership_eligibility, ensure_card, verification_url


def _private_headers(response):
    response["Cache-Control"] = "no-store, private"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["Referrer-Policy"] = "no-referrer"
    return response


def _verified_member(request):
    if not verified_account(request.user):
        return None
    return MemberProfile.objects.select_related("application").filter(
        application__user=request.user,
        application__status=MembershipApplication.Status.APPROVED,
    ).first()


def _member_card(request):
    member = _verified_member(request)
    if not member:
        return None, None, False, "Your membership has not yet been approved."
    card = DigitalMembershipCard.objects.filter(member=member).first()
    if card is None:
        eligible, reason = membership_eligibility(member)
        if eligible:
            card, _ = ensure_card(member)
        else:
            return member, None, False, reason
    eligible, reason = card_eligibility(card)
    return member, card, eligible, reason


@never_cache
@require_GET
@login_required
def my_card(request):
    if not verified_account(request.user):
        return _private_headers(render(request, "member_accounts/verification_required.html", status=403))
    member, card, valid, reason = _member_card(request)
    account = request.user.slqs_account
    application = MembershipApplication.objects.filter(user=request.user).first()
    return _private_headers(render(request, "digital_cards/my_card.html", {
        "account": account, "application": application, "member": member,
        "card": card, "valid": valid, "reason": reason,
    }))


@never_cache
@require_GET
@login_required
def my_qr(request):
    member, card, valid, _ = _member_card(request)
    if not valid:
        return _private_headers(HttpResponse(status=403))
    response = HttpResponse(qr_png_bytes(verification_url(card)), content_type="image/png")
    response["Content-Disposition"] = 'inline; filename="slqs-card-qr.png"'
    return _private_headers(response)


@never_cache
@require_GET
@login_required
def my_pdf(request):
    member, card, valid, _ = _member_card(request)
    if not valid:
        return _private_headers(HttpResponse(status=403))
    data = card_pdf_bytes(card, verification_url(card))
    response = HttpResponse(data, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{member.membership_number}-digital-card.pdf"'
    return _private_headers(response)


@never_cache
@require_GET
def verify(request, token):
    card = DigitalMembershipCard.objects.select_related("member", "member__application").filter(token=token).first()
    valid = bool(card and card_eligibility(card)[0])
    # The public result intentionally never discloses DOB, email, phone or member photo.
    response = render(request, "digital_cards/verify.html", {
        "valid": valid,
        "member": card.member if valid else None,
        "checked_at": timezone.now(),
    })
    return _private_headers(response)
