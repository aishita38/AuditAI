# Circular payment screening

Open **Audit Screens → Circular Payments** (/audit-screens?tab=circular) as a maker, checker or administrator. The old /circular-payments URL redirects here; it has no separate navigation item. Administrators can import UTF-8 CSVs with transaction_id, sender_account, receiver_account, amount, currency, timestamp, and optional claim_id. Timestamps require a timezone; amounts must be positive and have at most two decimal places. Account identifiers remain text so leading zeros survive. All timestamps are stored and displayed in UTC.

Download the synthetic sample from that page. The default 7-day, 4-transfer scan should identify DEMO-CYCLE-001/002/003 (A → B → C → A) and DEMO-RETURN-001/002 (D → E → D). These are fictional transfer examples, separate from previous employee approval-collusion fixtures. Open chains, currency mismatches, simultaneous transfers and a 19-day return are negative controls at default settings.

Transfers live in a new additive bank_transfers table; existing expense and ERP tables are preserved. App startup creates the table. Imports are atomic on validation failures, skip identical existing IDs and reject changed duplicate IDs. Uploads require admin; screening requires maker, checker or admin. No ML feature changes or retraining are required.

The detector follows strictly increasing timestamps in the same currency, closes a path when funds return to the starting account, and avoids repeated intermediate accounts. Default limits: 7 days, 4 transfers; adjustable 1–30 days and 2–6 transfers. The ledger is limited to 5,000 rows, scan exploration to 200,000 edge visits and results to 100. Search-limit warnings mean the result is incomplete. Time ties cannot establish transfer order. Self-transfers are excluded. Amounts are evidence, not a condition that proves tracing of identical funds; split/merged funds and cross-currency flows are not reconstructed. No claim anomaly score is changed.

## Send to review

Each detected cycle has a Send to review button. The backend revalidates the actual stored transfers; it never accepts client-supplied findings as evidence. A stable key deduplicates submissions of the same transfer set. A case preserves its evidence, settings and creation event, even when later screening settings hide that cycle.

The review queue is now the shared /review-queue page, alongside expense and reconciliation cases. Circular Payments remains a detection tab and links to the common queue. Makers recommend acceptable/explained or unresolved concern. A different checker signs off. Importers and owners/contributors of linked claims cannot review their own evidence. Closed cases cannot be changed. Every action records actor, UTC time, notes, prior state and new state. Optimistic versioning rejects conflicting concurrent decisions. The API exposes no audit-event edit/delete action. See docs/shared-review-queue.md.

Cycle cases use cycle_review_cases and cycle_review_events, because the existing expense Case table requires one claim and a transfer cycle can span several claims or none. They follow the same maker–checker sequence without inventing an expense claim. Cycle approval means the pattern has been explained; it does not approve linked expenses, execute payments, or establish legal innocence/guilt.

## Payment reconciliation

Open Audit Screens → Payment Reconciliation. Populate claim_id only on actual settlement payments, not every intermediate transfer. It must reference an existing expense claim. Unknown IDs reject the entire import; blank IDs remain valid for unlinked transfers. Startup adds the nullable claim_id column and index to existing bank_transfers tables without deleting existing data. Existing IDs remain immutable; importing changed data (including claim links) is rejected.

The screen reports: paid total different from claim amount; payment linked to a currently rejected claim; multiple settlements for one claim; payment before the recorded final checker approval; missing checker approval; currency mismatch or unavailable currency/history. All linked claims, including matches, are shown with their payment evidence. Amounts use decimals; mixed currencies never get a combined total. Approval time comes from the saved final_approved audit event, not submitted_at or updated_at. A later rejection is shown as current claim state rather than a historical fraud finding.

Amount comparison assumes full settlement. Fees, withholding, FX, partial payments and refunds require further accounting logic. Multiple payments may be legitimate installments. The current claim amount is compared; there is no versioned approved-amount history. Claim currency is taken from its entity; absent currency or approval history is explicitly unavailable. Unlinked transfers cannot be reconciled. Findings do not automatically change claim state or open expense review cases.

## Synthetic evaluation and limitations

Run `python scripts/evaluate_circular_payments.py`. It writes scripts/artifacts/circular-payment-evaluation.json. Seven isolated, hand-authored scenarios at the default settings produce 2 true positives, 1 false positive, 4 true negatives, and 0 false negatives: precision 66.7%, recall 100%, false-positive rate 20%. These are scenario-level illustrative numbers, not transaction-level accuracy or a real-world estimate. The false positive is a legitimate purchase followed by a refund: structurally it is a cycle, so human context is required. No ML performance is measured.

Automated tests additionally cover INR 4,500 approved versus INR 45,000 paid, rejected-claim payment, repeated payment, early payment, a correct settlement, missing history/currency, mixed currencies, unauthorized access, claim-owner/contributor restrictions, duplicate submissions, closed-case protection, audit trails and repeatable migration.

All examples are synthetic. Review signals are not proof of fraud. Graph structure alone cannot determine intent, trace identical funds, or distinguish all legitimate cycles. Short windows and hop bounds can miss patterns, and result/exploration limits can truncate screening. Do not present this small benchmark as production fraud detection accuracy.

Accounts are visible only to reviewer roles in this local single-company application. This is not a multi-tenant bank-ledger service. Currency codes are validated as three letters, without an FX or currency registry. Uploads do not infer counterparties from expense IDs or vendor master accounts.
