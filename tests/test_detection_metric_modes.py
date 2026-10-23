from types import SimpleNamespace
import pytest
from backend.app.api.detection import mode_results


def row(cid,label,score,policy,holiday=0,saved_flag=False):
    return SimpleNamespace(claim_id=cid,is_fraud=label,fraud_type='anomaly' if label else 'none',combined_fraud_score=score,policy_review=policy,holiday_policy=holiday,is_flagged=saved_flag)


def test_model_policy_and_union_have_independent_counts_and_deduplicate_overlap():
    rows=[row('BOTH',True,.9,True),row('ML',True,.8,False),row('POLICY',True,.1,True,saved_flag=True),row('NORMAL',False,.2,True,saved_flag=True),row('SAFE',False,.1,False)]
    result=mode_results(rows)
    model,policy,combined=[result[k] for k in ('model_only','policy_only','combined')]
    assert [r['flagged'] for r in (model,policy,combined)]==[2,3,4]
    assert model['metrics']['precision']==1 and model['metrics']['recall']==pytest.approx(2/3)
    assert policy['metrics']['precision']==pytest.approx(2/3) and policy['metrics']['recall']==pytest.approx(2/3)
    assert combined['metrics']['precision']==.75 and combined['metrics']['recall']==1
    assert [r['metrics']['evaluated'] for r in result.values()]==[5,5,5]
    assert model['metrics']['average_precision'] is not None
    assert policy['metrics']['average_precision'] is None and combined['metrics']['average_precision'] is None
    assert policy['metrics']['precision_at_k']=={} and combined['metrics']['precision_at_k']=={}


def test_holiday_override_is_policy_not_model_and_threshold_is_inclusive():
    result=mode_results([row('HOLIDAY',True,.1,False,holiday=1,saved_flag=True),row('BOUNDARY',True,.5,False)])
    assert result['model_only']['flagged']==1
    assert result['policy_only']['flagged']==1
    assert result['combined']['flagged']==2


def test_unknown_policy_unscored_and_unlabelled_are_not_treated_as_safe():
    rows=[row('UNKNOWN',True,.8,None,holiday=None),row('UNSCORED',True,None,True),row('KNOWN',False,.1,False)]
    rows.append(SimpleNamespace(**{**vars(row('UNLABELLED',False,.8,True)),'fraud_type':'unknown'}))
    result=mode_results(rows)
    assert all(r['metrics']['evaluated']==1 for r in result.values())
    assert result['policy_only']['available']==3
    assert result['model_only']['available']==3
    assert result['combined']['available']==4  # A known positive OR is evaluable.
    assert result['combined']['metrics']['true_positive']==0
    empty=mode_results([])
    assert all(r['metrics']['precision'] is None for r in empty.values())


def test_explicit_negative_holiday_flag_is_known_legacy_policy_coverage():
    result=mode_results([row('LEGACY',True,.8,None,holiday=0,saved_flag=True)])
    assert result['policy_only']['available']==1
    assert result['policy_only']['flagged']==0
    assert result['policy_only']['metrics']['false_negative']==1
    assert result['model_only']['metrics']['true_positive']==1
