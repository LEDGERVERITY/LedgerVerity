# LedgerVerity — Canonical Repository Handoff

**Checked:** 2026-10-10  
**Repository:** https://github.com/LEDGERVERITY/LedgerVerity  
**Default branch at start:** `8daa83c0e4ebfd83d7394e855b5af1dfc199c034`  
**Phase 02 pull request:** https://github.com/LEDGERVERITY/LedgerVerity/pull/1 — MERGED  
**Previous verified main commit:** `1a7d78962a33141c51a102e7bb8c1b9b02968bc5`
**Source importer PR:** https://github.com/LEDGERVERITY/LedgerVerity/pull/2 — MERGED  
**Verified source importer commit on main:** `2ffa6f9f5e803395dd8f52002642bb5497597965`

## Implemented

- Existing Python 3.10+ offline normalized-JSONL heuristic scanner preserved, with the original 13 tests.
- New strict candidate adapter `src/ledgerverity/formats.py` covering the documented ETL `ContractEventOutput` field subset and explicit claimed range/network manifest.
- New `ledgerverity validate-etl` CLI preserving legacy positional audit.
- Bounded reads, duplicate JSON-key detection, malformed and overflow rejection, exact numeric IDs, no invented canonical event IDs, and explicit unverified reporting.
- 33 candidate-format and 8 CLI tests (synthetic), with sample candidate and manifest fixtures.

## Verified evidence

- Local patch tests on Python 3.13.5: 41/41 new tests passed (original repository tests verified separately in CI).
- GitHub Actions on branch commit `f4ad752fdc9b107adac1b1916e093dea1cf97f27`: [run 38005321804](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38005321804) **SUCCESS** on Python 3.10 and 3.12, 54/54 tests in each matrix job (13 original + 41 new).
- Branch docs/CI acceptance: [run 38005479387](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38005479387) **SUCCESS** at `7c5d979c539fdd21be89d098f7ad364d944acfee`; all 54 tests, installed-CLI and validator smoke passed on both Python versions.
- Post-merge main evidence: [run 38005551427](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38005551427) **SUCCESS** at merge commit `33e73d388bcd1666ad02cef58d256463b15058e0`; 54/54 tests on each Python 3.10/3.12 job, pip installation, legacy CLI and `validate-etl` smoke successful.

## Original source-ledger inspection (bounded XDR importer)

- Added offline `ledgerverity inspect-source` (requires optional `stellar-sdk==16.1.0`) for saved `getLedgers` XDR, link/hash/ledger-range inspection, v3/v4 transaction event streams, and always-inconclusive evidence status. Old scanner and ETL candidate validator remain operational.
- Tests use actual serialized synthetic XDR objects as well as adversarial JSON/base64/metadata inputs; [88/88 passed on both Python 3.10 and 3.12](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38007310689) at `9a21de089a54aa3e712b8e81e7c5c58102ae97e7`. **Post-merge main CI** [run 38007519722](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38007519722) SUCCESS for `2ffa6f9f5e803395dd8f52002642bb5497597965`, 88 tests passing for each Python version.
- Genuine provider data: [Gateway Testnet live smoke](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38007310724), successful for ledger range **5113395–5113397**, adjacent hash links checked, original v2 ledger metadata/protocol 29; 61 transaction, 32 operation, 762 diagnostic events observed in three ledgers. Source capture SHA-256 `061b9810a627ecb5deb8c5e7491d33fa4d703ff91fd6a3098aa58d97868838ae`; time-limited artifact `testnet-source-evidence` expires 2026-11-09. The failed initial SDF RPC attempt received HTTP 403, then the documented Gateway provider succeeded.
- Distinguish **genuine single-provider ledger evidence** from independent consensus verification. No independently trusted checkpoint, second provider corroboration, signed network attestation or persistent production golden event corpus exists yet. The real provider may report a passphrase but this does not authenticate its historical truth.

## Event identity and limited SEP-41 semantics (Phase 04)

