"""Unified queue regression tests on isolated native case and transfer fixtures."""
from datetime import date,datetime
from backend.app.api.review_queue import router
from backend.app.models.review_queue import ReviewRecord,ReviewQueueEvent
from backend.app.models.expense import ExpenseClaim,Case,CaseAuditTrail,Entity
from backend.app.models.transfer import CycleReviewCase,CycleReviewEvent
from tests.test_transfer_workflow import environment
from tests.test_transfer_cycles import SAMPLE


def setup_queue(environment):
    client,factory,user=environment
    client.app.include_router(router)
    client.post('/api/v1/transfers/upload',files={'file':('sample.csv',SAMPLE.read_bytes(),'text/csv')}).raise_for_status()
    cycle=client.post('/api/v1/transfer-reviews',json={'transaction_ids':['DEMO-CYCLE-001','DEMO-CYCLE-002','DEMO-CYCLE-003']})
    cycle.raise_for_status()
    return client,factory,user


def test_unified_list_filtering_snapshot_history_and_real_links(environment):
    client,factory,user=setup_queue(environment)
    assert client.post('/api/v1/review-queue/sync').json()['added']==6
    assert client.post('/api/v1/review-queue/sync').json()['added']==0
    items=client.get('/api/v1/review-queue').json()['items']
    assert {i['case_type'] for i in items}=={'expense_claim','circular_payment'}
    assert len({i['id'] for i in items})==6
    assert client.get('/api/v1/review-queue?case_type=payroll_check').json()['total']==0
    cycle=client.get('/api/v1/review-queue?case_type=circular_payment').json()['items'][0]
    detail=client.get(f'/api/v1/review-queue/{cycle["id"]}').json()
    assert detail['audit_trail'][0]['action']=='created' and detail['related_records']==[]
    assert not detail['permissions']['can_make']
    expense=next(i for i in items if i['case_type']=='expense_claim')
    first=client.get(f'/api/v1/review-queue/{expense["id"]}').json()
    cid=first['evidence']['claim']['claim_id']
    with factory() as db:
        claim=db.query(ExpenseClaim).filter_by(claim_id=cid).one();claim.description='Later changed description';db.commit()
    client.post('/api/v1/review-queue/sync')
    after=client.get(f'/api/v1/review-queue/{expense["id"]}').json()
    assert after['evidence']==first['evidence']
    assert after['related_records']==[{'kind':'claim','id':cid}]
    assert after['audit_trail'][0]['action']=='final_approved'


def test_concurrent_refresh_does_not_duplicate_cases(environment):
    from concurrent.futures import ThreadPoolExecutor
    client,_,_=setup_queue(environment)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(lambda _:client.post('/api/v1/review-queue/sync'),range(2)))
    assert all(r.status_code==200 for r in responses)
    assert sum(r.json()['added'] for r in responses)==6
    assert client.get('/api/v1/review-queue').json()['total']==6


def test_cycle_actions_and_comments_share_native_history(environment):
    client,factory,user=setup_queue(environment)
    client.post('/api/v1/review-queue/sync')
    qid=client.get('/api/v1/review-queue?case_type=circular_payment').json()['items'][0]['id']
    root=f'/api/v1/review-queue/{qid}'
    user.id=2;user.roles=['maker','checker'];user.email='maker@auditai.example'
    body={'action':'reject','notes':'Investigate unexplained return'}
    assert client.post(root+'/checker-signoff',json=body).status_code==403
    made=client.post(root+'/maker-recommend',json=body)
    assert made.status_code==200,made.text
    assert made.json()['status']=='maker_recommended_reject'
    assert client.post(root+'/maker-recommend',json=body).status_code in (403,409)
    assert client.post(root+'/checker-signoff',json=body).status_code==403
    assert client.post(root+'/comments',json={'notes':'Supporting documents requested'}).status_code==200
    user.id=3;user.roles=['checker'];user.email='checker@auditai.example'
    closed=client.post(root+'/checker-signoff',json=body)
    assert closed.status_code==200,closed.text
    assert closed.json()['status']=='closed_rejected'
    actions=[e['action'] for e in closed.json()['audit_trail']]
    assert 'comment' in actions and 'maker-recommend:reject' in actions and 'checker-signoff:reject' in actions
    assert client.post(root+'/checker-signoff',json=body).status_code==403
    with factory() as db:
        assert db.query(CycleReviewCase).one().status=='closed_rejected'
        assert db.query(CycleReviewEvent).count()==3


