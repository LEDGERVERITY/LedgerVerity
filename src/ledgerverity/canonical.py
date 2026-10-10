"""Source-local event locators and conservative SEP-41 token-movement views.

No source locator is a universal ETL event ID or consensus attestation.
"""
from __future__ import annotations
import base64
import binascii
import hashlib
import json

from .source import SourceEvent, SourceInputError

TOKEN_TOPIC_ARITY = {"transfer": 3, "mint": 2, "burn": 2, "clawback": 2}
STAGES = {"TRANSACTION_EVENT_STAGE_BEFORE_ALL_TXS", "TRANSACTION_EVENT_STAGE_AFTER_TX",
          "TRANSACTION_EVENT_STAGE_AFTER_ALL_TXS"}
STREAMS = {"contract", "operation", "transaction", "diagnostic"}


def source_locator(event: SourceEvent, network_claim: str) -> dict:
    if not isinstance(network_claim, str) or not network_claim.strip():
        raise SourceInputError("Missing claimed network passphrase")
    if (type(event.ledger) is not int or not 1 <= event.ledger <= 0xffffffff or
        type(event.tx_ordinal) is not int or event.tx_ordinal < 1 or
        type(event.ordinal_in_stream) is not int or event.ordinal_in_stream < 0 or
        event.stream not in STREAMS):
        raise SourceInputError("Invalid source event position")
    if event.stream == "operation":
        if type(event.operation_ordinal) is not int or event.operation_ordinal < 0:
            raise SourceInputError("Operation event missing operation index")
    elif event.operation_ordinal is not None:
        raise SourceInputError("Operation index outside operation stream")
    if event.stream == "transaction":
        if event.stage not in STAGES:
            raise SourceInputError("Transaction event missing or invalid stage")
    elif event.stage is not None:
        raise SourceInputError("Stage outside transaction-level stream")
    if not isinstance(event.tx_hash, str) or len(event.tx_hash) != 64 or any(
        ch not in "0123456789abcdefABCDEF" for ch in event.tx_hash
    ):
        raise SourceInputError("Invalid transaction hash")
    return {
        "network_claim_sha256": hashlib.sha256(network_claim.encode()).hexdigest(),
        "ledger_sequence": event.ledger,
        "transaction_hash": event.tx_hash.lower(),
        "transaction_ordinal_1based": event.tx_ordinal,
        "stream": event.stream,
        "operation_ordinal_0based": event.operation_ordinal,
        "event_ordinal_in_stream_0based": event.ordinal_in_stream,
    }


def _decode(event: SourceEvent):
    try:
        from stellar_sdk import xdr
    except ImportError as exc:
        raise SourceInputError("Install ledgerverity[source] for event XDR") from exc
    try:
        blob = base64.b64decode(event.contract_event_xdr, validate=True)
        item = xdr.ContractEvent.from_xdr_bytes(blob)
        if not blob or item.to_xdr_bytes() != blob:
            raise ValueError("Invalid XDR roundtrip")
    except (binascii.Error, ValueError, TypeError, AttributeError, EOFError) as exc:
        raise SourceInputError("Invalid original contract-event XDR") from exc
    return item, blob, xdr


def _symbol(value, xdr):
    if value.type != xdr.SCValType.SCV_SYMBOL or value.sym is None:
        return None
    try:
        return value.sym.sc_symbol.decode("ascii")
    except UnicodeError:
        return None


def _amount(value, xdr):
    if value.type != xdr.SCValType.SCV_I128 or value.i128 is None:
        return None
    return (value.i128.hi.int64 << 64) + value.i128.lo.uint64


