"""Reproducible fictional company scenario dataset; never edits the live database."""
import csv
import json
import random
import zipfile
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / 'data' / 'company_demo'
R = random.Random(42)
COMPANY = 'Aster Precision Components Private Limited (fictional)'
CATALOG = [
 ('enterprise','vendor_invoice_fraud','critical',80),
 ('enterprise','payroll_fraud_risk','critical',80),
 ('enterprise','complex_structure_risk','critical',80),
 ('enterprise','manual_journal_manipulation','critical',80),
 *[('enterprise', name, 'high',80) for name in ['receipt_mismatch','unknown_emerging_risk','revenue_cutoff','duplicate_entry','complex_financial_instrument','ghost_vendor','related_party','unusual_amount','unusual_flow','split_invoice','rare_flow','cash_payment','reversal','high_monetary_value']],
 *[('enterprise', name, 'medium',80) for name in ['personal_expense','benford_cohort','weekend_after_hours','suspicious_wording','sequence_gaps','round_number','missing_information']],
 *[('erp',name,sev,200) for name,sev in [('circular_payment','critical'),('fake_vendors','critical'),('shell_network','critical'),('approval_limit','high'),('invoice_splitting','high'),('new_vendor_large_payment','high'),('shared_bank','high'),('velocity_spike','high'),('shared_address','medium'),('shared_phone','medium'),('duplicate_payment','medium'),('excessive_reimbursement','medium'),('weekend_payment','low'),('midnight_payment','low'),('round_payment','low')]],
 *[('expense',name,'high' if name != 'weekend_claim' else 'medium',30) for name in ['split_transaction','amount_inflation','duplicate','weekend_claim','fake_vendor']],
]

def write(name, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with (OUT / name).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)

