"""Retrain expense-only model with fixed stratified vendor-group splits; optional activation.

python scripts/retrain_expense_benchmark.py [--activate]
Never uses enterprise labels or test labels for fitting/selection/calibration.
"""
import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import torch
from backend.app import config
from backend.app.db import SessionLocal, engine
from backend.app.models.expense import ExpenseClaim, FraudPrediction, Case, CaseAuditTrail
from backend.app.features.behavioral import claim_record, compute_features_batch
from backend.app.ml.behavioral_pipeline import train_claims, score_claims, save_pipeline
from backend.app.detection_strategy import PATH, dataset_key
from scripts.calibrate_claim_threshold import select_threshold, metrics, split_rows
from sklearn.metrics import average_precision_score
from sklearn.model_selection import StratifiedGroupKFold


def benchmark_roles(claims):
    roles = [None] * len(claims)
    for key in ('aster', 'original'):
        indexes = [i for i,c in enumerate(claims) if dataset_key(c.claim_id) == key]
        labels = [int(claims[i].is_fraud) for i in indexes]
        groups = [claims[i].vendor_name.strip().casefold() for i in indexes]
        splitter = StratifiedGroupKFold(n_splits=10, shuffle=True, random_state=20261018)
        for fold, (_, held) in enumerate(splitter.split(indexes, labels, groups)):
            role = 0 if fold < 6 else 1 if fold == 6 else 2 if fold == 7 else 3
            for j in held:
                roles[indexes[j]] = role
    return roles


