"""Offline, evidence-limited checks for normalized Stellar contract-event exports.

This is intentionally NOT a proof of ledger completeness or an ETL backfill tool.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

MAX_FILE_BYTES = 20_000_000
MAX_LINE_BYTES = 256_000
MAX_ROWS = 50_000


class AuditInputError(ValueError):
    pass


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        raise AuditInputError("Input is not a regular file")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise AuditInputError("Input exceeds 20 MB limit")
    rows = []
    try:
        with path.open("rb") as stream:
            for line_number, raw in enumerate(stream, 1):
                if len(raw) > MAX_LINE_BYTES:
                    raise AuditInputError(f"Line {line_number} exceeds 256 KB limit")
                if not raw.strip():
                    continue
                if len(rows) >= MAX_ROWS:
                    raise AuditInputError("Input exceeds 50000-row limit")
                try:
                    row = json.loads(raw.decode("utf-8"))
                except (UnicodeError, json.JSONDecodeError) as exc:
                    raise AuditInputError(f"Invalid JSON/UTF-8 on line {line_number}") from exc
                if not isinstance(row, dict):
                    raise AuditInputError(f"Line {line_number} must contain an object")
                row = {**row, "_source_line": line_number}
                rows.append(row)
    except OSError as exc:
        raise AuditInputError("Unable to read input file") from exc
    return rows


def audit(rows: list[dict]) -> dict:
    findings: list[dict] = []
    by_fingerprint: dict[str, list[tuple[int, bool]]] = defaultdict(list)
    seen_event_ids: dict[str, int] = {}

    def add(code: str, severity: str, line: int, message: str, related_line: int | None = None):
        item = {"code": code, "severity": severity, "line": line, "message": message}
        if related_line is not None:
            item["related_line"] = related_line
        findings.append(item)

    for ordinal, row in enumerate(rows, 1):
        line = row.get("_source_line", ordinal)
        tx_id = row.get("transaction_id")
        if not isinstance(tx_id, (int, str)) or isinstance(tx_id, bool) or str(tx_id).strip() == "":
            add("INVALID_TRANSACTION_ID", "error", line, "Expected nonempty transaction_id (string or integer)")
            continue
        if not isinstance(row.get("successful"), bool):
            add("MISSING_SUCCESS_FLAG", "review", line, "Expected boolean successful; cannot assess consistency")
        if not isinstance(row.get("in_successful_contract_call"), bool):
            add("MISSING_CONTRACT_CALL_FLAG", "review", line, "Expected boolean in_successful_contract_call; cannot assess consistency")
        if row.get("successful") is False and row.get("in_successful_contract_call") is True:
            add("POSSIBLE_SUCCESS_FLAG_MISMATCH", "review", line,
                "Successful contract-call flag is true on a failed transaction; examine event-stage semantics")
        event_id = row.get("event_id")
        if event_id is not None:
            if not isinstance(event_id, str) or not event_id.strip():
                add("INVALID_EVENT_ID", "review", line, "Optional event_id must be a nonempty string")
            elif event_id in seen_event_ids:
                add("DUPLICATE_EVENT_ID", "error", line,
                    "Repeated event_id in this input; ensure event IDs belong to one network and canonical stream",
                    seen_event_ids[event_id])
            else:
                seen_event_ids[event_id] = line

        # This is NOT a proof of a duplicate: distinct real events can have
        # identical topics and data. Only flag pairs where operation_id
        # presence differs (the pattern in stellar/stellar-etl#452).
        if isinstance(row.get("topics"), list) and "data" in row:
            fingerprint = _canonical([str(tx_id), row.get("ledger_sequence"), row.get("type_string"),
                                      row.get("contract_id"), row["topics"], row["data"]])
            has_operation = row.get("operation_id") is not None
            existing = by_fingerprint[fingerprint]
            for prior_line, prior_has_operation in existing:
                if has_operation != prior_has_operation:
                    add("POSSIBLE_DIAGNOSTIC_DUPLICATE", "review", line,
                        "Matching payload appears with and without an operation_id; investigate diagnostic duplication",
                        prior_line)
                    break
            existing.append((line, has_operation))
        else:
            add("MISSING_EVENT_PAYLOAD", "review", line,
                "topics list or data field is absent; cannot compare payload fingerprints")

    findings.sort(key=lambda f: (f["line"], f["code"], f.get("related_line", 0)))
    errors = sum(f["severity"] == "error" for f in findings)
    review = sum(f["severity"] == "review" for f in findings)
    return {
        "schema_version": 1,
        "status": "ERRORS" if errors else "REVIEW_REQUIRED" if review else "NO_ISSUES_DETECTED",
        "rows_scanned": len(rows),
        "summary": {"errors": errors, "review": review},
        "findings": findings,
        "limitations": [
            "Inspects only supplied JSONL rows; no independent ledger verification or completeness proof.",
            "Matching event payloads may represent distinct legitimate events; possible duplicates require human review.",
            "Event identity is network-specific; cross-network files must not be combined.",
            "NO_ISSUES_DETECTED is not a guarantee of correctness or SEP-41 compliance."
        ],
    }
