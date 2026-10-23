# Aster company demo dataset

Entirely fictional Indian components manufacturer. No real company or personal data.

Start with company_profile.json, then transactions.csv. Link employee_id and vendor_id to their master files. anomaly_labels.csv is the answer key, and scenario_groups.csv identifies records that must be inspected together. coverage_validation.csv lists all 45 requested categories independently, including overlapping taxonomies. The user-specified counts are preserved: enterprise 25 x 80, ERP 15 x 200, expense 5 x 30.

Upload expense_claims_upload.csv through the existing claims upload as a reviewer/admin. It contains 2,000 claims (1,850 controls and 150 injected scenarios). Uploading records makes the uploader a contributor, so use other accounts for review; master employee IDs are fictional and do not provision accounts. No live data has been imported or models retrained by the generator.

Full ERP coverage requires new ingestion fields, master joins, rules and review routing; the current expense model will not automatically detect all 45 categories. Raw transactions intentionally include missing data and negative credit notes and are not a drop-in claims upload. Imported receipt totals are simulated, not extracted from actual images. Duplicate receipt_reference represents reuse of the same synthetic receipt; receipt images and OCR performance are not tested.

Keep anomaly_labels, scenario group IDs, source taxonomy, and descriptive master names OUT of model features. is_fraud in the upload is a legacy field for the planted scenario label, not a legal finding. In controls, absence of a planted scenario does not guarantee every policy check passes. Do not report synthetic accuracy as real-world fraud detection performance.

Suggested use: fit historical baselines using transactions before 2025-04-01; calibrate on a separate later control sample; evaluate injected scenarios separately. Split linked groups together and prevent employee/vendor identity leakage. Labels and dates deliberately create a controlled benchmark, not a production distribution.

Benford is a cohort screen, not an individual fraud label. Unknown/emerging risk is a deliberately unusual multivariate fixture; no model result has been fabricated. Offshore transactions, new vendors, round values and weekend activity are review triggers, not proof of wrongdoing. No fixed risk probabilities have been invented. Tax identifiers and banks use TEST fixtures except intentionally malformed identifiers; verified_fixture means trusted synthetic master data, not government verification. Circular_payment models employee/vendor-linked collusion (as described in the request), not a bank-to-bank circular cash-flow graph.

Company-specific policies: manager cap INR 50,000; CFO cap INR 50 million; senior-manager example policy INR 250,000; new vendor window 7 days; new-vendor payment trigger INR 2 million; cash review over INR 10,000; weekdays 09:00-18:00. Change the generator and profile together to adapt to your own company. All values are demo assumptions.

Data dictionary covers the raw transaction columns. Master columns describe employee organization and vendor identity; labels contain answer keys, severity and expected review teams; groups list pipe-separated transaction IDs. No model scores or actual approval decisions are included.