def partition_features(records, roles):
    output = [None] * len(records)
    for role in range(4):
        indexes = [i for i,r in enumerate(roles) if r in (0, role)]
        features, names = compute_features_batch([records[i] for i in indexes])
        for i,f in zip(indexes, features):
            if roles[i] == role:
                output[i] = f
    return output, names


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--activate', action='store_true')
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    directory = ROOT / 'scripts/artifacts' / f'expense-retrain-{stamp}'
    directory.mkdir(parents=True)
    cfg = SimpleNamespace(**{k: getattr(config, k) for k in dir(config) if k.isupper()})
    cfg.TRAINED_MODELS_DIR = directory
    torch.set_num_threads(2)
    with SessionLocal() as db:
        claims = db.query(ExpenseClaim).filter(
            ExpenseClaim.claim_id.like('AST-%') | ExpenseClaim.claim_id.like('CLM-%')).filter(
            ~ExpenseClaim.claim_id.like('AST-DEMO-%')).order_by(ExpenseClaim.claimed_date, ExpenseClaim.claim_id).all()
        records = [claim_record(c) for c in claims]
        labels = [int(c.is_fraud) for c in claims]
        if any(not c.fraud_type or bool(c.is_fraud) == (c.fraud_type in ('none', 'normal', 'Safe Transaction')) for c in claims):
            raise ValueError('Explicit consistent synthetic labels required')
        # Save complete normalized inputs so the exact run can be audited.
        (directory / 'inputs.json').write_text(json.dumps(dict(records=records, labels=labels), default=str, indent=2), encoding='utf-8')
        old_report = {}
        for key in ('aster', 'original'):
            old = [dict(id=c.claim_id, group=c.vendor_name.casefold().strip(), label=int(c.is_fraud),
                        score=float(c.prediction.combined_fraud_score)) for c in claims if dataset_key(c.claim_id) == key and c.prediction]
            validation, test = split_rows(old)
            cutoff = select_threshold(validation)
            old_report[key] = dict(threshold=cutoff, validation=metrics(validation, cutoff), test=metrics(test, cutoff),
                scope='Historical model; already inspected synthetic data, overlap unknown',
                manifest=dict(validation=[r['id'] for r in validation], test=[r['id'] for r in test]))
        print('Historical cutoff calibration saved. Training expense-only model...', flush=True)
        roles = benchmark_roles(claims)
        a = train_claims(records, labels, cfg, split_roles=roles)
        manifest = a['metadata']['split_manifest']
        feature_rows, names = partition_features(records, roles)
        scores = score_claims([[f[n] for n in names] for f in feature_rows], a)
        rows = [dict(id=c.claim_id, label=int(c.is_fraud), score=s['combined_fraud_score']) for c, s in zip(claims, scores)]
        thresholds, result = {}, {}
        for key in ('aster', 'original'):
            validation = [r for r in rows if r['id'] in set(manifest['cutoff_validation']) and dataset_key(r['id']) == key]
            test = [r for r in rows if r['id'] in set(manifest['test']) and dataset_key(r['id']) == key]
            # Threshold is frozen using calibration alone, before test metrics.
            if {r['label'] for r in test} != {0, 1} or {r['label'] for r in validation} != {0, 1}:
                raise ValueError(f'{key}: fixed grouped split lacks classes; do not activate or search seeds')
            try:
                threshold = select_threshold(validation)
                basis = 'Maximum cutoff-validation recall with precision >= 95%'
            except ValueError as exc:
                threshold = .5
                basis = f'Calibration target unavailable ({exc}); retain model default, no seed search'
            thresholds[key] = dict(threshold=threshold, basis=basis, run_id=a['metadata']['run_id'])
            result[key] = dict(validation_baseline=metrics(validation, .5), validation=metrics(validation, threshold),
                test_baseline=metrics(test, .5), test=metrics(test, threshold),
                test_average_precision=float(average_precision_score([r['label'] for r in test], [r['score'] for r in test])))
        thresholds['enterprise'] = dict(model_enabled=False, basis='Policy and dedicated rules only; excluded from expense ML training and decisions')
        a['metadata']['cohort_thresholds'] = thresholds
        save_pipeline(a, cfg)
        report = dict(run_id=a['metadata']['run_id'], scope=a['metadata']['evaluation_scope'],
            training_config={k:getattr(cfg,k) for k in ('ML_SEED','AE_EPOCHS','AE_PATIENCE','AE_BATCH_SIZE','AE_LATENT_DIM','AE_LEARNING_RATE','AE_WEIGHT_DECAY','IF_N_ESTIMATORS','ML_CLIP','SCORE_ALPHA')},
            split_method='Per-cohort StratifiedGroupKFold(10, shuffle=True, random_state=20261018); folds 0-5 train, 6 model-selection validation, 7 cutoff validation, 8-9 test. Group: normalized vendor name within dataset.',
            input_sha256=a['metadata']['input_sha256'], model_sha256=hashlib.sha256((directory / 'pipeline_v2.joblib').read_bytes()).hexdigest(),
            split_manifest=manifest, split_counts={k:len(v) for k,v in manifest.items()},
            historical_cutoffs=old_report, thresholds=thresholds, results=result,
            feature_context='Expense records only. Benchmark training features use train records only; each held-out partition uses train plus its own prior-only history. Live scoring uses full prior expense history; dashboard is retrospective and differs from the isolated test context.',
            activated=False, limitations=['Source data has been previously inspected; this repairs fitting overlap, not prior human exposure.',
                'Synthetic scenario labels, not real fraud outcomes. No independent external benchmark.',
                'Old cutoff 0.4351 cannot be transferred to the new model score scale.',
                'Model family and early stopping use selection validation; threshold uses cutoff validation; test never updates parameters.'])
        if args.activate:
            # Preserve database, current bundle and config before reversible activation.
            with sqlite3.connect(engine.url.database) as source, sqlite3.connect(directory / 'before-activation.db') as target:
                source.backup(target)
            active = Path(config.TRAINED_MODELS_DIR) / 'pipeline_v2.joblib'
            shutil.copy2(active, directory / 'previous-pipeline.joblib')
            if PATH.exists():
                shutil.copy2(PATH, directory / 'previous-strategy.json')
            shutil.copy2(directory / 'pipeline_v2.joblib', active)
            (active.parent / 'training_report.json').write_text(json.dumps(a['metadata'], indent=2) + '\n', encoding='utf-8')
            PATH.write_text(json.dumps(thresholds, indent=2) + '\n', encoding='utf-8')
            # Update saved scores without touching immutable case evidence, reports,
            # reviewer assignments or final decisions. Active signals are refreshed.
            from backend.app.detection_strategy import model_decision
            from backend.app.policy_service import run_checks
            for c, s, f in zip(claims, scores, feature_rows):
                p = c.prediction
                if not p:
                    p = FraudPrediction(claim_id=c.claim_id)
                    db.add(p)
                p.reconstruction_error = s['reconstruction_error']
                p.isolation_forest_score = s['isolation_forest_score']
                p.combined_fraud_score = s['combined_fraud_score']
                p.shap_values = None  # Previous model explanations cannot describe this run.
                holiday = bool(f['is_holiday'])
                p.feature_values = dict(f, _model_version=3, _model_run_id=report['run_id'],
                    _model_threshold=thresholds[dataset_key(c.claim_id)]['threshold'], _model_enabled=True,
                    _holiday_policy_flag=float(holiday))
                p.is_flagged = bool(model_decision(c.claim_id, s['combined_fraud_score']) or holiday)
                if c.status not in ('approved','rejected','processing'):
                    c.status = 'flagged' if p.is_flagged else 'scored'
                    if p.is_flagged and not c.case:
                        case = Case(claim_id=c.claim_id, status='open')
                        db.add(case); db.flush(); c.case = case
                        db.add(CaseAuditTrail(case_id=case.id, action='created', performed_by='system', notes=f'Expense model run {report["run_id"]}; validation-selected cutoff'))
                    elif p.is_flagged and c.case and c.case.status == 'cancelled_unflagged':
                        c.case.status = 'open'
                        db.add(CaseAuditTrail(case_id=c.case.id, action='reopened_after_rescore', performed_by='system', notes=f'Validation-calibrated model run {report["run_id"]} requires review'))
            enterprise = db.query(ExpenseClaim).filter(ExpenseClaim.claim_id.like('TXN%')).all()
            for c in enterprise:
                if c.prediction:
                    f = c.prediction.feature_values or {}
                    holiday = bool(f.get('_holiday_policy_flag', 0))
                    c.prediction.feature_values = dict(f, _model_enabled=False)
                    c.prediction.is_flagged = holiday
                    if c.status not in ('approved','rejected','processing'):
                        c.status = 'flagged' if holiday else 'scored'
            run_checks(db, True)
            db.flush()
            for c in claims + enterprise:
                if c.case and c.case.status == 'open' and not c.case.maker_id and not c.case.checker_id and c.status == 'scored':
                    c.case.status = 'cancelled_unflagged'
                    db.add(CaseAuditTrail(case_id=c.case.id, action='cancelled_after_rescore', performed_by='system', notes='No active model/policy signal after validation-calibrated model activation'))
            db.commit()
            report['activated'] = True
        (directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        (ROOT / 'scripts/artifacts/latest-expense-retrain.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        lines = ['# Expense-only model retraining', '', report['scope'], '', f'Run: {report["run_id"]}. Activated: {report["activated"]}.', '',
                 f'Split counts: {report["split_counts"]}', '', '| Dataset | Cutoff | Test positives | TP | FP | FN | Precision | Recall | F1 | AP |',
                 '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
        for key, value in result.items():
            m=value['test']
            lines.append(f"| {key} | {m['threshold']:.8f} | {m['positives']} | {m['tp']} | {m['fp']} | {m['fn']} | {m['precision']:.2%} | {m['recall']:.2%} | {m['f1']:.4f} | {value['test_average_precision']:.4f} |")
        lines += ['', *report['limitations'], '', f'Full input snapshot, split manifests, hashes, model and recovery backup: {directory}', '',
                  'Reproduce with python scripts/retrain_expense_benchmark.py (no activation by default). Add --activate to update the local model, routing and saved scores.',
                  'Dashboard metrics describe all loaded rows, including training rows. Only the test rows in report.json support the split-test results above.']
        (ROOT / 'docs/expense-retraining.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
        print(json.dumps(dict(directory=str(directory), split_counts=report['split_counts'], historical_cutoffs={k:v['threshold'] for k,v in old_report.items()}, results=result, thresholds=thresholds, activated=report['activated']), indent=2), flush=True)


if __name__ == '__main__':
    main()
