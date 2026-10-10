# LedgerVerity — Internal Engineering Roadmap and Evidence Ledger

**Checked:** 2026-10-10. This file is internal engineering tracking, not a Stellar Wave policy or an assertion of application approval. No phase number belongs in the public root README.

Status vocabulary: `NOT STARTED`, `IN PROGRESS`, `IMPLEMENTED — UNVERIFIED`, `VERIFIED`, `BLOCKED`. Tests proposed in roadmap sections have **not** run unless actual evidence is linked.

| Phase | Distinct objective | Status | Acceptance evidence / next gate |
|---|---|---|---|
| 01 | Recheck starter, define narrow genuine reconciliation MVP | VERIFIED (baseline only) | 13 existing unittest checks and GitHub CI; no completeness proof |
| 02 | Strict official-field ETL candidate JSONL adapter and manifest | VERIFIED for documented structural subset | 54 tests passing on Python 3.10 + 3.12; CI linked below; still no real export fixture |
| 03 | Inspect bounded original ledger-XDR source evidence, including hash-linked sequences | VERIFIED (bounded importer only) | Real Testnet 3-ledger smoke + 88 offline tests; provider consensus anchoring and permanent golden fixture still unverified |
| 04 | Source-local event identity, XDR stage/outcomes, limited SEP-41 amount semantics | VERIFIED (bounded source-local subset only) | Synthetic v3/v4 XDR tests and live provider-v4 regression; no global indexer ID or parity claim |
| 05 | Bounded source-XDR versus ETL export candidate comparison | VERIFIED (synthetic implementation only); REAL-DATA GATE OPEN | Exact multiset comparisons and CI tested; real ETL export and independent trusted ledger coverage not yet verified |
| 06 | Deterministic safe JSON/text/Markdown reports and CI integration | VERIFIED (synthetic reporting/CI only) | 201 distinct tests on Python 3.10/3.12, installed CI gate and short-retention synthetic artifact; real-data gate still open |
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

## Phase 03 acceptance and evidence record (2026-10-10)

- **Objective / distinct problem:** Inspect original ledger metadata rather than a candidate transformation to ground later reconciliation in a separate source path.
- **Scope delivered:** Offline, read-only inspection of a single bounded JSON-RPC `getLedgers` capture with base64 `headerXdr` and `metadataXdr`, Stellar SDK 16.1.0 optional `[source]` decoder, v0/v1/v2 ledger metadata, v3/v4 event-stream preservation, user-declared network, SHA-256 XDR ledger-header consistency, adjacent hash links, unsupported transaction-meta tracking, explicit gaps and inconclusive status.
- **Files:** `src/ledgerverity/source.py`, `src/ledgerverity/source_cli.py`, modified `src/ledgerverity/cli.py`, `pyproject.toml`, `tests/test_source.py`, `tests/test_source_xdr.py`, `docs/SOURCE_FORMATS.md`, `scripts/live_testnet_source.py`, `.github/workflows/live-testnet-source.yml`, CI and related docs.
- **Positive tests:** v1/v2 serialized synthetic XDR roundtrips, actual RPC-sourced v2 meta on protocol 29, 3 adjacent Testnet ledgers, intact v4 transaction/operation/diagnostic streams, deterministic reports and legacy CLI regression.
- **Malformed / negative tests:** invalid UTF-8, duplicate JSON keys, float JSON, invalid base64, trailing XDR bytes, altered embedded headers, wrong sequence, hash tampering, broken adjacent links, reversed/mixed/out-of-range/duplicate sequences, unsupported metadata markers, operational output errors.
- **Boundaries:** at most 25 requested ledgers, 12 MB capture, 2 MB per XDR object; missing ledgers, empty snapshots and unsupported metadata never count as proof of correct parity.
- **Regression risks:** `validate-etl` and positional `audit` must stay backward compatible; separate diagnostic and contract streams must never silently deduplicate.
- **CI gate:** [88/88 tests per Python 3.10 and 3.12 job](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38007310689) at commit `9a21de089a54aa3e712b8e81e7c5c58102ae97e7`, with optional SDK installed; [final Phase 03 branch run 38007458112](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38007458112) SUCCESS at `3f585ac846f6c9737fdf37eb72babd1d8bb05b25`, and [post-merge main run 38007519722](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38007519722) SUCCESS at `2ffa6f9f5e803395dd8f52002642bb5497597965` (88 tests per Python 3.10/3.12).
- **Real Testnet evidence:** [Live Testnet run 38007310724](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38007310724), `SUCCESS`, at `9a21de089a54aa3e712b8e81e7c5c58102ae97e7`; ledgers 5113395–5113397, three checked hash links/headers, protocol 29, metadata v2, 61 transaction events, 32 operation events, 762 diagnostic events; 30-day `testnet-source-evidence` artifact includes captured JSON and provenance SHA-256 `061b9810a627ecb5deb8c5e7491d33fa4d703ff91fd6a3098aa58d97868838ae`.
- **Explicit confidence limits:** This evidence is genuine **single-provider Testnet RPC data**, not a consensus-anchored historical proof, not a verified network identity independent of the provider, and not an ETL discrepancy. The retained artifact is time-limited, not a committed permanent golden corpus. `source_provenance_verified=false`, `ledger_chain_anchored=false` and `event_completeness_verified=false` remain truthful. No source/candidate comparison or canonical merged event identity is implemented.
- **Status:** `VERIFIED` for the **bounded provider-XDR inspection and internal ledger-link checks** only; source authentication and completeness are open dependencies for confirmed findings.
- **Blocker / owner:** Maintainer to obtain separately corroborated archival evidence and preserve durable, versioned event-rich reference fixtures; engineering to normalize stage and event identity next.
- **Next action:** Phase 04 — define canonical event-stream, operation and transaction identities for supported metadata versions, with actual XDR regression fixtures and explicit `INCONCLUSIVE` on unsupported forms.

