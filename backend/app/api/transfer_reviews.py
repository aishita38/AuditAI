"""Maker/checker cases with immutable transfer evidence and an append-only trail."""
import hashlib
import json
from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from backend.app.db import get_db
from backend.app.auth.security import require_roles, has_role, is_claim_participant
from backend.app.models.expense import ExpenseClaim
from backend.app.models.transfer import BankTransfer, CycleReviewCase, CycleReviewEvent
from backend.app.features.transfer_cycles import find_cycles
from backend.app.api.transfers import FIELDS

router=APIRouter(prefix='/api/v1/transfer-reviews', tags=['Transfer review cases'])


class SubmitCycle(BaseModel):
    transaction_ids: list[str] = Field(min_length=2, max_length=6)
    window_days: int = Field(default=7, ge=1, le=30)
    max_hops: int = Field(default=4, ge=2, le=6)


class Decision(BaseModel):
    action: Literal['approve','reject']
    notes: str = Field(min_length=5, max_length=5000)

    @field_validator('notes')
    @classmethod
    def meaningful_notes(cls,value):
        if len(value.strip())<5: raise ValueError('Provide at least 5 non-whitespace characters')
        return value.strip()


def review_block(db, user, case, role):
    if not has_role(user,role): return f'Your account does not have the {role} role.'
    transfers=db.query(BankTransfer).filter(BankTransfer.transaction_id.in_(case.evidence['transaction_ids'])).all()
    if any(t.imported_by==user.id for t in transfers): return 'A transfer importer cannot review their own evidence.'
    claim_ids={t.claim_id for t in transfers if t.claim_id}
    for claim in db.query(ExpenseClaim).filter(ExpenseClaim.claim_id.in_(claim_ids)).all():
        if is_claim_participant(db,user,claim): return 'A linked claim owner or contributor cannot review this cycle.'
    if role=='maker':
        if case.status!='open': return 'The maker recommendation is already recorded or this case is closed.'
    else:
        if case.status not in ('maker_recommended_approve','maker_recommended_reject'): return 'A maker recommendation is required first.'
        if case.maker_id==user.id: return 'The checker must be different from the maker.'
    return None


def payload(db, case, user):
    events=db.query(CycleReviewEvent).filter_by(case_id=case.id).order_by(CycleReviewEvent.id).all()
    maker=review_block(db,user,case,'maker'); checker=review_block(db,user,case,'checker')
    return dict(id=case.id,status=case.status,evidence=case.evidence,maker_id=case.maker_id,checker_id=case.checker_id,
        created_at=case.created_at.isoformat()+'Z',permissions=dict(can_make=maker is None,can_check=checker is None,maker_reason=maker,checker_reason=checker),
        audit_trail=[dict(id=e.id,action=e.action,actor=e.actor_email,prior_status=e.prior_status,new_status=e.new_status,notes=e.notes,timestamp=e.timestamp.isoformat()+'Z') for e in events])


@router.post('')
def send_to_review(body: SubmitCycle, db: Session=Depends(get_db), user=Depends(require_roles('maker','checker','admin'))):
    ids=body.transaction_ids
    if len(set(ids))!=len(ids): raise HTTPException(422,'Repeated transfer IDs are not allowed.')
    rows=db.query(BankTransfer).filter(BankTransfer.transaction_id.in_(ids)).all()
    if len(rows)!=len(ids): raise HTTPException(404,'One or more transfers do not exist.')
    result=find_cycles([{k:getattr(r,k) for k in FIELDS+['claim_id']} for r in rows], body.window_days, body.max_hops)
    cycle=next((c for c in result['cycles'] if set(c['transaction_ids'])==set(ids)),None)
    if not cycle: raise HTTPException(422,'These transfers do not form a cycle within the selected settings.')
    key=hashlib.sha256(json.dumps(sorted(ids)).encode()).hexdigest()
    old=db.query(CycleReviewCase).filter_by(cycle_key=key).first()
    if old: return payload(db,old,user)
    cycle['window_days']=body.window_days; cycle['max_hops']=body.max_hops
    case=CycleReviewCase(cycle_key=key,evidence=cycle,created_by=user.id,status='open')
    db.add(case)
    try:
        db.flush()
        db.add(CycleReviewEvent(case_id=case.id,action='created',actor_id=user.id,actor_email=user.email,prior_status=None,new_status='open',notes='Cycle submitted for review; evidence and screening settings preserved.'))
        db.commit()
    except IntegrityError:
        db.rollback()
        case=db.query(CycleReviewCase).filter_by(cycle_key=key).first()
        if not case: raise HTTPException(409,'Concurrent submission; retry.')
    return payload(db,case,user)


@router.get('')
def list_reviews(db: Session=Depends(get_db),user=Depends(require_roles('maker','checker','admin'))):
    return [payload(db,c,user) for c in db.query(CycleReviewCase).order_by(CycleReviewCase.id.desc()).all()]


@router.post('/{case_id}/{stage}')
def decide(case_id:int,stage:Literal['maker-recommend','checker-signoff'],body:Decision,
           db:Session=Depends(get_db),user=Depends(require_roles('maker','checker'))):
    case=db.query(CycleReviewCase).filter_by(id=case_id).first()
    if not case: raise HTTPException(404,'Review case not found.')
    role='maker' if stage=='maker-recommend' else 'checker'
    reason=review_block(db,user,case,role)
    if reason: raise HTTPException(403,reason)
    prior=case.status
    case.status=('maker_recommended_'+body.action) if role=='maker' else ('closed_approved' if body.action=='approve' else 'closed_rejected')
    if role=='maker': case.maker_id=user.id
    else: case.checker_id=user.id
    case.updated_at=datetime.utcnow()
    db.add(CycleReviewEvent(case_id=case.id,action=stage+':'+body.action,actor_id=user.id,actor_email=user.email,prior_status=prior,new_status=case.status,notes=body.notes))
    try: db.commit()
    except StaleDataError:
        db.rollback()
        raise HTTPException(409,'Another reviewer changed this case. Refresh before acting.')
    return payload(db,case,user)
