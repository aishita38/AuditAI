"""Separate transfer ledger: expense submissions are not bank transfers."""
from datetime import datetime
from sqlalchemy import Column, String, Numeric, DateTime, Integer, ForeignKey, JSON, Text
from backend.app.db import Base


class BankTransfer(Base):
    __tablename__ = 'bank_transfers'
    transaction_id = Column(String(80), primary_key=True)
    sender_account = Column(String(100), nullable=False, index=True)
    receiver_account = Column(String(100), nullable=False, index=True)
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    imported_by = Column(Integer, ForeignKey('auth_users.id'), nullable=False)
    claim_id = Column(String(50), ForeignKey('expense_claims.claim_id'), nullable=True, index=True)


class CycleReviewCase(Base):
    __tablename__ = 'cycle_review_cases'
    id = Column(Integer, primary_key=True)
    cycle_key = Column(String(64), nullable=False, unique=True)
    evidence = Column(JSON, nullable=False)
    status = Column(String(50), nullable=False, default='open')
    created_by = Column(Integer, ForeignKey('auth_users.id'), nullable=False)
    maker_id = Column(Integer, ForeignKey('auth_users.id'), nullable=True)
    checker_id = Column(Integer, ForeignKey('auth_users.id'), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    version = Column(Integer, nullable=False, default=1)
    __mapper_args__ = {'version_id_col': version}


class CycleReviewEvent(Base):
    __tablename__ = 'cycle_review_events'
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey('cycle_review_cases.id'), nullable=False, index=True)
    action = Column(String(60), nullable=False)
    actor_id = Column(Integer, ForeignKey('auth_users.id'), nullable=False)
    actor_email = Column(String(254), nullable=False)
    prior_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False)
    notes = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
