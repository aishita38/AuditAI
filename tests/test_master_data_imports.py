"""Phase 1: isolated DB tests; no live data, ML or transfer import changes."""
import csv
import io
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,inspect,event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.app.db import Base,get_db
from backend.app.auth.security import get_current_user
from backend.app.models.auth import AuthUser
from backend.app.models import expense  # register existing auth FK targets
from backend.app.models.master_data import VendorMaster,EmployeeMaster,PayrollPayment,MasterImportHistory
from backend.app.master_import_service import DATASETS,MAX_BYTES,MAX_ROWS
from backend.app.api.master_data import router


def encode(dataset,rows,fields=None):
    buffer=io.StringIO(); writer=csv.DictWriter(buffer,fieldnames=fields or DATASETS[dataset][2]); writer.writeheader(); writer.writerows(rows)
    return buffer.getvalue().encode('utf-8-sig')


def vendor(**updates):
    return dict(vendor_id=' ven-001 ',vendor_name=' Supplier One ',bank_account=' 00-123 456 ',ifsc=' abcd0000001 ',address='  10  INDUSTRIAL\t Road ',phone=' +91 987-654-3210 ',gstin=' malformed-gstin ',pan=' abcde1234f ',director_names=' Ada Rao ;  Ravi   Shah ; ',onboarding_date='2026-01-01',status=' Active ',**updates)


def employee():
    return dict(employee_id=' emp001 ',name=' Employee One ',bank_account=' 00-999 88 ',pan=' abcde1234f ',department=' Finance ',join_date='2025-01-01',exit_date='',monthly_salary='50000.00')


def payroll():
    return dict(payment_id=' pay001 ',employee_id=' ghost999 ',employee_name=' Unknown Employee ',bank_account=' 00-111 22 ',amount='51000.00',pay_period='2026-01',payment_date='2026-01-31')


@pytest.fixture
def context():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    @event.listens_for(engine,'connect')
    def enable_fk(connection,_): connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine); factory=sessionmaker(bind=engine)
    with factory() as db:
        db.add(AuthUser(id=1,email='admin@auditai.example',employee_id='ADMIN',display_name='Admin',roles=['admin'],password_hash='unused')); db.commit()
    app=FastAPI(); app.include_router(router)
    def database():
        with factory() as db: yield db
    user=SimpleNamespace(id=1,roles=['admin'])
    app.dependency_overrides[get_db]=database
    app.dependency_overrides[get_current_user]=lambda:user
    with TestClient(app) as client: yield client,factory,user,app,engine
    engine.dispose()


def upload(client,dataset,blob):
    return client.post(f'/api/v1/master-data/{dataset}/import',files={'file':('test.csv',blob,'text/csv')})


@pytest.mark.parametrize('dataset,make_row,model,key',[
    ('vendor-master',vendor,VendorMaster,'vendor_id'),('employee-roster',employee,EmployeeMaster,'employee_id'),('payroll-payments',payroll,PayrollPayment,'payment_id')])
def test_insert_identical_skip_changed_update_and_distinct_internal_key(context,dataset,make_row,model,key):
    client,factory,*_=context; row=make_row(); raw=encode(dataset,[row])
    first=upload(client,dataset,raw); assert first.status_code==200,first.text
    assert first.json()['inserted']==1
    second=upload(client,dataset,raw).json(); assert second['skipped']==1 and second['inserted']==0 and second['updated']==0
    changed='vendor_name' if dataset=='vendor-master' else 'name' if dataset=='employee-roster' else 'employee_name'
    row[changed]='Updated Name'
    assert upload(client,dataset,encode(dataset,[row])).json()['updated']==1
    with factory() as db:
        record=db.query(model).one()
        assert isinstance(record.id,int) and getattr(record,key)==make_row()[key].strip().upper()
        assert getattr(record,changed)=='Updated Name'
        assert db.query(MasterImportHistory).count()==3


def test_vendor_normalization_and_malformed_tax_ids_are_stored(context):
    client,factory,*_=context
    upload(client,'vendor-master',encode('vendor-master',[vendor()])).raise_for_status()
    with factory() as db:
        v=db.query(VendorMaster).one()
        assert v.bank_account=='00123456' and v.phone=='+919876543210'
        assert v.address=='10 industrial road' and v.ifsc=='ABCD0000001'
        assert v.pan=='ABCDE1234F' and v.gstin=='MALFORMED-GSTIN'
        assert v.director_names=='Ada Rao;Ravi Shah'


def test_ghost_employee_does_not_require_roster_and_nullable_exit(context):
    client,factory,_,_,engine=context
    upload(client,'payroll-payments',encode('payroll-payments',[payroll()])).raise_for_status()
    upload(client,'employee-roster',encode('employee-roster',[employee()])).raise_for_status()
    with factory() as db:
        assert db.query(PayrollPayment).one().employee_id=='GHOST999'
        assert db.query(EmployeeMaster).one().exit_date is None
    assert not inspect(engine).get_foreign_keys('payroll_payments')


@pytest.mark.parametrize('field,bad',[
    ('amount','NaN'),('amount','Infinity'),('amount','-1'),('amount','0'),('amount','1.001'),('amount','10000000000000'),
    ('payment_date','2026-02-30'),('payment_date','31/01/2026'),('pay_period','2026-13'),('employee_id',''),('payment_id','')])
