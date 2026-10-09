# Architecture and trust boundaries

LedgerVerity currently exposes two **separate** offline workflows:

1. The legacy normalized JSONL audit (`src/ledgerverity/audit.py`) flags narrowly defined suspicious patterns. It does not prove source-ledger correctness.
2. The ETL candidate validator (`src/ledgerverity/formats.py` plus `cli.py`) parses the documented `ContractEventOutput` JSONL subset and a separate, untrusted network/range manifest. It validates structure, exact numeric IDs, file bounds and scope consistency.

The candidate adapter does **not** transform an ETL file into original ledger metadata or establish a reference identity. Its result is an unverified candidate dataset; `CANDIDATE_FORMAT_VALID` cannot be interpreted as `MATCH`.

Planned, not implemented: acquire original `LedgerCloseMeta` XDR from a separately verified source, independently decode canonical event identities and event stages, validate exact network and ledger coverage, then reconcile only supported event types. Any missing coverage or undecodable event must result in an inconclusive rather than a false confirmation.

Safety: no wallet keys, signing, hidden network calls or repair writes. Existing tests are synthetic and must not be promoted to real-network evidence. See [the data-format contract](DATA_FORMATS.md) and [ADR-0001](decisions/0001-candidate-adapter-first.md).
