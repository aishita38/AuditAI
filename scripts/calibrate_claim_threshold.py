"""Read-only, retrospective Aster threshold experiment; never deploys a cutoff."""
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import average_precision_score


def metrics(rows, threshold):
    tp = sum(r['label'] == 1 and r['score'] >= threshold for r in rows)
    fp = sum(r['label'] == 0 and r['score'] >= threshold for r in rows)
    fn = sum(r['label'] == 1 and r['score'] < threshold for r in rows)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return dict(threshold=threshold, rows=len(rows), positives=sum(r['label'] for r in rows),
                tp=tp, fp=fp, fn=fn, precision=precision, recall=recall,
                f1=2 * precision * recall / (precision + recall) if precision + recall else 0.0)


def select_threshold(validation, minimum_precision=0.95):
    """Optimize validation recall, then precision, then the higher cutoff on ties."""
    if not 0 < minimum_precision <= 1:
        raise ValueError('minimum_precision must be in (0, 1]')
    if {r['label'] for r in validation} != {0, 1}:
        raise ValueError('Validation requires both classes')
    if any(not math.isfinite(r['score']) for r in validation):
        raise ValueError('Scores must be finite')
    candidates = [metrics(validation, t) for t in sorted({r['score'] for r in validation})]
    feasible = [m for m in candidates if m['precision'] >= minimum_precision]
    if not feasible:
        raise ValueError('No validation threshold meets the precision target')
    return max(feasible, key=lambda m: (m['recall'], m['precision'], m['threshold']))['threshold']


def split_rows(rows):
    # Vendor is a grouping key only. No vendor name is used to link payments.
    ordered = sorted(rows, key=lambda r: r['id'])
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.5, random_state=20261018)
    vi, ti = next(splitter.split(ordered, groups=[r['group'] for r in ordered]))
    validation, test = [ordered[i] for i in vi], [ordered[i] for i in ti]
    if any({r['label'] for r in part} != {0, 1} for part in (validation, test)):
        raise ValueError('Fixed split does not contain both classes; do not search seeds')
    return validation, test


def main():
    from backend.app.db import SessionLocal
    from backend.app.models.expense import ExpenseClaim, FraudPrediction
    with SessionLocal() as db:
        raw = db.query(ExpenseClaim.claim_id, ExpenseClaim.vendor_name, ExpenseClaim.is_fraud,
                       ExpenseClaim.fraud_type, FraudPrediction.combined_fraud_score).join(
            FraudPrediction, ExpenseClaim.claim_id == FraudPrediction.claim_id).filter(
            ExpenseClaim.claim_id.like('AST-%'), ~ExpenseClaim.claim_id.like('AST-DEMO-%')).all()
    rows = []
    for cid, vendor, label, kind, score in raw:
        if score is None or not math.isfinite(score) or not kind or kind.lower() in ('unknown', 'unlabelled', 'unlabeled'):
            raise ValueError(f'Invalid score or label: {cid}')
        if bool(label) == (kind in ('none', 'Safe Transaction', 'normal')):
            raise ValueError(f'Inconsistent label: {cid}')
        if not vendor:
            raise ValueError(f'Missing split group: {cid}')
        rows.append(dict(id=cid, group=vendor.strip().casefold(), label=int(label), score=float(score)))
    validation, test = split_rows(rows)
    # This function receives validation rows only. Freeze its result before evaluating test labels.
    threshold = select_threshold(validation)
    manifest = dict(validation=[r['id'] for r in validation], test=[r['id'] for r in test])
    digest = hashlib.sha256(json.dumps(sorted(rows, key=lambda r: r['id']), sort_keys=True).encode()).hexdigest()
    report = dict(scope='Retrospective synthetic Aster evaluation; previously inspected data; training overlap unknown. Not an untouched or production test.',
                  objective='Maximum validation recall subject to precision >= 0.95; ties prefer precision then higher cutoff.',
                  seed=20261018, split='50/50 by normalized vendor name; group key only, no record linkage. Existing scores and historical context are fixed, not recomputed per split.',
                  limitations=['Vendor grouping does not isolate shared employees or all historical dependencies.',
                               'Synthetic labels may not reflect real fraud. No confidence guarantee follows from the validation precision target.',
                               'Threshold changes decisions, not ranking: PR-AUC is unchanged.',
                               'A fresh benchmark excluded from training and previous inspection is required before deployment.'],
                  input_sha256=digest, selected_threshold=threshold, deployed_threshold=0.5, deployed=False,
                  split_manifest=manifest, results={})
    for name, part in [('validation', validation), ('test', test)]:
        report['results'][name] = dict(baseline=metrics(part, 0.5), candidate=metrics(part, threshold),
            average_precision=float(average_precision_score([r['label'] for r in part], [r['score'] for r in part])))
    out = ROOT / 'scripts/artifacts/threshold-calibration.json'
    out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    lines = ['# Aster threshold experiment', '', report['scope'], '', report['objective'], '',
             f'Selected cutoff: {threshold:.8f}. Live cutoff remains 0.50. Input SHA-256: `{digest}`.', '',
             '| Split | Cutoff | Rows | TP | FP | FN | Precision | Recall | F1 |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for name, result in report['results'].items():
        for mode in ('baseline', 'candidate'):
            m = result[mode]
            lines.append(f"| {name} | {m['threshold']:.8f} | {m['rows']} | {m['tp']} | {m['fp']} | {m['fn']} | {m['precision']:.2%} | {m['recall']:.2%} | {m['f1']:.4f} |")
        lines.extend(['', f"{name} average precision: {result['average_precision']:.4f} (same at either cutoff).", ''])
    lines.extend([report['split'], '', *report['limitations'], '',
                  'Reproduce: `python scripts/calibrate_claim_threshold.py`. The JSON includes every split claim ID. No database, model, policy or live threshold is changed.'])
    (ROOT / 'docs/threshold-calibration.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'split_manifest'}, indent=2))


if __name__ == '__main__':
    main()
