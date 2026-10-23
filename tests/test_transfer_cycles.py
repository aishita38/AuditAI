import csv
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.transfers import router, parse_transfer
from backend.app.auth.security import get_current_user
from backend.app.db import Base, get_db
from backend.app.features.transfer_cycles import find_cycles
from backend.app.models.auth import AuthUser
from backend.app.models import expense  # register referenced tables


SAMPLE = Path(__file__).resolve().parents[1] / 'frontend/public/sample-transfers.csv'


def sample():
    with SAMPLE.open() as f:
        return [parse_transfer(r) for r in csv.DictReader(f)]


def test_sample_has_two_cycles_and_preserves_evidence():
    result=find_cycles(sample())
    assert [c['transaction_ids'] for c in result['cycles']] == [
        ['DEMO-CYCLE-001','DEMO-CYCLE-002','DEMO-CYCLE-003'],
        ['DEMO-RETURN-001','DEMO-RETURN-002'],
    ]
    c=result['cycles'][0]
    assert c['accounts']==['TEST-A','TEST-B','TEST-C','TEST-A']
    assert c['return_ratio']==.95 and c['elapsed_hours']==24
    assert c['transfers'][0]['timestamp']=='2026-03-01T03:30:00Z'
    assert not result['search_limited']
    assert len(find_cycles(sample(),window_days=30)['cycles'])==3
    assert len(find_cycles(sample(),max_hops=2)['cycles'])==1


def test_backward_time_self_transfer_and_search_limit():
    rows=sample()[:3]
    rows[2]['timestamp']=rows[0]['timestamp']+timedelta(hours=1)
    rows[1]['timestamp']=rows[0]['timestamp']-timedelta(hours=1)
    assert find_cycles(rows)['cycles']==[]
    self_edge=dict(rows[0],receiver_account='TEST-A')
    assert find_cycles([self_edge])['cycles']==[]
    assert find_cycles(sample(),budget=1)['search_limited']
    assert find_cycles(sample(),max_results=1)['search_limited']


@pytest.mark.parametrize('field,value',[
    ('amount','NaN'),('amount','Infinity'),('amount','0'),('amount','-1'),
    ('amount','1.001'),('timestamp','2026-01-01'),('currency','IN'),('sender_account',''),
])
def test_invalid_rows(field,value):
    row=dict(transaction_id='T1',sender_account='001',receiver_account='002',amount='1.00',currency='INR',timestamp='2026-01-01T10:00:00Z')
    row[field]=value
    with pytest.raises(ValueError): parse_transfer(row)


def test_authenticated_import_atomicity_and_reviewer_visibility():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory=sessionmaker(bind=engine)
    app=FastAPI(); app.include_router(router)
    def database():
        with factory() as db: yield db
    app.dependency_overrides[get_db]=database
    with factory() as db:
        db.add(AuthUser(id=1,email='admin@auditai.example',employee_id='A',display_name='Admin',roles=['admin'],password_hash='unused')); db.commit()
    client=TestClient(app)
    assert client.get('/api/v1/transfers/cycles').status_code in (401,403)
    user=SimpleNamespace(id=1,roles=['admin'])
    app.dependency_overrides[get_current_user]=lambda:user
    raw=SAMPLE.read_bytes()
    def upload(blob): return client.post('/api/v1/transfers/upload',files={'file':('test.csv',blob,'text/csv')})
    first=upload(raw).json();assert (first['imported'],first['skipped'])==(13,0)
    assert first['checks']['stages'][0]['circular_findings']==2
    second=upload(raw).json();assert (second['imported'],second['skipped'])==(0,13)
    assert len(client.get('/api/v1/transfers/cycles').json()['cycles'])==2
    assert upload(raw.replace(b'100000.00',b'100001.00')).status_code==409
    invalid=b'transaction_id,sender_account,receiver_account,amount,currency,timestamp\nNEW,A,B,12,INR,2026-01-01T00:00:00Z\nBAD,B,C,-1,INR,2026-01-01T01:00:00Z\n'
    assert upload(invalid).status_code==422
    assert client.get('/api/v1/transfers/cycles').json()['transfer_count']==13
    user.roles=['maker']
    assert upload(raw).status_code==403
    assert client.get('/api/v1/transfers/cycles').status_code==200
    user.roles=['employee']
    assert client.get('/api/v1/transfers/cycles').status_code==403
    engine.dispose()
