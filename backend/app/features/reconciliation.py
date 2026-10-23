"""Payment review signals; no automated finding or claim mutation."""
from collections import defaultdict
from decimal import Decimal


def reconcile_payments(transfers, claims):
    groups=defaultdict(list)
    for t in transfers:
        if t['claim_id']: groups[t['claim_id']].append(t)
    result=[]
    for claim_id, payments in groups.items():
        c=claims.get(claim_id)
        if not c:
            result.append(dict(claim_id=claim_id,flags=['linked_claim_missing'],payments=payments)); continue
        flags=[]; currencies={p['currency'] for p in payments}
        total=sum((Decimal(str(p['amount'])) for p in payments),Decimal('0'))
        if not c['currency']: flags.append('claim_currency_unavailable')
        elif currencies!={c['currency']}: flags.append('currency_mismatch')
        elif total!=Decimal(str(c['amount'])): flags.append('payment_total_mismatch')
        if c['status']=='rejected': flags.append('payment_for_rejected_claim')
        if len(payments)>1: flags.append('multiple_payments_for_claim')
        if c['approved_at']:
            if any(p['timestamp']<c['approved_at'] for p in payments): flags.append('payment_before_checker_approval')
        elif c['status']=='approved': flags.append('checker_approval_time_unavailable')
        else: flags.append('payment_without_checker_approval')
        result.append(dict(claim_id=claim_id,claim_status=c['status'],claim_amount=str(c['amount']),claim_currency=c['currency'],
            paid_total=str(total) if len(currencies)==1 else None,payment_currencies=sorted(currencies),
            approved_at=c['approved_at'],flags=flags,payments=payments))
    return result
