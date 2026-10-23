"""Authenticated transfer import and explainable circular-payment screening."""
import csv
import io
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from backend.app.auth.security import require_roles
from backend.app.db import get_db
from backend.app.models.transfer import BankTransfer, CycleReviewCase
from backend.app.models.expense import ExpenseClaim
from backend.app.features.transfer_cycles import find_cycles

router = APIRouter(prefix='/api/v1/transfers', tags=['Bank transfers'])
FIELDS = ['transaction_id', 'sender_account', 'receiver_account', 'amount', 'currency', 'timestamp']


def parse_transfer(row):
    data = {k: str(row.get(k) or '').strip() for k in FIELDS}
    for key, limit in [('transaction_id',80),('sender_account',100),('receiver_account',100)]:
        if not data[key] or len(data[key]) > limit:
            raise ValueError(f'{key} must contain 1–{limit} characters')
    try:
        amount = Decimal(data['amount'])
        if not amount.is_finite() or amount <= 0 or amount >= Decimal('10000000000000000') or amount != amount.quantize(Decimal('.01')):
            raise ValueError('amount must be positive, finite, within 16 integer digits and at most 2 decimal places')
    except InvalidOperation:
        raise ValueError('Invalid amount')
    currency = data['currency'].upper()
    if not re.fullmatch('[A-Z]{3}', currency):
        raise ValueError('currency must be a three-letter code')
    ts = datetime.fromisoformat(data['timestamp'].replace('Z','+00:00'))
    if ts.tzinfo is None:
        raise ValueError('timestamp must include a timezone, e.g. +05:30 or Z')
    claim_id = str(row.get('claim_id') or '').strip() or None
    if claim_id and len(claim_id) > 50:
        raise ValueError('claim_id must contain at most 50 characters')
    return dict(data, amount=amount, currency=currency, timestamp=ts.astimezone(timezone.utc).replace(tzinfo=None), claim_id=claim_id)


@router.post('/upload')
async def upload(file: UploadFile = File(...), db: Session = Depends(get_db),
                 user=Depends(require_roles('admin'))):
    content = await file.read(2_000_001)
    if len(content) > 2_000_000:
        raise HTTPException(413, 'Maximum CSV size is 2 MB.')
    try:
        reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig')))
        if not set(FIELDS).issubset(reader.fieldnames or []):
            raise ValueError('Required columns: '+', '.join(FIELDS))
        rows = []
        for i, row in enumerate(reader, 2):
            if i > 5001:
                raise ValueError('Maximum 5,000 rows per upload')
            try:
                rows.append(parse_transfer(row))
            except (ValueError, TypeError) as exc:
                raise ValueError(f'CSV row {i}: {exc}') from exc
        if not rows:
            raise ValueError('CSV contains no transfers')
        if len({r['transaction_id'] for r in rows}) != len(rows):
            raise ValueError('Duplicate transaction IDs within upload')
    except (ValueError, UnicodeError, csv.Error) as exc:
        raise HTTPException(422, str(exc))
    claim_ids = {r['claim_id'] for r in rows if r['claim_id']}
    known = {r[0] for r in db.query(ExpenseClaim.claim_id).filter(ExpenseClaim.claim_id.in_(claim_ids)).all()} if claim_ids else set()
    if claim_ids - known:
        raise HTTPException(422, 'Unknown claim_id: '+', '.join(sorted(claim_ids-known))+'. No rows imported.')
    existing = {r.transaction_id:r for r in db.query(BankTransfer).filter(BankTransfer.transaction_id.in_([r['transaction_id'] for r in rows])).all()}
    for r in rows:
        old = existing.get(r['transaction_id'])
        if old and any(getattr(old,k) != r[k] for k in FIELDS + ['claim_id']):
            raise HTTPException(409, f'Transaction {r["transaction_id"]} already exists with different data. No rows imported.')
    new = [r for r in rows if r['transaction_id'] not in existing]
    if db.query(BankTransfer).count() + len(new) > 5000:
        raise HTTPException(422, 'Demo ledger limit is 5,000 transfers; no rows imported.')
    db.add_all([BankTransfer(**r, imported_by=user.id) for r in new])
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'A concurrent import changed these IDs. No rows imported; retry the upload.')
    from backend.app.automatic_checks import after_import
    return dict(imported=len(new), skipped=len(existing), checks=after_import(db,user,'transfers'))


@router.get('/cycles')
def cycles(window_days: int = Query(7, ge=1, le=30), max_hops: int = Query(4, ge=2, le=6),
           db: Session = Depends(get_db), user=Depends(require_roles('maker','checker','admin'))):
    rows=db.query(BankTransfer).order_by(BankTransfer.timestamp).limit(5001).all()
    if len(rows)>5000:
        raise HTTPException(422, 'Ledger exceeds supported scan size; narrow the dataset before screening.')
    import hashlib
    import json
    result = find_cycles([{k:getattr(r,k) for k in FIELDS + ['claim_id']} for r in rows], window_days, max_hops)
    cases = {c.cycle_key:c for c in db.query(CycleReviewCase).all()}
    for cycle in result['cycles']:
        key = hashlib.sha256(json.dumps(sorted(cycle['transaction_ids'])).encode()).hexdigest()
        case = cases.get(key)
        cycle['case_id'] = case.id if case else None
        cycle['case_status'] = case.status if case else None
    return result
