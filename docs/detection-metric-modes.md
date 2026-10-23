# Full policy evaluation

Generated: 2026-10-18T13:59:27.229066+00:00

Checked 14,000 claims. 4,306 require policy review. ML scores and final review decisions were not changed.

Loaded-data diagnostics include training rows; use the separate split-test results for model evaluation. Model-only uses the displayed dataset-specific validation cutoff. Enterprise expense ML is disabled; enterprise combined equals policy-only, while vendor, payroll, circular and reconciliation rules remain separate. Policy-only includes full saved company checks and the holiday override. Model and policy comparisons use labelled scored policy-evaluated expense claims; enterprise policy evaluation does not require ML scores. Missing evaluations are excluded. PR-AUC and top-K apply only to model scores. Vendor/payroll metrics have separate evaluation units.

| Dataset | Method | Flagged | TP | FP | FN | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Aster expense claims | model_only | 178 | 150 | 28 | 0 | 0.8427 | 1.0000 | 0.9146 |
| Aster expense claims | policy_only | 279 | 120 | 159 | 30 | 0.4301 | 0.8000 | 0.5594 |
| Aster expense claims | combined | 335 | 150 | 185 | 0 | 0.4478 | 1.0000 | 0.6186 |
| Enterprise records in expense schema (scope mismatch) | model_only | 0 | None | None | None | Unavailable | Unavailable | Unavailable |
| Enterprise records in expense schema (scope mismatch) | policy_only | 4547 | 1761 | 2786 | 239 | 0.3873 | 0.8805 | 0.5380 |
| Enterprise records in expense schema (scope mismatch) | combined | 4547 | 1761 | 2786 | 239 | 0.3873 | 0.8805 | 0.5380 |
| Original expense claims | model_only | 65 | 65 | 0 | 85 | 1.0000 | 0.4333 | 0.6047 |
| Original expense claims | policy_only | 184 | 57 | 127 | 93 | 0.3098 | 0.3800 | 0.3413 |
| Original expense claims | combined | 201 | 74 | 127 | 76 | 0.3682 | 0.4933 | 0.4217 |

## Rule coverage

Rules without required input fields remain unavailable; this run does not invent missing invoice, approver or transaction-time evidence.

| Rule | Review | Pass | Unavailable | Signal |
|---|---:|---:|---:|---:|
| after_hours | 0 | 0 | 14000 | 0 |
| approval_limit | 0 | 0 | 14000 | 0 |
| duplicate | 330 | 0 | 13670 | 0 |
| high_value | 1287 | 12713 | 0 | 0 |
| invoice_splitting | 260 | 13740 | 0 | 0 |
| missing_info | 110 | 13890 | 0 | 0 |
| receipt_mismatch | 590 | 11410 | 2000 | 0 |
| round_number | 143 | 13857 | 0 | 0 |
| sequence_gap | 0 | 0 | 14000 | 0 |
| suspicious_wording | 14 | 13986 | 0 | 0 |
| weekend | 2979 | 11021 | 0 | 0 |
