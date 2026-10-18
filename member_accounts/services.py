"""Six-digit OTPs with expiry, send cooldown, maximum resends and attempt limits.

Never store or log the plaintext code. Always send to the registered account email.
"""
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import MemberAccountProfile


class OTPProblem(Exception):
    pass


OTP_TTL_MINUTES = 10
OTP_COOLDOWN_SECONDS = 60
OTP_WINDOW_HOURS = 1
OTP_MAX_PER_WINDOW = 5
OTP_MAX_GUESSES = 5


@transaction.atomic
def send_activation_otp(user_id):
    account = MemberAccountProfile.objects.select_for_update().select_related("user").get(user_id=user_id)
    if account.verified_at or account.user.is_active:
        raise OTPProblem("This account is already activated.")
    now = timezone.now()
    if account.otp_last_sent_at and (now - account.otp_last_sent_at).total_seconds() < OTP_COOLDOWN_SECONDS:
        raise OTPProblem("Please wait one minute before requesting another code.")
    if not account.otp_window_started_at or account.otp_window_started_at <= now - timedelta(hours=OTP_WINDOW_HOURS):
        account.otp_window_started_at = now
        account.otp_sent_in_window = 0
    if account.otp_sent_in_window >= OTP_MAX_PER_WINDOW:
        raise OTPProblem("Too many codes requested. Try again after one hour.")
    code = f"{secrets.randbelow(1_000_000):06d}"
    # Send BEFORE updating the OTP so a failed mail send cannot invalidate a working code.
    send_mail(
        "SLQS KSA — email verification code",
        f"Your SLQS verification code is {code}. It expires in {OTP_TTL_MINUTES} minutes. "
        "If you did not register, you may ignore this email.",
        settings.DEFAULT_FROM_EMAIL,
        [account.user.email],
        fail_silently=False,
    )
    account.otp_hash = make_password(code)
    account.otp_expires_at = now + timedelta(minutes=OTP_TTL_MINUTES)
    account.otp_last_sent_at = now
    account.otp_attempts = 0
    account.otp_sent_in_window += 1
    account.save(update_fields=[
        "otp_hash", "otp_expires_at", "otp_last_sent_at", "otp_attempts",
        "otp_sent_in_window", "otp_window_started_at", "updated_at",
    ])


def verify_activation_otp(user_id, code):
    # Persist failed attempts BEFORE raising. Raising inside atomic would
    # otherwise roll them back and defeat lockout protection.
    with transaction.atomic():
        account = MemberAccountProfile.objects.select_for_update().select_related("user").get(user_id=user_id)
        now = timezone.now()
        result = None
        if account.verified_at or account.user.is_active:
            result = "This account is already activated."
        elif not account.otp_hash or not account.otp_expires_at or account.otp_expires_at <= now:
            result = "The code has expired. Request a new one."
        elif account.otp_attempts >= OTP_MAX_GUESSES:
            result = "Too many attempts. Request a new code."
        else:
            account.otp_attempts += 1
            if not check_password(code, account.otp_hash):
                if account.otp_attempts >= OTP_MAX_GUESSES:
                    account.otp_hash = ""
                    account.otp_expires_at = None
                account.save(update_fields=["otp_attempts", "otp_hash", "otp_expires_at", "updated_at"])
                result = "Incorrect code. Please check your email."
            else:
                account.verified_at = now
                account.otp_hash = ""
                account.otp_expires_at = None
                account.otp_attempts = 0
                account.save(update_fields=["verified_at", "otp_hash", "otp_expires_at", "otp_attempts", "updated_at"])
                account.user.is_active = True
                account.user.save(update_fields=["is_active"])
    if result:
        raise OTPProblem(result)
    return account.user
