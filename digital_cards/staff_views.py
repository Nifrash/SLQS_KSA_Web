"""Committee-only card management actions; no public card mutation."""
from functools import wraps
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from membership.models import MemberProfile, MembershipApplication
from membership_team.permissions import PERM_ASSIGN, PERM_DECIDE
from .models import DigitalMembershipCard, CardAuditEvent
from .services import card_eligibility, ensure_card, membership_eligibility, reissue_card, revoke_card


def card_staff_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), reverse("membership_team:login"))
        if not request.user.is_active or not request.user.is_staff or not (
            request.user.has_perm(PERM_ASSIGN) or request.user.has_perm(PERM_DECIDE)
        ):
            raise PermissionDenied("SLQS membership-card administration permission required.")
        return view(request, *args, **kwargs)
    return wrapped


@never_cache
@require_GET
@card_staff_required
def cards(request):
    query = request.GET.get("q", "").strip()[:100]
    qs = MemberProfile.objects.select_related("application", "digital_card").filter(
        application__status=MembershipApplication.Status.APPROVED
    ).order_by("-created_at")
    if query:
        qs = qs.filter(
            Q(application__full_name__icontains=query) |
            Q(membership_number__icontains=query) |
            Q(application__company_name__icontains=query)
        )
    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    rows = []
    for member in page:
        try:
            card = member.digital_card
        except DigitalMembershipCard.DoesNotExist:
            card = None
        valid, reason = card_eligibility(card) if card else membership_eligibility(member)
        rows.append({"member": member, "card": card, "valid": bool(card and valid), "reason": reason})
    response = render(request, "digital_cards/staff_cards.html", {
        "rows": rows, "page": page, "q": query,
        "recent": CardAuditEvent.objects.select_related("actor", "card__member")[:15],
    })
    response["Cache-Control"] = "no-store, private"
    return response


@require_POST
@card_staff_required
def revoke(request, member_id):
    member = get_object_or_404(MemberProfile, pk=member_id)
    try:
        revoke_card(member.pk, actor=request.user, note=request.POST.get("reason", ""))
    except (ValidationError, DigitalMembershipCard.DoesNotExist) as exc:
        messages.error(request, "; ".join(exc.messages) if isinstance(exc, ValidationError) else "Card has not been issued.")
    else:
        messages.success(request, "Card revoked. Its QR is no longer valid.")
    return redirect("digital_card_staff:cards")


@require_POST
@card_staff_required
def reissue(request, member_id):
    member = get_object_or_404(MemberProfile, pk=member_id)
    try:
        reissue_card(member.pk, actor=request.user, note=request.POST.get("reason", ""))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "Digital card issued/replaced. Previous QR codes no longer work.")
    return redirect("digital_card_staff:cards")