def test_expense_review_uses_original_authority_and_trail(environment):
    client,factory,user=setup_queue(environment)
    with factory() as db:
        entity=db.query(Entity).first()
        db.add(ExpenseClaim(claim_id='QUEUE-EXP',employee_id='OWNER',employee_name='Owner',claimed_amount=4500,vendor_name='Distinct Vendor',claimed_date=date(2026,3,1),status='flagged',entity_id=entity.id,description='Business purchase'));db.commit()
    r=client.post('/api/v1/review-queue/expense/QUEUE-EXP')
    assert r.status_code==200,r.text
    qid=r.json()['id'];path=f'/api/v1/review-queue/{qid}'
    user.id=2;user.roles=['maker','checker'];user.email='maker@auditai.example'
    decision={'action':'approve','notes':'Receipt and claim checked'}
    assert client.post(path+'/maker-recommend',json=decision).status_code==200
    assert client.post(path+'/checker-signoff',json=decision).status_code==403
    user.id=3;user.roles=['checker'];user.email='checker@auditai.example'
    r=client.post(path+'/checker-signoff',json=decision)
    assert r.status_code==200,r.text
    with factory() as db:
        c=db.query(ExpenseClaim).filter_by(claim_id='QUEUE-EXP').one()
        assert c.status=='approved'
        actions=[e.action for e in c.case.audit_trail]
        assert all(action in actions for action in ['created','recommended_approve','final_approved'])
    assert client.post('/api/v1/review-queue/expense/TEST-C0').status_code==200


def test_reconciliation_case_dedup_contributors_and_no_claim_mutation(environment):
    client,factory,user=setup_queue(environment)
    blob=b'transaction_id,sender_account,receiver_account,amount,currency,timestamp,claim_id\nRECON,A,B,45000,INR,2026-03-03T10:00:00Z,TEST-C0\n'
    client.post('/api/v1/transfers/upload',files={'file':('r.csv',blob,'text/csv')}).raise_for_status()
    r=client.post('/api/v1/review-queue/reconciliation/TEST-C0')
    assert r.status_code==200,r.text
    item=r.json();qid=item['id']
    assert item['case_type']=='reconciliation' and 'payment_total_mismatch' in item['evidence']['flags']
    assert not item['permissions']['can_make']
    assert client.post('/api/v1/review-queue/reconciliation/TEST-C0').json()['id']==qid
    assert {l['kind'] for l in item['related_records']}=={'claim','transfer'}
    user.id=2;user.roles=['maker'];user.email='maker@auditai.example'
    body={'action':'reject','notes':'Payment needs investigation'}
    assert client.post(f'/api/v1/review-queue/{qid}/maker-recommend',json=body).status_code==200
    user.id=3;user.roles=['checker'];user.email='checker@auditai.example'
    final=client.post(f'/api/v1/review-queue/{qid}/checker-signoff',json=body)
    assert final.status_code==200,final.text
    assert len(final.json()['audit_trail'])==3
    with factory() as db: assert db.query(ExpenseClaim).filter_by(claim_id='TEST-C0').one().status=='approved'
    user.roles=['employee']
    assert client.get('/api/v1/review-queue').status_code==403
    assert client.get(f'/api/v1/review-queue/{qid}').status_code==403
    assert client.post(f'/api/v1/review-queue/{qid}/comments',json={'notes':'Not authorized'}).status_code==403


def test_live_record_lookup_is_separate_from_immutable_snapshot(environment):
    from backend.app.api.review_records import router as records_router
    from backend.app.models.transfer import BankTransfer
    client,factory,user=setup_queue(environment)
    client.app.include_router(records_router)
    client.post('/api/v1/review-queue/sync').raise_for_status()
    cycle=client.get('/api/v1/review-queue?case_type=circular_payment').json()['items'][0]
    root=f'/api/v1/review-queue/{cycle["id"]}'
    before=client.get(root).json()['evidence']
    refs=[dict(kind='transfer',id='DEMO-CYCLE-001'),dict(kind='claim',id='CLM-01159')]
    response=client.post('/api/v1/review-records/lookup',json={'records':refs})
    assert response.status_code==200
    assert response.json()==[dict(**refs[0],exists=True),dict(**refs[1],exists=False)]
    assert client.get('/api/v1/review-records/transfer/DEMO-CYCLE-001').status_code==200
    assert client.get('/api/v1/review-records/claim/CLM-01159').status_code==404
    with factory() as db:
        db.query(BankTransfer).filter_by(transaction_id='DEMO-CYCLE-001').delete();db.commit()
    assert not client.post('/api/v1/review-records/lookup',json={'records':refs}).json()[0]['exists']
    assert client.get(root).json()['evidence']==before
    assert any(t['transaction_id']=='DEMO-CYCLE-001' for t in before['transfers'])


def test_expense_captures_all_linked_payments_without_refreshing_snapshot(environment):
    from backend.app.models.transfer import BankTransfer
    client,factory,user=setup_queue(environment)
    with factory() as db:
        db.add(ExpenseClaim(claim_id='SNAP-CLAIM',employee_id='OWNER',employee_name='Owner',claimed_amount=4500,vendor_name='Vendor',claimed_date=date(2026,3,1),status='flagged'))
        db.flush()
        for i in range(12):
            db.add(BankTransfer(transaction_id=f'SNAP-{i}',sender_account='A',receiver_account='B',amount=100,currency='INR',timestamp=datetime(2026,3,2),imported_by=1,claim_id='SNAP-CLAIM'))
        db.commit()
    created=client.post('/api/v1/review-queue/expense/SNAP-CLAIM')
    assert created.status_code==200,created.text
    evidence=created.json()['evidence']
    assert len(evidence['payments'])==12
    with factory() as db:
        db.query(BankTransfer).filter_by(transaction_id='SNAP-0').update({'amount':999});db.commit()
    assert client.get(f"/api/v1/review-queue/{created.json()['id']}").json()['evidence']==evidence
