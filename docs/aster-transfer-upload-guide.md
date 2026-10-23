# Aster transfer upload guide

Upload uploads/aster_circular_payments.csv as Admin under Audit Screens → Circular Payments → Import and screen. This file adds 25 fictional bank transfers to the Aster company dataset. It has not been imported automatically. Keep the defaults: 7 days and up to 4 transfers per cycle.

## Expected results

- AST-PAY-CYCLE-A-01 through 03: planted 3-account cycle; INR 100,000 initially, INR 95,000 returned; 2 hours.
- AST-PAY-CYCLE-B-01 through 04: planted 4-account cycle; INR 250,000 initially, INR 240,000 returned; 3 hours.
- AST-PAY-REFUND-01 and 02: legitimate fictional purchase/refund, INR 5,000; structurally a cycle and expected to be flagged. This is the deliberate false positive.
- AST-PAY-CLAIM-01 through 10: matching-amount reimbursements linked to existing Aster claims, no return transfers; no cycles expected.
- AST-PAY-FX-01/02: currency mismatch; no same-currency cycle.
- AST-PAY-TIED-01/02: equal timestamps; excluded because order is unknown.
- AST-PAY-LATE-01/02: 19-day return; outside the default 7-day window. A 30-day window will detect it.

Expect 3 additional cycle results at default settings: 2 planted concerns and 1 known legitimate refund. With the existing 13 example transfers still loaded, the screen should show 38 transfers and 5 total cycles. Existing cases/settings/data can change these totals. Resubmitting an identical file skips its IDs rather than duplicating it.

## Reconciliation

The 10 linked payments use the exact current claim amounts and employee bank accounts in Aster employees.csv. Check Payment Reconciliation after import. Matching amount does NOT mean a payment was authorized: pending/flagged/scored claims can still show payment without checker approval, and missing historical approval/currency is explicitly reported. Only settlement rows carry claim_id; cycle hops are intentionally unlinked to avoid pretending intermediate transfers are claim payments.

Linked claims at file generation:

| Transfer | Claim | Employee | Amount INR | Current claim status |
|---|---|---|---:|---|
| AST-PAY-CLAIM-01 | AST-CLM-018871 | EMP191 | 1019.07 | scored |
| AST-PAY-CLAIM-02 | AST-CLM-018872 | EMP166 | 2899.59 | flagged |
| AST-PAY-CLAIM-03 | AST-CLM-018873 | EMP012 | 4733.82 | scored |
| AST-PAY-CLAIM-04 | AST-CLM-018874 | EMP220 | 2366.96 | scored |
| AST-PAY-CLAIM-05 | AST-CLM-018875 | EMP197 | 1992.53 | scored |
| AST-PAY-CLAIM-06 | AST-CLM-018876 | EMP094 | 4165.89 | scored |
| AST-PAY-CLAIM-07 | AST-CLM-018877 | EMP196 | 1435.37 | scored |
| AST-PAY-CLAIM-08 | AST-CLM-018878 | EMP219 | 2498.77 | scored |
| AST-PAY-CLAIM-09 | AST-CLM-018879 | EMP100 | 1734.91 | scored |
| AST-PAY-CLAIM-10 | AST-CLM-018880 | EMP196 | 1988.47 | scored |

## Account provenance and limitations

Vendor accounts are copied from the first 15 entries of data/company_demo/vendors.csv; employee accounts come from data/company_demo/employees.csv. The treasury account TEST-ASTER-TREASURY-INR-001 is a newly invented company account fixture. This is an additive synthetic transfer scenario, not a reconstruction of historical bank movements or the original approval-collusion labels. Times and cycle amounts are deliberately planted in July 2025. Nothing here is a real payment or evidence of fraud. Do not train on scenario names in transaction IDs.

Vendor account mapping:

| Vendor ID | Vendor | Account |
|---|---|---|
| VEN0001 | Aster Test Supplier 001 | TEST-VENDOR-BANK-0001 |
| VEN0002 | Aster Test Supplier 002 | TEST-VENDOR-BANK-0002 |
| VEN0003 | Aster Test Supplier 003 | TEST-VENDOR-BANK-0003 |
| VEN0004 | Aster Test Supplier 004 | TEST-VENDOR-BANK-0004 |
| VEN0005 | Aster Test Supplier 005 | TEST-VENDOR-BANK-0005 |
| VEN0006 | Aster Test Supplier 006 | TEST-VENDOR-BANK-0006 |
| VEN0007 | Aster Test Supplier 007 | TEST-VENDOR-BANK-0007 |
| VEN0008 | Aster Test Supplier 008 | TEST-VENDOR-BANK-0008 |
| VEN0009 | Aster Test Supplier 009 | TEST-VENDOR-BANK-0009 |
| VEN0010 | Aster Test Supplier 010 | TEST-VENDOR-BANK-0010 |
| VEN0011 | Aster Test Supplier 011 | TEST-VENDOR-BANK-0011 |
| VEN0012 | Aster Test Supplier 012 | TEST-VENDOR-BANK-0012 |
| VEN0013 | Aster Test Supplier 013 | TEST-VENDOR-BANK-0013 |
| VEN0014 | Aster Test Supplier 014 | TEST-VENDOR-BANK-0014 |
| VEN0015 | Aster Test Supplier 015 | TEST-VENDOR-BANK-0015 |
