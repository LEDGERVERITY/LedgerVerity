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

All automated tests initially used **synthetic or stubbed** data. An end-to-end captured ledger with independently recorded network and provider provenance, authenticated trust anchor and real contract-event fixtures is required before marking the complete source-evidence gate verified. A read-only CLI is not a blockchain consensus verifier. Phase 04 will define canonical event identity and stage semantics; Phase 05 will do differential reconciliation.
