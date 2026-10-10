# Original Stellar ledger XDR ↔ ETL candidate reconciliation

**Experimental / offline / read-only.** Technical contract checked 2026-10-10. Neither a match nor a difference independently certifies ledger authenticity or an ETL defect.

## Run

```bash
python -m pip install '.[source]'
ledgerverity reconcile \
  --source saved-getledgers.json \
  --candidate candidate-contract-events.jsonl \
  --scope candidate.scope.json \
  --format json
```

The `--source` file is a saved JSON-RPC 2.0 `getLedgers` response containing original ledger header and metadata XDR, bounded to 25 ledgers / 12 MB. The `--candidate` file is a JSONL export of fields shaped like `ContractEventOutput`, limited to 20 MB, 256 KB/line, and 50,000 rows. The `--scope` file declares the same network passphrase and inclusive ledger range for both files; this manifest is a *claim*, not a historical completeness receipt. See [candidate format](DATA_FORMATS.md) and [original-XDR capture](SOURCE_FORMATS.md).

**Exit codes:** `3` for `REVIEW_REQUIRED` or `INCONCLUSIVE`, `2` for invalid input or file-writing failure. No clean comparison returns success `0` or certifies correctness. A report can be saved with `--output path`. No network calls, signing or input modifications occur.

## Exact comparison identity — pinned Stellar ETL implementation

The official ETL code serializes a **DiagnosticEvent XDR wrapper** into the unfortunately named `contract_event_xdr` field, *even for originally ordinary transaction and operation events*. It converts those into wrappers with `in_successful_contract_call=true`, retains original diagnostic flags for diagnostic events, and **does not preserve the original transaction event stage** in this column.

The source side reconstructs the correct wrapper and matches the supplied candidate as a multiset, using:

- Ledger sequence and transaction hash
- Exact 64-bit Stellar ETL `transaction_id` (ledger 32 bits / transaction ordinal 20 bits / operation slot 12 bits, with transaction slot 0-based *within the operation field*)
- Optional `operation_id` with operation component 1-based; null for transaction, diagnostic and legacy contract streams
- SHA-256 of canonical serialized `DiagnosticEvent` XDR

Two distinct source positions with the same payload are separately counted; no payload similarity or XDR hash alone constitutes a unique on-chain event ID. Source locators are separately preserved with stream and array ordinals for investigation, not invented for the exported candidate. This is the matching contract implemented for the pinned upstream ETL transform, not an assertion that all third-party indexers use it.

For matched event wrappers the tool also checks `successful` against the original XDR transaction result; `in_successful_contract_call`, `contract_id`, `type`, raw base64 `topics` and raw base64 `data` against the embedded DiagnosticEvent XDR. It does **not yet** certify human-readable sidecars (`type_string`, `topics_decoded`, `data_decoded`, `closed_at`) or token accounting.

## What a report means

| Output | Interpretation |
|---|---|
| `exact_xdr_matches` | One-to-one XDR pairs, preserving multiplicity |
| `SOURCE_ONLY_OBSERVATION` | An original-XDR event is unpaired **in the supplied candidate file** |
| `CANDIDATE_ONLY_OBSERVATION` | A candidate event is unpaired **in the supplied XDR capture** |
| `COLUMN_INTEGRITY_DIFFERENCE` | Candidate's own fields/packed IDs conflict with the embedded XDR or declared ledger placement |
| `TRANSACTION_OUTCOME_DIFFERENCE` | Candidate `successful` conflicts with XDR transaction result |
| `UNMATCHABLE_CANDIDATE` | No `contract_event_xdr` provided; exact comparison unavailable |

`REVIEW_REQUIRED` means differences observed in a structurally complete *captured* range; **not** proven ETL corruption. `INCONCLUSIVE` is used for missing source ledgers, unsupported metadata, unmatchable/invalid candidate identities, and for no observed difference (because the supplied source and export were not independently authenticated).

JSON reports include precise counts, sample findings limited to 100 with `findings_truncated`, claimed network/range, source capture digest, and explicitly false `source_provenance_verified`, `network_identity_independently_verified`, `candidate_export_coverage_verified` and `reconciliation_proven`.

## Boundaries and outstanding release gate

- The packed ID adapter only accepts ledger sequences through 2,147,483,647, transaction ordinals 1–1,048,575, and operation ordinals 0–4,094. It fails closed instead of creating unsafe IDs.
- The saved RPC file may be incomplete or forged; an ETL export file may be filtered, truncated, or from another transform revision. Neither check establishes network identity or proof of absent data.
- Tests for this module use **SDK-serialized synthetic original metadata and generated ETL-shaped JSONL**, including missing/extra rows, incorrect flags, absent XDR, malformed XDR, wrong scope, failed transactions and duplicate-looking valid events. This does **not** constitute a verified real production ETL comparison.
- [Real Testnet smoke](SOURCE_FORMATS.md) validates ingestion from one provider, not comparison with a independently captured actual ETL export.

**For genuine anomaly claims:** acquire and preserve actual ETL export files with version/query, network and range proof; independently corroborate original ledger history and complete coverage; create a durable real-XDR/export golden fixture; test the same transaction and event mapping across relevant protocol and ETL revisions. Until then the bounded comparator is implemented, but real-data release readiness remains blocked.

### Evidence and source mapping checked October 10, 2026

- [ETL contract-event transformer](https://github.com/stellar/stellar-etl/blob/34f6910b818767c0c2b8f187db21855a51f43c5e/internal/transform/contract_events.go) — wrapper conversion and XDR serializer
- [ETL packed TOID](https://github.com/stellar/stellar-etl/blob/34f6910b818767c0c2b8f187db21855a51f43c5e/internal/toid/main.go)
- [ETL output schema](https://github.com/stellar/stellar-etl/blob/34f6910b818767c0c2b8f187db21855a51f43c5e/internal/transform/schema.go)
