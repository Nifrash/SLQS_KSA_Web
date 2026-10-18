"""Head-only two-step preview/confirm upload and public one-time account activation."""
import logging
from datetime import timedelta
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from member_accounts.security import limited, too_many
from membership_team.permissions import committee_required, PERM_DECIDE
from .activation import request_code, verify_code, claim_membership, ActivationProblem
from .forms import ImportForm, EmailForm, CodeForm, ClaimForm
from .importer import preview, apply_import
from .models import LegacyImportBatch, LegacyMemberRecord, LegacyActivationChallenge

log=logging.getLogger(__name__)
SESSION_CHALLENGE='slqs_legacy_activation_token'
SESSION_PREVIEW='slqs_legacy_import_preview_sha'


def _head(user):
    return user.is_superuser or user.groups.filter(name='SLQS Membership Head').exists()


@committee_required(PERM_DECIDE)
@require_http_methods(['GET','POST'])
def import_members(request):
    if not _head(request.user):raise PermissionDenied('Only the Membership Head may import historical approvals.')
    form=ImportForm(request.POST or None,request.FILES or None)
    result=None
    if request.method=='POST' and form.is_valid():
        if limited(request,'legacy-import',limit=16,window=600):return too_many()
        upload=form.cleaned_data['workbook']
        try:
            result=preview(upload.read(),upload.name)
        except Exception as exc:
            # Surface validation errors, but do not leak detailed system tracebacks.
            if isinstance(exc,ValueError):form.add_error('workbook',str(exc))
            else:
                log.exception('SLQS legacy import failed parsing')
                form.add_error('workbook','Could not read file. Verify that it is a valid Excel/CSV export.')
        else:
            if request.POST.get('action')=='confirm':
                if request.session.get(SESSION_PREVIEW)!=result['sha256']:
                    form.add_error(None,'Preview this exact file first, then upload it again to confirm.')
                elif not form.cleaned_data['confirm_approvals']:
                    form.add_error('confirm_approvals','You must confirm the historical approval statuses.')
                elif result['errors']:
                    form.add_error(None,'Resolve every highlighted row before importing.')
                else:
                    try:
                        batch=apply_import(result,upload.name,request.user)
                    except Exception:
                        log.exception('SLQS legacy import transaction rejected')
                        form.add_error(None,'Import could not be completed; no partial import was committed. Please review member-number and email conflicts.')
                    else:
                        request.session.pop(SESSION_PREVIEW,None)
                        messages.success(request,f'Import completed: {batch.created_count} created, {batch.skipped_count} already imported.')
                        return redirect('legacy_members:import')
            else:
                request.session[SESSION_PREVIEW]=result['sha256']
    return render(request,'legacy_members/import.html',{'form':form,'result':result,
        'batches':LegacyImportBatch.objects.select_related('uploaded_by')[:15], 'can_confirm':bool(result and not result['errors']),
        'legacy_total':LegacyMemberRecord.objects.count(),
        'activation_total':LegacyMemberRecord.objects.filter(activated_at__isnull=False).count()})


def _challenge(request,needs_verified=False):
    token=request.session.get(SESSION_CHALLENGE)
    if not token:return None
    q=LegacyActivationChallenge.objects.filter(token=token,completed_at__isnull=True).first()
    if not q:return None
    if needs_verified and (not q.verified_at or q.verified_at+timedelta(minutes=15)<timezone.now()):return None
    return q


@require_http_methods(['GET','POST'])
def activate_start(request):
    if request.user.is_authenticated:return redirect('member_accounts:dashboard')
    form=EmailForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        if limited(request,'legacy-activation-start',limit=8,window=600):return too_many()
        request.session.pop(SESSION_CHALLENGE,None)
        try:challenge=request_code(form.cleaned_data['email'])
        except Exception:
            log.exception('Unable to send SLQS legacy activation OTP')
            challenge=None
        if challenge:
            request.session[SESSION_CHALLENGE]=str(challenge.token)
        # Same response whether a matching historical email exists or not.
        messages.info(request,'If this address is eligible for activation, we have sent a code. If no message arrives, please contact the SLQS Membership Team.')
        return redirect('legacy_members:activate_verify')
    return render(request,'legacy_members/activate_start.html',{'form':form})


@require_http_methods(['GET','POST'])
def activate_verify(request):
    challenge=_challenge(request)
    form=CodeForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        if limited(request,'legacy-activation-verify',limit=15,window=600):return too_many()
        if not challenge:
            form.add_error('code','Invalid or expired verification request. Please start again.')
        else:
            try:verify_code(challenge.token,form.cleaned_data['code'])
            except ActivationProblem as exc:form.add_error('code',str(exc))
            else:return redirect('legacy_members:activate_claim')
    return render(request,'legacy_members/activate_verify.html',{'form':form})


@require_http_methods(['GET','POST'])
def activate_claim(request):
    challenge=_challenge(request,needs_verified=True)
    if not challenge:return redirect('legacy_members:activate')
    form=ClaimForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        if limited(request,'legacy-activation-claim',limit=12,window=600):return too_many()
        try:user=claim_membership(challenge.token,form.cleaned_data['date_of_birth'],
                                  form.cleaned_data['password1'],form.cleaned_data['privacy_consent'])
        except ActivationProblem as exc:form.add_error(None,str(exc))
        except IntegrityError:
            form.add_error(None,'This email may already have a website account. Contact SLQS Membership Team.')
        else:
            request.session.pop(SESSION_CHALLENGE,None)
            login(request,user,backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request,'Your existing SLQS membership is linked. Welcome to your dashboard.')
            return redirect('member_accounts:dashboard')
    return render(request,'legacy_members/activate_claim.html',{'form':form})
