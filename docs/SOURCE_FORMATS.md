# Offline Stellar ledger source evidence (experimental)

LedgerVerity can inspect a **saved** Stellar RPC \`getLedgers\` JSON-RPC response containing original base64 \`headerXdr\` (LedgerHeaderHistoryEntry) and \`metadataXdr\` (LedgerCloseMeta).

**This is not trusted network provenance**: a captured JSON file can be modified or made up, and a caller-provided network passphrase is not authenticated by ledger headers. Even a structurally valid, contiguous XDR response is **INCONCLUSIVE** for event completeness, confirmed historical truth, or ETL parity. The importer does not yet produce source-to-candidate reconciliation.

## Install

\`\`\`bash
python -m pip install '.[source]'
ledgerverity inspect-source --help
\`\`\`

The optional \`source\` extra pins Stellar's Python SDK **16.1.0** for versioned XDR decoding (Python >=3.10). The older candidate and heuristic audit commands do not require an SDK.

## Save an authentic sample manually

\`\`\`bash
curl --fail --silent --show-error --max-time 20 \
  -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","id":1,"method":"getLedgers","params":{"startLedger":36233,"pagination":{"limit":1},"xdrFormat":"base64"}}' \
  https://soroban-testnet.stellar.org > source-rpc.json

ledgerverity inspect-source \
  --input source-rpc.json \
  --from-ledger 36233 \
  --to-ledger 36233 \
  --network-passphrase 'Test SDF Network ; September 2015' \
  --format json
\`\`\`

**Important:** ledger 36233 may no longer be retained by the public testnet RPC. Get a current ledger sequence and replace the example value. A retention gap or RPC error is not proof that original ledger data never existed. The tool does not initiate HTTP requests by itself. Do not put RPC secrets or private URLs in a public artifact.

Input: one saved successful JSON-RPC 2.0 envelope with a \`result.ledgers\` array containing \`sequence\`, \`hash\`, \`headerXdr\`, \`metadataXdr\` for each ledger. A single source page supports at most **25 ledgers**, **12 MB** total file size and **2 MB** per decoded XDR blob. Do not assume one page proves more ledgers exist.

## Actual checks

- Each ledger sequence must be a positive 32-bit number and inside the requested inclusive range.
- Duplicate/out-of-range sequences, malformed JSON/XDR, truncated or invalid base64, conflicting header/metadata XDR and mismatched computed SHA-256 header hashes result in **INPUT_ERROR** (exit 2).
- Adjacent retrieved headers must link by previous header hash. Missing sequence numbers remain **INCONCLUSIVE** (exit 3), never silently covered.
- Metadata versions v0, v1 and v2 are decoded. v3 Soroban event and diagnostic streams, plus v4 transaction, operation and diagnostic streams, are independently preserved and counted. Unsupported transaction metadata versions are recorded and prohibit interpreting the source as fully decoded.
- JSON report includes a capture SHA-256 checksum, ledger hashes/previous links, observed range gaps, event stream counts and event SHA-256 fingerprints. Duplicate-looking payloads across streams are never silently deduplicated.
- The passphrase is expressly **a user claim**; the XDR data contains no cryptographic attestation of it, and no consensus-anchored checkpoint or independent trusted node verification is performed.

## Evidence status

Automated tests use **synthetic or stubbed** data, including real serialized synthetic SDK XDR. An end-to-end captured ledger with independently recorded network and provider provenance, authenticated trust anchor and real contract-event fixtures is required before marking the complete source-evidence gate verified. A read-only CLI is not a blockchain consensus verifier. Phase 04 will define canonical event identity and stage semantics; Phase 05 will do differential reconciliation.

## Reproducible live-provider smoke (opt-in only)

The `Live Testnet Source Smoke (Opt-In)` GitHub workflow can be manually triggered. It requests `getNetwork`, `getLatestLedger` and at most three bounded `getLedgers` records through a documented public Testnet HTTPS RPC endpoint, checks the server-reported passphrase, performs the same local XDR/hash/link validation, and saves a 30-day artifact containing a captured response and `provenance.json`. The script does **not** submit transactions or handle wallet private keys; the public ledger capture is shared with GitHub Actions when running the workflow.

On 2026-10-10, [this live run](https://github.com/LEDGERVERITY/LedgerVerity/actions/runs/38007310724) succeeded for Testnet ledgers 5113395–5113397. This is genuine provider-returned data, not consensus-verified independent truth. Evidence must be preserved beyond the artifact's expiry if it is to become a durable golden corpus. The source importer and normal tests make no outbound network requests.

## Source-local event semantics (schema v2)

`inspect-source --format json` now includes `source_local_event_semantics` as a parallel, deterministic array to `events`; the JSON `schema_version` is **2**. This contains local locators and cautious XDR token-movement views, not globally comparable event IDs. See [event identity and semantics](EVENT_SEMANTICS.md). Transaction success and diagnostic in-successful-contract-call flags are reported separately; an unsupported token variant is **inconclusive**, not silently omitted or proof of financial discrepancy.
