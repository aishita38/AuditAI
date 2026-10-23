from threading import Lock
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from backend.app.db import get_db
from backend.app.auth.security import require_roles
from backend.app.models.master_finding import MasterFinding
from backend.app.models.review_queue import ReviewRecord, ReviewQueueEvent
from backend.app.master_rule_service import run, serialize
from backend.app.review_queue_service import freeze

router=APIRouter(prefix='/api/v1/master-checks',tags=['Vendor and payroll review signals'])
reviewer=Depends(require_roles('maker','checker','admin'))
write_lock=Lock()


@router.post('/{dataset}/run')
def run_checks(dataset:Literal['vendor','payroll'],db:Session=Depends(get_db),user=reviewer):
    db.rollback()
    with write_lock:
        result=run(db,dataset);db.commit()
    return result


@router.get('/{dataset}')
def findings(dataset:Literal['vendor','payroll'],db:Session=Depends(get_db),user=reviewer):
    return dict(items=[serialize(db,f) for f in db.query(MasterFinding).filter_by(dataset=dataset,active=True).order_by(MasterFinding.rule_id,MasterFinding.id).all()])


@router.post('/findings/{finding_id}/send-to-review')
def send_to_review(finding_id:str,db:Session=Depends(get_db),user=reviewer):
    # Recompute under the same lock as checks so stale findings cannot enter review.
    db.rollback()
    with write_lock:
        f=db.get(MasterFinding,finding_id)
        if not f:raise HTTPException(404,'Finding not found. Run checks first.')
        existing=db.query(ReviewRecord).filter_by(source_key='master:'+f.id).first()
        if existing:return dict(case_id=existing.id)
        run(db,f.dataset);db.flush();db.refresh(f)
        if not f.active:
            db.commit();raise HTTPException(409,'Finding changed after re-import or configuration update. Run checks again.')
        # Only explicit employee_id is used for related records. No vendor-name joins.
        links=[]
        if f.dataset=='payroll':
            roster_ids={r['employee_id'] for r in f.evidence.get('employees',[])}
            for p in f.evidence.get('payments',[]):
                if p.get('employee_id') in roster_ids:
                    link=dict(kind='employee',id=p['employee_id'])
                    if link not in links:links.append(link)
        r=ReviewRecord(source_key='master:'+f.id,case_type='vendor_check' if f.dataset=='vendor' else 'payroll_check',severity=f.severity,reason=f.rule_id+': '+f.explanation,evidence=freeze(f.evidence),related_records=links,excluded_actor_ids=f.excluded_actor_ids,status='open')
        db.add(r)
        try:
            db.flush();db.add(ReviewQueueEvent(review_id=r.id,action='created',actor_id=user.id,actor_email=user.email,notes='Master-data finding sent to shared review; all involved records and rule configuration preserved.',new_status='open'));db.commit()
        except IntegrityError:
            db.rollback();existing=db.query(ReviewRecord).filter_by(source_key='master:'+finding_id).first()
            if existing:return dict(case_id=existing.id)
            raise HTTPException(409,'Finding submitted concurrently; refresh.')
        return dict(case_id=r.id)
