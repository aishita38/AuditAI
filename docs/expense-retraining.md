# Expense-only model retraining

Fixed stratified vendor-group synthetic split; train-only fitting; validation selects model and threshold; test excluded from both. Previously inspected source data is not a fresh external benchmark.

Run: 1ddbe81cf99943cbbeb0e89bf3c3953a. Activated: True.

Split counts: {'train': 2463, 'selection_validation': 383, 'cutoff_validation': 377, 'test': 777}

| Dataset | Cutoff | Test positives | TP | FP | FN | Precision | Recall | F1 | AP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| aster | 0.48663636 | 20 | 20 | 12 | 0 | 62.50% | 100.00% | 0.7692 | 0.8618 |
| original | 0.66269526 | 36 | 10 | 0 | 26 | 100.00% | 27.78% | 0.4348 | 0.5667 |

Source data has been previously inspected; this repairs fitting overlap, not prior human exposure.
Synthetic scenario labels, not real fraud outcomes. No independent external benchmark.
Old cutoff 0.4351 cannot be transferred to the new model score scale.
Model family and early stopping use selection validation; threshold uses cutoff validation; test never updates parameters.

Full input snapshot, split manifests, hashes, model and recovery backup: C:\Users\aishi\AuditAI\scripts\artifacts\expense-retrain-20261018T134641Z

Reproduce with python scripts/retrain_expense_benchmark.py (no activation by default). Add --activate to update the local model, routing and saved scores.
Dashboard metrics describe all loaded rows, including training rows. Only the test rows in report.json support the split-test results above.

Historical-model calibration (before retraining): Aster cutoff 0.43508021; Original cutoff 0.33914711. These belong to the previous score scale, not the activated model. The chronological diagnostic had zero Aster test anomalies and is retained in expense-retrain-20261018T134527Z; it was superseded by the fixed vendor-group benchmark.

Routing currently uses synthetic dataset ID prefixes: AST- for Aster, CLM- for Original, TXN for enterprise. Vendor names are used only for evaluation grouping, never to link vendor payments.
