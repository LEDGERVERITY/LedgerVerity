# LedgerVerity — Canonical Repository Handoff

**Checked:** 2026-10-10  
**Repository:** https://github.com/LEDGERVERITY/LedgerVerity  
**Default branch at start:** `8daa83c0e4ebfd83d7394e855b5af1dfc199c034`  
**Development branch:** `feat/phase02-etl-candidate-validation`  
**Verified phase-code commit:** `f4ad752fdc9b107adac1b1916e093dea1cf97f27`

## Implemented

- Existing Python 3.10+ offline normalized-JSONL heuristic scanner preserved, with the original 13 tests.
- New strict candidate adapter `src/ledgerverity/formats.py` covering the documented ETL `ContractEventOutput` field subset and explicit claimed range/network manifest.
- New `ledgerverity validate-etl` CLI preserving legacy positional audit.
- Bounded reads, duplicate JSON-key detection, malformed and overflow rejection, exact numeric IDs, no invented canonical event IDs, and explicit unverified reporting.
- 33 candidate-format and 8 CLI tests (synthetic), with sample candidate and manifest fixtures.

## Verified evidence

- Local patch tests on Python 3.13.5: 41/41 new tests passed (original repository tests verified separately in CI).
- GitHub Actions on branch commit `f4ad752fdc9b107adac1b1916e093dea1cf97f27`: [run 38005321804](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38005321804) **SUCCESS** on Python 3.10 and 3.12, 54/54 tests in each matrix job (13 original + 41 new).
- Docs/CI enhancements are staged separately from the code-test commit and require a fresh successful Actions run at their own exact SHA before final signoff.

## Unfinished and material limitations

**NOT a source-backed reconciliation MVP.** No original `LedgerCloseMeta` XDR ingestion, independent network/coverage verification, canonical source event index, verified real ETL export fixture, token-variant normalization or proven missing-event finding. No release or Wave acceptance is claimed. Synthetic samples do not prove production correctness. See `docs/DATA_FORMATS.md` and `docs/PHASE_BUILDS.md`.

## Next executable step

Review/merge the Phase 02 PR after its final CI checks. Then implement Phase 03: bounded original ledger XDR ingestion with independently verifiable provenance, complete ledger-range coverage, and malformed/unsupported-version tests. Do not claim a genuine MVP until differential reconciliation and safety gates pass. No release, application submission or deployment without owner approval. Keep root README clear of private phase numbers.
