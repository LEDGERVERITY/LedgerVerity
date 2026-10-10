# LedgerVerity

**Experimental offline consistency checks for Stellar contract-event exports.**

Stellar's ETL project documents cases where contract events have been duplicated or incorrectly interpreted. LedgerVerity is a **small prototype**, not a full ledger reconciliation engine. It helps maintainers inspect exported event rows for a few explainable suspicious patterns without running a network service or requiring wallet keys.

## Current features

- Reads UTF-8 JSON Lines (`.jsonl`) files with normalized event rows.
- Checks for duplicated explicitly supplied canonical `event_id` values.
- Flags matching event payloads appearing with and without an `operation_id` as **possible** diagnostic duplicates.
- Flags suspect combinations of `successful: false` with `in_successful_contract_call: true` for **review**, not definitive errors.
- Detects missing required fields and malformed input.
- Inspects bounded, manually saved Stellar RPC `getLedgers` original ledger metadata XDR, verifies embedded header hashes and adjacent links, and preserves different contract/diagnostic event streams without conflating them.
- Strictly validates a versioned subset of Stellar ETL contract-event JSONL fields against a caller-declared ledger-range manifest (no independent source verification).
- Produces deterministic terminal or JSON reports with line references and explicit uncertainty.

## Try it

Python 3.10+ is required; the scanner itself has no external runtime dependencies.

```bash
PYTHONPATH=src python -m ledgerverity fixtures/synthetic-defective.jsonl
PYTHONPATH=src python -m ledgerverity fixtures/synthetic-clean.jsonl --format json
PYTHONPATH=src python -m unittest discover -s tests -v
```

For an installed command, use `python -m pip install .` in an isolated environment, then run `ledgerverity <file>`.

Exit codes: `0` no recognized issues; `1` error findings; `2` invalid input / operational error; `3` review required.

## Strict ETL candidate format validation

For exported rows conforming to Stellar ETL's documented `ContractEventOutput` JSON fields, use the separate offline command:

```bash
PYTHONPATH=src python -m ledgerverity validate-etl --input fixtures/synthetic-etl-candidate.jsonl --scope fixtures/synthetic-etl-candidate.scope.json --format json
```

These files are **synthetic**. This command checks types, bounds, declared ledger range and schema; it does **not** prove event completeness, network authenticity or ledger parity. The separate scope manifest is a caller-provided claim, not independent evidence. See [data formats](docs/DATA_FORMATS.md).

## Inspect independently transformed ledger metadata

Install the optional Stellar XDR decoder and inspect a **saved** RPC `getLedgers` response:

```bash
python -m pip install '.[source]'
ledgerverity inspect-source --input source-rpc.json --from-ledger 100 --to-ledger 102 --network-passphrase 'Test SDF Network ; September 2015' --format json
```

The example requires a genuine saved RPC response for the given ledger numbers. The command makes **no network calls**; it validates local XDR structure and internal hash links, but reports `INCONCLUSIVE` (exit 3) because a saved file cannot independently authenticate network consensus or prove historical completeness. See [source evidence format](docs/SOURCE_FORMATS.md).

## Legacy normalized audit input schema

This prototype reads JSONL objects with normalized, snake-case keys: `transaction_id` (string/integer), `ledger_sequence`, `type_string`, `contract_id`, `topics` (JSON array), `data` (JSON value), `operation_id` (nullable), `successful` (boolean), `in_successful_contract_call` (boolean), and optionally `event_id` (string). This is a **normalization contract for this tool**, not a claim that official BigQuery exports use identical JSON field names or JSON types. Export adapters for BigQuery and original ledger XDR are planned, not implemented.

A single input should represent **one network and a well-defined observation scope**. Do not mix networks or competing meanings of `event_id`.

## Limitations

- The strict candidate adapter supports the documented ETL JSONL field subset, not arbitrary BigQuery API envelopes or Parquet. It has not been verified against a genuine production export.
- Can independently **decode** supplied original ledger metadata XDR, but does **not** fetch it automatically, establish a consensus trust anchor, or verify source network identity beyond a user-declared passphrase. A separate opt-in GitHub workflow exercises genuine Testnet RPC data.
- Does **not** detect genuinely missing events; absence cannot be proven without a complete independent reference.
- Does **not** automatically repair Stellar ETL or backfill historical data.
- Event payload similarity is not proof of duplication because distinct events can legitimately have identical payloads.
- A clean result is not certification of correctness or token-standard compliance.
- Automated tests use **synthetic fixtures**; a separate, explicitly networked CI smoke has decoded real Testnet provider responses. This is not a real ETL comparison or a consensus attestation.
- File limit: 20 MB, individual line limit: 256 KB, row limit: 50,000. Process one bounded sample at a time.

## Evidence for the problem

- [Stellar ETL #452](https://github.com/stellar/stellar-etl/issues/452): diagnostic/operation event duplication and transaction flag inconsistencies.
- [Stellar ETL #467](https://github.com/stellar/stellar-etl/issues/467): event-shape deviations affecting token-transfer parsing.
- [Official transform code](https://github.com/stellar/stellar-etl/blob/master/internal/transform/contract_events.go).

These issues establish a real technical problem; **they do not prove this prototype solves every affected case**.

## Contributing and status

This is an early-stage prototype, not a production release. See [`docs/PHASE_BUILDS.md`](docs/PHASE_BUILDS.md), [`docs/PROJECT_HANDOFF.md`](docs/PROJECT_HANDOFF.md), and [`AGENTS.md`](AGENTS.md). Contributions should include tests and accurate evidence. Do not claim Wave acceptance unless it is confirmed by the Wave dashboard.

Licensed under MIT.
