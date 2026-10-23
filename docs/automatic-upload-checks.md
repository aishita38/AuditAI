# Upload and check in one step

Administrators can now upload vendor master, employee roster, payroll payments, expense claims, bank transfers and linked receipt images/PDFs in **Upload → Data Import**. A receipt still needs an existing Target Claim ID. Existing employee claim/receipt controls and API permissions remain available.

Relevant checks run after each successful upload:

- Vendor master: refresh vendor rules.
- Employee roster or payroll payments: refresh payroll rules using both stored datasets. If one is missing, the response says which dataset is needed. The next import automatically runs the checks again.
- Expense claims: use the existing model on the newly imported IDs with the full historical ledger for behavioral features. Company-policy checks remain enabled. Only non-final claims are scored. The ML model, weights and inputs are not changed or retrained.
- Successfully processed linked receipt: invalidate the previous affected score, then score only that linked non-final claim with the new OCR evidence. Other pending claims and final decisions remain unchanged.
- Bank transfers: check circular payments and claim/payment reconciliation. Claims and receipts also refresh transfer checks for reviewers because claim links/status can affect reconciliation. Bank-transfer validation, atomic imports, roles and idempotency are preserved.

Import responses include automatic-check outcomes and prerequisites. A failed detector does not discard an already committed upload or silently report success. Reviewers can inspect results directly; Recheck is optional recovery/configuration support, not a normal required step. Existing stored vendor/payroll data is checked when the API starts, avoiding a manual first scan after this update. Review recommendations and final approvals stay manual and retain contributor and maker/checker separation.

## Combined anomaly accounting

The dashboard begins with **All anomaly signals**. It includes flagged expense claims (model or policy, deduplicated per claim), current vendor findings, current payroll findings, detected transfer cycles and linked claims with reconciliation flags. It shows each detector's source-record count and unit. Vendor/payroll findings need not be sent to review to be counted.

The sum is a workload count of review signals, not unique fraudulent people, payments or claims. One payment/vendor/claim can participate in multiple legitimate findings, including a cycle and reconciliation discrepancy. No cross-type fraud rate, accuracy or mixed-unit recall is computed. Limited/failed transfer scans make the combined summary explicitly incomplete.

Expense results are separated by dataset in the metrics table: original expenses, Aster expenses, new Aster upload demo, enterprise-format records and other claims. Enterprise-format records are explicitly marked as a scope mismatch for an expense model. This classification is an evaluation/display grouping by existing IDs; records are not deleted or relabelled and the model is not changed.

Precision, recall and F1 in each cohort use the current saved review flags against scored, consistent synthetic scenario labels. Ranking metrics use saved model scores; average precision is the primary PR summary. Precision@K is available for K=10,50,100 when the cohort is large enough, ranked by score then claim ID. These are loaded-data diagnostics, not independent held-out performance. Vendor/payroll rules require their own labelled finding groups to measure precision/recall; the existing synthetic rule evaluation provides that separate benchmark. Additional rule findings are counted in the dashboard but are not falsely counted as recovered expense claims.

## API and validation

POST imports retain their existing paths and add a checks result. GET `/api/v1/detection/overview` requires a reviewer role. POST `/api/v1/detection/recheck` is administrator-only and retries checks against existing data; normal upload does not require calling it.

Tests cover automatic master findings without running a check endpoint, direct combined-form transfer and receipt imports, partial-row imports, stable finding identities on re-import, targeted scoring without touching other pending/final claims, saved imports after a model failure, counting every detector and separated metric cohorts. Existing receipt tests now expect automatic refreshed predictions; the model-cancellation fixture uses ordinary weekdays so it does not accidentally test the separate holiday-policy override.

Verified: 89 backend tests, 15 frontend tests, frontend production build and a clean diff whitespace check.