## Phase 04 evidence record (2026-10-10)

- **Objective/problem:** Prevent equal event payloads across distinct transaction/operation/event streams from being mistaken for duplicated real movements; preserve exact transaction-result and event-stage semantics.
- **Implemented scope:** `src/ledgerverity/canonical.py`, updated `source.py` and `inspect-source` JSON schema v2; stable claimed-network-hashed source-position locators; explicit 0/1-based ordinal naming; v3/v4 metadata event streams; XDR result-code transaction success; diagnostic-wrapper in-successful-call flag; transaction event stage; limited exact i128 SEP-41 transfer/mint/burn/clawback shapes, map/vec and muxed data; unsupported forms `INCONCLUSIVE`.
- **Out of scope:** universal Stellar event IDs, raw candidate-export index inference, consensus/authenticated network provenance, approved token list, SEP-57 normalization, all CAP-67/SEP-41 variants, cross-system parity, on-chain balance proofs, public release.
- **Positive and edge cases:** valid XDR v3/v4 metadata, two legitimate identical-payload events with different source positions, distinct diagnostic echoes, multiple operations, transaction stage, failed result vs diagnostic success flag, zero/max positive i128, map/vec/single-value, u64 and historical legacy muxed encodings, extension topics/keys.
- **Malformed/failure cases:** malformed/truncated base64/XDR, wrong/missing stage, invalid stream/operation position, repeated source positions, wrong Boolean types, wrong token topic shapes, missing/duplicated map amount, unsupported and negative amount, malformed muxed bytes.
- **Regression:** original input-only audit, ETL validator, bounded source inspection, existing CLI and CI must remain passing. A successful source observation is not an authenticated ledger or source-to-export mismatch.
- **Tests actually executed:** [CI 38008645840](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38008645840), `SUCCESS` at `6824eb333cdc1ab926bb930a85d6c3cf82eaa423`: 125 unittest checks on each of Python 3.10 and 3.12. Final docs commit and merged-main checks need fresh evidence.
- **Live original XDR regression:** [Testnet run 38008691999](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38008691999), `SUCCESS` at `e34e0d9a9c47503e8428b4da31455bab49dfadce`. Gateway Testnet RPC metadata v2 / protocol 29 for ledgers 5113618–5113620, internal linked headers checked, 94 transaction-level + 100 operation + 1142 diagnostic events; snapshot sha256 `6a4c8751823f7ff2aa73516a8d66cf2a2b6fc0980b89ccf614971b6107dac7ad`. **Genuine provider observation, not independent consensus proof.**
- **Blocked/owner:** maintainer to preserve an enduring, independently corroborated event-rich golden corpus and confirm an actual ETL export schema; engineering to design cautious candidate-to-source matching next.
- **Merged evidence:** [PR #3](https://github.com/LEDGERVERITY/LedgerVerity/pull/3), [post-merge main CI 38008883646](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38008883646) SUCCESS for `d667abdc6f659e6e1f417568e232301fa0ebd9bd`, 125 unit/integration checks passing in both Python 3.10 and 3.12.
- **Next action:** Phase 05 differential reconciliation with explicit `INCONCLUSIVE` for unverifiable candidate row identity, partial coverage or unsupported versions. No release or Wave submission without owner authorization.

## Phase 05 — Implementation and open evidence gate (2026-10-10)

- **Objective:** Enable usable source-vs-candidate event comparison, preserving real multiplicity and avoiding false ETL defect conclusions.
- **Core technical discovery (upstream verified):** Stellar ETL's `contract_event_xdr` encodes `DiagnosticEvent` XDR, including synthetic wrappers around transaction/operation events. `transaction_id` and `operation_id` follow its documented packed 32/20/12-bit TOID with the operation slot 1-based.
- **Delivered:** `src/ledgerverity/reconcile.py`, `reconcile_cli.py`, CLI routing, matching full wrapper XDR + ledger/tx/TOID, positive and negative multiset findings, inline field and transaction outcome checks, bounded stable text/JSON reports; always `reconciliation_proven=false`.
- **Tests:** [CI run 38009609558](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38009609558), SUCCESS at `4bee00a311d9dc5bbfec3eee0189770585a2aea1`, **167/167 tests** per Python 3.10 and 3.12 job. Positive/negative/malformed/edge synthetic scenarios include duplicate-looking valid operations, missing/extra records, changed DiagnosticEvent XDR, missing XDR, malformed JSON, invalid packed IDs, incomplete source, transaction failures, wrong inline types/topics/data. Installed-command CLI smoke [run 38009768895](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38009768895) SUCCESS for `14620ca36d358cae0447381334cbc766b1c87362`; final docs/post-merge CI require verification at their own SHAs.
- **CLI interpretation:** code 3 = inconclusive/review, code 2 = invalid; no source/export match is certified and no confirmed indexer bug is emitted.
- **Critical missing evidence:** Genuine ETL output with exporter revision, query and row-count/ledger-range proof; independently corroborated historical `LedgerCloseMeta` source and complete coverage; a durable source/export golden fixture. Current comparison tests use **generated synthetic ETL-shaped rows**. No real missing/extra/duplicated indexed event is verified.
- **Owner & next acceptance gate:** Maintainer obtains export provenance and independent ledger data; engineering tests this exact matcher with pinned *real* paired fixtures, including malformed and ambiguity cases. Build more user-friendly reports only after strengthening evidence semantics, or clearly mark them experimental. Not ready for v0.1.0, production use claims or Drips submission.

- **Merge and post-merge CI evidence:** [PR #4](https://github.com/LEDGERVERITY/LedgerVerity/pull/4) merged to main as `0d28d6883b7bc68198e05382a0d4ec171c47a39f`. [Main run 38009963474](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38009963474) SUCCESS — 167 tests and installed CLI synthetic exact/source-only smoke checks passing on both Python 3.10 and 3.12.
- **Status boundary:** Phase 05 is verified for its bounded synthetic-data implementation, **not** for proven parity against real ETL exports or trustworthy historical source data. Preserve this blocker through all remaining phases.

## Phase 06 acceptance record — October 10, 2026

- **Objective:** Make observed source/export differences reproducible and actionable for developers without confusing review findings with confirmed ETL defects.
- **Implementation:** `src/ledgerverity/reporting.py`, `ci_gate.py` and updated `reconcile_cli.py`; additive `report_contract=ledgerverity.reconciliation-report.v1`, evidence fingerprint SHA-256 for source/candidate/manifest files, fixed per-code investigation guidance, safe Markdown summaries, atomic report writes and explicit input-overwrite guards, including aliases.
- **CI integration:** `tests/generate_synthetic_demo.py` creates labeled generated source and ETL-shaped candidate fixtures; installed CLI writes JSON and Markdown, parses both exact and missing-source simulated outcomes, enforces valid exit code 3; `ledgerverity-ci-gate` verifies the report's lack of forged authenticity/completeness evidence and tests an optional review-failing policy. GitHub step summary and two version-specific 7-day report artifacts are synthetic.
- **Tests executed:** [GitHub Actions run 38010684124](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38010684124), SUCCESS on development commit `0045dedd0b2cec7421a8cdcdd15baf1193658d6b`: **201 distinct unittest tests** pass on both Python 3.10 and Python 3.12, installed synthetic comparison and observational CI gate pass. Final docs branch and main CI need their own verification.
- **Positive/edge cases:** deterministic output on unchanged bytes, Markdown and JSON consistency, exact synthetic pairing, synthetic missing-candidate review, verified three-file fingerprints, opt-in CI review failure, 100-finding cap preserved.
- **Malformed/safety cases:** malformed/nonfinite/oversized JSON report, fake source/network/coverage/reconciliation claims, bad fingerprint/status/counters, wrong output paths, direct and symlink aliases to original evidence, missing output directory, untrusted manifest Markdown injection, failure without truncating an existing report.
- **Trust boundary:** SHA-256 digests describe files, not independently authenticated origin. A clean supplied-file report remains `INCONCLUSIVE`, not proven parity. Real complete ETL export and independently anchored ledger evidence remain absent. No production setup or Drips/Wave application.
- **Owner/next gate:** Engineering verify final PR/main CI and continue Phase 07 malformed/regression/platform hardening; maintainer obtain actual ETL export and independent archival verification before release.

### Verified Phase 06 merge/CI

- **Phase 06 PR #5:** https://github.com/LEDGERVERITY/LedgerVerity/pull/5 — MERGED to main as `9c50253635cb388656211160ac89498da7fcf9bc`.
- **Verified post-merge CI:** [run 38010877352](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38010877352), **SUCCESS** at that exact commit. **201 distinct tests** passed per Python 3.10/3.12 job; installed synthetic report generation, CI policy evaluation, GitHub Actions summary and 7-day synthetic artifact uploads all passed.
- **Trust boundary maintained:** no verified source consensus attestation, no proven ETL export completeness, no genuine paired export fixture, and no real-world confirmed ETL discrepancies. Phase 07 engineering hardening can begin; release gate remains blocked on real data.
