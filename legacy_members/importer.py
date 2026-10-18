"""Side-effect-free CSV/XLSX validation followed by an atomic, idempotent import.

No imported row is ever trusted to grant an existing user access to a membership.
The file must be approved by a Membership Head; account linking is a separate OTP flow.
"""
import csv
import hashlib
import io
import re
import zipfile
from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath
from xml.etree import ElementTree as ET

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from membership.forms import normalize_ksa_phone, normalize_whatsapp_phone
from membership.models import (MembershipApplication, MemberProfile, MembershipReviewLog,
                               MemberActivity, PROFESSIONAL_QUALIFICATIONS, REGIONS)
from .models import LegacyImportBatch, LegacyMemberRecord

MAX_FILE_BYTES = 3 * 1024 * 1024
MAX_ROWS = 2000
MAX_UNCOMPRESSED = 25 * 1024 * 1024

FIELDS = {
 'key': ('Import Record ID',),
 'timestamp': ('Form Submission Timestamp', 'Timestamp'),
 'collected_email': ('Collected Email Address', 'Email Address'),
 'full_name': ('Full Name',),
 'dob': ('Date of Birth',),
 'email': ('Preferred Email', 'Preferred Email Address', 'Email'),
 'ksa_phone': ('KSA Phone Number',),
 'whatsapp': ('WhatsApp Phone Number',),
 'group': ('Already in SLQS WhatsApp Group', 'Are you already a member of our WhatsApp group with this WhatsApp number?'),
 'company': ('Company Name',),
 'job': ('Job Title',),
 'education': ('Highest Educational Qualification (QS / Engineering Related)',),
 'qualifications': ('Professional Qualifications (Active as of date)',),
 'qualification_other': ('Other Professional Qualification (if selected)',),
 'total_exp': ('Overall Years of Post-Qualification Experience', 'Overall Years of Post Qualification Experience'),
 'ksa_exp': ('Years of KSA Experience',),
 'region': ('Working Region in KSA',),
 'suggestions': ('Your Suggestions to Improve SLQS KSA Services',),
 'status': ('SLQS Approval Status (Legacy)',),
 'member_number': ('Existing SLQS Member Number',),
 'approved_date': ('Approved Date',),
}
REQUIRED = ('full_name','dob','email','ksa_phone','whatsapp','group','company','job','education','qualifications','total_exp','ksa_exp','region','status')
QUAL_MAP = {code.casefold():code for code,_ in PROFESSIONAL_QUALIFICATIONS}
REGION_MAP = {label.casefold():code for code,label in REGIONS}
REGION_MAP.update({code.casefold():code for code,_ in REGIONS})
STATUS_MAP = {
 'approved':MembershipApplication.Status.APPROVED,
 'pending':MembershipApplication.Status.SUBMITTED,
 'submitted':MembershipApplication.Status.SUBMITTED,
 'under review':MembershipApplication.Status.IN_REVIEW,
 'in review':MembershipApplication.Status.IN_REVIEW,
 'rejected':MembershipApplication.Status.REJECTED,
}


def _header(s):
    return re.sub(r'[^a-z0-9]+','',str(s or '').strip().lower())


def _string(value):
    if value is None: return ''
    if isinstance(value, datetime): return value.isoformat()
    if isinstance(value, date): return value.isoformat()
    return str(value).strip()


def _csv_rows(data):
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ValueError('CSV must be UTF-8 encoded.') from exc
    rows = list(csv.reader(io.StringIO(text)))
    return rows


