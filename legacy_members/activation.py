"""Historical member email challenge and secure account claim (never auto-link by email alone)."""
import secrets
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password, check_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from member_accounts.models import MemberAccountProfile
from membership.models import MembershipApplication
from .models import LegacyMemberRecord, LegacyActivationChallenge

MAX_EMAILS_HOUR = 5
MAX_ATTEMPTS = 5


class ActivationProblem(Exception):
    pass


@transaction.atomic
def request_code(email):
    """Returns a challenge or None; UI always responds generically to requests."""
    email=email.strip().lower()
    record=LegacyMemberRecord.objects.select_for_update().select_related('application').filter(
        imported_email__iexact=email,activated_at__isnull=True,application__user__isnull=True).first()
    if not record:return None
    users=get_user_model()
    if users.objects.filter(email__iexact=email).exists() or users.objects.filter(username__iexact=email).exists():
        # Existing accounts need assisted verification instead of a silent merge.
        return None
    now=timezone.now()
    recent=LegacyActivationChallenge.objects.filter(record=record,created_at__gt=now-timedelta(hours=1))
    if recent.count()>=MAX_EMAILS_HOUR:return None
    latest=recent.first()
    if latest and (now-latest.created_at).total_seconds()<60:return None
    code=f'{secrets.randbelow(1_000_000):06d}'
    send_mail('SLQS KSA — existing member activation code',
              'Your SLQS existing member activation code is '+code+'. It expires in 10 minutes. '
              'If you did not request this, please ignore this email.',
              settings.DEFAULT_FROM_EMAIL,[email],fail_silently=False)
    return LegacyActivationChallenge.objects.create(record=record,otp_hash=make_password(code),
                                                       expires_at=now+timedelta(minutes=10))


def verify_code(token, value):
    error=None
    with transaction.atomic():
        challenge=LegacyActivationChallenge.objects.select_for_update().filter(token=token).first()
        now=timezone.now()
        if not challenge or challenge.completed_at or challenge.expires_at<=now or challenge.verified_at:
            error='Code expired. Request a new activation code.'
        elif challenge.attempted>=MAX_ATTEMPTS:
            error='Too many attempts. Request a new code.'
        else:
            challenge.attempted+=1
            if not check_password(value,challenge.otp_hash):
                challenge.save(update_fields=['attempted'])
                error='Incorrect code.'
            else:
                challenge.verified_at=now
                challenge.otp_hash=''
                challenge.save(update_fields=['verified_at','otp_hash','attempted'])
    if error:raise ActivationProblem(error)
    return challenge


def claim_membership(token, birth_date, password, accepted):
    # Wrong DOB attempts MUST commit before the error is raised, otherwise
    # an attacker could make unlimited guesses with a valid email OTP.
    error=None;user=None
    with transaction.atomic():
        challenge=LegacyActivationChallenge.objects.select_for_update().select_related('record__application').filter(token=token).first()
        now=timezone.now()
        if not challenge or challenge.completed_at or not challenge.verified_at or not accepted:
            error='Complete email verification and accept the privacy notice first.'
        elif challenge.verified_at+timedelta(minutes=15)<now:
            error='Your verification session expired. Start activation again.'
        elif challenge.identity_attempts>=MAX_ATTEMPTS:
            error='Identity verification limit reached. Start again or contact SLQS.'
        else:
            record=LegacyMemberRecord.objects.select_for_update().select_related('application').get(pk=challenge.record_id)
            app=MembershipApplication.objects.select_for_update().get(pk=record.application_id)
            if record.activated_at or app.user_id:
                error='This historical membership has already been claimed.'
            elif app.date_of_birth!=birth_date:
                challenge.identity_attempts+=1
                challenge.save(update_fields=['identity_attempts'])
                error='Unable to verify membership identity. Contact SLQS Membership Team.'
            else:
                email=record.imported_email.strip().lower()
                users=get_user_model()
                if users.objects.filter(email__iexact=email).exists() or users.objects.filter(username__iexact=email).exists():
                    error='An account already exists for this address. Contact SLQS Membership Team.'
                else:
                    # The form validated password strength with Django's validators.
                    user=users.objects.create_user(username=email,email=email,password=password,is_active=True)
                    MemberAccountProfile.objects.create(user=user,full_name=app.full_name,ksa_phone=app.ksa_phone,
                       whatsapp_phone=app.whatsapp_phone,company_name=app.company_name,job_title=app.job_title,verified_at=now)
                    app.user=user
                    app.privacy_consent_at=now  # Explicit opt-in during activation.
                    app.save(update_fields=['user','privacy_consent_at','updated_at'])
                    record.activated_at=now
                    record.save(update_fields=['activated_at'])
                    challenge.completed_at=now
                    challenge.save(update_fields=['completed_at'])
    if error:raise ActivationProblem(error)
    return user
