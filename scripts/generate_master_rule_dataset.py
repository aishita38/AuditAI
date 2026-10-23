"""Reproducible synthetic inputs and independently specified finding-level truth."""
import csv,json,sys,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.app.master_import_service import DATASETS
OUT=ROOT/'data/master_rule_demo'


def build():
    vendors=[];employees=[];payments=[];transactions=[];truth=[]
    def vendor(key,**extra):
        r=dict(vendor_id=key,vendor_name='Synthetic '+key,bank_account='BANK'+key,ifsc='TEST0000001',address='address '+key,phone='PHONE'+key,gstin='27ABCDE1234F1Z5',pan='ABCDE1234F',director_names='Director '+key,onboarding_date='2025-01-01',status='active');r.update(extra);vendors.append(r);return r
    def employee(key,**extra):
        # Unique format-valid PAN per synthetic employee; never an actual identity.
        pan='ABCDE'+str(len(employees)+1000)+'F'
        r=dict(employee_id=key,name='Synthetic '+key,bank_account='BANK'+key,pan=pan,department='Demo',join_date='2024-01-01',exit_date='',monthly_salary='10000');r.update(extra);employees.append(r);return r
    def payment(key,eid,**extra):
        r=dict(payment_id=key,employee_id=eid,employee_name='Synthetic '+eid,bank_account='BANK'+eid,amount='10000',pay_period='2025-02',payment_date='2025-02-28');r.update(extra);payments.append(r);return r
    def expected(rule,vs=(),ps=(),es=(),ts=()):
        ids=dict(vendors=sorted(vs),payments=sorted(ps),employees=sorted(es))
        if ts:ids['transfers']=sorted(ts)
        truth.append(dict(rule_id=rule,involved_record_ids=ids))
    for i in range(20):
        vendor(f'BASEV{i:02}');employee(f'BASEE{i:02}');payment(f'BASEP{i:02}',f'BASEE{i:02}')
    for prefix,field,rule in [('VB','bank_account','VENDOR_SHARED_BANK'),('VA','address','VENDOR_SHARED_ADDRESS'),('VP','phone','VENDOR_SHARED_PHONE')]:
        for i in (1,2):vendor(f'{prefix}{i}',**{field:'SHARED '+prefix})
        expected(rule,vs=[prefix+'1',prefix+'2']);expected('VENDOR_SHELL_NETWORK',vs=[prefix+'1',prefix+'2'])
    vendor('VN1',director_names='Synthetic Alice');vendor('VN2',director_names=' Synthetic Alice ;Synthetic Bob');vendor('VN3',director_names='Synthetic Bob')
    expected('VENDOR_SHELL_NETWORK',vs=['VN1','VN2','VN3'])
    vendor('BADPAN',pan='INVALID');vendor('BADGST',gstin='INVALID');vendor('PANMISMATCH',pan='ZZZZZ9999Z')
    for key in ['BADPAN','BADGST','PANMISMATCH']:expected('VENDOR_INVALID_TAX_ID',vs=[key])
    vendor('NEWLARGE');vendor('LIMITDECOY');vendor('DAYDECOY')
    for key,amount,stamp in [('NEWLARGE','2000001','2025-01-08'),('LIMITDECOY','2000000','2025-01-04'),('DAYDECOY','2000001','2025-01-09')]:
        transactions.append(dict(transaction_id='VT-'+key,vendor_id=key,amount=amount,currency='INR',timestamp=stamp,sender_account='COMPANY',receiver_account='BANK'+key))
    expected('VENDOR_NEW_LARGE_PAYMENT',vs=['NEWLARGE'],ts=['VT-NEWLARGE'])
    vendor('NAMEDECOY1',vendor_name='Same Trading');vendor('NAMEDECOY2',vendor_name='Same Trading')
    for i in range(3):payment(f'GHOSTP{i}',f'UNKNOWN{i}');expected('PAYROLL_GHOST_EMPLOYEE',ps=[f'GHOSTP{i}'])
    for i in range(2):
        eid=f'EXIT{i}';pid=f'EXITP{i}';employee(eid,exit_date='2025-02-01');payment(pid,eid);expected('PAYROLL_AFTER_EXIT',ps=[pid],es=[eid])
        eid=f'JOIN{i}';pid=f'JOINP{i}';employee(eid,join_date='2025-03-01');payment(pid,eid);expected('PAYROLL_BEFORE_JOIN',ps=[pid],es=[eid])
    employee('EXITDAY',exit_date='2025-02-28');payment('EXITDAYP','EXITDAY')
    employee('JOINDAY',join_date='2025-02-28');payment('JOINDAYP','JOINDAY')
    employee('TOLERANCE');payment('TOLERANCEP','TOLERANCE',amount='10500')
    employee('SALARY');payment('SALARYP','SALARY',amount='10500.01');expected('PAYROLL_SALARY_MISMATCH',ps=['SALARYP'],es=['SALARY'])
    employee('DUP');payment('DUPP1','DUP');payment('DUPP2','DUP');expected('PAYROLL_DUPLICATE_PAYMENT',ps=['DUPP1','DUPP2'],es=['DUP'])
    employee('OTHERPERIOD');payment('PERIODP1','OTHERPERIOD');payment('PERIODP2','OTHERPERIOD',pay_period='2025-03',payment_date='2025-03-31')
    employee('BANKCHANGE');payment('BANKCHANGEP','BANKCHANGE',bank_account='CHANGED');expected('PAYROLL_BANK_MISMATCH',ps=['BANKCHANGEP'],es=['BANKCHANGE'])
    employee('SHARE1',bank_account='SAMEBANK');employee('SHARE2',bank_account=' SAME-BANK ')
    payment('SHAREP1','SHARE1',bank_account='SAMEBANK');payment('SHAREP2','SHARE2',bank_account='SAMEBANK')
    expected('PAYROLL_DUPLICATE_PAYEE',es=['SHARE1','SHARE2'],ps=['SHAREP1','SHAREP2'])
    employee('PAN1',pan='ZZZZZ1234Z');employee('PAN2',pan='ZZZZZ1234Z');expected('PAYROLL_DUPLICATE_PAYEE',es=['PAN1','PAN2'])
    # Roster-to-payment-only match across different IDs (a ghost payment shares an account).
    employee('CROSSROSTER',bank_account='CROSSBANK');payment('CROSSP','CROSSGHOST',bank_account='CROSSBANK')
    expected('PAYROLL_DUPLICATE_PAYEE',es=['CROSSROSTER'],ps=['CROSSP']);expected('PAYROLL_GHOST_EMPLOYEE',ps=['CROSSP'])
    employee('MISSINGBANK',bank_account='');payment('MISSINGBANKP','MISSINGBANK',bank_account='')
    vendor('EMPTY1',bank_account='',phone='',address='',director_names='',pan='',gstin='');vendor('EMPTY2',bank_account='',phone='',address='',director_names='',pan='',gstin='')
    decoys={
      'VENDOR_SHARED_BANK':['NAMEDECOY1','NAMEDECOY2','EMPTY1','EMPTY2'],
      'VENDOR_SHARED_ADDRESS':['NAMEDECOY1','NAMEDECOY2','EMPTY1','EMPTY2'],
      'VENDOR_SHARED_PHONE':['NAMEDECOY1','NAMEDECOY2','EMPTY1','EMPTY2'],
      'VENDOR_SHELL_NETWORK':['NAMEDECOY1','NAMEDECOY2','EMPTY1','EMPTY2'],
      'VENDOR_INVALID_TAX_ID':['BASEV00','EMPTY1','EMPTY2'],
      'VENDOR_NEW_LARGE_PAYMENT':['LIMITDECOY','DAYDECOY'],
      'PAYROLL_GHOST_EMPLOYEE':['BASEP00'],
      'PAYROLL_AFTER_EXIT':['EXITDAYP'],
      'PAYROLL_BEFORE_JOIN':['JOINDAYP'],
      'PAYROLL_DUPLICATE_PAYEE':['OTHERPERIOD','MISSINGBANK'],
      'PAYROLL_SALARY_MISMATCH':['TOLERANCEP'],
      'PAYROLL_DUPLICATE_PAYMENT':['PERIODP1','PERIODP2'],
      'PAYROLL_BANK_MISMATCH':['MISSINGBANKP','BASEP00']}
    return vendors,employees,payments,transactions,dict(scope='Synthetic deterministic rule fixtures, not production fraud labels.',findings=truth,decoys=decoys)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    v,e,p,t,truth=build()
    for dataset,rows in [('vendor-master',v),('employee-roster',e),('payroll-payments',p)]:
        with (OUT/(dataset+'.csv')).open('w',newline='',encoding='utf-8') as file:
            writer=csv.DictWriter(file,fieldnames=DATASETS[dataset][2]);writer.writeheader();writer.writerows(rows)
    with (OUT/'vendor-linked-transactions-fixture.csv').open('w',newline='',encoding='utf-8') as file:
        writer=csv.DictWriter(file,fieldnames=list(t[0]));writer.writeheader();writer.writerows(t)
    (OUT/'ground-truth.json').write_text(json.dumps(truth,indent=2)+'\n',encoding='utf-8')
    public=ROOT/'frontend/public/samples/master-data';public.mkdir(parents=True,exist_ok=True)
    for dataset in DATASETS:shutil.copyfile(OUT/(dataset+'.csv'),public/(dataset+'.csv'))
    print(f'Wrote synthetic CSVs and ground truth to {OUT}')


if __name__=='__main__':main()
