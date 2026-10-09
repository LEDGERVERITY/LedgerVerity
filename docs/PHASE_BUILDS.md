# LedgerVerity — Internal Engineering Roadmap and Evidence Ledger

**Checked:** 2026-10-10. This file is internal engineering tracking, not a Stellar Wave policy or an assertion of application approval. No phase number belongs in the public root README.

Status vocabulary: `NOT STARTED`, `IN PROGRESS`, `IMPLEMENTED — UNVERIFIED`, `VERIFIED`, `BLOCKED`. Tests proposed in roadmap sections have **not** run unless actual evidence is linked.

| Phase | Distinct objective | Status | Acceptance evidence / next gate |
|---|---|---|---|
| 01 | Recheck starter, define narrow genuine reconciliation MVP | VERIFIED (baseline only) | 13 existing unittest checks and GitHub CI; no completeness proof |
| 02 | Strict official-field ETL candidate JSONL adapter and manifest | VERIFIED for documented structural subset | 54 tests passing on Python 3.10 + 3.12; CI linked below; still no real export fixture |
| 03 | Independent network-scoped original ledger XDR evidence | NOT STARTED | Decode bounded genuine `LedgerCloseMeta` and prove provenance/coverage |
| 04 | Canonical identities, event stage/success and supported token shapes | NOT STARTED | Positive/negative tests for transaction, operation, event index, versions |
| 05 | Differential reconciliation against independently sourced evidence | NOT STARTED | Proven missing/extra/duplicate/misinterpreted outcomes with inconclusive cases |
| 06 | Deterministic terminal/JSON reconciliation reports and CI examples | NOT STARTED | Stable schema, exits, limits and evidence identifiers |
| 07 | Comprehensive regression and platform hardening | NOT STARTED | Malformed XDR, large amounts, failed tx, mixed network, limits, platform smoke tests |
| 08 | Public docs, contributor/security readiness and provenance | NOT STARTED | Clean install, independent docs review, real supported example |
| 09 | Working MVP release gate | NOT STARTED | Complete core gates, CI at release SHA and owner authorization |
| 10 | Brand identity and truthful documentation landing page | NOT STARTED | Usable accessible site and assets, no invented adoption |
| 11 | Wave / Drips evidence and application checks | NOT STARTED | Current official program terms and truthful evidence; owner approval |
| 12 | Maintenance, feedback and adopters | NOT STARTED | Real issues, support owner, schema compatibility commitments |

## Phase 02 acceptance record

- **Objective / distinct problem:** Remove ambiguity between the starter's normalized JSONL audit format and real ETL field names without pretending candidate rows are source evidence.
- **Scope:** `ContractEventOutput` JSON fields in pinned [stellar-etl upstream source](https://github.com/stellar/stellar-etl/blob/34f6910b818767c0c2b8f187db21855a51f43c5e/internal/transform/schema.go), bounded JSONL, six-field scope manifest, `validate-etl` CLI and JSON/text outputs. Excludes raw ledger decoding, BigQuery REST envelopes, Parquet, event IDs and reconciliation.
- **Files:** `src/ledgerverity/formats.py`, `src/ledgerverity/cli.py`, `tests/test_formats.py`, `tests/test_cli_validation.py`, two synthetic ETL fixtures, `docs/DATA_FORMATS.md`, `docs/ARCHITECTURE.md`, `docs/decisions/0001-candidate-adapter-first.md`; README, CI and handoff updates.
- **Dependencies:** Existing Python ≥3.10 project; no new runtime third-party dependencies. Candidate schema traced to upstream `ContractEventOutput`.
- **Positive tests:** valid ETL row, large exact integer string, nullable operation ID, ledger bounds, deterministic reports, installed-command smoke.
- **Negative and malformed tests:** wrong types, malformed JSON and UTF-8, repeated JSON keys, JSON float/nonfinite, missing/unknown keys, bad hash, unsupported version, oversized line, scope violations and number overflows.
- **Boundary tests:** maximum ledger sequence / transaction ID, empty file, similar consecutive rows not deduplicated, large JSON integer token rejected safely, zero ledger rejected.
- **Regression risks:** legacy positional audit CLI must remain unchanged; a `CANDIDATE_FORMAT_VALID` report must never suggest ledger parity, authenticity or completeness.
- **CI gate / evidence:** [54 tests successful under Python 3.10 and 3.12 on the phase branch](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38005321804) for commit `f4ad752fdc9b107adac1b1916e093dea1cf97f27`. Installed-CLI smoke succeeded on both versions at [branch run 38005479387](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38005479387) (`7c5d979c539fdd21be89d098f7ad364d944acfee`) and [post-merge main run 38005551427](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38005551427) (`33e73d388bcd1666ad02cef58d256463b15058e0`).
- **Status:** `VERIFIED` only for structurally validating the documented subset; real export files and independent source evidence remain absent.
- **Blocker and owner:** Maintainer to supply/export genuine source-backed ledger evidence in Phase 03; no ledger-XDR decoder exists yet.
- **Next action:** Phase 03 — independently decode bounded original ledger metadata and establish verified coverage before discrepancy claims.

## Evidence boundary

54 current branch tests consist of 13 legacy tests plus 33 format tests and 8 CLI tests. All candidate examples are **synthetic**. No successful GitHub action or clean candidate export is proof of an actual Stellar discrepancy. Never publish a release or submit a Wave application without explicit owner authorization.