- Implementation branch `feat/phase04-event-identity-semantics`: adds `src/ledgerverity/canonical.py` and source-XDR event position/transaction stage/result/diagnostic wrappers. Original stream ordinals are kept distinct; identical XDR payloads never automatically deduplicated.
- Source inspection JSON schema version 2 includes `source_local_event_semantics`. Locators use the claimed network, ledger number, transaction hash/ordinal, stream, operation index and stream-local event ordinal. They are **not universal ETL event IDs**.
- SEP-41 transfer/mint/burn/clawback base shapes read exact signed i128 amounts as decimal strings, with one-value vec and symbol-map options, muxed ID forms and `PARTIAL` for additional keys/topics; unsupported shapes are `INCONCLUSIVE`.
- [125 tests per Python 3.10/3.12](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38008645840) successful at `6824eb333cdc1ab926bb930a85d6c3cf82eaa423`. Includes serialized synthetic v3/v4 transaction metadata and diagnostic success vs transaction-result failure.
- [Real Testnet source semantic regression](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38008691999) SUCCESS at `e34e0d9a9c47503e8428b4da31455bab49dfadce`; ledger range 5113618–5113620, 94 transaction-level, 100 operation and 1142 diagnostic events observed (single-provider, not consensus anchored). Source SHA-256 `6a4c8751823f7ff2aa73516a8d66cf2a2b6fc0980b89ccf614971b6107dac7ad`.
- **Phase 04 PR #3:** https://github.com/LEDGERVERITY/LedgerVerity/pull/3 — MERGED; implemented in main commit `d667abdc6f659e6e1f417568e232301fa0ebd9bd`. **Verified post-merge CI:** [run 38008883646](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38008883646), SUCCESS, 125/125 tests per Python 3.10 and Python 3.12 job. A golden corpus, independent consensus anchoring and actual ETL candidate parity remain unimplemented.

## Unfinished and material limitations

**NOT a source-backed reconciliation MVP.** Original XDR ingestion is implemented and tested, but there is no independent consensus/network authentication, universal cross-system canonical event ID, verified real ETL export fixture, permanent golden corpus, comprehensive SEP-41/SEP-57 semantics or proven missing-event finding. No release or Wave acceptance is claimed. Synthetic samples do not prove production correctness. See `docs/DATA_FORMATS.md` and `docs/PHASE_BUILDS.md`.

## Next executable step

Phase 02 is merged and CI-verified; bounded source-XDR inspection is implemented and real provider-XDR tested on the Phase 03 branch. The bounded source importer is merged and CI-verified. The bounded source-local identity and selected event-stage/SEP-41 interpretation work is implemented and tested. Phase 04 is merged and CI-verified. Phase 05 bounded synthetic-data comparison is merged and CI-verified. Next secure a real versioned ETL export and independently corroborated historical ledger corpus, test against that evidence, then proceed to honest report/CI hardening. Preserve a durable real-source corpus and independently corroborate source data before confirmed mismatch claims. Do not claim a genuine MVP until differential reconciliation and safety gates pass. No release, application submission or deployment without owner approval. Keep root README clear of private phase numbers.

## Bounded source-vs-ETL comparison handoff (Phase 05)

- New `ledgerverity reconcile --source ... --candidate ... --scope ... --format json`; reads saved original RPC `getLedgers` XDR and strict Stellar ETL `ContractEventOutput` JSONL only, never makes network calls.
- Exact matching uses reconstructed `DiagnosticEvent` wrappers (the actual upstream value of `contract_event_xdr`), ledger/transaction hash and official packed TOID IDs. A multiset preserves two events with equal payload but distinct source positions. Inline fields and transaction success are checked against embedded XDR.
- Results are `REVIEW_REQUIRED` or `INCONCLUSIVE`, exit 3. Invalid inputs exit 2. Both source authenticity and candidate export coverage remain unverified; no real ETL defects are confirmed.
- [167-test CI on Python 3.10/3.12](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38009609558) SUCCESS at `4bee00a311d9dc5bbfec3eee0189770585a2aea1`. [Installed CLI smoke](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38009768895) SUCCESS at `14620ca36d358cae0447381334cbc766b1c87362`.
- **Merged evidence:** [PR #4](https://github.com/LEDGERVERITY/LedgerVerity/pull/4) merged at `0d28d6883b7bc68198e05382a0d4ec171c47a39f`. [Post-merge main CI 38009963474](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38009963474) SUCCESS, **167 tests plus installed synthetic reconciliation exact/missing smoke passed in Python 3.10 and 3.12**.
- **Unfinished:** Independently consensus-trusted historical source data; real complete ETL fixture/version; validated candidate field adapters against actual production exports; durable real golden corpus and release-quality comparison evidence. No public release or Wave submission.
