# Event identity and conservative contract-token semantics

Checked 2026-10-10. **This is not an ETL reconciliation result or proof of historical consensus.**

## Source-local locator (schema version 2)

The offline \`ledgerverity inspect-source\` JSON report now includes \`source_local_event_semantics\`. For each decoded original XDR contract event, the locator contains:

- \`network_claim_sha256\` — SHA-256 of the *caller-declared* network passphrase; it is not a network attestation.
- \`ledger_sequence\` — 1-based ledger number.
- \`transaction_hash\` and \`transaction_ordinal_1based\` — both preserved from XDR; do not infer the inner fee-bump transaction hash.
- \`stream\` — one of \`contract\` (legacy Soroban v3), \`transaction\`, \`operation\`, \`diagnostic\`. Never coalesce streams.
- \`operation_ordinal_0based\` — only for metadata v4 operation streams; \`null\` otherwise.
- \`event_ordinal_in_stream_0based\` — actual array position in that specific stream. This is **not** an official globally unique event ID.

A stable \`source_locator_sha256\` hashes the deterministic JSON representation of that complete locator, while \`contract_event_sha256\` hashes the raw serialized \`ContractEvent\` XDR. Two legitimate events can have equal XDR and different positions, and diagnostic echoes can reproduce other event bytes. Neither equality nor difference of these hashes independently proves an ETL defect. Duplicate exact *source-local positions* cause an input error; repeated payloads alone do not.

## Transaction result and event stage

The original XDR transaction result code determines \`transaction_success\`: successful for \`txSUCCESS\` or \`txFEE_BUMP_INNER_SUCCESS\`, false for other valid result codes; \`null\` is reserved for genuinely unknown caller-constructed data. For metadata v4 transaction-level events, \`transaction_event_stage\` preserves the official \`BEFORE_ALL_TXS\`, \`AFTER_TX\`, or \`AFTER_ALL_TXS\` XDR enum name. Operation and diagnostic events have no invented transaction stage.

For diagnostic events, \`diagnostic_in_successful_contract_call\` is taken from the XDR diagnostic wrapper itself, **separately** from transaction success. In particular, a failed transaction and a diagnostic flag indicating a previously successful contract-call context are not automatically a defect. Neither \`transaction_success\` nor this diagnostic flag means a token transfer was applied.

Metadata v3 legacy Soroban events and metadata v4 transaction/operation/diagnostic arrays are preserved in their original separate streams. Unknown transaction metadata versions prevent the entire capture from being labeled decoded/complete.

## Narrow SEP-41 token event interpretation

A typed token-movement view is computed **only** for \`CONTRACT\` events with a non-null contract ID and an event's first topic equal to a known symbol. Supported *base shapes*:

| Topic | Required base topics | Accepted data |
|---|---|---|
| \`transfer\` | symbol, from Address, to Address | i128, one-element i128 vec, or map |
| \`mint\` | symbol, to Address | i128, one-element i128 vec, or map |
| \`burn\` | symbol, from Address | i128, one-element i128 vec, or map |
| \`clawback\` | symbol, from Address | i128, one-element i128 vec, or map |

An accepted map must contain \`amount\` with an XDR i128 value. A \`transfer\` or \`mint\` map may contain \`to_muxed_id\` as void, u64, string, or exactly 32 bytes. Additional topic entries or extra map keys are **retained as evidence** (count/key names) and classified \`PARTIAL\`, not silently dropped. Unsupported, duplicate, malformed or ambiguous shapes are \`INCONCLUSIVE\`. Non-movement topics are \`NOT_APPLICABLE\`, not errors. Accepted minimum base shapes are \`SUPPORTED_SUBSET\`.

- Amounts use exact signed 128-bit XDR hi/lo arithmetic and are **serialized as decimal strings**, never IEEE-754 floating point. Negative movement amounts are left \`INCONCLUSIVE\`, not pronounced confirmed defects.
- Participants are preserved as SHA-256 digests of their original Address SCVal XDR, not guessed \`G...\`, \`M...\` or \`C...\` strings. Muxed memo/string bytes are hashed rather than disclosed.
- This subset does **not** prove SEP-41 implementation identity, contract asset/supply/balances, issuer authenticity, movement application, event completeness or candidate export equivalence.
- Approve events, protocol-specific fee events, and forms from SEP-57 or additional CAP-67 extension semantics are deliberately **not** normalized as token movements in this release.

## Evidence and compatibility boundaries

References checked 2026-10-10:

- [Stellar protocol XDR, original metadata v3/v4 structures](https://github.com/stellar/stellar-xdr/blob/main/Stellar-ledger.x).
- [CAP-67: classic operation and fee event semantics](https://github.com/stellar/stellar-protocol/blob/a5508c44633620742bb69f508c5887e3fbce22d0/core/cap-0067.md).
- [SEP-41: event shapes, including map, extension topics and muxed IDs](https://github.com/stellar/stellar-protocol/blob/a5508c44633620742bb69f508c5887e3fbce22d0/ecosystem/sep-0041.md).
- XDR decoding performed using pinned \`stellar-sdk==16.1.0\`.

Synthetic SDK-serialized metadata/XDR tests run in normal offline CI; a separate opt-in workflow tests genuine RPC-returned Testnet metadata. Its provider and network passphrase are **not** independently authenticated against consensus, and nothing produced here is a global event ID. Phase 05 must design a candidate-to-source matching rule and prove coverage independently before returning confirmed discrepancies.
