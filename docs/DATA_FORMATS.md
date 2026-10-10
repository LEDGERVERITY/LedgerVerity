# Stellar ETL candidate format (v1)

`ledgerverity validate-etl` validates **candidate export structure only**. It does not fetch or decode source ledger metadata, prove event existence or completeness, establish canonical event indices, or find missing events.

## Try the strict validator

```bash
python -m pip install .
ledgerverity validate-etl --input fixtures/synthetic-etl-candidate.jsonl --scope fixtures/synthetic-etl-candidate.scope.json --format json
```

The example is **synthetic** and does not represent a historical Stellar ledger. Exit `0` means structurally valid candidate input. Exit `2` means invalid input or an I/O error. This is separate from the legacy `ledgerverity <normalized.jsonl>` audit (exits 0 / 1 / 2 / 3).

The JSON report contains `schema_version: 1`, `status: CANDIDATE_FORMAT_VALID`, `rows_scanned` and the **unverified** `scope_claim`. It explicitly sets `source_evidence_verified: false` and `coverage_verified: false`. Even an empty input can pass structural validation, but that cannot prove absence of events.

## JSON Lines contract

The format identifier `stellar-etl-contract-events-jsonl-v1` corresponds to fields defined by upstream `ContractEventOutput` (not a direct BigQuery REST envelope or Parquet reader). One UTF-8 JSON object per line, with:

| Field | Required | Shape |
|---|---|---|
| `transaction_hash` | Yes | 64 hexadecimal characters, case folded on read |
| `transaction_id` | Yes | Nonnegative signed 64-bit integer or canonical decimal string |
| `ledger_sequence` | Yes | Positive unsigned 32-bit integer or canonical decimal string |
| `successful` | Yes | JSON boolean |
| `in_successful_contract_call` | Yes | JSON boolean |
| `contract_id` | Yes | String, including empty when applicable |
| `type` | Yes | Nonnegative signed 32-bit integer or canonical decimal string |
| `type_string` | Yes | Nonblank string |
| `topics` | Yes | JSON array |
| `data` | Yes | Arbitrary JSON value, with floating-point JSON tokens rejected |
| `operation_id` | Yes | JSON null, nonnegative signed 64-bit integer or canonical decimal string |
| `closed_at` | Optional | String or null |
| `topics_decoded` | Optional | Array or null |
| `data_decoded` | Optional | Any JSON value |
| `contract_event_xdr` | Optional | String or null |

Unknown columns are rejected instead of silently ignored. The adapter does not invent an event index or event ID. Nested integer values and decimal strings remain exact; floating-point tokens are rejected rather than rounded. It does not yet validate `contract_event_xdr` semantics or normalize SEP-41 token amounts. An upstream schema definition is not proof that a particular indexer exports compatible files.

## Caller-provided manifest

An adjacent JSON file is required. Example `fixtures/synthetic-etl-candidate.scope.json`:

```json
{"format":"stellar-etl-contract-events-jsonl-v1","network_passphrase":"Test SDF Network ; September 2015","first_ledger":100,"last_ledger":100,"exporter":"stellar-etl","source_description":"Synthetic demonstration, not a real export"}
```

Only these six keys are supported. The range is inclusive and must be ordered, positive and within uint32 bounds; all candidate ledger sequences must fall inside it. The network passphrase, range and exporter are **claims made by the input provider**, not independently verified. The manifest cannot establish coverage, authenticity or event correctness. Comparing these claims with independently verified source-ledger XDR is future work.

## Safety, limits and output

- Maximum candidate file size: **20,000,000 bytes**; each line: **256,000 bytes**; maximum **50,000 nonblank rows**.
- Maximum manifest size: **256,000 bytes**.
- Reject malformed UTF-8 / JSON, duplicate JSON keys, floats, nonfinite constants, out-of-range integers, incorrect types, unrecognized columns and schema versions, and records outside the supplied ledger range.
- Report structurally valid files to stdout or `--output`. Invalid/operational input exits `2` with a stderr explanation; JSON reports are stable and deterministically rendered.
- The workflow is local-first and makes no network calls or wallet/signing requests.

## Field provenance and limitations

Upstream fields checked 2026-10-10: [stellar-etl `ContractEventOutput`](https://github.com/stellar/stellar-etl/blob/34f6910b818767c0c2b8f187db21855a51f43c5e/internal/transform/schema.go). This is a verified field mapping from Go source, **not** an end-to-end production export fixture. BigQuery API envelopes, Parquet, altered transforms, raw XDR and unrelated provider formats remain unsupported without separate adapters and tests. See [source evidence](SOURCE_EVIDENCE.md) and [the architecture decision](decisions/0001-candidate-adapter-first.md).

## Raw contract-event XDR is a diagnostic wrapper

The pinned [stellar-etl event transform](https://github.com/stellar/stellar-etl/blob/34f6910b818767c0c2b8f187db21855a51f43c5e/internal/transform/contract_events.go) serializes a **`DiagnosticEvent` wrapper** as base64 in the `contract_event_xdr` field. Transaction/operation stream events are wrapped with `in_successful_contract_call=true`; original diagnostic stream events retain their diagnostic flag. Transaction event stage is not included in the converted wrapper. `ledgerverity reconcile` therefore compares the wrapper, not bare `ContractEvent` XDR. It also validates raw `topics` and `data` as serialized SCVal XDR strings, not decoded JSON. See [reconciliation guide](RECONCILIATION.md).
