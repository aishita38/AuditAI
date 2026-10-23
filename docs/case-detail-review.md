# Unified case detail

The queue opens `/review/cases/:caseId`. Both the case number and the row support navigation, including keyboard activation. Queue filters and pagination live in the URL; the case back link restores them. Old `/review-queue?case=...` links redirect to the case route.

The case page shows metadata, saved evidence, existing maker/checker actions, comments, and the combined audit trail. Server-side maker/checker and contributor restrictions remain authoritative.

Evidence is always read from the saved case snapshot. Transfers, claims, vendor records and payroll/roster records appear as individual records, with lists over ten rows expanded through Show all. The current-record lookup only controls links and missing-record labels; it never replaces saved values. `/records/:kind/:recordId` displays live transfer/vendor/roster/payroll data, while claims use the existing claim page. Record lookup APIs require a reviewer role.

New expense case snapshots also capture linked payments and supporting claims referenced by policy findings. Existing snapshots are intentionally not rewritten: if an older snapshot did not capture payments or supporting-record fields, the page says so rather than presenting current data as historical evidence. Related records are collapsed separately and use explicit record keys. Rules without saved trigger-field metadata retain their saved reason and explanation; explicit trigger fields, shared master-data fields, cycle account/amount/time fields and reconciliation flag fields are highlighted.

Validation: `npm test --prefix frontend`, `npm run build --prefix frontend`, and `python -m pytest tests/test_shared_review_queue.py tests/test_analytics_loading.py tests/test_auth_review_flow.py tests/test_transfer_workflow.py -q`.
