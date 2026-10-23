from datetime import datetime
from sqlalchemy import Column, String, JSON, Boolean, DateTime, Text
from backend.app.db import Base


class MasterFinding(Base):
    __tablename__='master_findings'
    id=Column(String(64),primary_key=True)
    dataset=Column(String(20),nullable=False,index=True)
    rule_id=Column(String(80),nullable=False,index=True)
    severity=Column(String(20),nullable=False)
    explanation=Column(Text,nullable=False)
    evidence=Column(JSON,nullable=False)
    involved_record_ids=Column(JSON,nullable=False)
    excluded_actor_ids=Column(JSON,nullable=False,default=list)
    active=Column(Boolean,nullable=False,default=True,index=True)
    created_at=Column(DateTime,nullable=False,default=datetime.utcnow)
