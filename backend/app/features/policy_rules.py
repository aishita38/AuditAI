"""Explicit demo-company checks, independent of ML and synthetic labels."""
import json
import re
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path

CONFIG=json.loads((Path(__file__).resolve().parents[1]/'policy_config.json').read_text())
IST=timezone(timedelta(hours=5,minutes=30))


def evaluate_policy(records, config=None):
    cfg=config or CONFIG
    inv=defaultdict(list); hashes=defaultdict(list); amounts=defaultdict(list); groups=defaultdict(list); series=defaultdict(list)
    def key(r): return (r.get('entity_id'), str(r.get('vendor','')).strip().casefold())
    for r in records:
        rkey=key(r)
        if r.get('invoice_id'): inv[(rkey,r['invoice_id'].strip().casefold())].append(r)
        if r.get('receipt_hash'): hashes[(r.get('entity_id'),r['receipt_hash'])].append(r)
        amounts[(rkey,str(Decimal(str(r['amount'])).quantize(Decimal('.01'))))].append(r)
        groups[(rkey,r.get('employee_id'),str(r['date']))].append(r)
        if r.get('invoice_series') and r.get('invoice_sequence') is not None:
            series[(rkey,r['invoice_series'])].append(r)
    gaps={}
    for group in series.values():
        ordered=sorted(group,key=lambda r:(r['date'],r['id']))
        previous=None
        for r in ordered:
            seq=int(r['invoice_sequence'])
            if previous and seq-previous[0]>cfg['sequence_gap_threshold']: gaps[r['id']]=(previous[0],seq,previous[1])
            previous=(seq,r['id'])
    results={}
    for r in records:
        checks=[]; amount=Decimal(str(r['amount'])); required=abs(amount)
        def add(code,status,detail,peers=None):
            checks.append(dict(code=code,status=status,detail=detail,related_claims=peers or []))
        currency_ok=r.get('currency')==cfg['currency']
        if r.get('source_approver_limit') is None: add('approval_limit','unavailable','Original approver authority was not supplied by an administrator.')
        elif not currency_ok: add('approval_limit','unavailable','Company currency is missing or different; no FX conversion is assumed.')
        else: add('approval_limit','review' if abs(amount)>Decimal(str(r['source_approver_limit'])) else 'pass',f"Amount {amount}; source approver limit {r['source_approver_limit']}; approver {r.get('source_approver_id') or 'unspecified'}.")
        group=groups[(key(r),r.get('employee_id'),str(r['date']))]
        total=sum((abs(Decimal(str(p['amount']))) for p in group),Decimal(0))
        split=currency_ok and len(group)>1 and total>cfg['split_threshold'] and all(0<Decimal(str(p['amount']))<cfg['split_threshold'] for p in group)
        if split: required=max(required,total)
        add('invoice_splitting','review' if split else ('pass' if currency_ok else 'unavailable'),f'{len(group)} claims, same employee/vendor/local date; combined {total}; threshold {cfg["split_threshold"]}.',[p['id'] for p in group if split and p['id']!=r['id']])
        definite=[]
        if r.get('invoice_id'): definite += inv[(key(r),r['invoice_id'].strip().casefold())]
        if r.get('receipt_hash'): definite += hashes[(r.get('entity_id'),r['receipt_hash'])]
        peers=sorted({p['id'] for p in definite if p['id']!=r['id']})
        probable=[p['id'] for p in amounts[(key(r),str(amount.quantize(Decimal('.01'))))] if p['id']!=r['id'] and abs((p['date']-r['date']).days)<=cfg['duplicate_window_days']]
        add('duplicate','review' if peers or probable else ('pass' if r.get('invoice_id') or r.get('receipt_hash') else 'unavailable'), 'Matching invoice/receipt fingerprint.' if peers else ('Same vendor and amount within 30 days; possible recurring payment, verify.' if probable else 'No matching evidence; invoice ID or exact receipt fingerprint required for a full check.'),peers or probable)
        ocr=r.get('ocr_amount'); confidence=r.get('ocr_confidence')
        usable=r.get('ocr_processed') and ocr is not None and (confidence is None or confidence>=cfg['minimum_ocr_confidence'])
        if usable:
            diff=abs(amount-Decimal(str(ocr))); tolerance=max(Decimal(str(cfg['receipt_absolute_tolerance'])),abs(Decimal(str(ocr)))*Decimal(str(cfg['receipt_relative_tolerance'])))
            add('receipt_mismatch','review' if diff>tolerance else 'pass',f'Claim {amount}; receipt {ocr}; difference {diff}; tolerance {tolerance}.')
        else: add('receipt_mismatch','unavailable','Receipt amount missing, OCR failed, or extraction confidence below policy minimum.')
        add('high_value','review' if currency_ok and required>cfg['high_value_threshold'] else ('pass' if currency_ok else 'unavailable'),f'Required approval amount {required}; senior-review threshold {cfg["high_value_threshold"]}.')
        add('weekend','review' if r['date'].weekday()>=5 and not r.get('business_exception') else 'pass',f"Claim date {r['date']}; exception recorded: {bool(r.get('business_exception'))}.")
        ts=r.get('event_timestamp')
        if ts:
            local=datetime.fromisoformat(ts.replace('Z','+00:00')).astimezone(IST)
            after=local.hour<cfg['business_start_hour'] or local.hour>=cfg['business_end_hour']
            add('after_hours','review' if after and not r.get('business_exception') else 'pass',f'Transaction time {local.isoformat()}; company hours 09:00–18:00 Asia/Kolkata.')
        else: add('after_hours','unavailable','No timezone-aware transaction timestamp supplied; upload time is not transaction time.')
        if not r.get('invoice_series') or r.get('invoice_sequence') is None: add('sequence_gap','unavailable','Vendor invoice series and numeric sequence required.')
        elif r['id'] in gaps:
            a,b,previous=gaps[r['id']]; add('sequence_gap','review',f'Invoice sequence jumps from {a} to {b}; incomplete imports may explain the gap.',[previous])
        else: add('sequence_gap','pass','No gap above threshold in the available series history.')
        found=[p for p in cfg['suspicious_phrases'] if re.search(r'(?<!\w)'+re.escape(p)+r'(?!\w)',str(r.get('description') or ''),re.I)]
        add('suspicious_wording','review' if found else 'pass','Matched phrases: '+', '.join(found) if found else 'No configured phrases matched.')
        missing=[k for k in ['vendor','employee_id','description'] if not str(r.get(k) or '').strip()]
        add('missing_info','review' if missing else 'pass','Missing: '+', '.join(missing) if missing else 'Core descriptive fields present; optional evidence availability is reported separately.')
        rounded=amount!=0 and abs(amount)%cfg['round_multiple']==0
        other=any(c['status']=='review' for c in checks)
        add('round_number','review' if rounded and currency_ok and (abs(amount)>=cfg['round_materiality'] or other) else ('signal' if rounded else 'pass'),'Round multiple of INR 1,000; requires materiality or another review signal to force review.' if rounded else 'Not a round INR 1,000 multiple.')
        results[r['id']]=dict(policy_version=cfg['version'],requires_review=any(c['status']=='review' for c in checks),required_approval_amount=str(required),currency=r.get('currency'),checks=checks)
    return results