def token_movement(item, xdr) -> dict:
    na = {"status": "NOT_APPLICABLE", "reason": "Not a supported SEP-41 movement topic"}
    if item.type != xdr.ContractEventType.CONTRACT or item.contract_id is None:
        return na
    if item.body.v != 0 or item.body.v0 is None or not item.body.v0.topics:
        return {"status": "INCONCLUSIVE", "reason": "Unsupported contract event body"}
    topics = item.body.v0.topics
    kind = _symbol(topics[0], xdr)
    if kind not in TOKEN_TOPIC_ARITY:
        return na
    n = TOKEN_TOPIC_ARITY[kind]
    if len(topics) < n or any(t.type != xdr.SCValType.SCV_ADDRESS for t in topics[1:n]):
        return {"status": "INCONCLUSIVE", "kind": kind, "reason": "Required address topics absent"}
    data = item.body.v0.data
    amount, encoding, muxed, extras = None, None, None, []
    if data.type == xdr.SCValType.SCV_I128:
        amount, encoding = _amount(data, xdr), "i128"
    elif data.type == xdr.SCValType.SCV_VEC and data.vec is not None:
        if len(data.vec.sc_vec) == 1:
            amount, encoding = _amount(data.vec.sc_vec[0], xdr), "vec_i128"
    elif data.type == xdr.SCValType.SCV_MAP and data.map is not None:
        encoding = "symbol_map"
        fields = {}
        for entry in data.map.sc_map:
            key = _symbol(entry.key, xdr)
            if key is None or key in fields:
                return {"status": "INCONCLUSIVE", "kind": kind,
                        "reason": "Map contains non-symbol or duplicated keys"}
            fields[key] = entry.val
        if "amount" in fields:
            amount = _amount(fields["amount"], xdr)
        extras = sorted(k for k in fields if k not in {"amount", "to_muxed_id"})
        if "to_muxed_id" in fields:
            if kind not in ("transfer", "mint"):
                return {"status": "INCONCLUSIVE", "kind": kind,
                        "reason": "Muxed ID is not supported for this movement"}
            val = fields["to_muxed_id"]
            if val.type == xdr.SCValType.SCV_VOID:
                muxed = None
            elif val.type == xdr.SCValType.SCV_U64 and val.u64 is not None:
                muxed = {"type": "u64", "value": str(val.u64.uint64)}
            elif val.type == xdr.SCValType.SCV_STRING and val.str is not None:
                muxed = {"type": "string", "xdr_sha256": hashlib.sha256(val.to_xdr_bytes()).hexdigest()}
            elif val.type == xdr.SCValType.SCV_BYTES and val.bytes is not None and len(val.bytes.sc_bytes) == 32:
                muxed = {"type": "bytes32", "xdr_sha256": hashlib.sha256(val.to_xdr_bytes()).hexdigest()}
            else:
                return {"status": "INCONCLUSIVE", "kind": kind,
                        "reason": "Unrecognized muxed ID encoding"}
    if amount is None or amount < 0:
        return {"status": "INCONCLUSIVE", "kind": kind, "reason": "Unsupported or negative amount"}
    return {
        "status": "PARTIAL" if extras or len(topics) > n else "SUPPORTED_SUBSET",
        "kind": kind,
        "amount_raw": str(amount),
        "encoding": encoding,
        "participant_xdr_sha256": [hashlib.sha256(t.to_xdr_bytes()).hexdigest() for t in topics[1:n]],
        "extra_topic_count": len(topics) - n,
        "extension_keys": extras,
        "to_muxed_id": muxed,
        "scope": "SEP-41 base event shape only; balances and supply unverified",
    }


def describe_source_event(event: SourceEvent, claimed_network_passphrase: str) -> dict:
    position = source_locator(event, claimed_network_passphrase)
    item, raw, xdr = _decode(event)
    if event.tx_success is not None and type(event.tx_success) is not bool:
        raise SourceInputError("Invalid XDR transaction success semantics")
    if event.diagnostic_success is not None and type(event.diagnostic_success) is not bool:
        raise SourceInputError("Invalid diagnostic success semantics")
    if event.stream != "diagnostic" and event.diagnostic_success is not None:
        raise SourceInputError("Diagnostic flag outside diagnostic stream")
    position_bytes = json.dumps(position, sort_keys=True, separators=(",", ":")).encode()
    return {
        "source_locator": position,
        "source_locator_sha256": hashlib.sha256(position_bytes).hexdigest(),
        "locator_consensus_anchored": False,
        "contract_event_sha256": hashlib.sha256(raw).hexdigest(),
        "contract_id_xdr": item.contract_id.to_xdr() if item.contract_id is not None else None,
        "contract_event_type": item.type.name,
        "transaction_success": event.tx_success,
        "diagnostic_in_successful_contract_call": event.diagnostic_success,
        "transaction_event_stage": event.stage,
        "semantics_known": event.tx_success is not None and (
            event.stream != "diagnostic" or event.diagnostic_success is not None),
        "token_movement": token_movement(item, xdr),
    }


def describe_snapshot_events(snapshot) -> list[dict]:
    seen = set()
    output = []
    for ledger in snapshot.ledgers:
        for ev in ledger.events:
            row = describe_source_event(ev, snapshot.declared_network_passphrase)
            key = row["source_locator_sha256"]
            if key in seen:
                raise SourceInputError("Repeated source-local event position")
            seen.add(key)
            output.append(row)
    return output
