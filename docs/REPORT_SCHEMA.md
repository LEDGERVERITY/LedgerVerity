# Reconciliation report schema contract

**Versioned contract:** `ledgerverity.reconciliation-report.v1`. This extends the existing reconciliation JSON `schema_version: 1` without deleting or changing previously present fields. The source-only `inspect-source` JSON schema is separate.

## Stable top-level fields

| Key | Format | Meaning |
|---|---|---|
| `status` | `INCONCLUSIVE` or `REVIEW_REQUIRED` | Observation classification, never confirmed ETL parity |
| `scope_claim` | object | Unverified manifest name/network/range and exporter claim |
| `summary` | object | Event/row/paired/unpaired/difference counts; counts refer only to supplied files |
| `observed_differences` | Boolean | Whether a difference was observed between supplied files |
| `findings` | array | Bounded observations (maximum 100); each includes a fixed code, classification and investigation suggestion |
| `finding_count` | integer | Total number of observations prior to finding truncation |
| `findings_truncated` | Boolean | Whether samples were capped at 100 |
| `source_capture_sha256` | string | SHA-256 of bytes read when the original source snapshot was decoded |
| `evidence_fingerprints` | object | SHA-256 of source, candidate JSONL and scope manifest files at reporting time |
| `evidence_gates` | object | Indicates only captured range completeness; authentic source, independent network, export coverage and proven reconciliation always false |
| `review_guidance` | array | Fixed per-code counts and suggested checks; not a repair instruction |
| `report_contract` | string | Exact schema contract identifier |

For compatibility, previously emitted `source_provenance_verified`, `network_identity_independently_verified`, `candidate_export_coverage_verified` and `reconciliation_proven` remain explicitly **false**.

## Verification and outputs

`ledgerverity reconcile --format json` emits deterministic keys/order for unchanged file bytes. `--format markdown` returns a GitHub-friendly summary intentionally **not** echoing raw scope description, exporter names, or arbitrary candidate field data. `--summary-output` can write it as a second report.

Exit codes: `3` for either valid observational status; `2` on invalid input or failed output. The CI gate uses separate `0` (valid observational report), `1` (optional review policy failure), and `2` (invalid report). It checks that source/event authenticity is never asserted by local comparison, and it does **not** independently recompute source or candidate file digests: a hash is an identifier, not an external provenance attestation.

Limitations: No independent consensus checkpoint, full ETL export coverage receipt, signed source provenance or genuine paired source-to-ETL fixture. See [the reconciliation contract](RECONCILIATION.md).
