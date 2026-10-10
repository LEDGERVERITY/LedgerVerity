# Architecture and trust boundaries

LedgerVerity currently exposes two **separate** offline workflows:

1. The legacy normalized JSONL audit (`src/ledgerverity/audit.py`) flags narrowly defined suspicious patterns. It does not prove source-ledger correctness.
2. The ETL candidate validator (`src/ledgerverity/formats.py` plus `cli.py`) parses the documented `ContractEventOutput` JSONL subset and a separate, untrusted network/range manifest. It validates structure, exact numeric IDs, file bounds and scope consistency.

The candidate adapter does **not** transform an ETL file into original ledger metadata or establish a reference identity. Its result is an unverified candidate dataset; `CANDIDATE_FORMAT_VALID` cannot be interpreted as `MATCH`.

Planned, not implemented: acquire original `LedgerCloseMeta` XDR from a separately verified source, independently decode canonical event identities and event stages, validate exact network and ledger coverage, then reconcile only supported event types. Any missing coverage or undecodable event must result in an inconclusive rather than a false confirmation.

Safety: no wallet keys, signing, hidden network calls or repair writes. Existing tests are synthetic and must not be promoted to real-network evidence. See [the data-format contract](DATA_FORMATS.md) and [ADR-0001](decisions/0001-candidate-adapter-first.md).

3. Original source-snapshot inspector (`src/ledgerverity/source.py` and `source_cli.py`) reads one saved Stellar RPC `getLedgers` JSON response. It independently decodes `LedgerCloseMeta` and `LedgerHeaderHistoryEntry` XDR using an optional pinned Stellar SDK, checks embedded header/hash consistency and adjacent hash links, and retains distinct event streams (v3/v4). Every result is `INCONCLUSIVE` for consensus authenticity, network provenance, historical completeness and ETL parity.

The separately opt-in `scripts/live_testnet_source.py` performs bounded read-only RPC calls to a documented Testnet provider and retains a 30-day GitHub Actions evidence artifact. This is a real provider observation, **not** independent consensus anchoring. The core user CLI is strictly offline and read-only.

4. Conservative original-XDR event semantics (`src/ledgerverity/canonical.py`) derives **source-local** locators from XDR ledger/transaction/stream/operation/event positions. It preserves v4 fee-event stage and separates transaction-result success from diagnostic contract-call success. It classifies base transfer/mint/burn/clawback event shapes without floating-point conversion or inventing universal IDs. See [event identity and semantics](EVENT_SEMANTICS.md). No candidate-source matching or proof of completeness occurs in this module.
