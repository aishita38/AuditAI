"""Normalized partial-load imports, isolated from claims and ML scoring."""
import csv
import hashlib
import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from sqlalchemy.exc import IntegrityError
from backend.app.models.master_data import VendorMaster, EmployeeMaster, PayrollPayment, MasterImportHistory

DATASETS = {
    'vendor-master': (VendorMaster, 'vendor_id', ['vendor_id','vendor_name','bank_account','ifsc','address','phone','gstin','pan','director_names','onboarding_date','status']),
    'employee-roster': (EmployeeMaster, 'employee_id', ['employee_id','name','bank_account','pan','department','join_date','exit_date','monthly_salary']),
    'payroll-payments': (PayrollPayment, 'payment_id', ['payment_id','employee_id','employee_name','bank_account','amount','pay_period','payment_date']),
}
MAX_BYTES = 2_000_000
MAX_ROWS = 5000


def normalize_row(dataset, row):
    _, key, fields = DATASETS[dataset]
    result = {}
    limits = {'vendor_id':80,'employee_id':80,'payment_id':80,'vendor_name':300,'name':300,'employee_name':300,'bank_account':100,'ifsc':30,'phone':80,'gstin':40,'pan':30,'department':150,'status':40,'address':5000,'director_names':5000}
    for field in fields:
        value = (row.get(field) or '').strip()
        if field in ('vendor_id','employee_id','payment_id','pan','gstin','ifsc'):
            value = value.upper()
        if field in ('bank_account','phone'):
            value = re.sub(r'[\s-]', '', value)
        if field == 'address': value = ' '.join(value.lower().split())
        if field == 'director_names': value = ';'.join(' '.join(n.split()) for n in value.split(';') if n.strip())
        if field in limits and len(value) > limits[field]: raise ValueError(f'{field} exceeds {limits[field]} characters')
        if field in ('onboarding_date','join_date','exit_date','payment_date'):
            if field == 'exit_date' and not value: result[field] = None; continue
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value): raise ValueError(f'{field} must be YYYY-MM-DD')
            try: value = date.fromisoformat(value)
            except ValueError: raise ValueError(f'{field} is not a valid calendar date')
        if field in ('monthly_salary','amount'):
            try:
                value = Decimal(value)
                if not value.is_finite() or value < 0 or (field == 'amount' and value == 0) or value >= Decimal('10000000000000') or value != value.quantize(Decimal('.01')):
                    raise ValueError(f'{field} must be finite, {"positive" if field == "amount" else "non-negative"}, and fit 13 integer digits / 2 decimals')
            except InvalidOperation: raise ValueError(f'{field} must be a decimal number')
        if field == 'pay_period' and not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', value): raise ValueError('pay_period must be YYYY-MM with a valid month')
        result[field] = value if value != '' else None
    required_values = {'vendor-master':['vendor_id','vendor_name','status'], 'employee-roster':['employee_id','name','department'], 'payroll-payments':['payment_id','employee_id','employee_name']}[dataset]
    for field in required_values:
        if not result[field]: raise ValueError(f'{field} cannot be blank')
    if dataset == 'employee-roster' and result['exit_date'] and result['exit_date'] < result['join_date']: raise ValueError('exit_date cannot be before join_date')
    # Tax identifiers intentionally accept malformed values for future format screening.
    return result


def import_master_csv(db, dataset, content, filename, actor_id):
    model, key, fields = DATASETS[dataset]
    report = dict(dataset=dataset,status='completed',inserted=0,updated=0,skipped=0,rejected=0,errors=[])
    history = MasterImportHistory(dataset=dataset, filename=(filename or 'unnamed.csv')[:200], file_sha256=hashlib.sha256(content).hexdigest() if len(content)<=MAX_BYTES else None, imported_by=actor_id)
    code = 200
    def file_error(reason):
        nonlocal code
        report['status']='rejected'; report['errors'].append(dict(row=None,reason=reason)); code=422
    valid = []
    if len(content) > MAX_BYTES: file_error('Maximum CSV size is 2 MB')
    elif not content.strip(): report['status']='empty'
    else:
        try:
            reader=csv.DictReader(io.StringIO(content.decode('utf-8-sig')), strict=True)
            headers=[str(h).strip().lower() for h in (reader.fieldnames or [])]
            if len(headers)!=len(set(headers)): raise ValueError('Duplicate column names')
            required=[f for f in fields if f != 'exit_date']
            missing=[f for f in required if f not in headers]
            if missing: raise ValueError('Missing required columns: '+', '.join(missing))
            reader.fieldnames=headers
            parsed=[]
            for row_number,row in enumerate(reader,2):
                if len(parsed)>=MAX_ROWS: raise ValueError('Maximum 5,000 data rows per import; no data loaded')
                parsed.append((row_number,row))
            seen={}
            for row_number,row in parsed:
                try:
                    if None in row: raise ValueError('Row has more values than the header')
                    if any(v is None for k,v in row.items() if k in required): raise ValueError('Row has fewer values than required columns')
                    data=normalize_row(dataset,row)
                    business_key=data[key]
                    if business_key in seen:
                        if seen[business_key] == data: report['skipped']+=1
                        else: raise ValueError(f'Conflicting repeated {key} within file; first valid row retained')
                    else:
                        seen[business_key]=data; valid.append((row_number,data))
                except ValueError as exc:
                    report['rejected']+=1; report['errors'].append(dict(row=row_number,reason=str(exc)))
            if not parsed: report['status']='empty'
        except (UnicodeError,csv.Error,ValueError) as exc:
            valid=[]; file_error(str(exc))
    if code == 200:
        for row_number,data in valid:
            try:
                # Savepoints isolate a racing business-key conflict from other rows.
                with db.begin_nested():
                    old=db.query(model).filter(getattr(model,key)==data[key]).first()
                    if old is None:
                        db.add(model(**data)); db.flush(); operation='inserted'
                    elif all(getattr(old,k)==v for k,v in data.items()): operation='skipped'
                    else:
                        for k,v in data.items(): setattr(old,k,v)
                        db.flush(); operation='updated'
                report[operation]+=1
            except IntegrityError:
                report['rejected']+=1; report['errors'].append(dict(row=row_number,reason='Business-key conflict; retry this row'))
        if report['rejected']:
            report['status']='partial' if report['inserted']+report['updated']+report['skipped'] else 'rejected'
    for k in ('status','inserted','updated','skipped','rejected','errors'): setattr(history,k,report[k])
    db.add(history); db.commit(); db.refresh(history)
    return dict(import_id=history.id,**report),code
