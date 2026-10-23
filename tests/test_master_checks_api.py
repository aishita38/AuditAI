from pathlib import Path
from backend.app.api.master_checks import router as checks
from backend.app.api.master_data import router as imports
from backend.app.api.review_queue import router as queue
from backend.app.models.master_data import PayrollPayment
from backend.app.models.master_finding import MasterFinding
from backend.app.models.review_queue import ReviewRecord
from tests.test_transfer_workflow import environment
DATA=Path(__file__).parents[1]/'data/master_rule_demo'


def setup(environment):
    client,factory,user=environment
    for router in (imports,checks,queue):client.app.include_router(router)
    return client,factory,user


def upload_all(client):
    for dataset in ('vendor-master','employee-roster','payroll-payments'):
        r=client.post(f'/api/v1/master-data/{dataset}/import',files={'file':('demo.csv',(DATA/(dataset+'.csv')).read_bytes(),'text/csv')})
        assert r.status_code==200,r.text


def test_missing_datasets_and_vendor_link_unavailable(environment):
    client,_,_=setup(environment)
    r=client.post('/api/v1/master-checks/vendor/run').json()
    assert r['items']==[] and r['missing_datasets']==['Vendor master']
    assert any(s['message']=='Cannot evaluate, vendor-linked transactions unavailable' for s in r['statuses'])
    assert client.post('/api/v1/master-checks/payroll/run').json()['missing_datasets']==['Employee roster','Payroll payments']


def test_import_reimport_findings_send_review_snapshot_and_permissions(environment):
    client,factory,user=setup(environment);upload_all(client)
    first=client.post('/api/v1/master-checks/vendor/run').json()
    payroll=client.post('/api/v1/master-checks/payroll/run').json()
    assert len(first['items'])==10 and len(payroll['items'])==14
    upload_all(client)
    again=client.post('/api/v1/master-checks/vendor/run').json()
    assert {f['id'] for f in first['items']}=={f['id'] for f in again['items']}
    finding=next(f for f in payroll['items'] if f['rule_id']=='PAYROLL_GHOST_EMPLOYEE')
    root=f"/api/v1/master-checks/findings/{finding['id']}/send-to-review"
    sent=client.post(root);assert sent.status_code==200,sent.text
    case=sent.json()['case_id'];assert client.post(root).json()['case_id']==case
    path=f'/api/v1/review-queue/{case}'
    evidence=client.get(path).json()['evidence']
    user.roles=['admin','maker','checker']
    assert client.post(path+'/maker-recommend',json={'action':'reject','notes':'Own import must be blocked'}).status_code==403
    user.id=2;user.email='maker@auditai.example';user.roles=['maker','checker']
    assert client.post(path+'/maker-recommend',json={'action':'reject','notes':'Investigate missing employee'}).status_code==200
    assert client.post(path+'/checker-signoff',json={'action':'reject','notes':'Same maker blocked'}).status_code==403
    user.id=3;user.email='checker@auditai.example';user.roles=['checker']
    assert client.post(path+'/checker-signoff',json={'action':'reject','notes':'No supporting roster record'}).status_code==200
    with factory() as db:
        db.query(PayrollPayment).filter_by(payment_id=evidence['payments'][0]['payment_id']).update({'amount':12345});db.commit()
    assert client.get(path).json()['evidence']==evidence
    assert client.get('/api/v1/review-queue?case_type=payroll_check').json()['total']==1
    user.roles=['employee']
    assert client.post('/api/v1/master-checks/payroll/run').status_code==403
    assert client.post(root).status_code==403


def test_vendor_case_lists_all_network_records_and_stale_findings_are_blocked(environment):
    from backend.app.models.master_data import VendorMaster
    client,factory,user=setup(environment);upload_all(client)
    items=client.post('/api/v1/master-checks/vendor/run').json()['items']
    finding=next(f for f in items if f['rule_id']=='VENDOR_SHELL_NETWORK' and len(f['evidence']['vendors'])==3)
    r=client.post(f"/api/v1/master-checks/findings/{finding['id']}/send-to-review")
    assert r.status_code==200
    detail=client.get(f"/api/v1/review-queue/{r.json()['case_id']}").json()
    assert len(detail['evidence']['vendors'])==3 and len(detail['evidence']['links'])==2
    unsent=next(f for f in items if f['rule_id']=='VENDOR_SHARED_BANK')
    with factory() as db:
        db.query(VendorMaster).filter_by(vendor_id='VB2').update({'bank_account':'NOW-UNIQUE'});db.commit()
    assert client.post(f"/api/v1/master-checks/findings/{unsent['id']}/send-to-review").status_code==409
    assert client.get(f"/api/v1/review-queue/{r.json()['case_id']}").json()['evidence']==detail['evidence']
