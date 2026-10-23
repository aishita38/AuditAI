import csv,json,sys
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.app.db import Base,get_db
from backend.app.auth.security import get_current_user
from backend.app.models.auth import AuthUser
from backend.app.models.expense import Entity
from backend.app.api.master_data import router as master
from backend.app.api.claims import router as claims
from backend.app.api.transfers import router as transfers
from backend.app.api.master_checks import router as checks
from scripts.evaluate_master_rules import signature
OUT=ROOT/'data/aster_upload_pack'
engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
@event.listens_for(engine,'connect')
def fk(conn,_):conn.execute('PRAGMA foreign_keys=ON')
Base.metadata.create_all(engine);factory=sessionmaker(bind=engine)
with factory() as db:
    db.add(AuthUser(id=1,email='admin@auditai.example',employee_id='ADMIN',display_name='Admin',roles=['admin'],password_hash='unused'))
    db.add(Entity(name='APAC Entity',currency='INR'));db.commit()
app=FastAPI()
for r in (master,claims,transfers,checks):app.include_router(r)
def database():
    with factory() as db:yield db
app.dependency_overrides[get_db]=database
app.dependency_overrides[get_current_user]=lambda:SimpleNamespace(id=1,email='admin@auditai.example',employee_id='ADMIN',roles=['admin'])
report={}
with TestClient(app) as client:
    for name,url in [('01_aster_vendor_master.csv','/master-data/vendor-master/import'),('02_aster_employee_roster.csv','/master-data/employee-roster/import'),('03_aster_payroll_payments.csv','/master-data/payroll-payments/import'),('04_aster_expense_claims.csv','/claims/upload'),('05_aster_bank_transfers.csv','/transfers/upload')]:
        r=client.post('/api/v1'+url,files={'file':(name,(OUT/name).read_bytes(),'text/csv')})
        assert r.status_code==200,(name,r.status_code,r.text)
        result=r.json();assert not result.get('errors'),(name,result)
        report[name]=result
    findings=[]
    for dataset in ('vendor','payroll'):
        r=client.post(f'/api/v1/master-checks/{dataset}/run');assert r.status_code==200,r.text
        findings+=r.json()['items'];report[dataset+'_findings']=len(r.json()['items'])
    truth=json.loads((OUT/'ground_truth.json').read_text(encoding='utf-8'))
    expected={(r['rule_id'],signature(r)) for r in truth['findings']}
    actual={(r['rule_id'],signature(r)) for r in findings}
    assert actual==expected,(actual-expected,expected-actual)
    report['ground_truth_matches']=True
    # Master imports skip, rather than duplicate, every row on the second import.
    for name,kind in [('01_aster_vendor_master.csv','vendor-master'),('02_aster_employee_roster.csv','employee-roster'),('03_aster_payroll_payments.csv','payroll-payments')]:
        r=client.post(f'/api/v1/master-data/{kind}/import',files={'file':(name,(OUT/name).read_bytes(),'text/csv')})
        assert r.status_code==200 and r.json()['inserted']==0 and r.json()['updated']==0 and r.json()['rejected']==0
(OUT/'validation_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if not isinstance(v,dict)},indent=2))
