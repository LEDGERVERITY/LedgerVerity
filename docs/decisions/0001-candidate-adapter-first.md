# ADR 0001: Validate an untrusted ETL candidate before comparing against ledger evidence

**Date:** 2026-10-10  
**Status:** Accepted for the candidate validation boundary; reconciliation not yet implemented.

## Context

The existing input-only checker consumes a custom normalized schema. It does not ingest actual contract-event export rows independently or verify network/range coverage. Stellar ETL defines `ContractEventOutput` fields in [its Go schema](https://github.com/stellar/stellar-etl/blob/34f6910b818767c0c2b8f187db21855a51f43c5e/internal/transform/schema.go) (source checked 2026-10-10).

## Decision

Introduce a strict, versioned JSONL candidate adapter preserving documented ETL fields, exact numeric IDs, nullable operation IDs and unmodified event payload structures. Require a separate manifest containing a claimed network and inclusive range. Reject unknown/malformed data rather than pretending to validate an arbitrary BigQuery response.

Expose `ledgerverity validate-etl --input ... --scope ...` without changing the existing heuristic audit. The command reports only candidate structure and always marks independent source evidence and ledger coverage unverified. It never invents an event index or event identity, drops a duplicate-looking row, or normalizes/token-interprets an unsupported event.

## Alternatives and consequences

Do not treat a user-supplied manifest as a cryptographic attestation, do not copy the ETL transformer as a reference implementation, and do not infer missing events from an incomplete source range. The strict adapter intentionally rejects provider extensions until an explicit versioned mapping is added. Real export compatibility, source-ledger XDR decoding and differential comparison remain future gates.