def build():
    OUT.mkdir(parents=True,exist_ok=True)
    departments=['Finance','Procurement','Production','Sales','IT','HR','Operations']
    employees=[dict(employee_id=f'EMP{i:03}',employee_name=f'Aster Employee {i:03}',department=departments[(i-1)%7],office=['Pune','Chennai','Bengaluru'][(i-1)%3],bank_account=f'TEST-EMP-BANK-{i:04}',phone=f'TEST-EMP-PHONE-{i:04}',address=f'Test Employee Campus {i}',role='Associate',approval_limit=0,manager_id=f'EMP{294+(i-1)%7:03}',payroll_verified=True) for i in range(1,301)]
    for e in employees[293:]: e.update(role='Manager',approval_limit=50000,manager_id='EMP300')
    employees[-1].update(role='CFO',approval_limit=50000000,manager_id='')
    vendors=[dict(vendor_id=f'VEN{i:04}',vendor_name=f'Aster Test Supplier {i:03}',category=['Raw Materials','Logistics','IT Services','Travel','Meals'][(i-1)%5],bank_account=f'TEST-VENDOR-BANK-{i:04}',phone=f'TEST-VENDOR-PHONE-{i:04}',address=f'Test Industrial Estate Unit {i}',director=f'Test Director {i}',gstin=f'TEST-GST-{i:04}',verification_status='verified_fixture',onboarded_at='2023-01-01',country='India') for i in range(1,101)]
    transactions=[]; labels=[]; groups=[]; checks=[]
    def base(dt=None,v=None,e=None):
        e=e or R.choice(employees[:293]); v=v or R.choice(vendors[:100])
        dt=dt or datetime(2025,4,1,10)+timedelta(days=R.randrange(365),minutes=R.randrange(420))
        while dt.weekday()>4: dt+=timedelta(days=1)
        amt=round(min(40000,max(200,R.lognormvariate(8,0.65))),2)
        i=len(transactions)+1
        return dict(transaction_id=f'AST-TXN-{i:06}',company_id='ASTER-IN-01',employee_id=e['employee_id'],vendor_id=v['vendor_id'],department=e['department'],cost_center='CC-'+e['department'][:3].upper(),project_id='PRJ-Factory-Expansion' if i%4==0 else 'PRJ-Operations',posting_timestamp=dt.isoformat(),amount=amt,currency='INR',invoice_number=f'INV-{i:07}',receipt_reference=f'RCP-{i:07}',receipt_amount=amt,receipt_vendor=v['vendor_name'],business_purpose='Approved operational purchase',account='Operating Expenses',payment_method='NEFT',approver_id=e['manager_id'],purchase_order=f'PO-{i:07}',supporting_document=f'DOC-{i:07}',original_transaction_id='',instrument='standard',contract_terms='standard supply agreement',invoice_sequence=i,revenue_delivery_date='',payroll_batch='',payroll_adjustment=False,tax_breakdown_present=True)
    # Reference population is historical and disjoint from scenario-specific vendors.
    for _ in range(13000):
        row=base(datetime(2024,4,1,10)+timedelta(days=R.randrange(365),minutes=R.randrange(420)))
        transactions.append(row)
    for source,kind,severity,n in CATALOG:
        before=len(transactions); evidence=[]
        for block in range(0,n,10):
            gid=f'{source}-{kind}-{block//10:03}'
            v=dict(vendors[0]); v.update(vendor_id=f'VEN{len(vendors)+1:04}',vendor_name=f'Aster Test {kind} Supplier {block//10:03}')
            # Scenario names are retained in the master for manual inspection; not model features.
            vendors.append(v)
            v2=dict(v); v2.update(vendor_id=f'VEN{len(vendors)+1:04}',vendor_name=v['vendor_name']+' Partner',bank_account=v['bank_account']+'-B',phone=v['phone']+'-B',address=v['address']+' B',director=v['director']+' B'); vendors.append(v2)
            v.update(bank_account=gid+'-BANK',phone=gid+'-PHONE',address=gid+'-ADDRESS',director=gid+'-DIRECTOR')
            # Normalize the partner to independent identity before selected shared-field injections.
            v2.update(bank_account=gid+'-BANK-B',phone=gid+'-PHONE-B',address=gid+'-ADDRESS-B',director=gid+'-DIRECTOR-B')
            e=employees[(block//10)%250]
            date=datetime(2025,7,7,11)+timedelta(days=(block//10)*7)
            if kind in ['fake_vendors','vendor_invoice_fraud','fake_vendor']:
                v.update(gstin='99INVALID0000Z0',verification_status='unverified',vendor_name='Aster Test Suppller '+gid,address='Unverified test address',email='disposable@invalid.example')
            if kind in ['ghost_vendor','new_vendor_large_payment']: v['onboarded_at']=(date-timedelta(days=3)).date().isoformat()
            if kind in ['complex_structure_risk']: v['country']='British Virgin Islands'
            if kind=='related_party': v.update(address=e['address'],director=e['employee_name'])
            if kind=='circular_payment': v.update(bank_account=e['bank_account'],phone=e['phone'])
            for field,kinds in [('bank_account',['shared_bank','shell_network']),('address',['shared_address','shell_network']),('phone',['shared_phone','shell_network']),('director',['shell_network'])]:
                if kind in kinds: v2[field]=v[field]
            if kind=='shell_network': v['onboarded_at']=v2['onboarded_at']='2025-07-01'
            # Historical control values for statistical cases, always preceding target transactions.
            if kind in ['unusual_amount','unusual_flow','unknown_emerging_risk']:
                for h in range(30):
                    row=base(date-timedelta(days=60-h),v,e); row.update(amount=1000+h%5*10,receipt_amount=1000+h%5*10)
                    transactions.append(row)
            ids=[]
            for j in range(10):
                row=base(date+timedelta(minutes=j*60),v2 if j%2 and kind in ['shared_bank','shared_address','shared_phone','shell_network'] else v,e)
                if kind in ['vendor_invoice_fraud','fake_vendors','fake_vendor']: row['receipt_vendor']=v['vendor_name']
                if kind=='payroll_fraud_risk':
                    ghost=dict(e); ghost.update(employee_id=f'GHOST-{gid}-{j}',employee_name='Unverified Payroll Fixture',payroll_verified=False); employees.append(ghost)
                    row.update(employee_id=ghost['employee_id'],amount=350000,account='Payroll',payroll_adjustment=True,payroll_batch='MANUAL-OFF-CYCLE')
                if kind=='complex_structure_risk': row.update(amount=7500000,contract_terms='intercompany licensing via layered holding entities')
                if kind=='manual_journal_manipulation': row.update(amount=2500000,account='Manual Journal Adjustment',purchase_order='',supporting_document='')
                if kind in ['receipt_mismatch','amount_inflation']: row.update(amount=25000,receipt_amount=5000)
                if kind=='unknown_emerging_risk': row.update(amount=63543.27,account='Research Licensing',payment_method='SWIFT',posting_timestamp=date.replace(hour=2).isoformat())
                if kind=='revenue_cutoff': row.update(amount=9200000,account='Revenue',posting_timestamp='2026-03-31T23:58:00',revenue_delivery_date='2026-04-05')
                if kind in ['duplicate_entry','duplicate_payment','duplicate']: row.update(amount=14235.51,invoice_number=gid+'-INVOICE',receipt_reference=gid+'-RECEIPT',posting_timestamp=(date+timedelta(hours=j if kind=='duplicate_entry' else 24*j)).isoformat())
                if kind=='complex_financial_instrument': row.update(instrument='OTC cross-currency swap',amount=8400000,account='Treasury Derivatives')
                if kind in ['ghost_vendor','new_vendor_large_payment']: row.update(amount=2500000)
                if kind=='unusual_amount': row['amount']=150000
                if kind=='unusual_flow': row['amount']=75000
                if kind in ['split_invoice','invoice_splitting','split_transaction']: row.update(amount=48000,purchase_order=gid+'-ORDER',business_purpose='Factory equipment installment')
                if kind=='rare_flow': v['category']='Travel'; row['account']='Raw Materials'
                if kind=='cash_payment': row.update(amount=150000,payment_method='Cash')
                if kind=='reversal': row.update(amount=-450000,account='Credit Note',original_transaction_id='')
                if kind=='high_monetary_value': row.update(amount=90000000,approver_id='EMP294')
                if kind=='personal_expense': row.update(business_purpose='Personal family resort holiday',account='Corporate Card')
                if kind=='benford_cohort': row['amount']=[71234.15,82345.26,93456.37][j%3]
                if kind in ['weekend_after_hours','weekend_payment','weekend_claim']: row.update(posting_timestamp=date.replace(hour=23).__add__(timedelta(days=6)).isoformat(),business_purpose='')
                if kind=='midnight_payment': row['posting_timestamp']=date.replace(hour=2).isoformat()
                if kind=='suspicious_wording': row['business_purpose']='off-the-books undisclosed facilitation'
                if kind=='sequence_gaps': row.update(invoice_sequence=1000+j*500,invoice_number=f'{gid}-INV-{1000+j*500}')
                if kind in ['round_number','round_payment']: row.update(amount=[500000,2000000][j%2],tax_breakdown_present=False)
                if kind=='missing_information': row.update(amount='' if j%3==0 else row['amount'],vendor_id='' if j%3==1 else row['vendor_id'],business_purpose='')
                if kind=='circular_payment': row.update(approver_id=employees[250]['employee_id'])
                if kind=='approval_limit': row.update(amount=350000,approver_id='EMP294')
                if kind=='excessive_reimbursement': row.update(amount=125000,account='Employee Reimbursement')
                if kind not in ['receipt_mismatch','amount_inflation']: row['receipt_amount']=row['amount']
                transactions.append(row); ids.append(row['transaction_id'])
                labels.append(dict(transaction_id=row['transaction_id'],source_taxonomy=source,anomaly_type=kind,severity=severity,scenario_group_id=gid,is_injected_anomaly=True,evidence='See scenario-specific fields and linked group; synthetic review trigger, not a finding',expected_review_team='HR' if kind=='payroll_fraud_risk' else 'Treasury' if kind=='complex_financial_instrument' else 'Finance',model_detection_guaranteed=False))
            groups.append(dict(scenario_group_id=gid,anomaly_type=kind,transaction_ids='|'.join(ids),scope='cohort' if kind=='benford_cohort' else 'linked_group'))
        count=sum(x['anomaly_type']==kind and x['source_taxonomy']==source for x in labels)
        assert count==n,(kind,count,n)
        checks.append(dict(source=source,anomaly_type=kind,expected=n,actual=count,passed=True))
    # Expense-only controls and upload projection: never cast ERP payments as employee claims.
    expense_rows=[]
    for _ in range(1850):
        row=base(); row['account']='Employee Reimbursement'; transactions.append(row); expense_rows.append(row)
    expense_ids={l['transaction_id'] for l in labels if l['source_taxonomy']=='expense'}
    expense_rows += [r for r in transactions if r['transaction_id'] in expense_ids]
    em={e['employee_id']:e for e in employees}; vm={v['vendor_id']:v for v in vendors}; lm={l['transaction_id']:l for l in labels}
    claims=[]
    for r in expense_rows:
        l=lm.get(r['transaction_id']); v=vm[r['vendor_id']]
        claims.append(dict(claim_id=r['transaction_id'].replace('TXN','CLM'),employee_id=r['employee_id'],employee_name=em[r['employee_id']]['employee_name'],claimed_amount=r['amount'],vendor_name=v['vendor_name'],claimed_date=r['posting_timestamp'][:10],submitted_at=r['posting_timestamp'],category='Travel',description=r['business_purpose'],ocr_amount=r['receipt_amount'],ocr_vendor=r['receipt_vendor'],is_fraud=bool(l),fraud_type=l['anomaly_type'] if l else 'none'))
    ids={r['transaction_id'] for r in transactions}
    assert len(ids)==len(transactions)
    assert all(r['employee_id'] in em for r in transactions)
    assert all(not r['vendor_id'] or r['vendor_id'] in vm for r in transactions)
    assert len(labels)==5150 and len(claims)==2000
    # Check actual injected relationships rather than only checking the labels.
    byid={r['transaction_id']:r for r in transactions}
    for g in groups:
        rr=[byid[i] for i in g['transaction_ids'].split('|')]; k=g['anomaly_type']
        if k in ['split_invoice','invoice_splitting','split_transaction']: assert all(r['amount']<50000 for r in rr) and sum(r['amount'] for r in rr)>50000 and len({r['posting_timestamp'][:10] for r in rr})==1
        if k in ['duplicate','duplicate_payment','duplicate_entry']: assert len({(r['vendor_id'],r['invoice_number'],r['amount'],r['receipt_reference']) for r in rr})==1
        if k in ['receipt_mismatch','amount_inflation']: assert all(r['amount']==5*r['receipt_amount'] for r in rr)
        if k in ['shared_bank','shared_address','shared_phone','shell_network']:
            field={'shared_bank':'bank_account','shared_address':'address','shared_phone':'phone','shell_network':'director'}[k]
            assert len({r['vendor_id'] for r in rr})==2 and len({vm[r['vendor_id']][field] for r in rr})==1
        if k in ['weekend_claim','weekend_payment','weekend_after_hours']: assert all(datetime.fromisoformat(r['posting_timestamp']).weekday()==6 for r in rr)
        if k=='approval_limit': assert all(r['amount']>em[r['approver_id']]['approval_limit'] for r in rr)
    transactions.sort(key=lambda r:(r['posting_timestamp'],r['transaction_id']))
    write('transactions.csv',transactions); write('employees.csv',employees); write('vendors.csv',vendors)
    write('anomaly_labels.csv',labels); write('scenario_groups.csv',groups); write('expense_claims_upload.csv',claims); write('coverage_validation.csv',checks)
    dictionary=[dict(file='transactions.csv',column=k,meaning={'amount':'INR; blank deliberately in data quality scenarios','posting_timestamp':'Synthetic local India time, ISO 8601','receipt_amount':'Simulated receipt total; not real OCR','original_transaction_id':'Original entry reference for reversal checks'}.get(k,k.replace('_',' '))) for k in transactions[0]]
    write('data_dictionary.csv',dictionary)
    profile=dict(company_name=COMPANY,industry='Manufacturing and industrial components',currency='INR',timezone='Asia/Kolkata',period='2024-04-01 through 2026-03-31',offices=['Pune','Chennai','Bengaluru'],manager_limit=50000,senior_manager_limit=250000,new_vendor_window_days=7,new_vendor_large_payment=2000000,cash_review_limit=10000,expense_review_limit=50000,working_hours='09:00-18:00 Monday-Friday',source='User supplied scenario taxonomy; all thresholds are fictional demo company policy, not statutory requirements',seed=42)
    (OUT/'company_profile.json').write_text(json.dumps(profile,indent=2),encoding='utf-8')
    report=dict(transactions=len(transactions),planted_anomaly_transactions=len(labels),unlabelled_control_transactions=len(transactions)-len(labels),taxonomy_categories=len(CATALOG),scenario_groups=len(groups),expense_claims=len(claims),expense_anomalies=150,checks='Coverage, unique IDs, master references, split groups, duplicates, receipt mismatches, shared identities, Sunday dates, approval limits passed')
    (OUT/'validation_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (OUT/'README.md').write_text('''# Aster company demo dataset

Entirely fictional Indian components manufacturer. No real company or personal data.

Start with company_profile.json, then transactions.csv. Link employee_id and vendor_id to their master files. anomaly_labels.csv is the answer key, and scenario_groups.csv identifies records that must be inspected together. coverage_validation.csv lists all 45 requested categories independently, including overlapping taxonomies. The user-specified counts are preserved: enterprise 25 x 80, ERP 15 x 200, expense 5 x 30.

Upload expense_claims_upload.csv through the existing claims upload as a reviewer/admin. It contains 2,000 claims (1,850 controls and 150 injected scenarios). Uploading records makes the uploader a contributor, so use other accounts for review; master employee IDs are fictional and do not provision accounts. No live data has been imported or models retrained by the generator.

Full ERP coverage requires new ingestion fields, master joins, rules and review routing; the current expense model will not automatically detect all 45 categories. Raw transactions intentionally include missing data and negative credit notes and are not a drop-in claims upload. Imported receipt totals are simulated, not extracted from actual images. Duplicate receipt_reference represents reuse of the same synthetic receipt; receipt images and OCR performance are not tested.

Keep anomaly_labels, scenario group IDs, source taxonomy, and descriptive master names OUT of model features. is_fraud in the upload is a legacy field for the planted scenario label, not a legal finding. In controls, absence of a planted scenario does not guarantee every policy check passes. Do not report synthetic accuracy as real-world fraud detection performance.

Suggested use: fit historical baselines using transactions before 2025-04-01; calibrate on a separate later control sample; evaluate injected scenarios separately. Split linked groups together and prevent employee/vendor identity leakage. Labels and dates deliberately create a controlled benchmark, not a production distribution.

Benford is a cohort screen, not an individual fraud label. Unknown/emerging risk is a deliberately unusual multivariate fixture; no model result has been fabricated. Offshore transactions, new vendors, round values and weekend activity are review triggers, not proof of wrongdoing. No fixed risk probabilities have been invented. Tax identifiers and banks use TEST fixtures except intentionally malformed identifiers; verified_fixture means trusted synthetic master data, not government verification. Circular_payment models employee/vendor-linked collusion (as described in the request), not a bank-to-bank circular cash-flow graph.

Company-specific policies: manager cap INR 50,000; CFO cap INR 50 million; senior-manager example policy INR 250,000; new vendor window 7 days; new-vendor payment trigger INR 2 million; cash review over INR 10,000; weekdays 09:00-18:00. Change the generator and profile together to adapt to your own company. All values are demo assumptions.

Data dictionary covers the raw transaction columns. Master columns describe employee organization and vendor identity; labels contain answer keys, severity and expected review teams; groups list pipe-separated transaction IDs. No model scores or actual approval decisions are included.
''',encoding='utf-8')
    archive=OUT.parent/'aster_company_dataset.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.iterdir()): z.write(p,arcname=p.name)
    print(json.dumps(report,indent=2)); print(archive)

if __name__=='__main__': build()
