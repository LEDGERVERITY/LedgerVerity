"""Read-only CLI: legacy heuristic audit and strict ETL candidate validation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .audit import AuditInputError, audit, read_jsonl
from .formats import CandidateFormatError, read_candidate_scope, read_etl_candidate_jsonl


def _write_report(rendered: str, output: Path | None) -> bool:
    if output is None:
        print(rendered, end="")
        return True
    try:
        output.write_text(rendered, encoding="utf-8")
    except OSError:
        print("ledgerverity: unable to write report", file=sys.stderr)
        return False
    return True


def _validate_etl(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="ledgerverity validate-etl",
        description="Validate a Stellar ETL JSONL candidate export; does not reconcile ledger evidence.",
    )
    parser.add_argument("--input", type=Path, required=True, help="UTF-8 JSONL candidate export")
    parser.add_argument("--scope", type=Path, required=True, help="Unverified candidate scope JSON manifest")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--output", type=Path, help="Report output (default stdout)")
    args = parser.parse_args(argv)
    try:
        scope = read_candidate_scope(args.scope)
        events = read_etl_candidate_jsonl(args.input, scope)
    except CandidateFormatError as exc:
        print(f"ledgerverity: {exc}", file=sys.stderr)
        return 2
    report = {
        "schema_version": 1,
        "status": "CANDIDATE_FORMAT_VALID",
        "candidate_format": "stellar-etl-contract-events-jsonl-v1",
        "rows_scanned": len(events),
        "scope_claim": {
            "network_passphrase": scope.network_passphrase,
            "first_ledger": scope.first_ledger,
            "last_ledger": scope.last_ledger,
            "exporter": scope.exporter,
            "source_description": scope.source_description,
        },
        "source_evidence_verified": False,
        "coverage_verified": False,
        "limitations": [
            "Structural validation only; original ledger metadata was not checked.",
            "The caller-provided network and ledger range are unverified claims.",
            "No event existence, completeness, correctness, duplication or parity is proven.",
        ],
    }
    if args.format == "json":
        rendered = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    else:
        rendered = (
            f"LedgerVerity: {report['status']}\n"
            f"Candidate rows validated: {len(events)}\n"
            f"Declared ledger range: {scope.first_ledger}..{scope.last_ledger}\n"
            "Source evidence / coverage: NOT VERIFIED\n"
            "Limitations: structural checks only; no ledger reconciliation or completeness proof.\n"
        )
    return 0 if _write_report(rendered, args.output) else 2


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "reconcile":
        from .reconcile_cli import main as reconcile_main
        return reconcile_main(argv[1:])
    if argv and argv[0] == "inspect-source":
        from .source_cli import main as source_main
        return source_main(argv[1:])
    if argv and argv[0] == "validate-etl":
        return _validate_etl(argv[1:])

    parser = argparse.ArgumentParser(
        prog="ledgerverity",
        description="Inspect normalized Stellar event exports. For strict candidate validation: ledgerverity validate-etl --help. For original ledger XDR: ledgerverity inspect-source --help. For comparison: ledgerverity reconcile --help",
    )
    parser.add_argument("input", type=Path, help="Legacy normalized event JSONL")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--output", type=Path, help="Report file (default stdout)")
    args = parser.parse_args(argv)
    try:
        report = audit(read_jsonl(args.input))
    except AuditInputError as exc:
        print(f"ledgerverity: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        rendered = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    else:
        lines = [f"LedgerVerity: {report['status']}", f"Rows inspected: {report['rows_scanned']}"]
        lines += [f"  line {f['line']}: [{f['severity']}] {f['code']} - {f['message']}" for f in report["findings"]]
        lines += ["Limitations: input-only consistency checks; not ledger verification."]
        rendered = "\n".join(lines) + "\n"
    if not _write_report(rendered, args.output):
        return 2
    return 1 if report["summary"]["errors"] else 3 if report["summary"]["review"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
