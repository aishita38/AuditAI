# Shared review queue

Detection and review are separate jobs. Audit Screens keeps type-specific checks; /review-queue is the single reviewer workspace. Expense claim pages and Circular Payments now link to this queue instead of offering separate decision forms. Reconciliation findings have a Send to review button that revalidates the stored finding server-side.

## Queue and evidence

The shared list has a global case ID, case_type, severity, reason and status. Types: expense_claim, circular_payment, reconciliation, vendor_check and payroll_check. Filters support type, severity and status, with 50 records per page. Empty vendor/payroll filters are expected until their rule phases are implemented; this change does not introduce those detectors or invent findings.

Each type has an evidence viewer. Expense snapshots include claim fields, receipt extraction/text, saved score, observed features, SHAP values and available policy findings. Circular evidence shows the account path and transfers. Reconciliation shows claim/payment values, recorded approval time and exception flags. Vendor/payroll viewers are ready for their future stored findings.

Evidence is saved in review_queue_records when a case enters the shared queue and is not overwritten by refresh or later source changes. Legacy expense cases did not previously have this snapshot; their snapshot explicitly states that capture happened at queue adoption, not at the historical native case creation time. Circular cases retain the evidence snapshot their original case already preserved. Source links are shown separately as current links, not silently substituted into frozen evidence.

Related records use actual keys only. Expense cases link to their claim; associated transfers are found by BankTransfer.claim_id. Circular cases may have linked claims through those same transfer keys. Reconciliation cases link to their actual claim/payments. No vendor-name or employee-name join is inferred. Where no relationship exists, no related-record section is shown.

## Workflow and preservation

Existing expense Case/CaseAuditTrail and CycleReviewCase/CycleReviewEvent tables are retained. New review_queue_records provides one shared identity and snapshot per native case; source_key prevents duplicate adoption. Existing statuses, actors, notes and histories are not deleted or renumbered. A shared ID can differ from its original case ID.

The shared API delegates expense decisions to the existing expense workflow, including owner/contributor restrictions and checker approval authority. Circular decisions retain importer and linked-claim participant exclusions. Reconciliation decisions use the same maker-then-different-checker sequence but do not change expense approval or execute payments. Repeated maker submissions and changes to closed cases are blocked. Contributors cannot decide their own evidence. Reviewer-role accounts can add comments; comments never change case status.

Native events and new shared comments appear in one chronological audit trail. Shared-only findings use review_queue_events for creation and decisions as well. No evidence or event edit/delete endpoint is provided. Version checks guard simultaneous decisions through the shared endpoint. Old endpoints remain for compatibility; the UI directs actual reviews to the shared queue.

## Synchronization and API

- POST /api/v1/review-queue/sync adopts existing native cases and refreshes mirrored status without duplicating snapshots. In-process locking serializes sync calls and avoids concurrent SQLite backfill writers; the authentication read transaction is released before waiting.
- GET /api/v1/review-queue lists cases with case_type/status/severity/offset/limit.
- GET /api/v1/review-queue/{id} returns typed evidence, permissions, current links and merged history.
- POST /api/v1/review-queue/expense/{claim_id} resolves the existing case or creates one for a flagged claim, then returns its shared ID.
- POST /api/v1/review-queue/reconciliation/{claim_id} verifies current reconciliation exceptions, stores evidence, and deduplicates the same claim/transfer-set/exception combination.
- POST /api/v1/review-queue/{id}/maker-recommend and checker-signoff accept action and meaningful notes.
- POST /api/v1/review-queue/{id}/comments appends a comment.

All endpoints require maker, checker or admin access; decisions additionally enforce the appropriate role and conflict checks. Employees cannot browse the shared queue. Admin access alone does not confer maker/checker decision authority. The initial sync creates additive snapshot records, but does not rescore, retrain, or approve claims.

## Validation and limits

Regression coverage includes native case adoption and deduplication, simultaneous refreshes, type filtering, immutable snapshots, retained native histories, real related-record keys, missing links, reviewer sequencing, comments, reconciliation cases, and lack of expense mutation from reconciliation decisions. Existing import/transfer/auth regressions are included. A pre-existing authentication fixture was adjusted to reuse cases already created by policy import checks instead of inserting a duplicate.

Vendor/payroll detectors remain pending. Future trusted rule services should create typed shared findings rather than add feature-specific review lists. This application remains a local single-company demo. Review signals and synthetic examples are not proof of fraud. Existing expense authority policy and bank-transfer import behavior are preserved. ML inputs, training and artifacts are unchanged by the shared queue.
