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
