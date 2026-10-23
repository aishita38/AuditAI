import json
from datetime import datetime
from decimal import Decimal
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import lazyload,load_only
from backend.app.models.review_queue import ReviewRecord,ReviewQueueEvent
from backend.app.models.expense import Case,CaseAuditTrail,ExpenseClaim,FraudPrediction,OcrResult
from backend.app.models.transfer import BankTransfer,CycleReviewCase,CycleReviewEvent
from backend.app.auth.security import review_block_reason,has_role,is_claim_participant
from backend.app.models.policy import ClaimPolicy


def freeze(value): return json.loads(json.dumps(jsonable_encoder(value,custom_encoder={Decimal:str})))


def adopt_existing(db):
    """Add queue identities without moving/deleting native cases or audit trails."""
    existing={r.source_key:r for r in db.query(ReviewRecord).options(load_only(ReviewRecord.id,ReviewRecord.source_key,ReviewRecord.status)).filter(ReviewRecord.case_type.in_(['expense_claim','circular_payment'])).all()}
    policies={p.claim_id:p for p in db.query(ClaimPolicy).all()}
    added=0
    for case in db.query(Case).options(lazyload("*")).all():
        key=f'expense:{case.id}'
        if key in existing:
            existing[key].status=case.status; continue
        claim=case.claim
        if claim is None: continue
        prediction=claim.prediction; ocr=claim.receipt.ocr_result if claim.receipt else None
        score=float(prediction.combined_fraud_score or 0) if prediction else None
        evidence=dict(claim=dict(claim_id=claim.claim_id,employee_id=claim.employee_id,employee_name=claim.employee_name,vendor_name=claim.vendor_name,claimed_amount=str(claim.claimed_amount),claimed_date=str(claim.claimed_date),description=claim.description),
            receipt=dict(receipt_id=claim.receipt.receipt_id,upload_status=claim.receipt.upload_status,extracted_amount=str(ocr.extracted_amount) if ocr and ocr.extracted_amount is not None else None,raw_text=ocr.raw_ocr_text if ocr else None) if claim.receipt else None,
            prediction=dict(score=score,feature_values=prediction.feature_values,shap_values=prediction.shap_values) if prediction else None,
            snapshot_note='Evidence captured when this existing case entered the shared queue; original case history is retained.',native_created_at=case.created_at.isoformat()+'Z')
        evidence['payments'] = [dict(transaction_id=t.transaction_id, sender_account=t.sender_account, receiver_account=t.receiver_account, amount=str(t.amount), currency=t.currency, timestamp=t.timestamp.isoformat()+'Z', claim_id=t.claim_id) for t in db.query(BankTransfer).filter_by(claim_id=claim.claim_id).all()]
        reason='Expense claim requires review'
        if prediction and (prediction.feature_values or {}).get('_holiday_policy_flag'): reason='Holiday policy requires expense review'
        policy=policies.get(claim.claim_id)
        if policy and policy.result:
            evidence['policy']=policy.result
            related_ids = {cid for check in policy.result.get('checks', []) if check.get('status') == 'review' for cid in check.get('related_claims', [])}
            evidence['supporting_claims'] = [dict(claim_id=c.claim_id, employee_id=c.employee_id, employee_name=c.employee_name, vendor_name=c.vendor_name, claimed_amount=str(c.claimed_amount), claimed_date=str(c.claimed_date), description=c.description) for c in db.query(ExpenseClaim).filter(ExpenseClaim.claim_id.in_(related_ids)).all()]
            evidence['trigger_fields'] = sorted({field for check in policy.result.get('checks', []) if check.get('status') == 'review' for field in check.get('fields', [])})
            triggers=[c['code'].replace('_',' ') for c in policy.result['checks'] if c['status']=='review']
            if triggers: reason='Policy review: '+', '.join(triggers[:4])
        db.add(ReviewRecord(source_key=key,source_id=case.id,case_type='expense_claim',severity='high' if score is not None and score>=.7 else 'medium',reason=reason,evidence=freeze(evidence),related_records=[dict(kind='claim',id=claim.claim_id)],status=case.status))
        added+=1
    for case in db.query(CycleReviewCase).all():
        key=f'circular:{case.id}'
        if key in existing:
            existing[key].status=case.status; continue
        e=case.evidence
        db.add(ReviewRecord(source_key=key,source_id=case.id,case_type='circular_payment',severity='high',reason=f"{len(e['transaction_ids'])}-transfer loop; {e['return_ratio']:.0%} returned",evidence=freeze(e),related_records=[],status=case.status))
        added+=1
    db.flush()
    return added