def _xlsx_rows(data):
    """Read simple worksheet cell values with Python stdlib (shared strings and Excel dates)."""
    ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise ValueError('The Excel file is not a valid XLSX workbook.')
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        entries = z.infolist()
        if any(x.file_size > MAX_UNCOMPRESSED or x.compress_size > MAX_UNCOMPRESSED for x in entries):
            raise ValueError('An XLSX worksheet is too large.')
        if sum(x.file_size for x in entries) > MAX_UNCOMPRESSED:
            raise ValueError('The XLSX workbook expands beyond the permitted size.')
        sheets = sorted(n for n in z.namelist() if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',n))
        if not sheets: raise ValueError('No worksheets found in the XLSX file.')
        # The supplied four-tab workbook begins with START_HERE: use Test_Members
        # when present, otherwise import the first worksheet as for Google exports.
        date1904=False
        if 'xl/workbook.xml' in z.namelist() and 'xl/_rels/workbook.xml.rels' in z.namelist():
            w=ET.fromstring(z.read('xl/workbook.xml'))
            workbook_props=w.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}workbookPr')
            date1904=bool(workbook_props is not None and workbook_props.attrib.get('date1904') in ('1','true'))
            relroot=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
            relmap={r.attrib.get('Id'):r.attrib.get('Target','') for r in relroot}
            main='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
            relation='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
            for item in w.findall('.//'+main+'sheet'):
                if item.attrib.get('name','').strip().lower()=='test_members':
                    target=relmap.get(item.attrib.get(relation),'')
                    target=target.lstrip('/') if target.startswith('/') else ('xl/'+target if not target.startswith('xl/') else target)
                    if target in z.namelist():sheets=[target];break
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            root=ET.fromstring(z.read('xl/sharedStrings.xml'))
            shared=[''.join(node.text or '' for node in si.iter(ns+'t')) for si in root.findall(ns+'si')]
        root = ET.fromstring(z.read(sheets[0]))
        rows=[]
        for row in root.findall('.//'+ns+'sheetData/'+ns+'row'):
            cols={}
            for cell in row.findall(ns+'c'):
                ref=cell.attrib.get('r','')
                letter=re.match(r'[A-Z]+',ref)
                if not letter: continue
                idx=0
                for ch in letter.group(): idx=idx*26+ord(ch)-64
                typ=cell.attrib.get('t')
                v=cell.find(ns+'v')
                if typ=='inlineStr':
                    inline=cell.find(ns+'is')
                    val=''.join(n.text or '' for n in inline.iter(ns+'t')) if inline is not None else ''
                elif v is None:
                    val=''
                elif typ=='s':
                    try: val=shared[int(v.text)]
                    except (ValueError,IndexError,TypeError) as exc: raise ValueError('Invalid XLSX shared string.') from exc
                else:
                    val=v.text or ''
                cols[idx-1]=val
            if cols:
                row_values=['']*(max(cols)+1)
                for k,v in cols.items(): row_values[k]=v
                rows.append(row_values)
            if len(rows)>MAX_ROWS+2:
                raise ValueError(f'Import files may contain at most {MAX_ROWS} members.')
        if date1904 and rows:
            date_indices=[i for i,h in enumerate(rows[0]) if _header(h) in {_header('Date of Birth'),_header('Approved Date'),_header('Form Submission Timestamp'),_header('Timestamp')}]
            for row in rows[1:]:
                for i in date_indices:
                    if i<len(row) and re.fullmatch(r'\d+(?:\.\d+)?',str(row[i])):
                        row[i]=str(float(row[i])+1462)
        return rows


def _datetime(value):
    if not value: return None
    try:
        if re.fullmatch(r'\d+(?:\.\d+)?',_string(value)):
            dt=datetime(1899,12,30)+timedelta(days=float(value))
        else:
            dt=datetime.fromisoformat(_string(value).replace('Z','+00:00'))
        if timezone.is_naive(dt):dt=timezone.make_aware(dt,timezone.get_current_timezone())
        return dt
    except (ValueError,OverflowError):
        raise ValueError('Invalid submission timestamp')


def _date(value):
    if not value: raise ValueError('Date is required')
    if isinstance(value, (date,datetime)): return value.date() if isinstance(value,datetime) else value
    value=_string(value)
    try:
        # 1900 date system; matches the SLQS provided test template.
        if re.fullmatch(r'\d+(?:\.\d+)?',value): return (datetime(1899,12,30)+timedelta(days=float(value))).date()
        for fmt in ('%Y-%m-%d','%d/%m/%Y','%m/%d/%Y','%d-%m-%Y'):
            try:return datetime.strptime(value[:10],fmt).date()
            except ValueError:pass
        return datetime.fromisoformat(value).date()
    except (ValueError,OverflowError) as exc:
        raise ValueError('Use a valid date (YYYY-MM-DD preferred).') from exc


def _years(value):
    s=_string(value).replace('years','').strip()
    if s.endswith('+'): s=s[:-1]
    try: result=Decimal(s)
    except (InvalidOperation,ValueError): raise ValueError('Experience must be numeric (e.g. 8 or 20+).')
    if not result.is_finite() or result<0 or result>80: raise ValueError('Experience must be between 0 and 80 years.')
    return result.quantize(Decimal('.01'))


def _qualifications(value):
    values=[x.strip() for x in re.split(r'[,;|\n]+', _string(value)) if x.strip()]
    codes=[]
    for x in values:
        code=QUAL_MAP.get(x.casefold())
        if not code: raise ValueError(f'Unknown qualification: {x}.')
        if code not in codes: codes.append(code)
    if not codes or ('None' in codes and len(codes)>1): raise ValueError('Choose valid qualification(s); None must stand alone.')
    return codes


