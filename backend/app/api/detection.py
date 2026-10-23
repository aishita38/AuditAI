"""Counts of all detectors, with separate evaluation units and dataset cohorts."""
import math
import json
from pathlib import Path
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.db import get_db
from backend.app.auth.security import require_roles
from backend.app.models.expense import ExpenseClaim,FraudPrediction
from backend.app.models.policy import ClaimPolicy
from backend.app.models.master_finding import MasterFinding
from backend.app.models.master_data import VendorMaster,EmployeeMaster,PayrollPayment
from backend.app.automatic_checks import after_import
from backend.app.detection_strategy import model_decision, strategy, settings
router=APIRouter(prefix='/api/v1/detection',tags=['Detection overview'])
reviewer=Depends(require_roles('admin','maker','checker'))


def cohort(cid):
    if cid.startswith('AST-DEMO-'):return 'Aster upload demo claims'
    if cid.startswith('AST-'):return 'Aster expense claims'
    if cid.startswith('CLM-'):return 'Original expense claims'
    if cid.startswith('TXN'):return 'Enterprise records in expense schema (scope mismatch)'
    return 'Other expense claims'


def consistent_label(row):
    kind=(row.fraud_type or '').strip()
    if not kind or kind.lower() in ('unknown','unlabelled','unlabeled'):return False
    return bool(row.is_fraud)!=(kind in ('none','Safe Transaction','normal'))


def has_score(row):
    return row.combined_fraud_score is not None and math.isfinite(row.combined_fraud_score)


def policy_decision(row):
    # A positive holiday override is policy evidence, never an ML decision.
    if getattr(row,'holiday_policy',None) is not None and row.holiday_policy>=.5:return True
    value=getattr(row,'policy_review',None)
    if value is not None:return bool(value)
    holiday=getattr(row,'holiday_policy',None)
    # An explicit saved zero is a negative for the recorded holiday check,
    # not evidence that the later company-policy suite was evaluated.
    return bool(holiday>=.5) if holiday is not None else None


def mode_results(rows):
    from sklearn.metrics import average_precision_score, precision_recall_curve, auc
    # Use one comparison population for all three rows. Unknown policy results
    # are not silently turned into negative decisions.
    common=[r for r in rows if consistent_label(r) and (has_score(r) or not strategy(r.claim_id)['model_enabled']) and policy_decision(r) is not None]
    labels=[int(r.is_fraud) for r in common]
    result={}
    for mode in ('model_only','policy_only','combined'):
        def decision(row):
            enabled=strategy(row.claim_id)['model_enabled']
            model=model_decision(row.claim_id,row.combined_fraud_score) if has_score(row) or not enabled else None
            policy=policy_decision(row)
            if mode=='model_only':return model if enabled else None
            if mode=='policy_only':return policy
            if model is True or policy is True:return True
            return False if model is False and policy is False else None
        predicted=[decision(r) for r in common]
        tp=sum(bool(y and p) for y,p in zip(labels,predicted));fp=sum(bool(not y and p) for y,p in zip(labels,predicted));fn=sum(bool(y and not p) for y,p in zip(labels,predicted));tn=len(common)-tp-fp-fn
        p=tp/(tp+fp) if tp+fp else 0;recall=tp/(tp+fn) if tp+fn else 0
        metric=dict(precision=p if common else None,recall=recall if common else None,f1=2*p*recall/(p+recall) if p+recall else 0 if common else None,true_positive=tp,false_positive=fp,false_negative=fn,true_negative=tn,evaluated=len(common),flagged_in_evaluation=sum(p is True for p in predicted),average_precision=None,pr_auc_trapezoidal=None,precision_at_k={})
        # Only the model supplies a continuous score. No fabricated policy or
        # combined ranking is used to make AP or top-K look comparable.
        if mode=='model_only' and any(strategy(r.claim_id)['model_enabled'] for r in common):
            ranked=sorted(common,key=lambda r:(-r.combined_fraud_score,r.claim_id))
            metric['precision_at_k']={str(k):sum(bool(r.is_fraud) for r in ranked[:k])/k for k in (10,50,100) if len(ranked)>=k}
            if len(set(labels))==2:
                scores=[r.combined_fraud_score for r in common];precision,recalls,_=precision_recall_curve(labels,scores)
                metric['average_precision']=float(average_precision_score(labels,scores));metric['pr_auc_trapezoidal']=float(auc(recalls,precision))
        disabled=mode=='model_only' and bool(rows) and not any(strategy(r.claim_id)['model_enabled'] for r in rows)
        if disabled:
            metric.update(precision=None,recall=None,f1=None,true_positive=None,false_positive=None,false_negative=None,true_negative=None,evaluated=0)
        result[mode]=dict(flagged=sum(decision(r) is True for r in rows),available=sum(decision(r) is not None for r in rows),metrics=metric,disabled=disabled)
    return result


