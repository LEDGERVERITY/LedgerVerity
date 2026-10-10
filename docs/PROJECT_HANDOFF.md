# LedgerVerity — Canonical Repository Handoff

**Checked:** 2026-10-10  
**Repository:** https://github.com/LEDGERVERITY/LedgerVerity  
**Default branch at start:** `8daa83c0e4ebfd83d7394e855b5af1dfc199c034`  
**Phase 02 pull request:** https://github.com/LEDGERVERITY/LedgerVerity/pull/1 — MERGED  
**Previous verified main commit:** `1a7d78962a33141c51a102e7bb8c1b9b02968bc5`
**Source importer development branch:** `feat/phase03-source-xdr-ingestion` (review/CI needed at final commit)

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
- Tests use actual serialized synthetic XDR objects as well as adversarial JSON/base64/metadata inputs; [88/88 passed on both Python 3.10 and 3.12](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38007310689) at `9a21de089a54aa3e712b8e81e7c5c58102ae97e7`.
- Genuine provider data: [Gateway Testnet live smoke](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38007310724), successful for ledger range **5113395–5113397**, adjacent hash links checked, original v2 ledger metadata/protocol 29; 61 transaction, 32 operation, 762 diagnostic events observed in three ledgers. Source capture SHA-256 `061b9810a627ecb5deb8c5e7491d33fa4d703ff91fd6a3098aa58d97868838ae`; time-limited artifact `testnet-source-evidence` expires 2026-11-09. The failed initial SDF RPC attempt received HTTP 403, then the documented Gateway provider succeeded.
- Distinguish **genuine single-provider ledger evidence** from independent consensus verification. No independently trusted checkpoint, second provider corroboration, signed network attestation or persistent production golden event corpus exists yet. The real provider may report a passphrase but this does not authenticate its historical truth.

## Unfinished and material limitations

**NOT a source-backed reconciliation MVP.** Original XDR ingestion is implemented and tested, but there is no independent consensus/network authentication, canonical global source event index, verified real ETL export fixture, permanent golden corpus, token-variant normalization or proven missing-event finding. No release or Wave acceptance is claimed. Synthetic samples do not prove production correctness. See `docs/DATA_FORMATS.md` and `docs/PHASE_BUILDS.md`.

## Next executable step

Phase 02 is merged and CI-verified; bounded source-XDR inspection is implemented and real provider-XDR tested on the Phase 03 branch. Next review/merge the source inspector with a green CI run, then implement Phase 04 canonical event identities/stages. Preserve a durable real-source corpus and independently corroborate source data before confirmed mismatch claims. Do not claim a genuine MVP until differential reconciliation and safety gates pass. No release, application submission or deployment without owner approval. Keep root README clear of private phase numbers.
