# Technical verification

The four notebooks and four script entry points share the same implementation. Verification covers the raw schemas and hashes, source-specific calendar offsets, missing-data decisions, label maturity, fixed experiments, answer-free prediction, independently recomputed metrics and SQLite-to-CSV agreement.

Current execution receipts, regression results, independent script-route comparisons and PDF checks are recorded under `outputs/results`. The separate `PM25_270702_690631023_Archive_Verification.json` binds a fresh local replay to the delivered ZIP SHA256. `RUBRIC_EVIDENCE.md` maps the lab requirements and C1-C6 to their evidence.

The report distinguishes development of the method from changes in accuracy. The retained initial benchmark has different targets, periods and source products; it is not a controlled algorithm-only comparison. No initial receipt is used to certify current execution.

Temporal-cutoff checks support the declared retrospective design. Exact historical public release remains unverified, operational use remains blocked, and the selected model's warning failures remain visible. Student review, disclosure/signature, actual GitHub access and video submission require the student's own completion.
