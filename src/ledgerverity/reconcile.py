"""Read-only, evidence-limited comparison of Stellar ETL candidate exports to XDR.

The official stellar-etl ContractEventOutput.contract_event_xdr stores a
DiagnosticEvent XDR wrapper, even for transaction and operation events.
Corresponding identity derives from the packed TOID, including the 1-based
transaction position and optional 1-based operation position.

This module reports OBSERVATIONS only, never verified ETL defects.
"""
from __future__ import annotations

import base64
import binascii
from collections import Counter, defaultdict
import hashlib
import json
from typing import Any

from .canonical import describe_snapshot_events
from .formats import CandidateEvent, CandidateScope
from .source import SourceInputError, SourceSnapshot

MAX_COMPARISON_RECORDS = 50000
MAX_FINDINGS = 100
MAX_TOID_LEDGER = (1 << 31) - 1
MAX_TX_ORDINAL = (1 << 20) - 1
MAX_OP_ORDINAL = (1 << 12) - 1


class ReconcileInputError(ValueError):
    """An invalid, incompatible or unsupported comparison input."""


def _xdr():
    try:
        from stellar_sdk import StrKey, xdr
    except ImportError as exc:
        raise ReconcileInputError("Install ledgerverity[source] to compare original XDR") from exc
    return xdr, StrKey


def _toid(ledger: int, tx_ordinal: int, operation_index: int | None) -> int:
    """Bit-for-bit stellar-etl internal/toid/main.go (signed int64, nonnegative)."""
    if (type(ledger) is not int or not 1 <= ledger <= MAX_TOID_LEDGER or
        type(tx_ordinal) is not int or not 1 <= tx_ordinal <= MAX_TX_ORDINAL or
        (operation_index is not None and (
            type(operation_index) is not int or not 0 <= operation_index < MAX_OP_ORDINAL
        ))):
        raise ReconcileInputError("Cannot safely represent source locator as stellar-etl TOID")
    return ((ledger << 32) | (tx_ordinal << 12) |
            (0 if operation_index is None else operation_index + 1))


def _canonical_diagnostic(blob: str, xdr):
    if not isinstance(blob, str) or len(blob) > 350000:
        raise ReconcileInputError("Missing or oversized candidate diagnostic event XDR")
    try:
        raw = base64.b64decode(blob, validate=True)
        wrapper = xdr.DiagnosticEvent.from_xdr_bytes(raw)
        if not raw or wrapper.to_xdr_bytes() != raw or base64.b64encode(raw).decode() != blob:
            raise ValueError("Noncanonical serialized diagnostic event")
    except (binascii.Error, ValueError, TypeError, EOFError, AttributeError) as exc:
        raise ReconcileInputError("Invalid contract_event_xdr: expected canonical DiagnosticEvent XDR") from exc
    return raw, wrapper


def _source_key(event, xdr):
    op = event.operation_ordinal if event.stream == "operation" else None
    if event.stream not in {"operation", "transaction", "contract", "diagnostic"}:
        raise ReconcileInputError("Unsupported original-XDR source event stream")
    txid = _toid(event.ledger, event.tx_ordinal, None)
    operation_id = _toid(event.ledger, event.tx_ordinal, op) if op is not None else None
    flag = event.diagnostic_success if event.stream == "diagnostic" else True
    if type(flag) is not bool:
        raise ReconcileInputError("Original diagnostic event missing XDR success flag")
    if type(event.tx_success) is not bool:
        raise ReconcileInputError("Original transaction result code is unavailable")
    try:
        contract = xdr.ContractEvent.from_xdr(event.contract_event_xdr)
        wrapper = xdr.DiagnosticEvent(in_successful_contract_call=flag, event=contract)
        blob = wrapper.to_xdr_bytes()
    except (AttributeError, ValueError, TypeError, EOFError) as exc:
        raise ReconcileInputError("Cannot convert original source stream to ETL DiagnosticEvent XDR") from exc
    key = (event.ledger, event.tx_hash.lower(), txid, operation_id, hashlib.sha256(blob).hexdigest())
    return key, {"stream": event.stream,
                 "transaction_ordinal_1based": event.tx_ordinal,
                 "operation_ordinal_0based": op,
                 "source_contract_event_sha256": hashlib.sha256(contract.to_xdr_bytes()).hexdigest(),
                 "transaction_success": event.tx_success,
                 "diagnostic_in_successful_contract_call": flag,
                 "event_type": int(contract.type)}


def _candidate_key(row: CandidateEvent, xdr):
    if row.raw.get("contract_event_xdr") is None:
        return None, None
    raw, diagnostic = _canonical_diagnostic(row.raw["contract_event_xdr"], xdr)
    key = (row.ledger_sequence, row.transaction_hash, row.transaction_id,
           row.operation_id, hashlib.sha256(raw).hexdigest())
    return key, diagnostic


