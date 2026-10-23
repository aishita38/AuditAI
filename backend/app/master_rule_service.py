import hashlib
import json
from sqlalchemy.orm import Session
from backend.app.models.master_data import VendorMaster, EmployeeMaster, PayrollPayment, MasterImportHistory
from backend.app.models.master_finding import MasterFinding
from backend.app.models.review_queue import ReviewRecord
from backend.app.features.master_rules import configuration, evaluate_vendors, evaluate_payroll
from backend.app.review_queue_service import freeze


def business_record(row):
    return {c.name:getattr(row,c.name) for c in row.__table__.columns if c.name!='id'}


def run(db:Session,dataset:str):
    config=configuration()
    vendors=[business_record(r) for r in db.query(VendorMaster).order_by(VendorMaster.vendor_id).all()] if dataset=='vendor' else []
    employees=[business_record(r) for r in db.query(EmployeeMaster).order_by(EmployeeMaster.employee_id).all()] if dataset=='payroll' else []
    payments=[business_record(r) for r in db.query(PayrollPayment).order_by(PayrollPayment.payment_id).all()] if dataset=='payroll' else []
    missing=[]
    if dataset=='vendor' and not vendors:missing.append('Vendor master')
    if dataset=='payroll':
        if not employees:missing.append('Employee roster')
        if not payments:missing.append('Payroll payments')
    findings=[] if missing else (evaluate_vendors(vendors,config,transactions=None) if dataset=='vendor' else evaluate_payroll(employees,payments,config))
    statuses=[]
    if missing:statuses.append(dict(status='unavailable',message='Import '+', '.join(missing)+' to enable this check'))
    if dataset=='vendor':statuses.append(dict(rule_id='VENDOR_NEW_LARGE_PAYMENT',status='unavailable',message='Cannot evaluate, vendor-linked transactions unavailable'))
    if dataset=='payroll':statuses.append(dict(rule_id='PAYROLL_DUPLICATE_PAYEE',status='limitation',message='Bank-account matching across roster and payments; PAN matching on roster only.'))
    import_types=['vendor-master'] if dataset=='vendor' else ['employee-roster','payroll-payments']
    actors=sorted({r.imported_by for r in db.query(MasterImportHistory).filter(MasterImportHistory.dataset.in_(import_types),MasterImportHistory.status.in_(['completed','partial']), ((MasterImportHistory.inserted>0)|(MasterImportHistory.updated>0))).all()})
    # Keep old evidence for existing cases, but only current findings can be submitted.
    db.query(MasterFinding).filter_by(dataset=dataset).update({'active':False})
    active=[]
    for f in findings:
        payload=freeze(dict(f,config=config.model_dump(mode='json')))
        key=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        old=db.get(MasterFinding,key)
        if old:
            old.active=True;old.excluded_actor_ids=actors
        else:
            old=MasterFinding(id=key,dataset=dataset,rule_id=f['rule_id'],severity=f['severity'],explanation=f['explanation'],evidence=freeze(dict(f['evidence'],rule_id=f['rule_id'],rule_config=config.model_dump(mode='json'))),involved_record_ids=f['involved_record_ids'],excluded_actor_ids=actors,active=True)
            db.add(old)
        active.append(key)
    db.flush()
    return dict(items=[serialize(db,db.get(MasterFinding,key)) for key in active],statuses=statuses,config=config.model_dump(mode='json'),missing_datasets=missing)


def serialize(db,f):
    case=db.query(ReviewRecord).filter_by(source_key='master:'+f.id).first()
    return dict(id=f.id,dataset=f.dataset,rule_id=f.rule_id,severity=f.severity,explanation=f.explanation,involved_record_ids=f.involved_record_ids,evidence=f.evidence,active=f.active,case_id=case.id if case else None)
