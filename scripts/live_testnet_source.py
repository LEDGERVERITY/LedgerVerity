"""Optional, explicitly networked TESTNET smoke; never runs during unit tests.

Makes three bounded HTTPS JSON-RPC read requests. Does not transact. Retains public-ledger snapshots as time-limited GitHub
Actions artifacts. Provider observations are not consensus attestations.
"""
import json
import datetime as dt
import urllib.request
from pathlib import Path

from ledgerverity.source import read_source_capture

RPC = "https://soroban-rpc.testnet.stellar.gateway.fm"
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
    sequence = latest - 4
    captured = call("getLedgers", {
        "startLedger": sequence, "pagination": {"limit": 3}, "xdrFormat": "base64"
    })
    folder = Path("artifacts")
    folder.mkdir(exist_ok=True)
    path = folder / "gateway-testnet-getledgers.json"
    path.write_text(json.dumps(captured, separators=(",", ":")), encoding="utf-8")
    snapshot = read_source_capture(path, sequence, sequence + 2, EXPECTED_NETWORK)
    report = snapshot.report()
    semantics = report.get("source_local_event_semantics", [])
    if len(semantics) != sum(report["event_counts_by_stream"].values()):
        raise RuntimeError("Original event stream semantics count mismatch")
    locators = [e["source_locator_sha256"] for e in semantics]
    if len(locators) != len(set(locators)):
        raise RuntimeError("Duplicate source-local event locator in live XDR")
    evidence = {
        "provider_url": RPC,
        "retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "reported_network_passphrase": network,
        "latest_ledger_when_requested": latest,
        "start_ledger": sequence,
        "end_ledger": sequence + 2,
        "response_sha256": snapshot.captured_sha256,
        "ledger_headers": report["ledger_headers"],
        "capture_classification": "genuine RPC provider data, not independent consensus-anchored",
        "source_provenance_verified": False,
        "ledger_chain_anchored": False,
    }
    (folder / "provenance.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if (not report["ledger_span_contiguous"]
            or not report["header_hashes_checked"]
            or not report["transaction_event_streams_decoded"]):
        raise RuntimeError("Live snapshot incomplete or cannot interpret event streams")
    print(json.dumps({
        "provider": RPC,
        "provider_network_passphrase_matched": True,
        "start_ledger": sequence,
        "end_ledger": sequence + 2,
        "ledger_hashes": [l.hash for l in snapshot.ledgers],
        "metadata_versions": [l.meta_version for l in snapshot.ledgers],
        "protocol_versions": [l.protocol for l in snapshot.ledgers],
        "adjacent_header_links_checked": report["adjacent_hash_links_checked"],
        "capture_sha256": snapshot.captured_sha256,
        "event_stream_counts": report["event_counts_by_stream"],
        "source_provenance_verified": False,
        "ledger_chain_anchored": False,
        "event_completeness_verified": False,
        "note": "Actual single-provider Testnet XDR; no independent chain consensus attestation"
    }, sort_keys=True))


if __name__ == "__main__":
    main()
