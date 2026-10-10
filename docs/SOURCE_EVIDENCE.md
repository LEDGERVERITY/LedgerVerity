# Evidence register

Checked 2026-10-09 (GitHub-connected source inspections):

- https://github.com/stellar/stellar-etl/issues/452 — Open. Reports operation/diagnostic event double-emission and transaction success flag issues. Its reported production study is **not independently reproduced by this project**.
- https://github.com/stellar/stellar-etl/issues/467 — Open. Reports nonconforming token-transfer event shapes and silently dropped transfers. **This prototype does not detect omitted events.**
- https://github.com/stellar/stellar-etl/blob/master/internal/transform/contract_events.go — Event extraction contains TransactionEvents, OperationEvents and DiagnosticEvents paths, and fields `TransactionID`, `OperationID`, `Successful`, `InSuccessfulContractCall`, `Topics`, `Data`.
- https://github.com/Event-Parity/eventparity-engine — Existing related comparison engine focused on classic payment operations; LedgerVerity must maintain distinct scope.

### Current evidence

The `fixtures/` directory contains only synthetic examples. There is **no proven new production finding** and no verification that real ETL exports are accepted without an adapter. This tool's current claims are intentionally narrow.

### Candidate field verification — 2026-10-10

- Upstream Stellar ETL tree pinned at `34f6910b818767c0c2b8f187db21855a51f43c5e`: [`internal/transform/schema.go` `ContractEventOutput`](https://github.com/stellar/stellar-etl/blob/34f6910b818767c0c2b8f187db21855a51f43c5e/internal/transform/schema.go). Verified fields: `transaction_hash`, `transaction_id`, `successful`, `ledger_sequence`, `closed_at`, `in_successful_contract_call`, `contract_id`, `type`, `type_string`, `topics`, `topics_decoded`, `data`, `data_decoded`, `contract_event_xdr`, and `operation_id`.
- This maps a documented **Go schema**, not a verified real BigQuery response or genuine ledger metadata fixture. The new `validate-etl` input contract is strict, versioned and synthetic-test-backed only. No independent source event identity, completeness or production anomaly is established.

### Genuine RPC source observation — checked 2026-10-10

- Official [getLedgers](https://developers.stellar.org/docs/data/apis/rpc/api-reference/methods/getLedgers) documents `headerXdr`, `metadataXdr`, `sequence`, `hash`, bounded pagination/retention and base64 XDR. [RPC providers](https://developers.stellar.org/docs/data/apis/rpc/providers) documents Gateway and SDF Testnet endpoints. [Python SDK 16.1.0](https://pypi.org/project/stellar-sdk/16.1.0/) supports Python ≥3.10.
- [Live provider run 38007207290](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38007207290): successfully decoded a single Testnet provider ledger (5113381; 21 transaction, 36 operation, 206 diagnostic events). Provider-reported protocol 29, metadata v2. This is a real provider observation, not an independent trust anchor.
- [Live 3-ledger run 38007310724](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38007310724): successfully decoded ledger range 5113395–5113397, checked three computed header hashes and two adjacent previous-header links; 61 transaction, 32 operation and 762 diagnostic events. Provider Gateway Testnet RPC. Captured response SHA-256 `061b9810a627ecb5deb8c5e7491d33fa4d703ff91fd6a3098aa58d97868838ae`, stored with claimed provenance as a 30-day GitHub Actions artifact, expires 2026-11-09.
- The earlier SDF-hosted Testnet RPC attempt failed with HTTP 403 from the GitHub runner; that is an access restriction and **not** a protocol defect.
- **Unverified:** independent consensus checkpoint anchoring, independent provider corroboration, source network identity beyond provider claims, any source/candidate parity finding, permanent golden fixture corpus.
