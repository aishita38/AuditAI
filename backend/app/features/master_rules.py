"""Deterministic review signals on normalized business records; never ML inputs."""
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import json
from pydantic import BaseModel, Field


class RuleConfig(BaseModel):
    new_vendor_amount_inr: Decimal = Field(default=Decimal('2000000'), ge=0)
    new_vendor_days: int = Field(default=7, ge=0, le=365)
    salary_tolerance: Decimal = Field(default=Decimal('.05'), ge=0, le=1)


def configuration():
    return RuleConfig.model_validate(json.loads(Path(__file__).parents[1].joinpath('master_rule_config.json').read_text(encoding='utf-8')))


def day(value):
    return value.date() if isinstance(value,datetime) else value if isinstance(value,date) else date.fromisoformat(str(value)[:10])

def moment(value):
    stamp=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    return stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp.astimezone(timezone.utc)


def normalized(field,value):
    if not value: return None
    value=str(value).strip()
    if field in ('bank_account','phone'): return re.sub(r'[\s-]','',value) or None
    if field in ('address','director_names'): return ' '.join(value.casefold().split()) or None
    return value.upper() or None


def finding(rule,severity,explanation,*,vendors=None,payments=None,employees=None,fields=None,**extra):
    groups={'vendors':vendors or [],'payments':payments or [],'employees':employees or []}
    ids={key:[str(r['vendor_id' if key=='vendors' else 'payment_id' if key=='payments' else 'employee_id']) for r in rows] for key,rows in groups.items()}
    if extra.get('transactions'): ids['transfers']=[str(t['transaction_id']) for t in extra['transactions']]
    return dict(rule_id=rule,severity=severity,involved_record_ids=ids,explanation=explanation,
        evidence=dict(**groups,trigger_fields=fields or [],explanation=explanation,**extra))


def vendor_shared(vendors,field,rule):
    groups=defaultdict(list)
    for v in vendors:
        key=normalized(field,v.get(field))
        if key:groups[key].append(v)
    return [finding(rule,'high' if field=='bank_account' else 'medium',f'{len(rows)} different vendors share {field.replace("_"," ")}.',vendors=rows,fields=[field],shared_value=value)
            for value,rows in sorted(groups.items()) if len({v['vendor_id'] for v in rows})>1]


def vendor_shared_bank(vendors,config): return vendor_shared(vendors,'bank_account','VENDOR_SHARED_BANK')
def vendor_shared_address(vendors,config): return vendor_shared(vendors,'address','VENDOR_SHARED_ADDRESS')
def vendor_shared_phone(vendors,config): return vendor_shared(vendors,'phone','VENDOR_SHARED_PHONE')


def vendor_shell_network(vendors,config):
    # Attribute buckets form a bipartite graph; BFS avoids constructing a quadratic clique.
    by_id={v['vendor_id']:v for v in vendors};buckets=defaultdict(set);members=defaultdict(list)
    for v in vendors:
        for field in ('bank_account','phone','address','director_names'):
            values=str(v.get(field) or '').split(';') if field=='director_names' else [v.get(field)]
            for value in values:
                key=normalized(field,value)
                if key:buckets[(field,key)].add(v['vendor_id']);members[v['vendor_id']].append((field,key))
    unseen=set(by_id);result=[]
    while unseen:
        start=min(unseen);unseen.remove(start);component={start};pending=[start];links={}
        while pending:
            current=pending.pop()
            for attribute in members[current]:
                neighbors=buckets[attribute]
                if len(neighbors)>1:links[attribute]=neighbors
                new=neighbors & unseen;unseen.difference_update(new);component.update(new);pending.extend(sorted(new))
        if len(component)>1:
            edges=[dict(field=f,value=v,vendor_ids=sorted(ids)) for (f,v),ids in sorted(links.items())]
            result.append(finding('VENDOR_SHELL_NETWORK','high',f'{len(component)} vendors form a connected group through shared attributes; this is a review signal.',vendors=[by_id[i] for i in sorted(component)],fields=sorted({e['field'] for e in edges}),links=edges))
    return result


def vendor_new_large_payment(vendors,config,transactions):
    if transactions is None:return []
    grouped=defaultdict(list)
    for t in transactions:
        if t.get('vendor_id'):grouped[t['vendor_id']].append(t)
    result=[]
    for v in vendors:
        payments=grouped.get(v['vendor_id'],[])
        if not payments:continue
        first=min(moment(t.get('timestamp') or t['payment_date']) for t in payments)
        elapsed=(first.date()-day(v['onboarding_date'])).days
        selected=[t for t in payments if moment(t.get('timestamp') or t['payment_date'])==first and t.get('currency','').upper()=='INR' and Decimal(str(t['amount']))>config.new_vendor_amount_inr]
        if 0<=elapsed<=config.new_vendor_days and selected:
            result.append(finding('VENDOR_NEW_LARGE_PAYMENT','high',f'First recorded payment exceeds INR {config.new_vendor_amount_inr} within {config.new_vendor_days} days of onboarding.',vendors=[v],fields=['amount','onboarding_date','timestamp'],transactions=selected,days_after_onboarding=elapsed))
    return result