def native(db,r):
    if r.case_type=='expense_claim': return db.get(Case,r.source_id)
    if r.case_type=='circular_payment': return db.get(CycleReviewCase,r.source_id)
    return None


def permissions(db,user,r):
    if r.case_type=='expense_claim':
        c=native(db,r)
        if not c or not c.claim: return dict(maker='Source claim not found; review actions unavailable.', checker='Source claim not found; review actions unavailable.')
        return {role:review_block_reason(db,user,c.claim,role) for role in ['maker','checker']}
    if r.case_type=='circular_payment':
        from backend.app.api.transfer_reviews import review_block
        if not native(db,r): return dict(maker='Source case not found; review actions unavailable.', checker='Source case not found; review actions unavailable.')
        return {role:review_block(db,user,native(db,r),role) for role in ['maker','checker']}
    reasons={}
    for role in ['maker','checker']:
        reason=None
        if not has_role(user,role): reason=f'Your account does not have the {role} role.'
        elif user.id in (r.excluded_actor_ids or []): reason='A contributor cannot review their own evidence.'
        elif role=='maker' and r.status!='open': reason='A recommendation already exists or the case is closed.'
        elif role=='checker' and r.status not in ['maker_recommended_approve','maker_recommended_reject']: reason='A maker recommendation is required first.'
        elif role=='checker' and r.maker_id==user.id: reason='Checker must be different from maker.'
        if not reason:
            for link in r.related_records or []:
                if link['kind']=='claim':
                    claim=db.query(ExpenseClaim).filter_by(claim_id=link['id']).first()
                    if claim and is_claim_participant(db,user,claim): reason='Linked claim owner or contributor cannot review this case.'
        reasons[role]=reason
    return reasons


def state(db,r):
    c=native(db,r)
    return c.status if c else r.status


def serialize(db,r,user,detail=False):
    c=native(db,r); status=c.status if c else r.status
    out=dict(id=r.id,case_type=r.case_type,severity=r.severity,reason=r.reason,status=status,created_at=r.created_at.isoformat()+'Z',maker_id=c.maker_id if c else r.maker_id,checker_id=c.checker_id if c else r.checker_id)
    if not detail: return out
    history=[]
    if r.case_type=='expense_claim':
        history=[dict(id=f'expense-{e.id}',action=e.action,actor=e.performed_by,notes=e.notes,timestamp=e.timestamp.isoformat()+'Z') for e in db.query(CaseAuditTrail).filter_by(case_id=r.source_id).all()]
    elif r.case_type=='circular_payment':
        history=[dict(id=f'cycle-{e.id}',action=e.action,actor=e.actor_email,notes=e.notes,prior_status=e.prior_status,new_status=e.new_status,timestamp=e.timestamp.isoformat()+'Z') for e in db.query(CycleReviewEvent).filter_by(case_id=r.source_id).all()]
    history += [dict(id=f'queue-{e.id}',action=e.action,actor=e.actor_email,notes=e.notes,prior_status=e.prior_status,new_status=e.new_status,timestamp=e.timestamp.isoformat()+'Z') for e in db.query(ReviewQueueEvent).filter_by(review_id=r.id).all()]
    links=list(r.related_records or [])
    claim_ids={link['id'] for link in links if link['kind']=='claim'}
    if r.case_type=='circular_payment':
        ids=r.evidence['transaction_ids']
        transfers=db.query(BankTransfer).filter(BankTransfer.transaction_id.in_(ids)).all()
        for t in transfers:
            if t.claim_id: claim_ids.add(t.claim_id)
    if claim_ids:
        for cid in sorted(claim_ids):
            if not any(l['kind']=='claim' and l['id']==cid for l in links): links.append(dict(kind='claim',id=cid))
        for t in db.query(BankTransfer).filter(BankTransfer.claim_id.in_(claim_ids)).all():
            links.append(dict(kind='transfer',id=t.transaction_id,claim_id=t.claim_id,amount=str(t.amount),currency=t.currency))
    reasons=permissions(db,user,r)
    out.update(evidence=r.evidence,related_records=links,audit_trail=sorted(history,key=lambda e:(e['timestamp'],e['id'])),permissions=dict(can_make=reasons['maker'] is None,can_check=reasons['checker'] is None,maker_reason=reasons['maker'],checker_reason=reasons['checker']))
    return out
