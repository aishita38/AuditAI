from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.db import get_db
from backend.app.auth.security import require_roles
from backend.app.models.transfer import BankTransfer
from backend.app.models.expense import ExpenseClaim, CaseAuditTrail
from backend.app.features.reconciliation import reconcile_payments

router=APIRouter(prefix='/api/v1/transfers',tags=['Payment reconciliation'])


@router.get('/reconciliation')
def reconciliation(db:Session=Depends(get_db), user=Depends(require_roles('maker','checker','admin'))):
    rows=db.query(BankTransfer).order_by(BankTransfer.timestamp).limit(5001).all()
    if len(rows)>5000: raise HTTPException(422,'Ledger exceeds supported scan size.')
    linked_ids={r.claim_id for r in rows if r.claim_id}
    claims={}
    for c in db.query(ExpenseClaim).filter(ExpenseClaim.claim_id.in_(linked_ids)).all():
        event=(db.query(CaseAuditTrail).filter_by(case_id=c.case.id,action='final_approved').order_by(CaseAuditTrail.timestamp.desc(),CaseAuditTrail.id.desc()).first()) if c.case else None
        claims[c.claim_id]=dict(amount=c.claimed_amount,status=c.status,currency=c.entity.currency.upper() if c.entity else None,approved_at=event.timestamp if event else None)
    items=reconcile_payments([dict(transaction_id=r.transaction_id,claim_id=r.claim_id,amount=str(r.amount),currency=r.currency,timestamp=r.timestamp,sender_account=r.sender_account,receiver_account=r.receiver_account) for r in rows],claims)
    for item in items:
        if item.get('approved_at'): item['approved_at']=item['approved_at'].isoformat()+'Z'
        for p in item['payments']: p['timestamp']=p['timestamp'].isoformat()+'Z'
    return dict(items=items,transfer_count=len(rows),unlinked_transfers=sum(not r.claim_id for r in rows))
