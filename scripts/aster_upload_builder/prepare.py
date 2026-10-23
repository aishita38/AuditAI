"""Prepare linked synthetic Aster inputs without changing the live database."""
import csv,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.generate_master_rule_dataset import build
from backend.app.master_import_service import DATASETS

v,e,p,transactions,truth=build()
def read(name):
    with (ROOT/'data/aster_company_dataset'/name).open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
old_v=read('vendors.csv');old_e=read('employees.csv')
vm={r['vendor_id']:(old_v[i]['vendor_id'] if i<20 else 'AST-DEMO-V-'+r['vendor_id']) for i,r in enumerate(v)}
em={r['employee_id']:(old_e[i]['employee_id'] if i<20 else 'AST-DEMO-E-'+r['employee_id']) for i,r in enumerate(e)}
for row in p:
    em.setdefault(row['employee_id'],'AST-DEMO-E-'+row['employee_id'])
pm={r['payment_id']:'AST-DEMO-P-'+r['payment_id'] for r in p}
for i,row in enumerate(v):
    row['vendor_id']=vm[row['vendor_id']]
    row['vendor_name']=old_v[i]['vendor_name'] if i<20 else 'Aster Demo Supplier '+row['vendor_name'].removeprefix('Synthetic ')
    row['status']='active'
for i,row in enumerate(e):
    row['employee_id']=em[row['employee_id']]
    row['name']=old_e[i]['employee_name'] if i<20 else 'Aster Demo Employee '+row['name'].removeprefix('Synthetic ')
for row in p:
    row['payment_id']=pm[row['payment_id']];row['employee_id']=em[row['employee_id']]
    row['employee_name']=next((r['name'] for r in e if r['employee_id']==row['employee_id']),'Aster Demo Unlisted Employee')
for f in truth['findings']:
    for key,mapping in [('vendors',vm),('employees',em),('payments',pm)]:
        f['involved_record_ids'][key]=[mapping[i] for i in f['involved_record_ids'][key]]
truth['findings']=[f for f in truth['findings'] if f['rule_id']!='VENDOR_NEW_LARGE_PAYMENT']
for rule,ids in truth['decoys'].items():
    mapping=vm if rule.startswith('VENDOR_') else em if rule=='PAYROLL_DUPLICATE_PAYEE' else pm
    truth['decoys'][rule]=[mapping.get(i,i) for i in ids]
truth['unavailable_rules']={'VENDOR_NEW_LARGE_PAYMENT':'Cannot evaluate, vendor-linked transactions unavailable'}
claims=[]
for i in range(15):
    amount=45000 if i==1 else 4500 if i==0 else 6000 if i==2 else 1500+i*100
    row=dict(claim_id=f'AST-DEMO-CLM-{i+1:03}',employee_id=e[i]['employee_id'],employee_name=e[i]['name'],claimed_amount=amount,vendor_name=v[i]['vendor_name'],claimed_date='2025-02-28',submitted_at='2025-02-28T11:00:00Z',category='Office supplies',description='Aster synthetic operational purchase',ocr_amount=4500 if i==1 else amount,ocr_vendor=v[i]['vendor_name'],is_fraud=i==1,fraud_type='receipt_mismatch' if i==1 else 'none')
    claims.append(row)
bank=[]
def transfer(key,sender,receiver,amount,stamp,claim_id=''):
    bank.append(dict(transaction_id=key,sender_account=sender,receiver_account=receiver,amount=amount,currency='INR',timestamp=stamp,claim_id=claim_id))
accounts=[v[i]['bank_account'] for i in range(3)]
for i,amount in enumerate([100000,98000,95000]):
    transfer(f'AST-DEMO-CYCLE-{i+1:02}',accounts[i],accounts[(i+1)%3],amount,f'2025-03-01T0{9+i}:00:00Z'.replace('T010:','T10:').replace('T011:','T11:'))
for i in range(3):transfer(f'AST-DEMO-OPEN-{i+1:02}','ASTER-DEMO-COMPANY',v[i+5]['bank_account'],12000+i*500,f'2025-03-02T0{9+i}:00:00Z'.replace('T010:','T10:').replace('T011:','T11:'))
transfer('AST-DEMO-PAID-01','ASTER-DEMO-COMPANY',accounts[0],4500,'2025-03-03T09:00:00Z',claims[0]['claim_id'])
transfer('AST-DEMO-PAID-02','ASTER-DEMO-COMPANY',accounts[0],4500,'2025-03-03T10:00:00Z',claims[0]['claim_id'])
transfer('AST-DEMO-PAID-03','ASTER-DEMO-COMPANY',accounts[1],450000,'2025-03-03T11:00:00Z',claims[1]['claim_id'])
transfer('AST-DEMO-PAID-04','ASTER-DEMO-COMPANY',accounts[2],6000,'2025-03-03T12:00:00Z',claims[2]['claim_id'])
receipts=[dict(filename=f"receipt_{c['claim_id']}.png",claim_id=c['claim_id'],receipt_id=f'AST-DEMO-RCP-{i+1:03}',vendor=c['vendor_name'],amount=c['ocr_amount'],date=c['claimed_date']) for i,c in enumerate(claims[:3])]
tables={
 '01_aster_vendor_master.csv':(DATASETS['vendor-master'][2],v),
 '02_aster_employee_roster.csv':(DATASETS['employee-roster'][2],e),
 '03_aster_payroll_payments.csv':(DATASETS['payroll-payments'][2],p),
 '04_aster_expense_claims.csv':(list(claims[0]),claims),
 '05_aster_bank_transfers.csv':(list(bank[0]),bank),
 '06_receipt_upload_map.csv':(list(receipts[0]),receipts),
}
payload=dict(tables={name:dict(headers=h,rows=rows) for name,(h,rows) in tables.items()},receipts=receipts,truth=truth)
payload['truth']['bank_transfer_expectations']=dict(cycle_ids=[r['transaction_id'] for r in bank[:3]],open_chain_decoys=[r['transaction_id'] for r in bank[3:6]],duplicate_payment_claim=claims[0]['claim_id'],amount_mismatch_claim=claims[1]['claim_id'],note='New claims are pending, so all linked payments also lack checker approval. Reconciliation depends on current live approval state.')
(Path(__file__).parent/'inputs.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
