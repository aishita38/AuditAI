"""One routing/cutoff decision shared by scoring and dashboard metrics."""
import json
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).with_name('detection_strategy.json')


def settings():
    return _settings(PATH.stat().st_mtime_ns) if PATH.exists() else {}


@lru_cache(maxsize=4)
def _settings(modified):
    return json.loads(PATH.read_text(encoding='utf-8'))


def dataset_key(claim_id):
    if claim_id.startswith('TXN'):
        return 'enterprise'
    if claim_id.startswith('AST-'):
        return 'aster'
    if claim_id.startswith('CLM-'):
        return 'original'
    return 'other'


def strategy(claim_id):
    key = dataset_key(claim_id)
    value = settings().get(key, {})
    return dict(dataset=key, model_enabled=key != 'enterprise',
                threshold=float(value.get('threshold', .5)),
                basis=value.get('basis', 'Default model cutoff'))


def model_decision(claim_id, score):
    value = strategy(claim_id)
    if not value['model_enabled']:
        return False
    return None if score is None else bool(score >= value['threshold'])