def _parse_row(cells, idx, positions):
    raw={key:_string(cells[position]) if position is not None and position<len(cells) else '' for key,position in positions.items()}
    errors=[]
    def parse(key, fn, default=None):
        try:return fn(raw[key])
        except (ValueError,ValidationError) as exc:
            errors.append(f'{key}: {exc}')
            return default
    for key in REQUIRED:
        if not raw[key]: errors.append(f'{key}: required')
    email=raw['email'].lower().strip()
    if email and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email): errors.append('email: invalid email address')
    if raw['collected_email'] and raw['collected_email'].lower()!=email:
        errors.append('collected_email: differs from preferred email; committee must resolve the mismatch')
    status=STATUS_MAP.get(raw['status'].lower())
    if raw['status'] and status is None: errors.append('status: use Approved, Pending, Under Review or Rejected')
    dob=parse('dob',_date)
    if dob and (dob>timezone.localdate() or dob.year<timezone.localdate().year-110): errors.append('dob: outside the allowed age/date range')
    approved_date=parse('approved_date',_date) if raw['approved_date'] else None
    submitted_at=parse('timestamp',_datetime) if raw['timestamp'] else None
    if status==MembershipApplication.Status.APPROVED and approved_date is None: errors.append('approved_date: required for approved historical members')
    region=REGION_MAP.get(raw['region'].lower())
    if raw['region'] and not region: errors.append('region: unsupported working region')
    group= {'yes':'yes','no':'no'}.get(raw['group'].lower())
    if raw['group'] and not group: errors.append('group: expected Yes or No')
    quals=parse('qualifications',_qualifications,[])
    other=raw['qualification_other']
    if 'Other' in quals and not other: errors.append('qualification_other: specify Other')
    if other and 'Other' not in quals: errors.append('qualification_other: select Other in qualifications')
    ksa=parse('ksa_phone',normalize_ksa_phone)
    wa=parse('whatsapp',normalize_whatsapp_phone)
    years=parse('total_exp',_years)
    ksa_years=parse('ksa_exp',_years)
    if years is not None and ksa_years is not None and ksa_years>years: errors.append('ksa_exp: cannot exceed total experience')
    member_number=raw['member_number'].strip().upper()
    if member_number and (status!=MembershipApplication.Status.APPROVED or not re.fullmatch(r'SLQS-KSA-\d{6,}',member_number)):
        errors.append('member_number: approved members only; expected SLQS-KSA-000250 format')
    for k,n in [('full_name',180),('email',254),('ksa_phone',20),('whatsapp',20),('company',180),('job',150),('education',250),('qualification_other',250),('suggestions',3000)]:
        if len(raw[k])>n:errors.append(f'{k}: maximum length {n}')
    source=raw['key'] or ('email:'+hashlib.sha256(email.encode()).hexdigest()[:64])
    if len(source)>128:errors.append('key: must be at most 128 characters')
    values={'source_key':source,'full_name':raw['full_name'],'date_of_birth':dob,'preferred_email':email,
            'ksa_phone':ksa,'whatsapp_phone':wa,'whatsapp_group_member':group,'company_name':raw['company'],
            'job_title':raw['job'],'highest_educational_qualification':raw['education'],
            'professional_qualifications':quals,'professional_qualifications_other':other,
            'overall_post_qualification_experience':years,'ksa_experience':ksa_years,
            'working_region':region,'suggestions':raw['suggestions'],'status':status,
            'approved_date':approved_date,'member_number':member_number,'submitted_at':submitted_at}
    return {'row':idx,'key':source,'email':email,'name':raw['full_name'], 'status':raw['status'], 'values':values,'errors':errors,'action':'create'}


