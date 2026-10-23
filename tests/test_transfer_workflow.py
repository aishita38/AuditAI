from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.app.db import Base,get_db
from backend.app.auth.security import get_current_user
from backend.app.models.auth import AuthUser,ClaimContributor
from backend.app.models.expense import ExpenseClaim,Entity,Case,CaseAuditTrail
from backend.app.models.transfer import BankTransfer,CycleReviewCase,CycleReviewEvent
from backend.app.api.transfers import router as transfers
from backend.app.api.transfer_reviews import router as reviews
from backend.app.api.reconciliation import router as reconciliation
from backend.app.features.reconciliation import reconcile_payments
from backend.app.transfer_migrations import migrate_transfer_claim_link
from tests.test_transfer_cycles import SAMPLE


@pytest.fixture
def environment():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine); factory=sessionmaker(bind=engine)
    app=FastAPI()
    for router in [transfers,reviews,reconciliation]: app.include_router(router)
    def db_session():
        with factory() as db: yield db
    user=SimpleNamespace(id=1,roles=['admin'],email='admin@auditai.example',employee_id='ADMIN')
    app.dependency_overrides[get_db]=db_session
    app.dependency_overrides[get_current_user]=lambda:user
    with factory() as db:
        for i in range(1,5): db.add(AuthUser(id=i,email=f'u{i}@auditai.example',employee_id=f'E{i}',display_name=f'U{i}',roles=[],password_hash='unused'))
        entity=Entity(name='Synthetic IN',currency='INR'); db.add(entity); db.flush()
        for i,status in enumerate(['approved','rejected','approved','approved','approved']):
            claim=ExpenseClaim(claim_id=f'TEST-C{i}',employee_id='OWNER',employee_name='Synthetic Owner',claimed_amount=4500,vendor_name='Synthetic Vendor',claimed_date=date(2026,3,1),status=status,entity_id=entity.id)
            case=Case(claim_id=claim.claim_id,status='closed_approved' if status=='approved' else 'closed_rejected',maker_id='2',checker_id='3')
            db.add_all([claim,case]); db.flush()
            db.add(CaseAuditTrail(case_id=case.id,action='final_approved' if status=='approved' else 'final_rejected',performed_by='checker: synthetic',notes='Isolated test fixture',timestamp=datetime(2026,3,2,10)))
        db.commit()
    yield TestClient(app),factory,user
    engine.dispose()


def test_cycle_case_dedup_sequence_conflicts_and_append_only_trail(environment):
    client,factory,user=environment
    client.post('/api/v1/transfers/upload',files={'file':('demo.csv',SAMPLE.read_bytes(),'text/csv')}).raise_for_status()
    body=dict(transaction_ids=['DEMO-CYCLE-001','DEMO-CYCLE-002','DEMO-CYCLE-003'])
    case=client.post('/api/v1/transfer-reviews',json=body).json(); case_id=case['id']
    assert client.post('/api/v1/transfer-reviews',json=body).json()['id']==case_id
    assert len(client.get('/api/v1/transfer-reviews').json())==1
    assert len(case['audit_trail'])==1 and not case['permissions']['can_make']
    user.roles=['maker']; assert client.post(f'/api/v1/transfer-reviews/{case_id}/maker-recommend',json={'action':'approve','notes':'My own upload'}).status_code==403
    user.id=2; user.email='maker@auditai.example'; user.roles=['maker','checker']
    path=f'/api/v1/transfer-reviews/{case_id}'
    assert client.post(path+'/checker-signoff',json={'action':'approve','notes':'Too early'}).status_code==403
    assert client.post(path+'/maker-recommend',json={'action':'approve','notes':'     '}).status_code==422
    assert client.post(path+'/maker-recommend',json={'action':'reject','notes':'Unexplained return'}).status_code==200
    assert client.post(path+'/maker-recommend',json={'action':'approve','notes':'Repeat attempt'}).status_code==403
    assert client.post(path+'/checker-signoff',json={'action':'reject','notes':'Same reviewer'}).status_code==403
    user.id=3; user.email='checker@auditai.example'; user.roles=['checker']
    closed=client.post(path+'/checker-signoff',json={'action':'reject','notes':'Concern remains after review'}).json()
    assert closed['status']=='closed_rejected' and len(closed['audit_trail'])==3
    assert closed['audit_trail'][-1]['prior_status']=='maker_recommended_reject'
    assert client.post(path+'/checker-signoff',json={'action':'approve','notes':'Cannot alter closed case'}).status_code==403
    assert client.post('/api/v1/transfer-reviews',json={'transaction_ids':['DEMO-OPEN-001','DEMO-OPEN-002']}).status_code==422
    user.roles=['employee']
    assert client.get('/api/v1/transfer-reviews').status_code==403
    assert client.get('/api/v1/transfers/reconciliation').status_code==403


