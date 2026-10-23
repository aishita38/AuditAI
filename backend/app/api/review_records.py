"""Live record lookup is separate from immutable case evidence."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, lazyload
from backend.app.db import get_db
from backend.app.auth.security import require_roles
from backend.app.models.expense import ExpenseClaim
from backend.app.models.transfer import BankTransfer
from backend.app.models.master_data import VendorMaster, EmployeeMaster, PayrollPayment

router = APIRouter(prefix='/api/v1/review-records', tags=['Review records'])
reviewer = Depends(require_roles('maker', 'checker', 'admin'))
MODELS = {'claim': (ExpenseClaim, 'claim_id'), 'transfer': (BankTransfer, 'transaction_id'),
          'vendor': (VendorMaster, 'vendor_id'), 'employee': (EmployeeMaster, 'employee_id'),
          'payroll_payment': (PayrollPayment, 'payment_id')}


class Reference(BaseModel):
    kind: Literal['claim', 'transfer', 'vendor', 'employee', 'payroll_payment']
    id: str = Field(min_length=1, max_length=100)


class Lookup(BaseModel):
    records: list[Reference] = Field(max_length=1000)


@router.post('/lookup')
def lookup(body: Lookup, db: Session = Depends(get_db), user=reviewer):
    found = set()
    for kind, (model, key) in MODELS.items():
        ids = {r.id for r in body.records if r.kind == kind}
        if ids:
            found.update((kind, value) for (value,) in db.query(getattr(model, key)).filter(getattr(model, key).in_(ids)).all())
    return [{'kind': r.kind, 'id': r.id, 'exists': (r.kind, r.id) in found} for r in body.records]


@router.get('/{kind}/{record_id}')
def detail(kind: str, record_id: str, db: Session = Depends(get_db), user=reviewer):
    if kind not in MODELS:
        raise HTTPException(404, 'Not found')
    model, key = MODELS[kind]
    row = db.query(model).options(lazyload('*')).filter(getattr(model, key) == record_id).first()
    if not row:
        raise HTTPException(404, 'Not found')
    # Only business fields; internal IDs and importer identities are not evidence.
    return {c.name: getattr(row, c.name) for c in model.__table__.columns if c.name not in ('id', 'imported_by')}
