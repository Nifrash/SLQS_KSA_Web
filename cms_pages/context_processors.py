"""Public-only navigation / footer data; no content is hardcoded in a view."""
from .models import NavigationItem, SiteBranding


def global_content(request):
    # Avoid querying the Wagtail navigation for administrative requests.
    if request.path.startswith(("/admin/", "/system-admin/")):
        return {}

    links = list(NavigationItem.objects.filter(is_active=True).select_related("page").order_by("location", "sort_order", "pk"))
    menu = {"header": [], "explore": [], "community": []}
    for item in links:
        if item.page_id and not item.page.live:
            continue
        if item.url:
            menu[item.location].append(item)

    return {
        "slqs_nav": menu,
        "slqs_branding": SiteBranding.for_request(request),
    }
