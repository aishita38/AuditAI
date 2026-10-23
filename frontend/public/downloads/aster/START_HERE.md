# Aster Company synthetic upload pack

This compact, fictional demonstration pack is adapted to the current AuditAI upload schemas. Baseline employee/vendor names and IDs come from the existing Aster demo; accounts, tax-ID fixtures, employment dates and salaries here are synthetic test assumptions. This is not actual Aster company data. Use these files together. The larger older Aster transactions/master files have different schemas.

Sign in as **Demo Administrator** using developer OTP. Open **Upload → Data Import**. Upload in this order:

| Order | Dataset option | File | Records |
|---|---|---|---:|
| 1 | Vendor master | 01_aster_vendor_master.csv | 39 |
| 2 | Employee roster | 02_aster_employee_roster.csv | 37 |
| 3 | Payroll payments | 03_aster_payroll_payments.csv | 40 |
| 4 | Expense claims | 04_aster_expense_claims.csv | 15 |
| 5 | Bank transfers | 05_aster_bank_transfers.csv | 10 |
| 6 | Receipt | Individual PNGs in receipts/ | 3 |

All six types can be uploaded in the same Data Import form; relevant checks run automatically. Import claims **before** bank transfers so their claim_id links exist. Do not upload the ZIP itself. Extract it first. Keep CSV headers and ISO dates unchanged; opening/resaving in Excel can alter IDs and dates.

## Receipt uploads

Receipt upload accepts an image/PDF, not a CSV. Select Receipt, enter the matching Target Claim ID, and upload the image below. `06_receipt_upload_map.csv` is a guide, not an upload dataset.

| Image | Target Claim ID | Receipt total | Claim amount |
|---|---|---:|---:|
| receipts/receipt_AST-DEMO-CLM-001.png | AST-DEMO-CLM-001 | INR 4,500 | INR 4,500 |
| receipts/receipt_AST-DEMO-CLM-002.png | AST-DEMO-CLM-002 | INR 4,500 | INR 45,000 |
| receipts/receipt_AST-DEMO-CLM-003.png | AST-DEMO-CLM-003 | INR 6,000 | INR 6,000 |

These are generated receipt images, not actual tax invoices. CSV claims already include simulated OCR amounts, so the tabular receipt mismatch can be tested independently of OCR. Actual image OCR depends on the configured OCR runtime and has not been guaranteed by these files.

## Checks to try

Checks run automatically on upload. Open Audit Screens to inspect the results (Recheck is optional):

- **Vendor Master Checks:** 10 expected findings covering shared bank, address, phone, connected vendor groups, invalid tax-ID formats and embedded-PAN mismatches. Similar names and blank fields are included as decoys.
- **Payroll Checks:** 14 expected findings covering ghost employees, before-join/after-exit payments, bank/PAN duplicate payees, salary mismatch, duplicate payments and bank mismatch. Join/exit boundary dates, salary exactly at tolerance and separate pay periods are decoys.
- **Circular Payments:** AST-DEMO-CYCLE-01 → AST-DEMO-CYCLE-02 → AST-DEMO-CYCLE-03 is a three-transfer cycle returning 95% of the initial amount. AST-DEMO-OPEN-01/02/03 are normal outbound transfers and do not form a cycle.
- **Payment Reconciliation:** AST-DEMO-CLM-001 has two INR 4,500 payments (total INR 9,000 against a INR 4,500 claim). AST-DEMO-CLM-002 has a INR 450,000 payment against a INR 45,000 claim. AST-DEMO-CLM-003 has a matching INR 6,000 payment. All newly imported claims start pending, so their payments also lack checker approval until the real workflow records it.
- **Expense claims:** AST-DEMO-CLM-002 has a planted receipt mismatch. The remaining claims are controls for that scenario, not promises that every company-policy check will pass. Run the existing scoring/policy workflow to generate its flags.

Click **Send to review** on any vendor/payroll finding, then use another permitted maker/checker account to investigate. Re-importing unchanged master files should skip existing rows. Re-running unchanged checks should preserve finding and review-case identities.

## Limits and answer key

`ground_truth.json` identifies exact vendor/payroll record groups and circular/reconciliation examples. `validation_report.json` records the isolated upload checks. Expected counts are for this pack by itself; existing imported master data can create additional groups/findings.

The new-vendor large-payment rule remains **Cannot evaluate, vendor-linked transactions unavailable**. Bank-transfer uploads do not contain a vendor_id link. Shared names or accounts do not substitute for that key. No claim approval decisions or fraud scores are fabricated by this pack. Findings are review signals, not proof of fraud. Synthetic fixture results are not held-out or real-world model performance.