def test_reconciliation_examples_claim_validation_and_participant_block(environment):
    client,factory,user=environment
    header='transaction_id,sender_account,receiver_account,amount,currency,timestamp,claim_id\n'
    lines=[
      'PAY-OVER,A,B,45000,INR,2026-03-03T10:00:00Z,TEST-C0',
      'PAY-REJECT,A,C,4500,INR,2026-03-03T10:00:00Z,TEST-C1',
      'PAY-DUP1,A,D,4500,INR,2026-03-03T10:00:00Z,TEST-C2',
      'PAY-DUP2,A,D,4500,INR,2026-03-04T10:00:00Z,TEST-C2',
      'PAY-EARLY,A,E,4500,INR,2026-03-01T10:00:00Z,TEST-C3',
      'PAY-OK,A,F,4500,INR,2026-03-03T10:00:00Z,TEST-C4',
    ]
    def upload(content): return client.post('/api/v1/transfers/upload',files={'file':('test.csv',content.encode(),'text/csv')})
    assert upload(header+'\n'.join(lines)).status_code==200
    assert upload(header+'BAD,A,B,1,INR,2026-03-03T10:00:00Z,NO-CLAIM').status_code==422
    data=client.get('/api/v1/transfers/reconciliation').json()
    results={r['claim_id']:r for r in data['items']}
    assert results['TEST-C0']['paid_total']=='45000.00'
    assert 'payment_total_mismatch' in results['TEST-C0']['flags']
    assert 'payment_for_rejected_claim' in results['TEST-C1']['flags']
    assert 'multiple_payments_for_claim' in results['TEST-C2']['flags']
    assert 'payment_before_checker_approval' in results['TEST-C3']['flags']
    assert results['TEST-C4']['flags']==[]
    cycle=header+'LINK1,X,Y,4500,INR,2026-03-03T10:00:00Z,TEST-C4\nLINK2,Y,X,4500,INR,2026-03-04T10:00:00Z,\n'
    assert upload(cycle).status_code==200
    user.id=2; user.email='maker@auditai.example'; user.roles=['maker']
    with factory() as db:
        db.add(ClaimContributor(claim_id='TEST-C4',user_id=2,source='claim_upload')); db.commit()
    case=client.post('/api/v1/transfer-reviews',json={'transaction_ids':['LINK1','LINK2']}).json()
    assert not case['permissions']['can_make']
    assert 'contributor' in case['permissions']['maker_reason']


def test_reconciliation_unknown_currency_history_and_mixed_currency():
    ts=datetime(2026,3,3)
    claims={'C':dict(amount=4500,currency=None,status='approved',approved_at=None)}
    payments=[dict(claim_id='C',amount='4500',currency='USD',timestamp=ts)]
    flags=reconcile_payments(payments,claims)[0]['flags']
    assert set(flags)=={'claim_currency_unavailable','checker_approval_time_unavailable'}
    claims['C']['currency']='INR'
    payments.append(dict(claim_id='C',amount='4500',currency='INR',timestamp=ts))
    item=reconcile_payments(payments,claims)[0]
    assert 'currency_mismatch' in item['flags'] and item['paid_total'] is None


def test_migration_preserves_existing_transfers_and_is_repeatable():
    engine=create_engine('sqlite://')
    with engine.begin() as c:
        c.execute(text('CREATE TABLE bank_transfers (transaction_id VARCHAR(80) PRIMARY KEY, sender_account VARCHAR(100), receiver_account VARCHAR(100), timestamp DATETIME)'))
        c.execute(text("INSERT INTO bank_transfers VALUES ('OLD','A','B','2026-01-01')"))
    migrate_transfer_claim_link(engine); migrate_transfer_claim_link(engine)
    assert 'claim_id' in {c['name'] for c in inspect(engine).get_columns('bank_transfers')}
    with engine.connect() as c: assert c.execute(text("SELECT transaction_id,claim_id FROM bank_transfers")).fetchall()==[('OLD',None)]
    engine.dispose()


def test_synthetic_benchmark_includes_legitimate_refund_false_positive():
    from scripts.evaluate_circular_payments import evaluate
    r=evaluate()
    assert (r['true_positive'],r['false_positive'],r['true_negative'],r['false_negative'])==(2,1,4,0)
