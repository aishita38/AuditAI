"""Shared review identity and immutable evidence; native case history is retained."""
from datetime import datetime
from sqlalchemy import Column,Integer,String,JSON,DateTime,Text,ForeignKey
from backend.app.db import Base


class ReviewRecord(Base):
    __tablename__='review_queue_records'
    id=Column(Integer,primary_key=True)
    source_key=Column(String(150),unique=True,nullable=False)
    case_type=Column(String(40),nullable=False,index=True)
    source_id=Column(Integer,nullable=True)
    severity=Column(String(20),nullable=False)
    reason=Column(Text,nullable=False)
    evidence=Column(JSON,nullable=False)
    related_records=Column(JSON,nullable=False,default=list)
    status=Column(String(50),nullable=False,default='open')
    maker_id=Column(Integer,ForeignKey('auth_users.id'),nullable=True)
    checker_id=Column(Integer,ForeignKey('auth_users.id'),nullable=True)
    excluded_actor_ids=Column(JSON,nullable=False,default=list)
    created_at=Column(DateTime,nullable=False,default=datetime.utcnow)
    version=Column(Integer,nullable=False,default=1)
    __mapper_args__={'version_id_col':version}


class ReviewQueueEvent(Base):
    __tablename__='review_queue_events'
    id=Column(Integer,primary_key=True)
    review_id=Column(Integer,ForeignKey('review_queue_records.id'),nullable=False,index=True)
    action=Column(String(60),nullable=False)
    actor_id=Column(Integer,ForeignKey('auth_users.id'),nullable=False)
    actor_email=Column(String(254),nullable=False)
    notes=Column(Text,nullable=False)
    prior_status=Column(String(50),nullable=True)
    new_status=Column(String(50),nullable=False)
    timestamp=Column(DateTime,nullable=False,default=datetime.utcnow)
