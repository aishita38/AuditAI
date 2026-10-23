"""Refresh full policy results and the method comparison without ML rescoring."""
import hashlib
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.db import SessionLocal, engine
from backend.app.models.auth import AuthUser
from backend.app.models.expense import FraudPrediction, Case
from backend.app.api.policies import run
from backend.app.api.detection import overview
from backend.app.models.policy import ClaimPolicy


def score_digest(db):
    rows = db.query(FraudPrediction.claim_id, FraudPrediction.reconstruction_error,
                    FraudPrediction.isolation_forest_score,
                    FraudPrediction.combined_fraud_score).order_by(FraudPrediction.claim_id).all()
    return hashlib.sha256(json.dumps([list(r) for r in rows], default=str).encode()).hexdigest()


def main():
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    artifact = ROOT / 'scripts/artifacts'
    if engine.url.get_backend_name() == 'sqlite' and engine.url.database != ':memory:':
        with sqlite3.connect(engine.url.database) as source, sqlite3.connect(artifact / f'before-full-policy-{stamp}.db') as target:
            source.backup(target)
    print('Saved database recovery snapshot. Running all policy checks...', flush=True)
    with SessionLocal() as db:
        admin = db.query(AuthUser).filter(AuthUser.active.is_(True)).all()
        admin = next(u for u in admin if 'admin' in u.roles)
        before = score_digest(db)
        decisions = {c.id: (c.status, c.maker_id, c.checker_id) for c in db.query(Case).filter(Case.status.in_(['closed_approved', 'closed_rejected'])).all()}
        result = run(db, admin)
        print(json.dumps(result), flush=True)
        assert score_digest(db) == before, 'Saved ML scores changed unexpectedly'
        assert all((db.get(Case, key).status, db.get(Case, key).maker_id, db.get(Case, key).checker_id) == value for key, value in decisions.items())
        counters = defaultdict(Counter)
        for (policy,) in db.query(ClaimPolicy.result).all():
            for check in (policy or {}).get('checks', []):
                counters[check['code']][check['status']] += 1
        report = overview(db, admin)
        report.update(generated_at=datetime.now(timezone.utc).isoformat(), full_policy_run=result,
                      ml_scores_unchanged=True, final_review_decisions_unchanged=True,
                      rule_availability={key: dict(value) for key, value in counters.items()})
        (artifact / 'full-policy-comparison.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        (artifact / 'detection-metric-modes.json').write_text(json.dumps(report['cohorts'], indent=2), encoding='utf-8')
        lines = ['# Full policy evaluation', '', f"Generated: {report['generated_at']}", '',
                 f"Checked {result['checked']:,} claims. {result['requires_review']:,} require policy review. ML scores and final review decisions were not changed.", '',
                 report['metric_scope'], '', '| Dataset | Method | Flagged | TP | FP | FN | Precision | Recall | F1 |',
                 '|---|---|---:|---:|---:|---:|---:|---:|---:|']
        for cohort in report['cohorts']:
            print(cohort['name'], flush=True)
            for mode, data in cohort['modes'].items():
                m = data['metrics']
                print(mode, data['flagged'], m['precision'], m['recall'], m['f1'], flush=True)
                fmt = lambda value: 'Unavailable' if value is None else f'{value:.4f}'
                lines.append(f"| {cohort['name']} | {mode} | {data['flagged']} | {m['true_positive']} | {m['false_positive']} | {m['false_negative']} | {fmt(m['precision'])} | {fmt(m['recall'])} | {fmt(m['f1'])} |")
        lines += ['', '## Rule coverage', '', 'Rules without required input fields remain unavailable; this run does not invent missing invoice, approver or transaction-time evidence.', '',
                  '| Rule | Review | Pass | Unavailable | Signal |', '|---|---:|---:|---:|---:|']
        for rule, counts in sorted(counters.items()):
            lines.append(f"| {rule} | {counts['review']} | {counts['pass']} | {counts['unavailable']} | {counts['signal']} |")
        (ROOT / 'docs/detection-metric-modes.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
