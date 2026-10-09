# LedgerVerity Handoff

As of 2026-10-09 (initial GitHub source upload in progress; CI not yet verified).

- **Purpose:** Read-only checks for certain Stellar ETL contract-event anomalies; expand into source-backed differential reconciliation only with independent evidence.
- **Canonical repo URL:** https://github.com/LEDGERVERITY/LedgerVerity
- **Implemented source:** Python 3.10+ package `src/ledgerverity`, CLI `python -m ledgerverity`.
- **Phase builds:** `docs/PHASE_BUILDS.md`.
- **State:** Early experimental codebase; full source-backed reconciliation MVP NOT YET implemented; NOT a public release.
- **Test status:** 13/13 local unit tests passed on 2026-10-09 with `PYTHONPATH=src python -m unittest discover -s tests -v`; GitHub CI must be checked separately.
- **Verified commit:** Pending initial upload; verify the latest main SHA in GitHub before further development.
- **GitHub Actions:** Not yet verified at this handoff revision; workflow configuration committed with initial source upload.
- **Known limitations:** No original XDR decoder, no actual BigQuery adapter, no completeness proof, synthetically constructed sample data.
- **Next action:** Verify main commit and CI after push; then implement source-backed fixtures and reconciliation against independently validated ledger metadata, with regression tests.
