import json
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,Field,field_validator
from sqlalchemy.orm import Session
from backend.app.db import get_db
from backend.app.auth.security import require_roles
from backend.app.models.auth import AuthUser
from backend.app.models.expense import ExpenseClaim
from backend.app.models.policy import ClaimPolicy,ReviewerAuthority,PolicyAdminEvent
from backend.app.policy_service import run_checks
from backend.app.features.policy_rules import CONFIG

router=APIRouter(prefix='/api/v1/policies',tags=['Company policy'])


class Inputs(BaseModel):
    invoice_id:str|None=Field(default=None,max_length=100)
    invoice_series:str|None=Field(default=None,max_length=100)
    invoice_sequence:int|None=Field(default=None,ge=0)
    event_timestamp:datetime|None=None
    source_approver_id:str|None=Field(default=None,max_length=100)
    source_approver_limit:Decimal|None=Field(default=None,ge=0,max_digits=15,decimal_places=2)
    business_exception:bool=False

    @field_validator('event_timestamp')
    @classmethod
    def aware(cls,v):
        if v is not None and v.tzinfo is None: raise ValueError('A timezone is required')
        return v


class Authority(BaseModel):
    limit:Decimal=Field(ge=0,max_digits=15,decimal_places=2)


@router.get('')
def list_checks(offset:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=500),db:Session=Depends(get_db),user=Depends(require_roles('maker','checker','admin'))):
    rows=db.query(ClaimPolicy).filter(ClaimPolicy.result.isnot(None)).order_by(ClaimPolicy.claim_id)
    total=rows.count(); items=rows.offset(offset).limit(limit).all()
    return dict(config=CONFIG,total=total,items=[dict(claim_id=p.claim_id,**p.result) for p in items])


@router.post('/run')
def run(db:Session=Depends(get_db),user=Depends(require_roles('admin'))):
    result=run_checks(db,True); db.commit()
    return dict(checked=len(result),requires_review=sum(r['requires_review'] for r in result.values()))


@router.put('/claims/{claim_id}')
def inputs(claim_id:str,body:Inputs,db:Session=Depends(get_db),user=Depends(require_roles('admin'))):
    if not db.query(ExpenseClaim).filter_by(claim_id=claim_id).first(): raise HTTPException(404,'Claim not found')
    p=db.get(ClaimPolicy,claim_id)
    if not p: p=ClaimPolicy(claim_id=claim_id,inputs={}); db.add(p)
    values=body.model_dump(mode='json',exclude_unset=True)
    p.inputs={**(p.inputs or {}),**values}
    db.add(PolicyAdminEvent(actor_id=user.id,action='claim_policy_inputs',subject=claim_id,details=json.dumps(values)))
    db.commit()
    return dict(status='saved',message='Run policy checks to refresh findings.')


@router.get('/reviewers')
def reviewers(db:Session=Depends(get_db),user=Depends(require_roles('admin'))):
    limits={r.user_id:str(r.limit) for r in db.query(ReviewerAuthority).all()}
    return [dict(id=u.id,email=u.email,limit=limits.get(u.id,str(CONFIG['default_checker_limit']))) for u in db.query(AuthUser).filter(AuthUser.active.is_(True)).all() if 'checker' in (u.roles or [])]


@router.put('/authorities/{user_id}')
def authority(user_id:int,body:Authority,db:Session=Depends(get_db),user=Depends(require_roles('admin'))):
    target=db.get(AuthUser,user_id)
    if not target or 'checker' not in (target.roles or []): raise HTTPException(422,'Select an existing checker account')
    row=db.get(ReviewerAuthority,user_id)
    if not row: row=ReviewerAuthority(user_id=user_id,limit=body.limit); db.add(row)
    else: row.limit=body.limit
    db.add(PolicyAdminEvent(actor_id=user.id,action='checker_authority',subject=str(user_id),details=json.dumps({'limit':str(body.limit),'currency':'INR'})))
    db.commit(); return dict(user_id=user_id,limit=str(row.limit),currency='INR')