def _column_checks(row: CandidateEvent, diagnostic, xdr, StrKey) -> list[str]:
    """Compare inline ETL fields against the embedded DiagnosticEvent XDR."""
    if diagnostic is None:
        return []
    ev = diagnostic.event
    mismatches = []
    if row.in_successful_contract_call != diagnostic.in_successful_contract_call:
        mismatches.append("in_successful_contract_call")
    if row.type != int(ev.type):
        mismatches.append("type")
    if ev.contract_id is None:
        expected_contract = ""
    else:
        expected_contract = StrKey.encode_contract(ev.contract_id.contract_id.hash)
    if row.contract_id != expected_contract:
        mismatches.append("contract_id")
    if ev.body.v != 0 or ev.body.v0 is None:
        mismatches.append("unsupported_event_body")
    else:
        expected_topics = [base64.b64encode(topic.to_xdr_bytes()).decode()
                           for topic in ev.body.v0.topics]
        expected_data = base64.b64encode(ev.body.v0.data.to_xdr_bytes()).decode()
        if row.topics != expected_topics:
            mismatches.append("topics")
        if row.data != expected_data:
            mismatches.append("data")
    return mismatches


def compare_source_candidate(snapshot: SourceSnapshot, scope: CandidateScope,
                             candidate: list[CandidateEvent]) -> dict[str, Any]:
    """Compare exact opaque XDR multiset within one matching *claimed* scope.

    Input scope and provider data are NOT independent attestations. This
    algorithm never labels a discrepancy as a confirmed ETL bug.
    """
    if (snapshot.declared_network_passphrase != scope.network_passphrase or
        (snapshot.first_ledger, snapshot.last_ledger) != (scope.first_ledger, scope.last_ledger)):
        raise ReconcileInputError("Source/candidate network claim or ledger range does not match")
    if len(candidate) > MAX_COMPARISON_RECORDS:
        raise ReconcileInputError("Candidate comparison limit exceeded")
    if not all(scope.first_ledger <= ld.sequence <= scope.last_ledger for ld in snapshot.ledgers):
        raise ReconcileInputError("Source ledger outside requested scope")
    if sum(len(ld.events) for ld in snapshot.ledgers) > MAX_COMPARISON_RECORDS:
        raise ReconcileInputError("Source comparison event limit exceeded")

    xdr, StrKey = _xdr()
    # This also enforces unique original event positions; matching payloads
    # in DISTINCT positions remain valid and are separately counted.
    identities = describe_snapshot_events(snapshot)
    source_events = [ev for ld in snapshot.ledgers for ev in ld.events]
    if len(identities) != len(source_events):
        raise ReconcileInputError("Source event identity cardinality mismatch")
    source = defaultdict(list)
    for ev, identity in zip(source_events, identities):
        try:
            key, meta = _source_key(ev, xdr)
        except (SourceInputError, ReconcileInputError) as exc:
            raise ReconcileInputError(str(exc)) from exc
        source[key].append({
            "source_locator_sha256": identity["source_locator_sha256"],
            "ledger_sequence": ev.ledger,
            "transaction_hash": ev.tx_hash,
            "source_event_stream": meta["stream"],
            "source_operation_ordinal_0based": meta["operation_ordinal_0based"],
            "source_xdr_sha256": key[-1],
            "source_transaction_success": meta["transaction_success"],
        })

    candidates = defaultdict(list)
    missing_xdr = []
    integrity_mismatch = []
    for row in candidate:
        try:
            key, diagnostic = _candidate_key(row, xdr)
        except ReconcileInputError as exc:
            raise ReconcileInputError(f"Candidate line {row.line}: {exc}") from exc
        if key is None:
            missing_xdr.append({"candidate_line": row.line,
                                "reason": "contract_event_xdr unavailable"})
            continue
        packed_ledger = row.transaction_id >> 32
        packed_transaction = (row.transaction_id >> 12) & MAX_TX_ORDINAL
        packed_operation = row.transaction_id & MAX_OP_ORDINAL
        valid_toid = (packed_ledger == row.ledger_sequence
                      and 0 < packed_transaction <= MAX_TX_ORDINAL
                      and packed_operation == 0)
        valid_op = (row.operation_id is None or (
            (row.operation_id >> 32) == row.ledger_sequence
            and ((row.operation_id >> 12) & MAX_TX_ORDINAL) == packed_transaction
            and 0 < (row.operation_id & MAX_OP_ORDINAL) <= MAX_OP_ORDINAL
        ))
        if not valid_toid or not valid_op:
            integrity_mismatch.append({"candidate_line": row.line,
                "fields": ["transaction_id/operation_id"], "reason": "TOID conflicts with ledger/transaction placement"})
        fields = _column_checks(row, diagnostic, xdr, StrKey)
        if fields:
            integrity_mismatch.append({"candidate_line": row.line,
                                       "fields": fields, "reason": "ETL columns differ from embedded DiagnosticEvent XDR"})
        candidates[key].append({"candidate_line": row.line, "successful": row.successful,
                                "candidate_xdr_sha256": key[-1]})

    # Stable, multiplicity-preserving multiset matching: equal payloads are
    # neither deduplicated nor treated as universally identified event IDs.
    matches, source_only, candidate_only, outcome_mismatch = 0, [], [], []
    for key in sorted(set(source) | set(candidates)):
        originals = source.get(key, [])
        exports = candidates.get(key, [])
        pairs = min(len(originals), len(exports))
        matches += pairs
        for i in range(pairs):
            if originals[i]["source_transaction_success"] != exports[i]["successful"]:
                outcome_mismatch.append({
                    "candidate_line": exports[i]["candidate_line"],
                    "source_locator_sha256": originals[i]["source_locator_sha256"],
                    "field": "successful",
                    "source_value": originals[i]["source_transaction_success"],
                    "candidate_value": exports[i]["successful"],
                })
        source_only.extend(originals[pairs:])
        candidate_only.extend(exports[pairs:])

    complete_observation = (snapshot.span_contiguous and snapshot.events_decoded
                            and len(snapshot.ledgers) == scope.last_ledger - scope.first_ledger + 1)
    matchable = (not missing_xdr and complete_observation
                 and all(row["fields"] != ["transaction_id/operation_id"] for row in integrity_mismatch))
    observed_difference = bool(source_only or candidate_only or integrity_mismatch or outcome_mismatch)
    # All results have a trust boundary: one caller-supplied source and manifest.
    status = "REVIEW_REQUIRED" if observed_difference and matchable else "INCONCLUSIVE"
    findings = []
    for code, rows in (
        ("SOURCE_ONLY_OBSERVATION", source_only),
        ("CANDIDATE_ONLY_OBSERVATION", candidate_only),
        ("COLUMN_INTEGRITY_DIFFERENCE", integrity_mismatch),
        ("TRANSACTION_OUTCOME_DIFFERENCE", outcome_mismatch),
        ("UNMATCHABLE_CANDIDATE", missing_xdr),
    ):
        for row in rows[:max(0, MAX_FINDINGS - len(findings))]:
            findings.append({"code": code, **row})
        if len(findings) >= MAX_FINDINGS:
            break
    return {
        "schema_version": 1, "status": status,
        "source_capture_sha256": snapshot.captured_sha256,
        "candidate_format": "stellar-etl-contract-events-jsonl-v1",
        "scope_claim": {
            "network_passphrase": scope.network_passphrase,
            "first_ledger": scope.first_ledger, "last_ledger": scope.last_ledger,
            "exporter": scope.exporter, "source_description": scope.source_description,
        },
        "summary": {
            "source_events": len(source_events), "candidate_rows": len(candidate),
            "exact_xdr_matches": matches, "source_only": len(source_only),
            "candidate_only": len(candidate_only), "column_integrity_mismatches": len(integrity_mismatch),
            "transaction_outcome_mismatches": len(outcome_mismatch),
            "unmatchable_candidate_rows": len(missing_xdr),
            "missing_source_ledgers": len(snapshot.gaps),
            "unsupported_source_tx_meta_versions": sum(len(x.unsupported_tx_versions) for x in snapshot.ledgers),
        },
        "observed_differences": observed_difference,
        "finding_count": len(source_only) + len(candidate_only) + len(integrity_mismatch) + len(outcome_mismatch) + len(missing_xdr),
        "findings_truncated": (len(source_only) + len(candidate_only) + len(integrity_mismatch) + len(outcome_mismatch) + len(missing_xdr)) > len(findings),
        "findings": findings,
        "source_range_observed_complete": complete_observation,
        "source_provenance_verified": False,
        "network_identity_independently_verified": False,
        "candidate_export_coverage_verified": False,
        "reconciliation_proven": False,
        "limitations": [
            "Exact multiset matching is scoped to the provided ledger, transaction hash, packed TOID, optional operation ID and DiagnosticEvent XDR.",
            "This is a comparison of caller-supplied datasets, not independently consensus-anchored ledger history.",
            "The network and export-range declarations are not independently authenticated or completeness-certified.",
            "Absent rows, repeated XDR, and column mismatches are observations for review, never confirmed ETL defects.",
            "Original event stream stage is not represented in ETL DiagnosticEvent XDR; it is not inferred for candidates.",
        ],
    }
