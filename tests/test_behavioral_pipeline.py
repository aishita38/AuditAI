from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
import torch

from backend.app import config
from backend.app.features.behavioral import FEATURE_NAMES, compute_features_batch, event_time_info
from backend.app.ml.pipeline import train_claims, score_claims, load_pipeline


def records(n=200):
    return [dict(claim_id=f'C{i}', employee_id=f'E{i%4}', vendor_id=f'V{i%3}', vendor_name=f'Vendor{i%3}',
                 claimed_amount=100 + i%17, claimed_date='2025-01-01',
                 submitted_at=pd.Timestamp('2025-01-01')+pd.Timedelta(hours=i),
                 category='travel', ocr_amount=100+i%17, ocr_confidence=.95) for i in range(n)]


def test_future_cannot_change_past_and_ids_are_only_keys():
    rows = records()
    before, names = compute_features_batch(rows)
    changed = [dict(c) for c in rows]
    for row in changed[100:]:
        row.update(claimed_amount=1e9, employee_id='future', vendor_name='future')
    assert compute_features_batch(changed)[0][:100] == before[:100]
    renamed = [dict(c, employee_id='renamed_'+c['employee_id'], vendor_id='renamed_'+c['vendor_id']) for c in rows]
    assert compute_features_batch(renamed)[0] == before
    assert not set(names) & {'employee_id','vendor_id','claim_id','is_fraud'}


def test_equal_time_no_self_or_peer_history_and_order_preserved():
    rows = records(3)
    rows[1]['submitted_at'] = rows[0]['submitted_at']
    rows[1]['employee_id'] = rows[0]['employee_id']
    rows[1]['vendor_name'] = rows[0]['vendor_name']
    f, _ = compute_features_batch(rows)
    assert f[0]['employee_is_new'] == f[1]['employee_is_new'] == 1
    assert compute_features_batch(list(reversed(rows)))[0] == list(reversed(f))


def test_receipt_quality_and_signed_amounts():
    row = records(1)[0]
    row.update(claimed_amount=-100, ocr_amount=-50)
    f = compute_features_batch([row])[0][0]
    assert f['is_negative'] == 1 and f['ocr_mismatch_ratio'] == .5
    row['ocr_confidence'] = .1
    f = compute_features_batch([row])[0][0]
    assert f['ocr_mismatch_ratio'] == 0 and f['ocr_low_confidence'] == 1
    row['ocr_amount'] = None
    f = compute_features_batch([row])[0][0]
    assert f['ocr_amount_missing'] == 1


def test_invalid_amount_not_silently_dropped():
    row = records(1)[0]; row['claimed_amount'] = float('nan')
    with pytest.raises(ValueError, match='amount'):
        compute_features_batch([row])


def test_date_only_claim_does_not_create_false_after_hours_evidence():
    date_only = dict(records(1)[0], submitted_at=None, claimed_date='2025-06-20')
    timestamp, known = event_time_info(date_only)
    features = compute_features_batch([date_only])[0][0]
    assert timestamp.hour == 12 and not known
    assert features['hour'] == 12 and features['is_after_hours'] == 0

    with_clock = dict(date_only, transaction_date='2025-06-20', transaction_time='02:15:00')
    timestamp, known = event_time_info(with_clock)
    features = compute_features_batch([with_clock])[0][0]
    assert timestamp.hour == 2 and known
    assert features['is_after_hours'] == 1


def test_model_reload_and_batch_invariance(tmp_path):
    cfg = SimpleNamespace(**{k: getattr(config,k) for k in dir(config) if k.isupper()})
    cfg.TRAINED_MODELS_DIR = tmp_path
    cfg.AE_EPOCHS = 4; cfg.IF_N_ESTIMATORS = 15
    torch.set_num_threads(2)
    rows = records()
    labels = [int(i%11 == 0) for i in range(len(rows))]
    a = train_claims(rows, labels, cfg)
    manifest = a['metadata']['split_manifest']
    assert len(set(sum(manifest.values(), []))) == len(rows)
    assert manifest['train'] == [f'C{i}' for i in range(120)]
    assert manifest['test'] == [f'C{i}' for i in range(170,200)]
    f, names = compute_features_batch(rows)
    x = np.array([[r[n] for n in names] for r in f])
    scores = score_claims(x[-10:], a)
    alone = score_claims(x[-1:], a)[0]
    assert alone['combined_fraud_score'] == pytest.approx(scores[-1]['combined_fraud_score'], abs=1e-6)
    reloaded = score_claims(x[-10:], load_pipeline(cfg))
    assert [s['combined_fraud_score'] for s in reloaded] == pytest.approx([s['combined_fraud_score'] for s in scores])
    assert reloaded[-1]['is_flagged'] == alone['is_flagged']
    with pytest.raises(ValueError, match='known-normal'):
        train_claims(rows, [-1]*len(rows), cfg)


def test_held_out_inputs_and_labels_cannot_change_fitted_model(tmp_path):
    cfg = SimpleNamespace(**{k: getattr(config,k) for k in dir(config) if k.isupper()})
    cfg.TRAINED_MODELS_DIR = tmp_path
    cfg.AE_EPOCHS = 2; cfg.IF_N_ESTIMATORS = 10
    torch.set_num_threads(2)
    rows = records()
    roles = [0]*120 + [1]*30 + [2]*20 + [3]*30
    labels = [int(i%11 == 0) for i in range(200)]
    first = train_claims(rows, labels, cfg, split_roles=roles)
    changed = [dict(c) for c in rows]
    other_labels = list(labels)
    for i in range(170,200):
        changed[i]['claimed_amount'] = 1e8
        changed[i]['submitted_at'] = pd.Timestamp('2020-01-01') + pd.Timedelta(hours=i)
        other_labels[i] = 1-labels[i]
    second = train_claims(changed, other_labels, cfg, split_roles=roles)
    assert first['threshold'] == second['threshold']
    assert first['family'] == second['family']
    assert first['metadata']['validation_candidates'] == second['metadata']['validation_candidates']
    assert np.array_equal(first['scaler']['scale'].mean_, second['scaler']['scale'].mean_)
    for name, tensor in first['autoencoder'].state_dict().items():
        assert torch.equal(tensor, second['autoencoder'].state_dict()[name])
