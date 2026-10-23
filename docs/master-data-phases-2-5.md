# Vendor and payroll checks: Phases 2–5

## What is available

Upload the three master datasets once under **Upload → Master data import** (administrator). Choose Vendor master, Employee roster or Payroll payments. Existing expense, receipt and bank-transfer import paths retain their existing behavior. The new section shows stored counts, last import attempt/status, inserted/updated/skipped/rejected totals and row-level rejection reasons, including rejected-file attempts.

Open **Audit Screens → Vendor Master Checks / Payroll Checks**, then **Run checks**. Findings can be filtered by rule and opened to inspect every saved source record, highlighted trigger fields, connected attributes and rule thresholds. Lists over ten records expand with Show all. Send to review creates an idempotent case in the shared review queue and links to `/review/cases/:caseId`; maker/checker actions, comments and audit history are reused.

The live vendor master, employee roster and payroll tables were empty at implementation verification. No synthetic rows were silently mixed into the existing live claims database. Import the files below to exercise the new screens.

## Rules

Vendor rules: VENDOR_SHARED_BANK, VENDOR_SHARED_ADDRESS, VENDOR_SHARED_PHONE, VENDOR_SHELL_NETWORK, VENDOR_INVALID_TAX_ID, VENDOR_NEW_LARGE_PAYMENT.

Network components use normalized bank accounts, phones, addresses and semicolon-separated, case-insensitive director names. Evidence lists all participating vendors and attribute groups; each group's vendor IDs identifies the pairs sharing that attribute. Missing/blank attributes never match. Similar vendor names do not create links.

Tax-ID checks enforce PAN/GSTIN formats and compare the GSTIN's embedded PAN to the supplied PAN. This is a **format check, not verification**, and is not a government identity lookup. Missing identifiers are not treated as malformed identifiers.

The new-vendor large-payment function requires explicit vendor_id-linked transactions. It examines the first recorded payment time and applies a strict amount threshold within an inclusive onboarding window. The app has no reliable vendor_id-linked transaction dataset, so its live status is **Cannot evaluate, vendor-linked transactions unavailable**. It never matches vendor names and does not register or query the legacy ERP router. The separate fixture CSV exercises this function in tests/evaluation only; it is not an upload type and does not establish live integration coverage.

Payroll rules: PAYROLL_GHOST_EMPLOYEE, PAYROLL_AFTER_EXIT, PAYROLL_BEFORE_JOIN, PAYROLL_DUPLICATE_PAYEE, PAYROLL_SALARY_MISMATCH, PAYROLL_DUPLICATE_PAYMENT, PAYROLL_BANK_MISMATCH.

Employment date comparisons are strict: payments exactly on join/exit dates do not trigger them. Salary mismatches require a difference strictly greater than the configured tolerance; a zero salary with a positive payment is flagged. Duplicate payment means the same employee_id/pay_period has multiple payments, even when amounts differ. Duplicate payees require different employee IDs sharing bank accounts across roster and payments, or sharing PAN on the roster only. Same employee/account across successive periods is not a duplicate-payee finding. Missing bank accounts are not compared as equal or mismatched.

## Configuration and evidence lifecycle

`backend/app/master_rule_config.json` is the single configuration object, validated on every run. Defaults: new-vendor amount INR 2,000,000; window 7 days; payroll salary tolerance 0.05 (5%). Edit that file and rerun checks; no ML retraining or model input changes occur.

Finding identities hash rule, involved records, evidence and configuration. Unchanged reruns and idempotent re-imports keep the same finding/case identity. Changed data produces a new finding identity and deactivates obsolete findings. Submitting a finding revalidates it against current data; stale unsent findings are rejected. Existing cases retain their original evidence, rule configuration, excluded contributors and audit events. Live-record lookups affect links only and do not overwrite saved evidence.

Reviewers cannot be both maker and checker. Because the approved master tables do not record per-row import ownership, the conservative contributor policy excludes all actors who inserted or updated the relevant dataset through successful/partial imports. Import attempts with zero changes do not add exclusions. Case creation records the submitting actor, and existing shared permissions enforce review separation.

## Reproducible synthetic demonstration

Run:

```powershell
python scripts/generate_master_rule_dataset.py
python scripts/evaluate_master_rules.py
```

Files in `data/master_rule_demo/`:

- `vendor-master.csv`: import as Vendor master.
- `employee-roster.csv`: import as Employee roster.
- `payroll-payments.csv`: import as Payroll payments.
- `ground-truth.json`: independently specified finding-level record sets and per-rule decoys; not generated from detector output.
- `vendor-linked-transactions-fixture.csv`: test-only input for the unavailable live vendor payment rule. Do not upload it as bank transfers.

The demo includes a clean baseline, shared vendor attributes, a three-vendor director network, invalid/mismatched tax formats, four unknown-employee payments, two payments after exit, two before join, bank/PAN duplicate-payee groups, salary/duplicate-payment/bank mismatches, and decoys for every rule. Boundary decoys include exactly-on-exit/join dates, exactly-at-tolerance salary, exactly-at-amount/window boundaries, same names with different attributes, missing attributes and legitimate separate pay periods.

Expected live-schema findings after importing all three files: **10 vendor findings and 14 payroll findings**. Some findings concern the same records; these are not 24 distinct fraudulent entities. The fixture-only new-vendor payment rule adds one expected evaluation finding.

The evaluator reports per-rule TP, FP, FN, precision and recall against exact involved-record sets, and saves `scripts/artifacts/master-rule-evaluation.json`. Matching complete record sets checks that grouped findings include all involved records. No accuracy metric is used.

## Limitations

Findings are review signals, never proof of fraud, based on imported records only. Shared addresses/directors/accounts can be legitimate; payroll bonuses, deductions, arrears, installments and prorating can explain mismatches. Imported history may be incomplete, so “first payment” means first recorded payment. PAN matching is roster-only; missing required datasets produce import instructions. There is no vendor-name joining, identity verification, or automatic payment/claim approval.

Perfect results on the deliberately constructed small synthetic fixtures demonstrate rule behavior, not real-world fraud detection performance. The existing 14,000-claim ML evaluation is unchanged: vendor/payroll findings are separate entities and cannot be counted as recovered expense claims without actual linking keys and matching ground truth.

## Validation and changes

New backend: `features/master_rules.py`, `master_rule_config.json`, `models/master_finding.py`, `master_rule_service.py`, `api/master_checks.py`; router registration in `main.py`.

Frontend: `MasterChecks.jsx`, `MasterDataImport.jsx`, Audit Screens tabs, Upload section, API client methods, and evidence support for vendor-linked transfer snapshots.

Fixtures/tests: generator and evaluator above, synthetic CSVs/ground truth, `tests/test_master_rules.py`, `tests/test_master_checks_api.py`, `frontend/src/pages/MasterChecks.test.jsx`. Phase 1 validation/import tests and existing workflow tests are also run as regression checks.

Validation result: 79 backend regression tests passed; 12 frontend tests passed; frontend production build passed (existing large-bundle advisory remains). Browser verification confirmed both Audit Screens tabs, missing-dataset instructions, rule configuration and unavailable vendor-link status.
