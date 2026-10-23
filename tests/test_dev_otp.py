import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.app.db import Base,get_db
from backend.app.api import dev_otp
from backend.app.api.auth import router as auth_router
from backend.app.models.auth import AuthUser,AuthSession
from backend.app.models import expense


@pytest.fixture
def environment(monkeypatch):
    monkeypatch.setenv('AUDITAI_DEV_OTP','1')
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine);factory=sessionmaker(bind=engine)
    app=FastAPI();app.include_router(dev_otp.router);app.include_router(auth_router)
    def database():
        with factory() as db:yield db
    app.dependency_overrides[get_db]=database
    with factory() as db:
        db.add(AuthUser(id=1,email='maker@auditai.example',employee_id='EMP014',display_name='Maker',roles=['employee','maker'],password_hash='unused'));db.commit()
    dev_otp._challenges.clear();dev_otp._requests.clear()
    with TestClient(app,base_url='http://127.0.0.1:8000',client=('127.0.0.1',50000)) as client:
        yield client,factory,app
    dev_otp._challenges.clear();dev_otp._requests.clear();engine.dispose()


def generate(client):
    r=client.post('/api/v1/auth/dev-otp/generate',json={'email':'maker@auditai.example'})
    assert r.status_code==200
    assert r.headers['cache-control']=='no-store'
    return r.json()


def test_developer_otp_creates_normal_revocable_session_and_is_single_use(environment):
    client,factory,_=environment
    status=client.get('/api/v1/auth/dev-otp/status').json()
    assert status['enabled'] and status['accounts'][0]['roles']==['employee','maker']
    challenge=generate(client)
    assert len(challenge['otp'])==6 and challenge['otp'].isdigit()
    assert 'otp' not in dev_otp._challenges[challenge['challenge_id']]
    payload={'challenge_id':challenge['challenge_id'],'otp':challenge['otp'],'roles':['admin'],'email':'admin@auditai.example'}
    r=client.post('/api/v1/auth/dev-otp/verify',json=payload)
    assert r.status_code==200 and r.json()['user']['roles']==['employee','maker']
    headers={'Authorization':'Bearer '+r.json()['access_token']}
    assert client.get('/api/v1/auth/me',headers=headers).status_code==200
    assert client.post('/api/v1/auth/dev-otp/verify',json=payload).status_code==401
    assert client.post('/api/v1/auth/logout',headers=headers).status_code==200
    assert client.get('/api/v1/auth/me',headers=headers).status_code==401
    with factory() as db:assert db.query(AuthSession).count()==1


def test_expiry_replacement_and_wrong_attempt_limit(environment,monkeypatch):
    client,_,_=environment
    now=[100.0];monkeypatch.setattr(dev_otp,'_clock',lambda:now[0])
    first=generate(client);second=generate(client)
    assert client.post('/api/v1/auth/dev-otp/verify',json={k:first[k] for k in ['challenge_id','otp']}).status_code==401
    wrong='000000' if second['otp']!='000000' else '999999'
    for _ in range(5):assert client.post('/api/v1/auth/dev-otp/verify',json={'challenge_id':second['challenge_id'],'otp':wrong}).status_code==401
    assert client.post('/api/v1/auth/dev-otp/verify',json={k:second[k] for k in ['challenge_id','otp']}).status_code==401
    third=generate(client);now[0]+=121
    assert client.post('/api/v1/auth/dev-otp/verify',json={k:third[k] for k in ['challenge_id','otp']}).status_code==401


@pytest.mark.parametrize('reason',['disabled','remote','origin','host'])
def test_developer_login_is_unavailable_outside_opt_in_loopback(environment,monkeypatch,reason):
    client,_,app=environment
    if reason=='disabled':monkeypatch.delenv('AUDITAI_DEV_OTP')
    if reason=='remote':client=TestClient(app,base_url='http://127.0.0.1:8000',client=('10.0.0.5',50000),headers={'x-forwarded-for':'127.0.0.1'})
    if reason=='origin':client.headers['origin']='https://untrusted.example'
    if reason=='host':client.headers['host']='untrusted.example'
    assert client.get('/api/v1/auth/dev-otp/status').json()=={'enabled':False,'accounts':[]}
    assert client.post('/api/v1/auth/dev-otp/generate',json={'email':'maker@auditai.example'}).status_code==404


def test_unknown_inactive_and_rate_limited_accounts(environment):
    client,factory,_=environment
    assert client.post('/api/v1/auth/dev-otp/generate',json={'email':'missing@auditai.example'}).status_code==401
    challenge=generate(client)
    with factory() as db:
        db.get(AuthUser,1).active=False;db.commit()
    assert client.post('/api/v1/auth/dev-otp/verify',json={k:challenge[k] for k in ['challenge_id','otp']}).status_code==401
    assert client.post('/api/v1/auth/dev-otp/generate',json={'email':'maker@auditai.example'}).status_code==401
    with factory() as db:
        db.get(AuthUser,1).active=True;db.commit()
    dev_otp._requests.clear()
    for _ in range(30):generate(client)
    assert client.post('/api/v1/auth/dev-otp/generate',json={'email':'maker@auditai.example'}).status_code==429
