# ADR 0002 — XDR multiset comparison is observational, not historical proof

**Date:** 2026-10-10  
**Status:** Accepted for bounded experimental comparison; verified real-data reconciliation not yet complete.

The ETL field named `contract_event_xdr` encodes a `DiagnosticEvent` wrapper. Ordinary contract/operation/transaction events are converted to wrappers; transaction stages are discarded; operation IDs use 1-based TOID slots. Comparing bare `ContractEvent` or merging equal payloads would report incorrect discrepancies.

**Decision:** compare the exact canonical DiagnosticEvent XDR together with ledger, transaction hash, packed transaction ID and optional operation ID. Preserve multiplicity, source positions, opaque SHA-256 digests and line-level field checks. All differences are observations, not confirmed ETL errors. A missing source range or absent candidate XDR is inconclusive. User-supplied scope is not an authenticity or export-completeness attestation.

**Rejected:** payload-only identity; unqualified duplicate detection; treating diagnostic echoes as asset transfers; marking zero differences as independently verified chain parity; inventing event indices absent from the candidate schema.

**Needed before promotion:** a real ETL sample and independently corroborated, durable original ledger corpus; verified network and range coverage; reproducible source and exporter revisions.
