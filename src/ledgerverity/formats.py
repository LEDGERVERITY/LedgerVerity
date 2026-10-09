"""Strict, offline adapter for exported stellar-etl contract-event JSONL rows.

This module parses CANDIDATE rows, not trusted reference events. Validation
never establishes completeness, ledger authenticity, or an event's identity.

Schema basis: stellar/stellar-etl internal/transform/schema.go:
ContractEventOutput (checked 2026-10-10; see docs/DATA_FORMATS.md).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FORMAT = "stellar-etl-contract-events-jsonl-v1"
MAX_FILE_BYTES = 20_000_000
MAX_LINE_BYTES = 256_000
MAX_ROWS = 50_000
_U32 = (1 << 32) - 1
_I64 = (1 << 63) - 1
_HASH = re.compile(r"[0-9a-fA-F]{64}\Z")
_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)\Z")
_REQUIRED = frozenset({"transaction_hash", "transaction_id", "successful",
    "ledger_sequence", "in_successful_contract_call", "contract_id",
    "type", "type_string", "topics", "data", "operation_id"})
_OPTIONAL = frozenset({"closed_at", "topics_decoded", "data_decoded", "contract_event_xdr"})


class CandidateFormatError(ValueError):
    """Invalid input or unsupported candidate export: fail closed."""


@dataclass(frozen=True)
class CandidateScope:
    network_passphrase: str
    first_ledger: int
    last_ledger: int
    exporter: str
    source_description: str
    provenance_verified: bool = False
    coverage_verified: bool = False


@dataclass(frozen=True)
class CandidateEvent:
    line: int
    transaction_hash: str
    transaction_id: int
    ledger_sequence: int
    operation_id: int | None
    successful: bool
    in_successful_contract_call: bool
    contract_id: str
    type: int
    type_string: str
    topics: list[Any]
    data: Any
    raw: dict[str, Any]


def _object_no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out = {}
    for k, v in pairs:
        if k in out:
            raise CandidateFormatError(f"Duplicate JSON key: {k}")
        out[k] = v
    return out


def _no_nonfinite(s: str) -> None:
    raise CandidateFormatError(f"Non-JSON numeric constant: {s}")


def _no_float(s: str) -> None:
    raise CandidateFormatError("Floating-point JSON numbers are unsupported; use exact strings/integers")


def _json(raw: bytes, context: str) -> Any:
    try:
        return json.loads(raw.decode("utf-8"),
            object_pairs_hook=_object_no_duplicate_keys,
            parse_constant=_no_nonfinite, parse_float=_no_float)
    except CandidateFormatError:
        raise
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise CandidateFormatError(f"{context}: invalid JSON, integer size or UTF-8") from exc


def _integer(value: Any, name: str, ceiling: int, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise CandidateFormatError(f"{name} must be an integer, not a boolean")
    if isinstance(value, int):
        integer = value
    elif isinstance(value, str) and _DECIMAL.fullmatch(value):
        if len(value) > 20:
            raise CandidateFormatError(f"{name} out of range")
        integer = int(value)
    else:
        raise CandidateFormatError(f"{name} must be an integer or canonical decimal string")
    if not minimum <= integer <= ceiling:
        raise CandidateFormatError(f"{name} out of range")
    return integer


def _nonempty_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CandidateFormatError(f"{name} must be a nonempty string")
    return value


def read_candidate_scope(path: Path) -> CandidateScope:
    """Read a caller-supplied scope claim. It is NEVER independent evidence."""
    try:
        if not path.is_file() or path.stat().st_size > MAX_LINE_BYTES:
            raise CandidateFormatError("Scope manifest missing or too large")
        obj = _json(path.read_bytes(), "scope manifest")
    except OSError as exc:
        raise CandidateFormatError("Cannot read scope manifest") from exc
    if not isinstance(obj, dict):
        raise CandidateFormatError("Scope manifest must be a JSON object")
    expected = {"format", "network_passphrase", "first_ledger", "last_ledger",
                "exporter", "source_description"}
    if obj.keys() != expected:
        raise CandidateFormatError("Scope manifest requires exactly: " + ", ".join(sorted(expected)))
    if obj["format"] != FORMAT:
        raise CandidateFormatError("Unsupported candidate format/version")
    first = _integer(obj["first_ledger"], "first_ledger", _U32, minimum=1)
    last = _integer(obj["last_ledger"], "last_ledger", _U32, minimum=1)
    if last < first:
        raise CandidateFormatError("Scope ledger range reversed")
    return CandidateScope(
        network_passphrase=_nonempty_str(obj["network_passphrase"], "network_passphrase"),
        first_ledger=first, last_ledger=last,
        exporter=_nonempty_str(obj["exporter"], "exporter"),
        source_description=_nonempty_str(obj["source_description"], "source_description"),
    )


def parse_candidate_row(row: dict[str, Any], line: int, scope: CandidateScope) -> CandidateEvent:
    if not isinstance(row, dict):
        raise CandidateFormatError(f"Line {line}: expected JSON object")
    missing = _REQUIRED - row.keys()
    unknown = row.keys() - (_REQUIRED | _OPTIONAL)
    if missing:
        raise CandidateFormatError(f"Line {line}: missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise CandidateFormatError(f"Line {line}: unsupported fields: {', '.join(sorted(unknown))}")
    h = row["transaction_hash"]
    if not isinstance(h, str) or not _HASH.fullmatch(h):
        raise CandidateFormatError(f"Line {line}: invalid transaction_hash")
    ledger = _integer(row["ledger_sequence"], "ledger_sequence", _U32, minimum=1)
    if not (scope.first_ledger <= ledger <= scope.last_ledger):
        raise CandidateFormatError(f"Line {line}: ledger outside declared scope")
    transaction_id = _integer(row["transaction_id"], "transaction_id", _I64)
    op_value = row["operation_id"]
    operation_id = None if op_value is None else _integer(op_value, "operation_id", _I64)
    for name in ("successful", "in_successful_contract_call"):
        if type(row[name]) is not bool:
            raise CandidateFormatError(f"Line {line}: {name} must be boolean")
    if not isinstance(row["contract_id"], str):
        raise CandidateFormatError(f"Line {line}: contract_id must be string")
    type_id = _integer(row["type"], "type", (1 << 31) - 1)
    type_string = _nonempty_str(row["type_string"], "type_string")
    if not isinstance(row["topics"], list):
        raise CandidateFormatError(f"Line {line}: topics must be an array")
    if "topics_decoded" in row and row["topics_decoded"] is not None and not isinstance(row["topics_decoded"], list):
        raise CandidateFormatError(f"Line {line}: topics_decoded must be an array or null")
    if "contract_event_xdr" in row and row["contract_event_xdr"] is not None and not isinstance(row["contract_event_xdr"], str):
        raise CandidateFormatError(f"Line {line}: contract_event_xdr must be string or null")
    if "closed_at" in row and row["closed_at"] is not None and not isinstance(row["closed_at"], str):
        raise CandidateFormatError(f"Line {line}: closed_at must be string or null")
    return CandidateEvent(line=line, transaction_hash=h.lower(), transaction_id=transaction_id,
        ledger_sequence=ledger, operation_id=operation_id,
        successful=row["successful"], in_successful_contract_call=row["in_successful_contract_call"],
        contract_id=row["contract_id"], type=type_id, type_string=type_string,
        topics=row["topics"], data=row["data"], raw=row)


def read_etl_candidate_jsonl(path: Path, scope: CandidateScope) -> list[CandidateEvent]:
    """Validate bounds, types and scope; do not infer unique event IDs."""
    try:
        if not path.is_file():
            raise CandidateFormatError("Candidate input must be a regular file")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise CandidateFormatError("Candidate input exceeds 20 MB")
        events = []
        consumed = 0
        with path.open("rb") as fh:
            for line, raw in enumerate(fh, 1):
                consumed += len(raw)
                if consumed > MAX_FILE_BYTES:
                    raise CandidateFormatError("Candidate input exceeds 20 MB")
                if len(raw) > MAX_LINE_BYTES:
                    raise CandidateFormatError(f"Line {line} exceeds 256 KB")
                if not raw.strip():
                    continue
                if len(events) == MAX_ROWS:
                    raise CandidateFormatError("Candidate exceeds 50000 rows")
                obj = _json(raw, f"line {line}")
                events.append(parse_candidate_row(obj, line, scope))
    except OSError as exc:
        raise CandidateFormatError("Cannot read candidate input") from exc
    return events
