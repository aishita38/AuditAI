"""Read-only evaluation of saved claim scores against synthetic dataset labels."""
import json
import math
import sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sklearn.metrics import average_precision_score,precision_recall_curve,auc,precision_recall_fscore_support,confusion_matrix
from backend.app.db import SessionLocal
from backend.app.models.expense import ExpenseClaim,FraudPrediction


def evaluate(rows):
    labels=[r['label'] for r in rows]; scores=[r['score'] for r in rows]
    result=dict(claims=len(rows),labelled_anomalies=sum(labels),labelled_controls=len(rows)-sum(labels),prevalence=sum(labels)/len(rows))
    for name,predicted in [('score_threshold_50',[r['score']>=.5 for r in rows]),('saved_review_flags',[r['review_flag'] for r in rows])]:
        p,r,f,_=precision_recall_fscore_support(labels,predicted,average='binary',zero_division=0)
        tn,fp,fn,tp=confusion_matrix(labels,predicted,labels=[0,1]).ravel()
        result[name]=dict(precision=float(p),recall=float(r),f1=float(f),true_positive=int(tp),false_positive=int(fp),false_negative=int(fn),true_negative=int(tn),flagged=sum(predicted))
    if len(set(labels))==2:
        precision,recall,_=precision_recall_curve(labels,scores)
        result['pr_auc_average_precision']=float(average_precision_score(labels,scores))
        result['pr_auc_trapezoidal']=float(auc(recall,precision))
    else:
        result['pr_auc_average_precision']=None; result['pr_auc_trapezoidal']=None
    ranked=sorted(rows,key=lambda r:(-r['score'],r['id']))
    result['precision_at_k']={}
    for k in [10,50,100]:
        if len(ranked)<k: continue
        boundary=ranked[k-1]['score']
        above=[r for r in ranked if r['score']>boundary]
        tied=[r for r in ranked if r['score']==boundary]
        slots=k-len(above); positives=sum(r['label'] for r in above); tied_positives=sum(r['label'] for r in tied)
        result['precision_at_k'][str(k)]=dict(precision=sum(r['label'] for r in ranked[:k])/k,
            anomalous_in_top_k=sum(r['label'] for r in ranked[:k]),boundary_score=boundary,
            ties_at_boundary=len(tied),tie_min_precision=(positives+max(0,slots-(len(tied)-tied_positives)))/k,
            tie_max_precision=(positives+min(slots,tied_positives))/k)
    return result


def main():
    with SessionLocal() as db:
        raw=db.query(ExpenseClaim.claim_id,ExpenseClaim.is_fraud,ExpenseClaim.fraud_type,FraudPrediction.combined_fraud_score,FraudPrediction.is_flagged,FraudPrediction.feature_values).outerjoin(FraudPrediction,ExpenseClaim.claim_id==FraudPrediction.claim_id).all()
    rows=[]; excluded=Counter()
    for cid,label,kind,score,flag,features in raw:
        # Explicit synthetic taxonomy labels only: do not treat DB's default False as ground truth.
        known=bool(kind and str(kind).strip().lower() not in ('','unknown','unlabelled','unlabeled'))
        if not known: excluded['unlabelled']+=1; continue
        if (not label and kind not in ('none','Safe Transaction','normal')) or (label and kind in ('none','Safe Transaction','normal')):
            excluded['inconsistent_label']+=1; continue
        if score is None or not math.isfinite(score): excluded['unscored_or_invalid_score']+=1; continue
        rows.append(dict(id=cid,label=int(label),score=float(score),review_flag=bool(flag),kind=kind,version=(features or {}).get('_model_version')))
    if not rows: raise RuntimeError('No scored claims with explicit synthetic labels.')
    report=dict(generated_at=datetime.now(timezone.utc).isoformat(),
        evaluation_scope='Retrospective loaded synthetic claims; training overlap not excluded. Not held-out production performance.',
        label_source='ExpenseClaim.is_fraud, checked against explicit fraud_type; synthetic scenario truth, not confirmed wrongdoing.',
        ranking='Descending saved anomaly index, then claim_id ascending for tied scores.',
        pr_auc_definition='Average precision is the primary PR summary; trapezoidal PR area is also reported separately.',
        loaded_rows=len(raw),excluded=dict(excluded),model_versions=dict(Counter(str(r['version']) for r in rows)),
        overall=evaluate(rows),cohorts={})
    for prefix,name in [('CLM-','original_expenses'),('AST-','aster_expenses'),('TXN','enterprise_transactions_imported_as_claims')]:
        cohort=[r for r in rows if r['id'].startswith(prefix)]
        if cohort: report['cohorts'][name]=evaluate(cohort)
    out=ROOT/'scripts/artifacts/loaded-claim-metrics.json'
    out.write_text(json.dumps(report,indent=2),encoding='utf-8')
    summary=ROOT/'docs/loaded-claim-metrics.md'
    lines=['# Loaded claim evaluation','',report['evaluation_scope'],'',f"Scored and labelled: {len(rows):,}. Positive labels: {sum(r['label'] for r in rows):,}. Source: synthetic is_fraud labels, not case approvals. No accuracy metric is used.",'',
           '| Scope | Decision | Precision | Recall | F1 | TP | FP | FN |','|---|---|---:|---:|---:|---:|---:|---:|']
    for name,c in [('overall',report['overall']),*report['cohorts'].items()]:
        for decision in ['score_threshold_50','saved_review_flags']:
            m=c[decision];lines.append(f"| {name} | {decision} | {m['precision']:.2%} | {m['recall']:.2%} | {m['f1']:.4f} | {m['true_positive']} | {m['false_positive']} | {m['false_negative']} |")
        lines.extend(['',f"{name}: average precision {c['pr_auc_average_precision']:.4f}; trapezoidal PR area {c['pr_auc_trapezoidal']:.4f}; prevalence baseline {c['prevalence']:.2%}.",''])
        for k,m in c['precision_at_k'].items(): lines.append(f"- Precision@{k}: {m['precision']:.2%} ({m['anomalous_in_top_k']}/{k}); boundary-tie range {m['tie_min_precision']:.2%}–{m['tie_max_precision']:.2%}.")
    lines.extend(['','## Interpretation and limits','','Precision@K means: of the K highest-scoring claims a reviewer can inspect, what fraction carry an anomaly label? Ties use claim ID, not labels; the possible range from boundary ties is disclosed in the JSON.',
        'Saved review flags include policy overrides; the score-threshold row isolates thresholding the saved ML index at 0.5. PR summaries and Precision@K use saved scores, not policy flags.',
        'These claims may have participated in training, calibration or model selection. This is a current-data diagnostic, not an independent test-set result. Aster and enterprise sources have different scenario distributions; per-source results are included.',
        'Some labelled scenarios require ERP fields absent from the expense model. A synthetic normal claim may still trigger a legitimate company-policy review; such flags count as false positives against the scenario labels here.',
        'PR-AUC measures ranking across thresholds, but depends on class prevalence and label quality. Average precision and trapezoidal PR area are different calculations; do not present them as interchangeable.',
        'No database rows, thresholds, flags or model artifacts were changed by this evaluation.'])
    summary.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
