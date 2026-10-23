# Vendor and payroll master data — Phase 1

Phase 1 adds storage and import APIs only. It does not add vendor/payroll rules, findings, new review cases, synthetic benchmark datasets or frontend tabs. Existing bank-transfer import behavior, legacy ERP router registration, and ML inputs/models/training are unchanged.

## Tables

`vendor_master`, `employee_master`, and `payroll_payments` each have an integer internal primary key and a separate unique, indexed business key: vendor_id, employee_id, and payment_id respectively. Payroll employee_id is text, with no roster foreign key: unknown employees remain importable. No accounts or tax identifiers are assumed unique across records; sharing will be screened in later phases.

The existing startup `Base.metadata.create_all` creates the additive tables and `master_import_history` after the new router registers their models. Existing tables are not rebuilt or modified. No data is loaded automatically. For a running API without auto-reload, restart it to activate the new routes/tables.

## Endpoints

All imports use multipart/form-data with a `file` field and require an authenticated admin:

- POST /api/v1/master-data/vendor-master/import
- POST /api/v1/master-data/employee-roster/import
- POST /api/v1/master-data/payroll-payments/import

GET /api/v1/master-data/status is available to admin, maker and checker roles. It returns one entry per dataset: rows_loaded, last_imported_at (latest attempt, including empty/rejected), last_import_status, and last_successful_imported_at. Timestamps are UTC with Z. Unimported datasets report 0 rows and null times.

Import summaries contain import_id, dataset, status, inserted, updated, skipped, rejected, and errors (row, reason). Row numbers are logical CSV rows, with the header as row 1. Counts describe data rows, not file-level failures. Missing-header, encoding, CSV syntax and size failures use HTTP 422 and persist history with a file-level error (row null). An all-invalid but structurally valid CSV returns HTTP 200 with status rejected and a per-row rejection count; callers must inspect status as well as the HTTP code. Mixed valid/invalid data returns status partial. Missing authentication/authorization or a missing multipart file is rejected by FastAPI before import processing and does not create an import-history entry.

Empty bytes and valid header-only files are recorded with status empty and zero counts. Maximum size: 2 MB. Maximum data rows: 5,000. Files exceeding either limit load no records. Malformed CSV structure/encoding aborts file parsing before data loading; row-level value errors do not abort other valid rows.

History records the actor, filename, UTC timestamp, summary and rejection report. It stores a SHA-256 of accepted-size file bytes; oversize uploads store no digest because the upload is read only up to the size limit plus one byte. Existing history is retained on re-import.

## CSV columns and normalization

Column names are trimmed and lowercased; UTF-8 BOM is supported. Duplicate headers are rejected. Extra named columns are ignored. All listed columns are required except exit_date, which may be omitted or blank.

Vendor:
`vendor_id,vendor_name,bank_account,ifsc,address,phone,gstin,pan,director_names,onboarding_date,status`

Employee roster:
`employee_id,name,bank_account,pan,department,join_date,exit_date,monthly_salary`

Payroll:
`payment_id,employee_id,employee_name,bank_account,amount,pay_period,payment_date`

- All strings are trimmed; IDs, PAN, GSTIN and IFSC are uppercased.
- Accounts and phones lose whitespace and dashes, preserving leading zeros and other characters.
- Addresses are lowercased with collapsed whitespace.
- Director names remain semicolon-separated, with whitespace cleaned and empty segments removed.
- Business keys, names, department and vendor status must be nonblank. Optional account/tax/contact values may be blank and are stored as null, not invented placeholders. Later matching rules must ignore missing values.
- Dates require YYYY-MM-DD and a valid calendar date. Exit cannot precede join.
- Pay period requires YYYY-MM with month 01–12.
- Salary is finite and non-negative; payments are finite and positive. Both allow at most 13 integer digits and 2 decimal places, using decimal arithmetic.
- Tax-ID format is deliberately NOT validated on import: malformed PAN/GSTIN must be stored so the later format-check rule can report them. No government verification is performed.

Upserts compare normalized values against the unique business key. Unchanged rows are skipped; changed records update in place, preserving internal IDs. Within one file, repeated identical normalized records are skipped; conflicting repeated keys reject the later row and keep the first valid record. Per-row savepoints isolate database uniqueness races and report the affected row for retry.

## Approved decisions for later phases

New-vendor payment checks must use an explicit vendor_id transaction link only, never a vendor-name match. No legacy ERP router will be revived. Where that link is unavailable, show “Cannot evaluate, vendor-linked transactions unavailable”. Proposed defaults are INR 2,000,000 and 7 days in a shared rule configuration.

Duplicate-payee screening will compare accounts across roster and payments; PAN matching will be roster-only because the approved payroll schema has no PAN field. The import endpoints do not implement these checks in Phase 1.

## Validation

`python -m pytest tests/test_master_data_imports.py tests/test_transfer_cycles.py tests/test_transfer_workflow.py -q --tb=short --disable-warnings`

Result: 43 passed. Tests use isolated SQLite databases with foreign-key enforcement enabled for the new import cases, and do not import fixtures into the live application. Coverage includes all three datasets, normalized unique keys, leading zeros, malformed tax-ID storage, unknown payroll employees, partial rejection reports, updates/skips, duplicate rows, empty/rejected history, status timestamps, invalid dates/amounts, oversize/row-limit failures, roles and existing transfer behavior.

`npm run build` in frontend: passed; existing bundle-size warning remains. No frontend files changed in this phase.

## Phase 1 changed files

- backend/app/models/master_data.py — new tables
- backend/app/schemas/master_data.py — response contracts
- backend/app/master_import_service.py — normalization, validation, partial upserts/history
- backend/app/api/master_data.py — import and status routes
- backend/app/main.py — register the new router (two added lines for this phase)
- tests/test_master_data_imports.py — isolated import/API tests
- docs/master-data-phase-1.md — contracts, limits and results

The working tree already contained other changes from earlier tasks; those are outside this Phase 1 change list.
