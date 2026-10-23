from types import SimpleNamespace
from fastapi import HTTPException
from backend.app.api.detection import router as detection
from backend.app.api.claims import router as claims
from backend.app.api.master_checks import router as checks
from backend.app.models.expense import ExpenseClaim,FraudPrediction
from tests.test_master_checks_api import setup,upload_all
from tests.test_transfer_workflow import environment


def test_uploads_generate_findings_without_run_button_and_overview_counts_every_type(environment):
    client,factory,user=setup(environment);client.app.include_router(detection)
    upload_all(client)
    vendor=client.get('/api/v1/master-checks/vendor').json()['items']
    payroll=client.get('/api/v1/master-checks/payroll').json()['items']
    assert len(vendor)==10 and len(payroll)==14
    r=client.get('/api/v1/detection/overview');assert r.status_code==200,r.text
    data=r.json();counts={r['detector']:r['findings'] for r in data['breakdown']}
    assert counts['Vendor rules']==10 and counts['Payroll rules']==14
    assert data['total_review_signals']==sum(counts.values())
    assert all(c['metrics']['recall'] is None for c in data['cohorts'])
    user.roles=['employee'];assert client.get('/api/v1/detection/overview').status_code==403
    assert client.post('/api/v1/detection/recheck').status_code==403


def test_claim_upload_automatically_scores_only_new_ids_and_reports_failures_without_losing_upload(environment,monkeypatch):
    from backend.app.api import fraud
    client,factory,user=setup(environment);client.app.include_router(claims)
    calls=[]
    def score(db,user,**kwargs):
        calls.append(kwargs['claim_ids']);return dict(status='success',scored_count=1,flagged_count=0)
    monkeypatch.setattr(fraud,'score_selected_claims',score)
    raw=b'claim_id,employee_id,employee_name,claimed_amount,vendor_name,claimed_date\nAUTO1,EMP100,Example,4500,Supplier,2025-01-06\n'
    r=client.post('/api/v1/claims/upload',files={'file':('claims.csv',raw,'text/csv')})
    assert r.status_code==200,r.text
    assert calls==[['AUTO1']]
    assert r.json()['checks']['stages'][0]['scored_count']==1
    assert r.json()['checks']['stages'][0]['status']=='completed'
    def fail(*args,**kwargs):raise HTTPException(500,'Model artifacts unavailable')
    monkeypatch.setattr(fraud,'score_selected_claims',fail)
    r=client.post('/api/v1/claims/upload',files={'file':('claims.csv',raw.replace(b'AUTO1',b'AUTO2'),'text/csv')})
    assert r.status_code==200 and r.json()['checks']['status']=='partial'
    assert r.json()['checks']['stages'][0]['message']=='Model artifacts unavailable'
    with factory() as db:assert db.query(ExpenseClaim).filter_by(claim_id='AUTO2').count()==1


def test_master_partial_import_runs_accepted_rows_and_reimport_does_not_duplicate_findings(environment):
    from tests.test_master_data_imports import encode,vendor
    client,factory,user=setup(environment)
    rows=[vendor(),dict(vendor(),vendor_id='VEN2'),dict(vendor(),vendor_id='')]
    r=client.post('/api/v1/master-data/vendor-master/import',files={'file':('vendors.csv',encode('vendor-master',rows),'text/csv')})
    assert r.status_code==200 and r.json()['rejected']==1
    assert r.json()['checks']['stages'][0]['finding_count']>0
    first=client.get('/api/v1/master-checks/vendor').json()['items']
    client.post('/api/v1/master-data/vendor-master/import',files={'file':('vendors.csv',encode('vendor-master',rows),'text/csv')})
    assert {f['id'] for f in first}=={f['id'] for f in client.get('/api/v1/master-checks/vendor').json()['items']}


def test_actual_scoring_subset_preserves_approved_claims_and_other_pending_claims(environment,monkeypatch):
    from datetime import date
    from backend.app.api import fraud
    client,factory,user=environment
    monkeypatch.setattr(fraud,'load_pipeline',lambda _:dict(family='ae',isolation_forest=None))
    monkeypatch.setattr(fraud,'compute_features_batch',lambda records:([{'is_holiday':0} for _ in records],['is_holiday']))
    monkeypatch.setattr(fraud,'event_time_info',lambda record:(None,True))
    monkeypatch.setattr(fraud,'score_claims',lambda matrix,*args:[dict(is_flagged=False,reconstruction_error=0,isolation_forest_score=0,combined_fraud_score=.1) for _ in matrix])
    with factory() as db:
        for cid in ['ONLY-THIS','LEAVE-PENDING']:
            db.add(ExpenseClaim(claim_id=cid,employee_id='OWNER',employee_name='Owner',claimed_amount=100,vendor_name='Vendor',claimed_date=date(2025,1,6),status='pending'))
        db.commit()
        result=fraud.score_selected_claims(db,user,claim_ids=['ONLY-THIS','TEST-C0'])
        assert result['scored_count']==1
        assert db.query(FraudPrediction).filter_by(claim_id='ONLY-THIS').count()==1
        assert db.query(FraudPrediction).filter_by(claim_id='LEAVE-PENDING').count()==0
        assert db.query(ExpenseClaim).filter_by(claim_id='TEST-C0').one().status=='approved'


def test_overview_keeps_per_dataset_ground_truth_separate_and_reports_incomplete_scans(environment,monkeypatch):
    from backend.app.api import transfers
    from datetime import date
    client,factory,user=setup(environment);client.app.include_router(detection)
    with factory() as db:
        for cid,label,score,flag in [('CLM-POS',True,.9,True),('CLM-NEG',False,.1,False),('TXN-POS',True,.1,False)]:
            db.add(ExpenseClaim(claim_id=cid,employee_id='E',employee_name='Example',vendor_name='Vendor',claimed_amount=100,claimed_date=date(2025,1,1),is_fraud=label,fraud_type='anomaly' if label else 'none'))
            db.flush();db.add(FraudPrediction(claim_id=cid,combined_fraud_score=score,is_flagged=flag))
            from backend.app.models.policy import ClaimPolicy
            db.add(ClaimPolicy(claim_id=cid,result={'requires_review':False}))
        db.commit()
    def fail(*args):raise HTTPException(422,'Search size unsupported')
    monkeypatch.setattr(transfers,'cycles',fail)
    data=client.get('/api/v1/detection/overview').json();groups={c['name']:c for c in data['cohorts']}
    assert groups['Original expense claims']['metrics']['precision']==1
    assert groups['Original expense claims']['metrics']['recall']==1
    assert groups['Enterprise records in expense schema (scope mismatch)']['metrics']['recall']==0
    assert data['incomplete'] and data['errors'][0]['detector']=='circular'
