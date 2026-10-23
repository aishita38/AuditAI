"""One queue/API for native expense/cycle cases and independently reviewed findings."""
import hashlib,json
from threading import Lock
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,Field,field_validator
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.exc import IntegrityError
from backend.app.db import get_db
from backend.app.auth.security import require_roles
from backend.app.models.review_queue import ReviewRecord,ReviewQueueEvent
from backend.app.models.transfer import BankTransfer
from backend.app.models.expense import Case,ExpenseClaim
from backend.app.review_queue_service import adopt_existing,serialize,permissions,state

router=APIRouter(prefix='/api/v1/review-queue',tags=['Shared review queue'])
Reviewer=Depends(require_roles('maker','checker','admin'))
SYNC_LOCK=Lock()


class Notes(BaseModel):
    notes:str=Field(min_length=5,max_length=5000)
    @field_validator('notes')
    @classmethod
    def nonblank(cls,v):
        if len(v.strip())<5: raise ValueError('At least 5 non-whitespace characters are required.')
        return v.strip()


class Decision(Notes):
    action:Literal['approve','reject']


@router.post('/sync')
def sync(db:Session=Depends(get_db),user=Reviewer):
    # Release the authentication read transaction before waiting on SQLite's writer.
    db.rollback()
    with SYNC_LOCK:
        try:
            with db.no_autoflush:
                added=adopt_existing(db)
            db.commit()
        except IntegrityError:
            db.rollback();raise HTTPException(409,'Queue changed concurrently; refresh again.')
    return dict(added=added)


@router.get('')
def listing(case_type:Literal['expense_claim','circular_payment','reconciliation','vendor_check','payroll_check']|None=None,
            status:str|None=None,severity:Literal['low','medium','high','critical']|None=None,
            offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),db:Session=Depends(get_db),user=Reviewer):
    q=db.query(ReviewRecord)
    if case_type:q=q.filter_by(case_type=case_type)
    if severity:q=q.filter_by(severity=severity)
    if status:q=q.filter_by(status=status)
    count=q.count()
    return dict(total=count,items=[serialize(db,r,user) for r in q.order_by(ReviewRecord.id.desc()).offset(offset).limit(limit).all()])


def get_record(db,review_id):
    r=db.get(ReviewRecord,review_id)
    if not r: raise HTTPException(404,'Review case not found.')
    return r


@router.get('/{review_id}')
def detail(review_id:int,db:Session=Depends(get_db),user=Reviewer):
    return serialize(db,get_record(db,review_id),user,True)


@router.post('/reconciliation/{claim_id}')
def submit_reconciliation(claim_id:str,db:Session=Depends(get_db),user=Reviewer):
    from backend.app.api.reconciliation import reconciliation
    result=reconciliation(db,user)
    evidence=next((i for i in result['items'] if i['claim_id']==claim_id),None)
    if not evidence or not evidence['flags']:raise HTTPException(422,'No current reconciliation finding for this claim.')
    key='reconciliation:'+hashlib.sha256(json.dumps([claim_id,sorted(p['transaction_id'] for p in evidence['payments']),sorted(evidence['flags'])]).encode()).hexdigest()
    r=db.query(ReviewRecord).filter_by(source_key=key).first()
    if not r:
        ids=[p['transaction_id'] for p in evidence['payments']]
        excluded=sorted({t.imported_by for t in db.query(BankTransfer).filter(BankTransfer.transaction_id.in_(ids)).all()})
        r=ReviewRecord(source_key=key,case_type='reconciliation',severity='high',reason='Payment reconciliation: '+', '.join(f.replace('_',' ') for f in evidence['flags']),evidence=evidence,related_records=[dict(kind='claim',id=claim_id)],excluded_actor_ids=excluded,status='open')
        db.add(r)
        try:
            db.flush();db.add(ReviewQueueEvent(review_id=r.id,action='created',actor_id=user.id,actor_email=user.email,notes='Reconciliation finding sent to shared review; evidence preserved.',new_status='open'));db.commit()
        except IntegrityError:
            db.rollback();raise HTTPException(409,'Finding submitted concurrently; refresh.')
    return serialize(db,r,user,True)


@router.post('/expense/{claim_id}')
def submit_expense(claim_id:str,db:Session=Depends(get_db),user=Reviewer):
    claim=db.query(ExpenseClaim).filter_by(claim_id=claim_id).first()
    if not claim:raise HTTPException(404,'Claim not found.')
    if not claim.case:
        if claim.status!='flagged':raise HTTPException(422,'Only flagged claims can open review cases.')
        c=Case(claim_id=claim_id,status='open');db.add(c);db.flush();claim.case=c
        from backend.app.models.expense import CaseAuditTrail
        db.add(CaseAuditTrail(case_id=c.id,action='created',performed_by=user.email,notes='Flagged expense submitted to shared review.'))
    adopt_existing(db);db.commit()
    r=db.query(ReviewRecord).filter_by(source_key=f'expense:{claim.case.id}').one()
    return serialize(db,r,user,True)


@router.post('/{review_id}/comments')
def comment(review_id:int,body:Notes,db:Session=Depends(get_db),user=Reviewer):
    r=get_record(db,review_id);current=state(db,r)
    db.add(ReviewQueueEvent(review_id=r.id,action='comment',actor_id=user.id,actor_email=user.email,notes=body.notes,prior_status=current,new_status=current));db.commit()
    return serialize(db,r,user,True)


@router.post('/{review_id}/{stage}')
def decide(review_id:int,stage:Literal['maker-recommend','checker-signoff'],body:Decision,db:Session=Depends(get_db),user=Reviewer):
    r=get_record(db,review_id);role='maker' if stage=='maker-recommend' else 'checker'
    reasons=permissions(db,user,r)
    if reasons[role]:raise HTTPException(403,reasons[role])
    current=state(db,r)
    if role=='maker' and current!='open':raise HTTPException(409,'Recommendation already recorded.')
    expected=r.version
    changed=db.query(ReviewRecord).filter_by(id=r.id,version=expected).update({'version':expected+1},synchronize_session=False)
    if not changed:
        db.rollback();raise HTTPException(409,'Case changed concurrently; refresh before acting.')
    db.expire(r)
    if r.case_type=='expense_claim':
        from backend.app.api.cases import maker_recommend,checker_signoff
        c=db.get(Case,r.source_id)
        (maker_recommend if role=='maker' else checker_signoff)(c.claim_id,body.action,body.notes,db,user)
        r.status=c.status
    elif r.case_type=='circular_payment':
        from backend.app.api.transfer_reviews import decide as cycle_decide
        cycle_decide(r.source_id,stage,body,db,user)
        from backend.app.models.transfer import CycleReviewCase
        r.status=db.get(CycleReviewCase,r.source_id).status
    else:
        r.status=('maker_recommended_'+body.action) if role=='maker' else ('closed_approved' if body.action=='approve' else 'closed_rejected')
        if role=='maker':r.maker_id=user.id
        else:r.checker_id=user.id
        db.add(ReviewQueueEvent(review_id=r.id,action=stage+':'+body.action,actor_id=user.id,actor_email=user.email,notes=body.notes,prior_status=current,new_status=r.status))
    try:db.commit()
    except StaleDataError:
        db.rollback();raise HTTPException(409,'Case changed concurrently; refresh before acting.')
    return serialize(db,r,user,True)
