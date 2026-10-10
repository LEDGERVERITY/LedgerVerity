# Changelog

## Unreleased experimental prototype (2026-10-09)

- Local-only Python package and command-line interface.
- Bounded JSON Lines parsing, deterministic JSON reports and explicit exit codes.
- Consistency checks for repeated event identifiers, possible diagnostic duplicate patterns, and transaction success flag inconsistencies.
- Synthetic fixtures and 13 local automated tests.

No public release or production validation is claimed.

## Unreleased candidate export validation (2026-10-10)

- Added read-only `validate-etl` command and strict `ContractEventOutput`-field JSONL candidate adapter.
- Added network/range manifest, explicit unverified source/coverage reporting, malformed-input and boundary tests, and installed-CLI CI smoke checks.
- Kept the original heuristic audit command backward compatible. **Still not a source-backed reconciliation MVP or public release.**

## Unreleased original ledger XDR inspection (2026-10-10)

- Added read-only `inspect-source` for bounded saved Stellar RPC `getLedgers` responses; optional pinned Stellar Python SDK XDR decoder; headers/meta hash checks; adjacent chain-link checks; v3/v4 event streams; always-inconclusive trust state.
- Added synthetic XDR round-trip/adversarial coverage and separately opt-in genuine Testnet RPC evidence workflow, with a 30-day provenance artifact.
- Verified 88 tests on Python 3.10/3.12 and real three-ledger Gateway Testnet ingestion. **Not a completed source-to-candidate reconciliation MVP, security audit, or public release.**
