import pytest
from scripts.calibrate_claim_threshold import metrics, select_threshold, split_rows


def test_selects_recall_under_precision_constraint_and_keeps_ties_together():
    rows = [dict(label=y, score=s) for y, s in [(1, .8), (1, .4), (0, .3), (1, .3)]]
    cutoff = select_threshold(rows, .95)
    assert cutoff == .4
    assert metrics(rows, cutoff)['recall'] == pytest.approx(2 / 3)
    assert metrics(rows, .5)['recall'] == pytest.approx(1 / 3)


def test_test_labels_cannot_change_selected_threshold():
    validation = [dict(label=1, score=.4), dict(label=0, score=.2)]
    cutoff = select_threshold(validation)
    test = [dict(label=1, score=.3), dict(label=0, score=.8)]
    assert metrics(test, cutoff)['precision'] == 0
    assert select_threshold(validation) == cutoff


def test_fixed_split_is_disjoint_by_vendor_and_reproducible():
    rows = [dict(id=f'{g}-{y}', group=str(g), label=y, score=.2 + y / 2) for g in range(20) for y in (0, 1)]
    validation, test = split_rows(rows)
    assert not {r['group'] for r in validation} & {r['group'] for r in test}
    assert split_rows(list(reversed(rows))) == (validation, test)
    assert len(validation) + len(test) == len(rows)


def test_infeasible_precision_target_is_explicit():
    with pytest.raises(ValueError, match='No validation threshold'):
        select_threshold([dict(label=0, score=.9), dict(label=1, score=.2)])