def preview(data, filename):
    if len(data)>MAX_FILE_BYTES: raise ValueError('File must be no larger than 3 MB.')
    filename=filename or ''
    if filename.lower().endswith('.csv'): cells=_csv_rows(data)
    elif filename.lower().endswith('.xlsx'): cells=_xlsx_rows(data)
    else:raise ValueError('Upload an Excel XLSX or UTF-8 CSV file.')
    if len(cells)<2:raise ValueError('Include a header row and at least one registration.')
    if len(cells)>MAX_ROWS+1:raise ValueError(f'Maximum {MAX_ROWS} member rows per import.')
    header={_header(x):i for i,x in enumerate(cells[0]) if x}
    positions={key: next((header[_header(alias)] for alias in choices if _header(alias) in header),None) for key,choices in FIELDS.items()}
    for key in REQUIRED:
        if positions[key] is None: raise ValueError(f'Missing required column: {FIELDS[key][0]}')
    result=[];seen_emails=set();seen_keys=set();seen_numbers=set()
    for i,row in enumerate(cells[1:], start=2):
        if not any(_string(x) for x in row):continue
        item=_parse_row(row,i,positions)
        v=item['values']
        if item['email'] in seen_emails:item['errors'].append('email: duplicated within this file')
        if item['key'] in seen_keys:item['errors'].append('key: duplicated within this file')
        if v['member_number'] and v['member_number'] in seen_numbers:item['errors'].append('member_number: duplicated within this file')
        seen_emails.add(item['email']);seen_keys.add(item['key']);seen_numbers.add(v['member_number'])
        result.append(item)
    if not result: raise ValueError('No member rows found.')
    # Cross-reference current DB, without altering any existing record.
    known_keys={x.source_key:x for x in LegacyMemberRecord.objects.select_related('application').filter(source_key__in=[x['key'] for x in result])}
    from django.db.models.functions import Lower
    known_emails={x.preferred_email.lower():x for x in MembershipApplication.objects.annotate(normalized_email=Lower('preferred_email')).filter(normalized_email__in=[x['email'] for x in result])}
    user_model=get_user_model()
    website_emails=set(user_model.objects.annotate(normalized_email=Lower('email')).filter(normalized_email__in=[x['email'] for x in result]).values_list('normalized_email',flat=True))
    known_numbers={x.membership_number:x for x in MemberProfile.objects.filter(membership_number__in=[x['values']['member_number'] for x in result if x['values']['member_number']])}
    for item in result:
        item['warnings']=[]
        if item['email'] in website_emails:item['warnings'].append('Website account already exists; requires manual verified linking after import.')
        existing=known_keys.get(item['key']); match=known_emails.get(item['email']);number=known_numbers.get(item['values']['member_number'])
        if existing:
            if existing.imported_email.lower()!=item['email'] or existing.application.preferred_email.lower()!=item['email']:
                item['errors'].append('key: imported identifier already belongs to a different email')
            else:
                item['action']='skip'
                if item['values']['status']!=existing.application.status:
                    item['errors'].append('status: differs from the already-imported record; use the normal membership review workflow')
        elif match:item['errors'].append('email: already belongs to a separate membership application; manual review needed')
        if number and (not existing or number.application_id!=existing.application_id):
            item['errors'].append('member_number: already allocated to another member')
    return {'rows':result,'total':len(result),'create':sum(x['action']=='create' for x in result),
            'skip':sum(x['action']=='skip' for x in result),
            'errors':sum(bool(x['errors']) for x in result),'sha256':hashlib.sha256(data).hexdigest()}


@transaction.atomic
def apply_import(result, filename, actor):
    """Atomic, all-or-nothing import. Caller must hold Head permission and confirm status evidence."""
    if result['errors']: raise ValueError('Fix all validation and conflict errors before importing.')
    batch=LegacyImportBatch.objects.create(filename=filename[:240], sha256=result['sha256'], uploaded_by=actor,
                                          row_count=result['total'], skipped_count=result['skip'])
    # Reserve legacy identifiers first, then allocate new system numbers.
    ordered=sorted(result['rows'], key=lambda row: 0 if row['values']['member_number'] else 1)
    for row in ordered:
        if row['action']=='skip':continue
        v=row['values'].copy();approved_date=v.pop('approved_date');number=v.pop('member_number');submitted_at=v.pop('submitted_at');v.pop('source_key')
        state=v['status']
        v['privacy_consent_at']=None  # Google Form data is NOT proof of this website's consent.
        v['reviewed_by']=actor if state==MembershipApplication.Status.APPROVED else None
        v['reviewed_at']=timezone.make_aware(datetime.combine(approved_date,datetime.min.time())) if state==MembershipApplication.Status.APPROVED and approved_date else None
        app=MembershipApplication(**v)
        app.full_clean()
        app.save() # Existing signals safely provision approved members, case, digital card.
        if submitted_at:
            MembershipApplication.objects.filter(pk=app.pk).update(created_at=submitted_at)
            app.created_at=submitted_at
        LegacyMemberRecord.objects.create(application=app,source_key=row['key'],batch=batch,
                                          imported_email=row['email'],imported_status=state)
        MembershipReviewLog.objects.create(application=app,from_status='',to_status=state,actor=actor,
               note='Historical Google Forms import; recorded status validated by Membership Head.')
        if state==MembershipApplication.Status.APPROVED:
            member=app.member_profile
            changes=[]
            if number and member.membership_number!=number:
                member.membership_number=number;changes.append('membership_number')
            if approved_date and member.joined_on!=approved_date:
                member.joined_on=approved_date;changes.append('joined_on')
            if changes:
                member.full_clean()
                member.save(update_fields=changes+['updated_at'])
                MemberActivity.objects.create(member=member,action=MemberActivity.Action.JOINED_DATE,actor=actor,
                    note='Historical SLQS membership number and/or joining date imported from approved legacy record.')
        batch.created_count+=1
    batch.save(update_fields=['created_count'])
    return batch
