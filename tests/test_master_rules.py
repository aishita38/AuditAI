import copy,json
from decimal import Decimal
from pathlib import Path
import pytest
from backend.app.features.master_rules import *
from backend.app.master_import_service import normalize_row
from scripts.generate_master_rule_dataset import build
from scripts.evaluate_master_rules import signature


def inputs():
    v,e,p,t,truth=build()
    return ([normalize_row('vendor-master',r) for r in v],[normalize_row('employee-roster',r) for r in e],[normalize_row('payroll-payments',r) for r in p],t,truth)


@pytest.mark.parametrize('rule',list(build()[4]['decoys']))
def test_each_rule_catches_injected_cases_and_rejects_decoys(rule):
    v,e,p,t,truth=inputs()
    original=copy.deepcopy((v,e,p,t))
    findings=[f for f in evaluate_vendors(v,transactions=t)+evaluate_payroll(e,p) if f['rule_id']==rule]
    expected=[f for f in truth['findings'] if f['rule_id']==rule]
    assert findings and {signature(f) for f in findings}=={signature(f) for f in expected}
    involved={key for f in findings for ids in f['involved_record_ids'].values() for key in ids}
    assert not involved.intersection(truth['decoys'][rule])
    assert (v,e,p,t)==original


def test_configurable_thresholds_strict_boundaries_and_first_recorded_payment():
    v,_,_,t,_=inputs()
    assert not vendor_new_large_payment(v,RuleConfig(new_vendor_amount_inr=3000000),t)
    assert not vendor_new_large_payment(v,RuleConfig(new_vendor_days=6),t)
    earlier=dict(t[0],transaction_id='EARLY',amount='10',timestamp='2024-12-31')
    assert not vendor_new_large_payment(v,configuration(),t+[earlier])
    assert not vendor_new_large_payment(v,configuration(),None)
    assert not vendor_new_large_payment(v,configuration(),[dict(t[0],currency='USD')])


def test_salary_tolerance_zero_and_pan_is_roster_only():
    _,e,p,_,_=inputs()
    assert not payroll_salary_mismatch(e,p,RuleConfig(salary_tolerance='.1'))
    assert payroll_salary_mismatch([dict(e[0],monthly_salary=0)],[p[0]],configuration())
    assert not payroll_duplicate_payee([], [dict(p[0],pan='SAME'),dict(p[1],pan='SAME')],configuration())


def test_missing_values_never_match_and_director_names_are_normalized():
    v,_,_,_,_=inputs()
    blank=[r for r in v if r['vendor_id'].startswith('EMPTY')]
    assert not evaluate_vendors(blank)
    records=[dict(v[0],vendor_id='X',director_names=' Alice   Rao '),dict(v[1],vendor_id='Y',director_names='alice rao')]
    network=vendor_shell_network(records,configuration())
    assert len(network)==1 and network[0]['evidence']['links'][0]['field']=='director_names'


def test_later_large_payment_on_first_day_is_not_the_first_payment():
    v,_,_,t,_=inputs()
    early=dict(t[0],transaction_id='FIRST-SMALL',timestamp='2025-01-08T08:00:00Z',amount='100')
    late=dict(t[0],timestamp='2025-01-08T09:00:00Z')
    assert not vendor_new_large_payment(v,configuration(),[early,late])
