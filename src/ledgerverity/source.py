"""Offline, bounded parsing of original RPC getLedgers LedgerCloseMeta XDR.

Only internal integrity of a caller-supplied RPC snapshot can be checked here.
No ledger hash is independently trusted or consensus-anchored. Do NOT treat
a successful decode as proof of source network identity or completeness.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .formats import CandidateFormatError, _json

MAX_CAPTURE_BYTES = 12_000_000
MAX_XDR_BYTES = 2_000_000
MAX_LEDGERS = 25
HEX_HASH = re.compile(r"[0-9a-fA-F]{64}\Z")


class SourceInputError(ValueError):
    """Malformed, ambiguous or unsupported source-evidence input."""


@dataclass(frozen=True)
class SourceEvent:
    ledger: int
    tx_hash: str
    tx_ordinal: int
    stream: str
    ordinal_in_stream: int
    operation_ordinal: int | None
    stage: str | None
    contract_event_xdr: str
    tx_success: bool | None = None
    diagnostic_success: bool | None = None

    def public(self) -> dict[str, Any]:
        return {
            "ledger": self.ledger,
            "transaction_hash": self.tx_hash,
            "tx_ordinal": self.tx_ordinal,
            "stream": self.stream,
            "ordinal_in_stream": self.ordinal_in_stream,
            "operation_ordinal": self.operation_ordinal,
            "stage": self.stage,
            "contract_event_sha256": hashlib.sha256(
                base64.b64decode(self.contract_event_xdr)
            ).hexdigest(),
        }


@dataclass(frozen=True)
class DecodedLedger:
    sequence: int
    hash: str
    previous_hash: str
    protocol: int
    meta_version: int
    events: tuple[SourceEvent, ...]
    unsupported_tx_versions: tuple[int, ...]


@dataclass(frozen=True)
class SourceSnapshot:
    declared_network_passphrase: str
    first_ledger: int
    last_ledger: int
    ledgers: tuple[DecodedLedger, ...]
    gaps: tuple[int, ...]
    captured_sha256: str

    @property
    def span_contiguous(self) -> bool:
        return not self.gaps

    @property
    def events_decoded(self) -> bool:
        return all(not l.unsupported_tx_versions for l in self.ledgers)

    def report(self) -> dict[str, Any]:
        from .canonical import describe_snapshot_events
        canonical_events = describe_snapshot_events(self)
        counts = {"contract": 0, "diagnostic": 0, "transaction": 0, "operation": 0}
        for ledger in self.ledgers:
            for event in ledger.events:
                counts["diagnostic" if event.stream == "diagnostic" else event.stream] += 1
        return {
            "schema_version": 2,
            "status": "INCONCLUSIVE",
            "declared_network_passphrase": self.declared_network_passphrase,
            "first_ledger": self.first_ledger,
            "last_ledger": self.last_ledger,
            "ledgers_parsed": len(self.ledgers),
            "missing_ledger_sequences": list(self.gaps),
            "ledger_span_contiguous": self.span_contiguous,
            "header_hashes_checked": bool(self.ledgers),
            "adjacent_hash_links_checked": len(self.ledgers) >= 2 and not self.gaps,
            "transaction_event_streams_decoded": self.events_decoded,
            "event_counts_by_stream": counts,
            "events": [event.public() for ledger in self.ledgers for event in ledger.events],
            "source_local_event_semantics": canonical_events,
            "ledger_headers": [
                {"sequence": l.sequence, "hash": l.hash, "previous_hash": l.previous_hash,
                 "protocol": l.protocol, "metadata_version": l.meta_version,
                 "unsupported_transaction_metadata_versions": list(l.unsupported_tx_versions)}
                for l in self.ledgers
            ],
            "capture_sha256": self.captured_sha256,
            "source_provenance_verified": False,
            "network_identity_verified": False,
            "ledger_chain_anchored": False,
            "event_completeness_verified": False,
            "limitations": [
                "The snapshot is caller-supplied and not independently consensus-anchored.",
                "The network passphrase is a caller claim, not provable from these XDR headers.",
                "Contiguous captured ledger sequences do not independently prove historical completeness.",
                "Distinct contract/transaction/operation/diagnostic streams are not canonical event IDs.",
                "No comparison against candidate exports has been performed.",
            ],
        }


def _strict_positive_int(value: Any, name: str) -> int:
    if type(value) is not int or not 1 <= value <= (1 << 32) - 1:
        raise SourceInputError(f"{name} must be an unsigned positive uint32 JSON integer")
    return value


def _hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or not HEX_HASH.fullmatch(value):
        raise SourceInputError(f"{label} must be a 64-character hex hash")
    return value.lower()


def _bytes(value: Any, label: str) -> bytes:
    if not isinstance(value, str) or len(value) > 4 * ((MAX_XDR_BYTES + 2) // 3) + 8:
        raise SourceInputError(f"{label} missing or too large")
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise SourceInputError(f"{label} is not canonical base64") from exc
    if not raw or len(raw) > MAX_XDR_BYTES or base64.b64encode(raw).decode("ascii") != value:
        raise SourceInputError(f"{label} must be nonempty canonical bounded base64")
    return raw


def _event(
    event_obj: Any, ledger: int, tx_hash: str, tx_index: int, stream: str,
    ordinal: int, operation_index: int | None = None, stage: str | None = None,
    tx_success: bool | None = None, diagnostic_success: bool | None = None,
) -> SourceEvent:
    if not hasattr(event_obj, "to_xdr_bytes"):
        raise SourceInputError("Unsupported contract event XDR object")
    return SourceEvent(ledger, tx_hash, tx_index, stream, ordinal,
                       operation_index, stage, base64.b64encode(event_obj.to_xdr_bytes()).decode("ascii"),
                       tx_success, diagnostic_success)


def _decode_ledger(entry: dict[str, Any]) -> DecodedLedger:
    """Decode both official RPC XDR fields and preserve original event streams."""
    try:
        from stellar_sdk import xdr
    except ImportError as exc:
        raise SourceInputError("XDR decoder unavailable; install ledgerverity[source]") from exc

    seq = _strict_positive_int(entry.get("sequence"), "ledger sequence")
    reported_hash = _hash(entry.get("hash"), f"ledger {seq} hash")
    header_xdr = _bytes(entry.get("headerXdr"), f"ledger {seq} headerXdr")
    meta_xdr = _bytes(entry.get("metadataXdr"), f"ledger {seq} metadataXdr")
    try:
        header_entry = xdr.LedgerHeaderHistoryEntry.from_xdr_bytes(header_xdr)
        meta = xdr.LedgerCloseMeta.from_xdr_bytes(meta_xdr)
    except Exception as exc:
        raise SourceInputError(f"ledger {seq}: invalid or unsupported XDR") from exc
    if meta.v not in (0, 1, 2):
        raise SourceInputError(f"ledger {seq}: unsupported LedgerCloseMeta version {meta.v}")
    payload = getattr(meta, f"v{meta.v}", None)
    if payload is None:
        raise SourceInputError(f"ledger {seq}: missing metadata v{meta.v}")
    embedded = payload.ledger_header
    if (header_entry.to_xdr_bytes() != embedded.to_xdr_bytes()
            or header_entry.hash.hash != embedded.hash.hash):
        raise SourceInputError(f"ledger {seq}: headerXdr / metadataXdr mismatch")
    header = header_entry.header
    if header.ledger_seq.uint32 != seq:
        raise SourceInputError(f"ledger {seq}: XDR ledger sequence mismatch")
    computed_hash = hashlib.sha256(header.to_xdr_bytes()).hexdigest()
    if computed_hash != reported_hash or header_entry.hash.hash.hex() != computed_hash:
        raise SourceInputError(f"ledger {seq}: header hash does not match XDR")
    previous = header.previous_ledger_hash.hash.hex()
    events: list[SourceEvent] = []
    unsupported: list[int] = []
    try:
        for tx_index, tx_result in enumerate(payload.tx_processing, 1):
            tx_hash = tx_result.result.transaction_hash.hash.hex()
            result_code = tx_result.result.result.result.code
            tx_success = result_code in (
                xdr.TransactionResultCode.txSUCCESS,
                xdr.TransactionResultCode.txFEE_BUMP_INNER_SUCCESS,
            )
            tx_meta = tx_result.tx_apply_processing
            if tx_meta.v == 3:
                soroban = tx_meta.v3.soroban_meta
                if soroban is not None:
                    for n, ev in enumerate(soroban.events):
                        events.append(_event(ev, seq, tx_hash, tx_index, "contract", n, tx_success=tx_success))
                    for n, diagnostic in enumerate(soroban.diagnostic_events):
                        events.append(_event(diagnostic.event, seq, tx_hash, tx_index, "diagnostic", n,
                                             tx_success=tx_success, diagnostic_success=diagnostic.in_successful_contract_call))
            elif tx_meta.v == 4:
                v4 = tx_meta.v4
                for n, transaction_event in enumerate(v4.events):
                    events.append(_event(transaction_event.event, seq, tx_hash, tx_index,
                                         "transaction", n, stage=transaction_event.stage.name,
                                         tx_success=tx_success))
                for op_index, operation in enumerate(v4.operations):
                    for n, event in enumerate(operation.events):
                        events.append(_event(event, seq, tx_hash, tx_index,
                                             "operation", n, operation_index=op_index, tx_success=tx_success))
                for n, diagnostic in enumerate(v4.diagnostic_events):
                    events.append(_event(diagnostic.event, seq, tx_hash, tx_index,
                                         "diagnostic", n, tx_success=tx_success,
                                         diagnostic_success=diagnostic.in_successful_contract_call))
            else:
                unsupported.append(tx_meta.v)
    except (AttributeError, TypeError, IndexError, ValueError) as exc:
        raise SourceInputError(f"ledger {seq}: unexpected event metadata shape") from exc
    return DecodedLedger(seq, computed_hash, previous, header.ledger_version.uint32,
                         meta.v, tuple(events), tuple(unsupported))


def read_source_capture(path: Path, first: int, last: int, network_passphrase: str) -> SourceSnapshot:
    """Verify internal chain links of one locally saved getLedgers RPC response."""
    first = _strict_positive_int(first, "first ledger")
    last = _strict_positive_int(last, "last ledger")
    if last < first or last - first + 1 > MAX_LEDGERS:
        raise SourceInputError(f"ledger range must be ordered and at most {MAX_LEDGERS} ledgers")
    if not isinstance(network_passphrase, str) or not network_passphrase.strip():
        raise SourceInputError("A nonempty network passphrase claim is required")
    try:
        if not path.is_file() or path.stat().st_size > MAX_CAPTURE_BYTES:
            raise SourceInputError("Source file missing or exceeds 12 MB")
        raw = path.read_bytes()
    except OSError as exc:
        raise SourceInputError("Unable to read source file") from exc
    try:
        capture = _json(raw, "source RPC capture")
    except CandidateFormatError as exc:
        raise SourceInputError(str(exc)) from exc
    if not isinstance(capture, dict) or capture.get("jsonrpc") != "2.0" or "error" in capture:
        raise SourceInputError("Expected a successful JSON-RPC 2.0 getLedgers response")
    result = capture.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("ledgers"), list):
        raise SourceInputError("Missing getLedgers result.ledgers array")
    arr = result["ledgers"]
    if len(arr) > MAX_LEDGERS:
        raise SourceInputError(f"Source capture exceeds {MAX_LEDGERS} ledgers")
    ledgers: list[DecodedLedger] = []
    seen: set[int] = set()
    for item in arr:
        if not isinstance(item, dict):
            raise SourceInputError("Source ledger must be an object")
        seq = _strict_positive_int(item.get("sequence"), "ledger sequence")
        if seq in seen or not first <= seq <= last:
            raise SourceInputError("Repeated or out-of-scope ledger sequence")
        seen.add(seq)
        ledgers.append(_decode_ledger(item))
    ledgers.sort(key=lambda x: x.sequence)
    for previous, current in zip(ledgers, ledgers[1:]):
        if current.sequence == previous.sequence + 1 and current.previous_hash != previous.hash:
            raise SourceInputError(f"Ledger {current.sequence} breaks preceding header-hash link")
    gaps = tuple(n for n in range(first, last + 1) if n not in seen)
    return SourceSnapshot(network_passphrase, first, last,
                          tuple(ledgers), gaps, hashlib.sha256(raw).hexdigest())
