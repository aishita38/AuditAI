# Loaded claim evaluation

Retrospective loaded synthetic claims; training overlap not excluded. Not held-out production performance.

Scored and labelled: 14,000. Positive labels: 2,300. Source: synthetic is_fraud labels, not case approvals. No accuracy metric is used.

| Scope | Decision | Precision | Recall | F1 | TP | FP | FN |
|---|---|---:|---:|---:|---:|---:|---:|
| overall | score_threshold_50 | 25.67% | 34.39% | 0.2940 | 791 | 2290 | 1509 |
| overall | saved_review_flags | 23.52% | 39.74% | 0.2955 | 914 | 2972 | 1386 |

overall: average precision 0.1863; trapezoidal PR area 0.1843; prevalence baseline 16.43%.

- Precision@10: 10.00% (1/10); boundary-tie range 10.00%–10.00%.
- Precision@50: 6.00% (3/50); boundary-tie range 6.00%–6.00%.
- Precision@100: 14.00% (14/100); boundary-tie range 14.00%–14.00%.
| original_expenses | score_threshold_50 | 100.00% | 32.67% | 0.4925 | 49 | 0 | 101 |
| original_expenses | saved_review_flags | 32.26% | 40.00% | 0.3571 | 60 | 126 | 90 |

original_expenses: average precision 0.8060; trapezoidal PR area 0.8057; prevalence baseline 7.50%.

- Precision@10: 100.00% (10/10); boundary-tie range 100.00%–100.00%.
- Precision@50: 100.00% (50/50); boundary-tie range 100.00%–100.00%.
- Precision@100: 94.00% (94/100); boundary-tie range 94.00%–94.00%.
| aster_expenses | score_threshold_50 | 100.00% | 60.67% | 0.7552 | 91 | 0 | 59 |
| aster_expenses | saved_review_flags | 36.40% | 60.67% | 0.4550 | 91 | 159 | 59 |

aster_expenses: average precision 0.9847; trapezoidal PR area 0.9847; prevalence baseline 7.50%.

- Precision@10: 100.00% (10/10); boundary-tie range 100.00%–100.00%.
- Precision@50: 100.00% (50/50); boundary-tie range 100.00%–100.00%.
- Precision@100: 100.00% (100/100); boundary-tie range 100.00%–100.00%.
| enterprise_transactions_imported_as_claims | score_threshold_50 | 22.14% | 32.55% | 0.2635 | 651 | 2290 | 1349 |
| enterprise_transactions_imported_as_claims | saved_review_flags | 22.12% | 38.15% | 0.2800 | 763 | 2687 | 1237 |

enterprise_transactions_imported_as_claims: average precision 0.1599; trapezoidal PR area 0.1576; prevalence baseline 20.00%.

- Precision@10: 10.00% (1/10); boundary-tie range 10.00%–10.00%.
- Precision@50: 4.00% (2/50); boundary-tie range 4.00%–4.00%.
- Precision@100: 8.00% (8/100); boundary-tie range 8.00%–8.00%.

## Interpretation and limits

Precision@K means: of the K highest-scoring claims a reviewer can inspect, what fraction carry an anomaly label? Ties use claim ID, not labels; the possible range from boundary ties is disclosed in the JSON.
Saved review flags include policy overrides; the score-threshold row isolates thresholding the saved ML index at 0.5. PR summaries and Precision@K use saved scores, not policy flags.
These claims may have participated in training, calibration or model selection. This is a current-data diagnostic, not an independent test-set result. Aster and enterprise sources have different scenario distributions; per-source results are included.
Some labelled scenarios require ERP fields absent from the expense model. A synthetic normal claim may still trigger a legitimate company-policy review; such flags count as false positives against the scenario labels here.
PR-AUC measures ranking across thresholds, but depends on class prevalence and label quality. Average precision and trapezoidal PR area are different calculations; do not present them as interchangeable.
No database rows, thresholds, flags or model artifacts were changed by this evaluation.
