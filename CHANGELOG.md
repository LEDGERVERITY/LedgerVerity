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