def test_partial_load_with_row_number_and_reason(context,field,bad):
    client,factory,*_=context
    a=payroll(); b=payroll(); b['payment_id']='BAD'; b[field]=bad
    res=upload(client,'payroll-payments',encode('payroll-payments',[a,b])).json()
    assert res['status']=='partial' and res['inserted']==1 and res['rejected']==1
    assert res['errors'][0]['row']==3 and res['errors'][0]['reason']
    with factory() as db:
        assert db.query(PayrollPayment).count()==1
        history=db.query(MasterImportHistory).one()
        assert history.rejected==1 and history.errors==res['errors']


def test_duplicate_normalized_ids_conflict_and_identical_rows(context):
    client,factory,*_=context
    a=vendor(); b=dict(a,vendor_id='VEN-001'); c=dict(b,vendor_name='Conflicting Name')
    res=upload(client,'vendor-master',encode('vendor-master',[a,b,c])).json()
    assert (res['inserted'],res['skipped'],res['rejected'])==(1,1,1)
    assert res['errors'][0]['row']==4
    with factory() as db: assert db.query(VendorMaster).one().vendor_name=='Supplier One'


@pytest.mark.parametrize('blob,status,code',[
    (b'','empty',200),(b'wrong_header\nx\n','rejected',422),(b'\xff\xfe','rejected',422),
    (b'x'*(MAX_BYTES+1),'rejected',422)], ids=['empty-file','missing-columns','invalid-encoding','oversize-file'])
def test_file_failures_and_empty_attempts_have_history(context,blob,status,code):
    client,factory,*_=context
    response=upload(client,'vendor-master',blob)
    assert response.status_code==code
    assert response.json()['status']==status
    with factory() as db:
        assert db.query(VendorMaster).count()==0
        assert db.query(MasterImportHistory).one().status==status
    if code==422 and blob.startswith(b'wrong'): assert 'Missing required columns: vendor_id' in response.json()['errors'][0]['reason']


def test_header_only_and_all_rows_rejected_are_recorded(context):
    client,factory,*_=context
    assert upload(client,'employee-roster',encode('employee-roster',[])).json()['status']=='empty'
    bad=employee(); bad['exit_date']='2020-01-01'
    res=upload(client,'employee-roster',encode('employee-roster',[bad])).json()
    assert res['status']=='rejected' and res['rejected']==1
    with factory() as db: assert db.query(MasterImportHistory).count()==2


def test_missing_exit_column_and_empty_account_are_valid(context):
    client,factory,*_=context
    row=employee(); row.pop('exit_date'); row['bank_account']=''
    result=upload(client,'employee-roster',encode('employee-roster',[row],fields=[f for f in DATASETS['employee-roster'][2] if f!='exit_date']))
    assert result.json()['inserted']==1
    with factory() as db: assert db.query(EmployeeMaster).one().bank_account is None


def test_status_reports_latest_attempt_and_last_success(context):
    client,_,*_=context
    empty=client.get('/api/v1/master-data/status').json()
    assert len(empty)==3 and all(r['rows_loaded']==0 and r['last_imported_at'] is None for r in empty)
    upload(client,'vendor-master',encode('vendor-master',[vendor()]))
    upload(client,'vendor-master',b'bad\n')
    v=next(r for r in client.get('/api/v1/master-data/status').json() if r['dataset']=='vendor-master')
    assert v['rows_loaded']==1 and v['last_import_status']=='rejected'
    assert v['last_imported_at'].endswith('Z') and v['last_successful_imported_at'].endswith('Z')


def test_unauthorized_requests_do_not_create_history(context):
    client,factory,user,app,_=context
    for role in ['employee','maker','checker']:
        user.roles=[role]
        assert upload(client,'vendor-master',encode('vendor-master',[vendor()])).status_code==403
    assert client.get('/api/v1/master-data/status').status_code==200
    user.roles=['employee']; assert client.get('/api/v1/master-data/status').status_code==403
    app.dependency_overrides.pop(get_current_user)
    assert upload(client,'vendor-master',b'').status_code in (401,403)
    with factory() as db: assert db.query(MasterImportHistory).count()==0


def test_normalized_headers_and_structurally_short_rows(context):
    client,factory,*_=context
    blob=encode('payroll-payments',[payroll()]).decode('utf-8-sig')
    header,rest=blob.split('\r\n',1)
    blob=(' , '.join(h.upper() for h in header.split(','))+'\r\n'+rest+'SHORT,EMP01\r\n').encode()
    res=upload(client,'payroll-payments',blob).json()
    assert res['inserted']==1 and res['rejected']==1


def test_too_many_rows_does_not_load_a_partial_file(context):
    client,factory,*_=context
    raw=encode('payroll-payments',[dict(payroll(),payment_id=f'PAY{i}') for i in range(MAX_ROWS+1)])
    response=upload(client,'payroll-payments',raw)
    assert response.status_code==422
    with factory() as db:
        assert db.query(PayrollPayment).count()==0
        assert db.query(MasterImportHistory).count()==1
