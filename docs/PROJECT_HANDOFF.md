# LedgerVerity Handoff

Checked 2026-10-09 against the connected GitHub repository and local starter.

- **Purpose:** Read-only checks for selected Stellar ETL contract-event anomalies; the proposed full MVP will reconcile exports against independently verified ledger evidence.
- **Canonical repository:** https://github.com/LEDGERVERITY/LedgerVerity
- **Implementation:** Python 3.10+ package `src/ledgerverity`, CLI `python -m ledgerverity`; 20 tracked source/docs/config files in the initial upload.
- **Project phases:** `docs/PHASE_BUILDS.md`.
- **Current status:** Initial offline JSONL consistency-checking codebase pushed; NOT the full source-backed reconciliation MVP; NOT a published release.
- **Initial tested source commit:** `3a4c0ae7ac14ea88895be3c6ea66e8ca6d14cac8`.
- **Local tests:** 13/13 passed on 2026-10-09 using `PYTHONPATH=src python -m unittest discover -s tests -v`.
- **GitHub CI:** https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38003430977 — SUCCESS for source commit `3a4c0ae7ac14ea88895be3c6ea66e8ca6d14cac8`; Python 3.10 and 3.12 unit tests and CLI fixture checks succeeded. A later documentation-only commit must be checked separately.
- **Verified limitations:** No independent original-ledger XDR decoder or verifier, no live BigQuery adapter, no proof that any transfers are missing, and only synthetic test fixtures.
- **Next milestone:** Implement a source-backed reference/ETL adapter and reproducible reconciliation, with malformed inputs, double-emission cases, accurate event identity, incomplete coverage semantics, and regression tests.
- **Safety:** Do not claim full MVP readiness, Wave approval, or a published release without fresh evidence. Do not place internal phase numbers in the public root README.

When resuming development, check current main SHA, current GitHub Actions results, repository code, and this handoff before making implementation claims.