def vendor_invalid_tax_id(vendors,config):
    result=[]
    for v in vendors:
        pan=normalized('pan',v.get('pan'));gst=normalized('gstin',v.get('gstin'));issues=[];fields=[]
        if pan and not re.fullmatch(r'[A-Z]{5}[0-9]{4}[A-Z]',pan):issues.append('PAN format invalid');fields.append('pan')
        if gst and not re.fullmatch(r'[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]',gst):issues.append('GSTIN format invalid');fields.append('gstin')
        if pan and gst and re.fullmatch(r'[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]',gst) and gst[2:12]!=pan:issues.append('Embedded GSTIN PAN differs from vendor PAN');fields+=['pan','gstin']
        if issues:result.append(finding('VENDOR_INVALID_TAX_ID','medium','; '.join(issues)+'. Format check, not verification.',vendors=[v],fields=sorted(set(fields))))
    return result


def payroll_ghost_employee(employees,payments,config):
    roster={e['employee_id'] for e in employees}
    return [finding('PAYROLL_GHOST_EMPLOYEE','high','Payment employee_id is absent from the imported roster.',payments=[p],fields=['employee_id'],roster_match='Not found at capture') for p in payments if p['employee_id'] not in roster]


def paired(employees,payments,rule,predicate,explanation,fields):
    roster={e['employee_id']:e for e in employees}
    return [finding(rule,'high' if rule in ('PAYROLL_AFTER_EXIT','PAYROLL_BEFORE_JOIN') else 'medium',explanation,payments=[p],employees=[roster[p['employee_id']]],fields=fields) for p in payments if p['employee_id'] in roster and predicate(p,roster[p['employee_id']])]


def payroll_after_exit(employees,payments,config):
    return paired(employees,payments,'PAYROLL_AFTER_EXIT',lambda p,e:e.get('exit_date') and day(p['payment_date'])>day(e['exit_date']),'Payment date is after the roster exit date.',['payment_date','exit_date'])


def payroll_before_join(employees,payments,config):
    return paired(employees,payments,'PAYROLL_BEFORE_JOIN',lambda p,e:day(p['payment_date'])<day(e['join_date']),'Payment date is before the roster join date.',['payment_date','join_date'])


def payroll_duplicate_payee(employees,payments,config):
    result=[]
    for field in ('bank_account','pan'):
        groups=defaultdict(lambda:{'employees':[],'payments':[]})
        for kind,rows in [('employees',employees),('payments',payments if field=='bank_account' else [])]:
            for r in rows:
                key=normalized(field,r.get(field))
                if key:groups[key][kind].append(r)
        for value,g in sorted(groups.items()):
            if len({r['employee_id'] for rows in g.values() for r in rows})>1:
                result.append(finding('PAYROLL_DUPLICATE_PAYEE','high',f'Different employee IDs share {field.replace("_"," ")}. PAN matching is roster-only; bank accounts are compared across roster and payments.',fields=[field],shared_value=value,**g))
    return result


def payroll_salary_mismatch(employees,payments,config):
    return paired(employees,payments,'PAYROLL_SALARY_MISMATCH',lambda p,e:abs(Decimal(str(p['amount']))-Decimal(str(e['monthly_salary'])))>abs(Decimal(str(e['monthly_salary'])))*config.salary_tolerance,f'Payment differs from roster monthly salary by more than {config.salary_tolerance*100}% (no adjustment for bonuses or prorating).',['amount','monthly_salary'])


def payroll_duplicate_payment(employees,payments,config):
    groups=defaultdict(list);roster={e['employee_id']:e for e in employees}
    for p in payments:groups[(p['employee_id'],p['pay_period'])].append(p)
    return [finding('PAYROLL_DUPLICATE_PAYMENT','high','Multiple payments for the same employee_id and pay_period; installments may be legitimate.',payments=rows,employees=[roster[key[0]]] if key[0] in roster else [],fields=['employee_id','pay_period']) for key,rows in sorted(groups.items()) if len(rows)>1]


def payroll_bank_mismatch(employees,payments,config):
    return paired(employees,payments,'PAYROLL_BANK_MISMATCH',lambda p,e:normalized('bank_account',p.get('bank_account')) and normalized('bank_account',e.get('bank_account')) and normalized('bank_account',p['bank_account'])!=normalized('bank_account',e['bank_account']),'Payment bank account differs from the linked roster bank account.',['bank_account'])


VENDOR_RULES=[vendor_shared_bank,vendor_shared_address,vendor_shared_phone,vendor_shell_network,vendor_invalid_tax_id]
PAYROLL_RULES=[payroll_ghost_employee,payroll_after_exit,payroll_before_join,payroll_duplicate_payee,payroll_salary_mismatch,payroll_duplicate_payment,payroll_bank_mismatch]


def evaluate_vendors(vendors,config=None,transactions=None):
    config=config or configuration()
    return [f for rule in VENDOR_RULES for f in rule(vendors,config)]+vendor_new_large_payment(vendors,config,transactions)


def evaluate_payroll(employees,payments,config=None):
    config=config or configuration()
    return [f for rule in PAYROLL_RULES for f in rule(employees,payments,config)]
