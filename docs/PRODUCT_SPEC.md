# Product scope

**Mission:** Give Stellar infrastructure maintainers a reproducible way to identify suspicious event-row patterns and ultimately reconcile processed token movements against independent source metadata.

**Target maintainers:** token indexer operators, ETL developers and backend engineers.

**Current experimental functionality (not the reconciliation MVP):** Local, bounded JSONL file checks for explicit event-ID collisions and certain suspicious inconsistencies. All event-payload matches lacking canonical identity are *review-required*, not proven duplicates.

**Not yet implemented:** first-party ETL export adapters, full raw ledger XDR decoding, SEP-41 or CAP-67 canonical token-movement semantics, retrieval from public RPC, account balance reconstruction, completeness proofs, or automatic repair.

**Success measure for next meaningful milestone:** reproduce at least one independently evidenced source-to-export discrepancy using a fixture based on genuine ledger metadata, preserving evidence and coverage, with a corresponding regression test.

**Candidate schema milestone:** A separate `validate-etl` command validates a versioned subset of `ContractEventOutput` JSONL fields against an *unverified* scope manifest. It is structural validation only, not source-ledger reconciliation or a confirmed MVP.
