import json
from types import SimpleNamespace
from backend.app import detection_strategy as ds
from backend.app.api.detection import mode_results
from scripts.retrain_expense_benchmark import benchmark_roles


def test_per_dataset_thresholds_and_enterprise_model_disable(tmp_path,monkeypatch):
    path=tmp_path/'strategy.json'
    path.write_text(json.dumps(dict(aster=dict(threshold=.4351),original=dict(threshold=.34))))
    monkeypatch.setattr(ds,'PATH',path)
    ds._settings.cache_clear()
    assert ds.model_decision('AST-1',.44) is True
    assert ds.model_decision('CLM-1',.35) is True
    assert ds.model_decision('AST-1',.43) is False
    assert ds.model_decision('TXN001',.99) is False
    row=SimpleNamespace(claim_id='TXN001',is_fraud=True,fraud_type='anomaly',combined_fraud_score=None,holiday_policy=0,policy_review=True)
    result=mode_results([row])
    assert result['model_only']['disabled']
    assert result['model_only']['metrics']['precision'] is None
    assert result['combined']['metrics']['true_positive']==1
    assert result['combined']['metrics']==result['policy_only']['metrics']


def test_fixed_group_split_is_exhaustive_and_vendor_disjoint():
    claims=[SimpleNamespace(claim_id=f'{prefix}{i}-{y}', vendor_name=f'{prefix}Vendor{i}',is_fraud=bool(y))
            for prefix in ('AST-','CLM-') for i in range(30) for y in (0,1)]
    roles=benchmark_roles(claims)
    assert set(roles)=={0,1,2,3}
    assert benchmark_roles(claims)==roles
    owners={}
    for c,r in zip(claims,roles):
        assert owners.setdefault(c.vendor_name,r)==r
