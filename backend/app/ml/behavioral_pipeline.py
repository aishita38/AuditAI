"""Parallel AE/IF detector, chronological validation and frozen calibration.

UI scores use a monotonic arctan mapping, not batch min/max normalization.
They are anomaly rankings, not fraud probabilities. Only trusted normal rows
train the models; labels are never inputs. Legacy bundles are not compatible.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import uuid

import joblib
import numpy as np
import torch
from torch import nn
from sklearn.ensemble import IsolationForest, HistGradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.metrics import average_precision_score, precision_recall_curve, precision_score, recall_score, f1_score

from backend.app.features.behavioral import FEATURE_NAMES, compute_features_batch, event_time

VERSION = 3


class BehavioralAutoencoder(nn.Module):
    def __init__(self, input_dim, latent_dim=16):
        super().__init__()
        self.encoder = nn.Sequential(nn.Linear(input_dim, 64), nn.ReLU(),
            nn.Dropout(.1), nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, latent_dim))
        self.decoder = nn.Sequential(nn.Linear(latent_dim, 32), nn.ReLU(),
            nn.Linear(32, 64), nn.ReLU(), nn.Linear(64, input_dim))

    def forward(self, x):
        return self.decoder(self.encoder(x))


def reconstruct(model, x):
    model.eval()
    with torch.no_grad():
        return np.concatenate([model(torch.as_tensor(b, dtype=torch.float32)).numpy()
                               for b in np.array_split(x, max(1, (len(x)+255)//256))])


def train_autoencoder(train, validation, config):
    torch.manual_seed(config.ML_SEED)
    np.random.seed(config.ML_SEED)
    model = BehavioralAutoencoder(train.shape[1], config.AE_LATENT_DIM)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.AE_LEARNING_RATE,
                                  weight_decay=config.AE_WEIGHT_DECAY)
    tensor = torch.as_tensor(train, dtype=torch.float32)
    best, state, wait = float('inf'), None, 0
    history = []
    for epoch in range(config.AE_EPOCHS):
        model.train()
        for idx in torch.randperm(len(tensor)).split(config.AE_BATCH_SIZE):
            batch = tensor[idx]
            optimizer.zero_grad()
            loss = ((model(batch) - batch)**2).mean()
            loss.backward()
            optimizer.step()
        tr = float(np.mean((reconstruct(model, train)-train)**2))
        va = float(np.mean((reconstruct(model, validation)-validation)**2))
        history.append({'epoch': epoch+1, 'train_loss': tr, 'validation_loss': va})
        if va < best:
            best, state, wait = va, copy.deepcopy(model.state_dict()), 0
        else:
            wait += 1
        if wait >= config.AE_PATIENCE:
            break
    if state is None:
        raise ValueError('Autoencoder did not converge to a finite validation loss.')
    model.load_state_dict(state)
    model.eval()
    return model, history


def transform_features(x, artifacts):
    x = np.asarray(x, dtype=np.float32)
    if x.ndim != 2 or x.shape[1] != len(artifacts['feature_names']):
        raise ValueError('Feature schema mismatch; rebuild features and retrain v2.')
    return np.clip(artifacts['scaler'].transform(x), -artifacts['clip'], artifacts['clip']).astype('float32')


def _reference(scores):
    log = np.log(np.maximum(scores, 1e-12))
    center = float(np.median(log))
    return center, max(float(np.median(abs(log-center))*1.4826), .05)


def _standardize(scores, reference):
    return (np.log(np.maximum(scores, 1e-12))-reference[0])/reference[1]


def _raw_scores(x, a):
    err = ((reconstruct(a['autoencoder'], x)-x)**2).mean(axis=1)
    iso = -a['isolation_forest'].score_samples(x)
    za, zi = _standardize(err, a['references']['ae']), _standardize(iso, a['references']['if'])
    family = a.get('family', 'combined')
    combined = a['alpha']*za+(1-a['alpha'])*zi
    if family == 'ae':
        combined = za
    elif family == 'if':
        combined = zi
    elif family == 'supervised':
        combined = a['supervised'].predict_proba(x)[:, 1]
    return err, iso, za, zi, combined


def _display(score, threshold):
    return .5 + np.arctan(np.asarray(score)-threshold)/np.pi


def score_claims(feature_matrix, pipeline_artifacts, config=None):
    a = pipeline_artifacts
    if len(feature_matrix) == 0:
        return []
    x = transform_features(feature_matrix, a)
    err, iso, za, zi, raw = _raw_scores(x, a)
    display = _display(raw, a['threshold'])
    return [dict(reconstruction_error=float(err[i]), isolation_forest_score=float(iso[i]),
                 combined_fraud_score=float(display[i]), anomaly_score=float(raw[i]),
                 is_flagged=bool(raw[i] >= a['threshold'])) for i in range(len(x))]


def train_pipeline(feature_matrix, feature_names, config, *, labels=None, timestamps=None, split_roles=None):
    """Chronological 60/15/10/15 train/stop/calibration/test partitions.

    Labels: 0=reviewed normal, 1=known anomaly, -1=unknown. Callers must explicitly
    opt into trusting synthetic labels; default-false DB labels are not evidence.
    """
    if list(feature_names) != FEATURE_NAMES:
        raise ValueError('Training requires the v3 behavioral feature schema.')
    if labels is None or timestamps is None:
        raise ValueError('Trusted labels and availability timestamps are required; unknown is not normal.')
    x, y = np.asarray(feature_matrix, dtype='float32'), np.asarray(labels)
    if len(x) < 50 or len(y) != len(x) or len(timestamps) != len(x):
        raise ValueError('Need at least 50 aligned claims, labels and timestamps.')
    if not np.isin(y, [-1, 0, 1]).all() or not np.isfinite(x).all():
        raise ValueError('Invalid labels or non-finite feature values.')
    times = np.asarray(timestamps)
    if split_roles is not None:
        roles = np.asarray(split_roles)
        if len(roles) != len(x) or set(roles) != {0, 1, 2, 3}:
            raise ValueError('Explicit split roles must contain all four aligned partitions')
        order = np.lexsort((times, roles))
    else:
        order = np.argsort(times, kind='stable')
    x, y, times = x[order], y[order], times[order]
    cuts = [int(sum(roles < k)) for k in (1, 2, 3)] if split_roles is not None else [int(np.searchsorted(times, times[int(len(x)*q)], side='left')) for q in [.6, .75, .85]]
    c1, c2, c3 = cuts
    if not 0 < c1 < c2 < c3 < len(x):
        raise ValueError('Need distinct time periods for training, validation, calibration and test.')
    normal_train, normal_stop = x[:c1][y[:c1] == 0], x[c1:c2][y[c1:c2] == 0]
    normal_cal = x[c2:c3][y[c2:c3] == 0]
    if min(len(normal_train), len(normal_stop), len(normal_cal)) < 5:
        raise ValueError('Each development period needs at least 5 independently known-normal claims.')
    pre = Pipeline([('impute', SimpleImputer(strategy='median', keep_empty_features=True)), ('scale', StandardScaler())])
    pre.fit(normal_train)
    a = dict(version=VERSION, feature_names=list(feature_names), scaler=pre,
             clip=config.ML_CLIP, alpha=config.SCORE_ALPHA)
    tr, va = [transform_features(z, a) for z in [normal_train, normal_stop]]
    ae, history = train_autoencoder(tr, va, config)
    forest = IsolationForest(n_estimators=config.IF_N_ESTIMATORS, random_state=config.ML_SEED, n_jobs=1).fit(tr)
    a.update(autoencoder=ae, isolation_forest=forest,
             references={'ae': _reference(((reconstruct(ae, va)-va)**2).mean(axis=1)),
                         'if': _reference(-forest.score_samples(va))})
    # Select on development data, never on the calibration/test periods.
    selection = {}
    sy = y[c1:c2]
    sx = transform_features(x[c1:c2], a)
    known_stop = sy >= 0
    if set(sy[known_stop]) == {0, 1}:
        for family in ['combined', 'ae', 'if']:
            a['family'] = family
            selection[family] = float(average_precision_score(sy[known_stop], _raw_scores(sx, a)[-1][known_stop]))
        # A shallow supervised challenger is legitimate only when BOTH classes
        # have explicit trusted labels in training. No pseudo-labels are made.
        known_train = y[:c1] >= 0
        if set(y[:c1][known_train]) == {0, 1}:
            gbm = HistGradientBoostingClassifier(max_iter=100, max_leaf_nodes=7,
                max_depth=3, min_samples_leaf=20, l2_regularization=1,
                early_stopping=False, random_state=config.ML_SEED)
            gbm.fit(transform_features(x[:c1][known_train], a), y[:c1][known_train])
            a['supervised'] = gbm
            a['family'] = 'supervised'
            selection['supervised'] = float(average_precision_score(sy[known_stop], _raw_scores(sx, a)[-1][known_stop]))
        a['family'] = max(selection, key=selection.get)
    else:
        a['family'] = 'combined'
    cal_scores = _raw_scores(transform_features(x[c2:c3], a), a)[-1]
    cy = y[c2:c3]; known = cy >= 0
    if set(cy[known]) == {0, 1}:
        p, r, thresholds = precision_recall_curve(cy[known], cal_scores[known])
        f = 2*p[:-1]*r[:-1]/np.maximum(p[:-1]+r[:-1], 1e-12)
        a['threshold'] = float(thresholds[np.argmax(f)])
        method = 'calibration_f1'
    else:
        a['threshold'] = float(np.quantile(cal_scores[cy == 0], config.NORMAL_SCORE_QUANTILE))
        method = 'known_normal_calibration_quantile'
    te = transform_features(x[c3:], a)
    ty = y[c3:]; known = ty >= 0
    ts = _raw_scores(te, a)[-1]
    metrics = {}
    if set(ty[known]) == {0, 1}:
        yp = ts[known] >= a['threshold']
        metrics = dict(average_precision=float(average_precision_score(ty[known], ts[known])),
                       precision=float(precision_score(ty[known], yp, zero_division=0)),
                       recall=float(recall_score(ty[known], yp, zero_division=0)),
                       f1=float(f1_score(ty[known], yp, zero_division=0)))
    a['metadata'] = dict(version=VERSION, family=a['family'], validation_candidates=selection,
        threshold_method=method, display_threshold=.5,
        score_meaning='anomaly ranking, not fraud probability', train_rows=c1,
        stop_rows=c2-c1, calibration_rows=c3-c2, test_rows=len(x)-c3,
        normal_train_rows=len(tr), history=history, test_metrics=metrics,
        normal_validation_train_ratio=float(np.mean((reconstruct(ae, va)-va)**2)/max(np.mean((reconstruct(ae, tr)-tr)**2), 1e-12)))
    save_pipeline(a, config)
    return a


def train_claims(claims, labels, config, *, split_roles=None):
    ids = [str(c.get('claim_id', c.get('transaction_id', i))) for i,c in enumerate(claims)]
    if len(ids) != len(set(ids)):
        raise ValueError('Training claim IDs must be unique across all partitions')
    if split_roles is None:
        features, names = compute_features_batch(claims)
    else:
        # Each evaluation partition sees the frozen train ledger and itself,
        # never the inputs from another held-out partition. Labels are not features.
        features = [None] * len(claims)
        for role in (0, 1, 2, 3):
            indexes = [i for i,r in enumerate(split_roles) if r in (0, role)]
            values, names = compute_features_batch([claims[i] for i in indexes])
            for i,f in zip(indexes, values):
                if split_roles[i] == role:
                    features[i] = f
    times = np.asarray([event_time(c).value for c in claims])
    artifacts = train_pipeline([[f[n] for n in names] for f in features], names, config,
                              labels=labels, timestamps=times, split_roles=split_roles)
    order = np.lexsort((times, np.asarray(split_roles))) if split_roles is not None else np.argsort(times, kind='stable')
    metadata = artifacts['metadata']
    cuts = np.cumsum([0, metadata['train_rows'], metadata['stop_rows'],
                      metadata['calibration_rows'], metadata['test_rows']])
    manifest = {}
    for role, lo, hi in zip(('train', 'selection_validation', 'cutoff_validation', 'test'), cuts[:-1], cuts[1:]):
        manifest[role] = [str(claims[i].get('claim_id', claims[i].get('transaction_id', i))) for i in order[lo:hi]]
    ids = sum(manifest.values(), [])
    if len(set(ids)) != len(ids):
        raise ValueError('Training claim IDs must be unique across all partitions')
    metadata['split_manifest'] = manifest
    metadata['input_sha256'] = hashlib.sha256(json.dumps(claims, default=str, sort_keys=True).encode()).hexdigest()
    metadata['run_id'] = uuid.uuid4().hex
    metadata['evaluation_scope'] = ('Fixed stratified vendor-group synthetic split' if split_roles is not None else 'Chronological synthetic split') + '; train-only fitting; validation selects model and threshold; test excluded from both. Previously inspected source data is not a fresh external benchmark.'
    save_pipeline(artifacts, config)
    return artifacts


def save_pipeline(a, config):
    directory = Path(config.TRAINED_MODELS_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    payload = {k: v for k, v in a.items() if k != 'autoencoder'}
    payload['ae_state'] = a['autoencoder'].state_dict()
    payload['latent_dim'] = config.AE_LATENT_DIM
    temporary = directory / f'.pipeline-{uuid.uuid4().hex}.joblib'
    joblib.dump(payload, temporary)
    os.replace(temporary, directory / 'pipeline_v2.joblib')


def load_pipeline(config):
    path = Path(config.TRAINED_MODELS_DIR) / 'pipeline_v2.joblib'
    if not path.exists():
        return None
    a = joblib.load(path)
    if a.get('version') != VERSION or a.get('feature_names') != FEATURE_NAMES:
        raise ValueError('Incompatible model bundle; retrain the model.')
    model = BehavioralAutoencoder(len(FEATURE_NAMES), a.pop('latent_dim'))
    model.load_state_dict(a.pop('ae_state'))
    model.eval()
    a['autoencoder'] = model
    return a
