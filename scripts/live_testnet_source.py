"""Optional, explicitly networked TESTNET smoke; never runs during unit tests.

Makes three bounded HTTPS JSON-RPC read requests. Does not transact or
upload raw ledger data. Provider observations are not consensus attestations.
"""
import hashlib
import json
import tempfile
import urllib.request
from pathlib import Path

from ledgerverity.source import read_source_capture

RPC = "https://soroban-testnet.stellar.org"
EXPECTED_NETWORK = "Test SDF Network ; September 2015"
MAX_RESPONSE = 12_000_000


def call(method, params=None):
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}
    }).encode("utf-8")
    req = urllib.request.Request(RPC, data=payload,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        if resp.status != 200:
            raise RuntimeError(f"RPC returned HTTP {resp.status}")
        raw = resp.read(MAX_RESPONSE + 1)
    if len(raw) > MAX_RESPONSE:
        raise RuntimeError("RPC response larger than 12 MB")
    data = json.loads(raw)
    if "error" in data or not isinstance(data.get("result"), dict):
        raise RuntimeError(f"{method} returned an error: {str(data.get('error'))[:200]}")
    return data


def main():
    network = call("getNetwork")["result"]["passphrase"]
    if network != EXPECTED_NETWORK:
        raise RuntimeError("RPC returned an unexpected network passphrase")
    latest = call("getLatestLedger")["result"]["sequence"]
    if type(latest) is not int or latest < 5:
        raise RuntimeError("RPC returned an invalid latest ledger")
    # A recently closed ledger, not the current not-yet-consistently indexed tip.
    sequence = latest - 2
    captured = call("getLedgers", {
        "startLedger": sequence, "pagination": {"limit": 1}, "xdrFormat": "base64"
    })
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "real-testnet-rpc.json"
        path.write_text(json.dumps(captured, separators=(",", ":")), encoding="utf-8")
        snapshot = read_source_capture(path, sequence, sequence, EXPECTED_NETWORK)
        report = snapshot.report()
    if (not report["ledger_span_contiguous"]
            or not report["header_hashes_checked"]
            or not report["transaction_event_streams_decoded"]):
        raise RuntimeError("Live snapshot incomplete or cannot interpret event streams")
    print(json.dumps({
        "provider": RPC,
        "provider_network_passphrase_matched": True,
        "ledger": sequence,
        "ledger_hash": snapshot.ledgers[0].hash,
        "metadata_version": snapshot.ledgers[0].meta_version,
        "protocol": snapshot.ledgers[0].protocol,
        "capture_sha256": snapshot.captured_sha256,
        "event_stream_counts": report["event_counts_by_stream"],
        "source_provenance_verified": False,
        "ledger_chain_anchored": False,
        "event_completeness_verified": False,
        "note": "Actual single-provider Testnet XDR; no independent chain consensus attestation"
    }, sort_keys=True))


if __name__ == "__main__":
    main()
