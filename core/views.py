"""Phase 1 public views, with optional published Phase 2 CMS overrides."""
import logging

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from wagtail.models import Site

from cms_pages.models import ContentPage
from .forms import ContactForm

logger = logging.getLogger(__name__)


def _cms_override(request, slug):
    """Serve a published first-level Wagtail page in place of a legacy view.

    Only the specifically approved legacy slugs call this function. For a draft,
    unpublished or restricted page, the original Phase 1 page is still served.
    """
    site = Site.find_for_request(request)
    if site is None:
        return None
    page = (ContentPage.objects.live().child_of(site.root_page)
            .filter(slug=slug).first())
    if page is not None and not page.get_view_restrictions().exists():
        return page.serve(request)
    return None


def about(request):
    return _cms_override(request, "about") or render(request, "core/about.html", {"active_page": "about"})


def what_we_do(request):
    return _cms_override(request, "what-we-do") or render(request, "core/what_we_do.html", {"active_page": "what"})


def news(request):
    return render(request, "core/news.html", {"active_page": "news"})


def events(request):
    return render(request, "core/events.html", {"active_page": "events"})


def membership(request):
    return render(request, "core/membership.html", {"active_page": "membership"})


def privacy(request):
    return _cms_override(request, "privacy") or render(request, "core/privacy.html")


@require_http_methods(["GET", "POST"])
def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        inquiry = form.save()
        if settings.CONTACT_INBOX_EMAIL:
            try:
                send_mail(
                    subject=f"SLQS website enquiry: {inquiry.get_topic_display()}",
                    message=(f"From: {inquiry.full_name} <{inquiry.email}>\n\n"
                             f"Topic: {inquiry.get_topic_display()}\n\n{inquiry.message}"),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.CONTACT_INBOX_EMAIL],
                    fail_silently=False,
                )
            except Exception:
                logger.exception("Contact enquiry #%s saved, but email delivery failed", inquiry.pk)
        messages.success(request, "Thank you. Your message has been received by SLQS.")
        return redirect("core:contact")
    return render(request, "core/contact.html", {"active_page": "contact", "form": form})
