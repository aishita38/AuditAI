from datetime import datetime
from sqlalchemy import Column,String,JSON,DateTime,Integer,ForeignKey,Numeric,Text
from backend.app.db import Base


class ClaimPolicy(Base):
    __tablename__='claim_policy_checks'
    claim_id=Column(String(50),ForeignKey('expense_claims.claim_id'),primary_key=True)
    inputs=Column(JSON,nullable=False,default=dict)
    result=Column(JSON,nullable=True)
    checked_at=Column(DateTime,nullable=True)


class ReviewerAuthority(Base):
    __tablename__='reviewer_authorities'
    user_id=Column(Integer,ForeignKey('auth_users.id'),primary_key=True)
    limit=Column(Numeric(15,2),nullable=False)


class PolicyAdminEvent(Base):
    __tablename__='policy_admin_events'
    id=Column(Integer,primary_key=True)
    actor_id=Column(Integer,ForeignKey('auth_users.id'),nullable=False)
    action=Column(String(80),nullable=False)
    subject=Column(String(100),nullable=False)
    details=Column(Text,nullable=False)
    timestamp=Column(DateTime,nullable=False,default=datetime.utcnow)