def cohort_summary(name,rows):
    modes=mode_results(rows)
    routing=strategy(rows[0].claim_id) if rows else {}
    return dict(strategy=routing,company_policy_evaluated=sum(getattr(r,'policy_review',None) is not None for r in rows),holiday_policy_evaluated=sum(getattr(r,'holiday_policy',None) is not None for r in rows),name=name,claims=len(rows),scored=sum(has_score(r) for r in rows),policy_evaluated=sum(policy_decision(r) is not None for r in rows),comparison_claims=modes['combined']['metrics']['evaluated'],flagged=sum(bool(r.is_flagged) or r.status=='flagged' for r in rows),modes=modes,
        # Deprecated combined-metric alias; the UI uses the explicit modes above.
        metrics=dict(modes['combined']['metrics'],labelled_scored=modes['combined']['metrics']['evaluated']))


@router.get('/overview')
def overview(db:Session=Depends(get_db),user=reviewer):
    rows=db.query(ExpenseClaim.claim_id,ExpenseClaim.status,ExpenseClaim.is_fraud,ExpenseClaim.fraud_type,FraudPrediction.combined_fraud_score,FraudPrediction.is_flagged,FraudPrediction.feature_values['_holiday_policy_flag'].as_float().label('holiday_policy'),ClaimPolicy.result['requires_review'].as_boolean().label('policy_review')).outerjoin(FraudPrediction,ExpenseClaim.claim_id==FraudPrediction.claim_id).outerjoin(ClaimPolicy,ExpenseClaim.claim_id==ClaimPolicy.claim_id).all()
    groups={}
    for r in rows:groups.setdefault(cohort(r.claim_id),[]).append(r)
    counts={name:db.query(MasterFinding).filter_by(dataset=name,active=True).count() for name in ('vendor','payroll')}
    flagged=sum(bool(r.is_flagged) or r.status=='flagged' for r in rows)
    transfers={};errors=[]
    try:
        from backend.app.api.transfers import cycles
        c=cycles(7,4,db,user);transfers['circular']=dict(findings=len(c['cycles']),unit='cycles',source_records=c['transfer_count'],limited=c.get('search_limited',False))
    except Exception as exc:errors.append(dict(detector='circular',message=str(getattr(exc,'detail','Could not evaluate'))))
    try:
        from backend.app.api.reconciliation import reconciliation
        r=reconciliation(db,user);transfers['reconciliation']=dict(findings=sum(bool(i['flags']) for i in r['items']),unit='linked claims with payment discrepancies',source_records=r['transfer_count'])
    except Exception as exc:errors.append(dict(detector='reconciliation',message=str(getattr(exc,'detail','Could not evaluate'))))
    breakdown=[dict(detector='Expense claims (model + policy, deduplicated)',findings=flagged,unit='claims',source_records=len(rows),url='/claims?status=flagged'),
        dict(detector='Vendor rules',findings=counts['vendor'],unit='rule findings (groups may overlap)',source_records=db.query(VendorMaster).count(),url='/audit-screens?tab=vendor'),
        dict(detector='Payroll rules',findings=counts['payroll'],unit='rule findings (groups may overlap)',source_records=db.query(PayrollPayment).count(),roster_records=db.query(EmployeeMaster).count(),url='/audit-screens?tab=payroll')]
    for key,v in transfers.items():breakdown.append(dict(detector='Circular payments' if key=='circular' else 'Payment reconciliation',url='/audit-screens?tab=circular' if key=='circular' else '/audit-screens?tab=reconciliation',**v))
    benchmark_path=Path(__file__).resolve().parents[3]/'scripts/artifacts/latest-expense-retrain.json'
    benchmark=None
    if benchmark_path.exists():
        saved=json.loads(benchmark_path.read_text(encoding='utf-8'))
        if saved.get('activated') and settings().get('aster',{}).get('run_id')==saved.get('run_id'):
            benchmark={k:saved[k] for k in ('run_id','scope','split_counts','results','thresholds','limitations')}
    return dict(benchmark=benchmark,total_review_signals=sum(r['findings'] for r in breakdown),breakdown=breakdown,incomplete=bool(errors) or any(v.get('limited') for v in transfers.values()),errors=errors,
        definition='Review signals across detectors, not unique fraudulent entities. A record can participate in several findings.',
        cohorts=[cohort_summary(name,items) for name,items in sorted(groups.items())],
        metric_scope='Loaded-data diagnostics include training rows; use the separate split-test results for model evaluation. Model-only uses the displayed dataset-specific validation cutoff. Enterprise expense ML is disabled; enterprise combined equals policy-only, while vendor, payroll, circular and reconciliation rules remain separate. Policy-only includes full saved company checks and the holiday override. Model and policy comparisons use labelled scored policy-evaluated expense claims; enterprise policy evaluation does not require ML scores. Missing evaluations are excluded. PR-AUC and top-K apply only to model scores. Vendor/payroll metrics have separate evaluation units.')


@router.post('/recheck')
def recheck(db:Session=Depends(get_db),user=Depends(require_roles('admin'))):
    return after_import(db,user,'all')
