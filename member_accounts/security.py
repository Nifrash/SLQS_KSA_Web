"""Basic per-client throttling. Use a shared cache (Redis) on multi-worker servers."""
from django.core.cache import cache
from django.http import HttpResponse
from django.utils.crypto import salted_hmac


def limited(request, action, limit=10, window=600):
    # Do not trust spoofable X-Forwarded-For headers by default.
    ip = request.META.get("REMOTE_ADDR", "unknown")
    key = "slqs-rate:" + salted_hmac("slqs-accounts", f"{action}:{ip}").hexdigest()
    if cache.add(key, 1, window):
        return False
    try:
        return cache.incr(key) > limit
    except ValueError:
        cache.set(key, 1, window)
        return False


def too_many():
    response = HttpResponse("Too many requests. Please try again later.", status=429)
    response["Retry-After"] = "600"
    return response


def verified_account(user):
    if not user.is_authenticated or not user.is_active:
        return False
    try:
        return bool(user.slqs_account.verified_at)
    except Exception:
        return False
