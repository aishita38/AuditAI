# Aster threshold experiment

Retrospective synthetic Aster evaluation; previously inspected data; training overlap unknown. Not an untouched or production test.

Maximum validation recall subject to precision >= 0.95; ties prefer precision then higher cutoff.

Selected cutoff: 0.43508021. Live cutoff remains 0.50. Input SHA-256: `e830961ad3c12aac5fd321ca6d54244fe49135166deba75853ccba57d24c2f9c`.

| Split | Cutoff | Rows | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| validation | 0.50000000 | 988 | 64 | 0 | 36 | 100.00% | 64.00% | 0.7805 |
| validation | 0.43508021 | 988 | 96 | 4 | 4 | 96.00% | 96.00% | 0.9600 |

validation average precision: 0.9908 (same at either cutoff).

| test | 0.50000000 | 1012 | 27 | 0 | 23 | 100.00% | 54.00% | 0.7013 |
| test | 0.43508021 | 1012 | 42 | 2 | 8 | 95.45% | 84.00% | 0.8936 |

test average precision: 0.9664 (same at either cutoff).

50/50 by normalized vendor name; group key only, no record linkage. Existing scores and historical context are fixed, not recomputed per split.

Vendor grouping does not isolate shared employees or all historical dependencies.
Synthetic labels may not reflect real fraud. No confidence guarantee follows from the validation precision target.
Threshold changes decisions, not ranking: PR-AUC is unchanged.
A fresh benchmark excluded from training and previous inspection is required before deployment.

Reproduce: `python scripts/calibrate_claim_threshold.py`. The JSON includes every split claim ID. No database, model, policy or live threshold is changed.
