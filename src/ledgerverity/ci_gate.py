"""Validate an observational report in CI, without claiming chain parity."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .reporting import CONTRACT, MAX_REPORT_BYTES


class CIGateError(ValueError):
    pass


def evaluate_report(data: dict, fail_on_review: bool = False) -> int:
    if not isinstance(data, dict) or data.get("report_contract") != CONTRACT:
        raise CIGateError("Unsupported report contract")
    if data.get("schema_version") != 1 or data.get("status") not in ("INCONCLUSIVE", "REVIEW_REQUIRED"):
        raise CIGateError("Invalid report version/status")
    for field in ("reconciliation_proven", "source_provenance_verified",
                  "network_identity_independently_verified", "candidate_export_coverage_verified"):
        if data.get(field) is not False:
            raise CIGateError("Unsafe or missing evidence assertion: " + field)
    gates = data.get("evidence_gates")
    if not isinstance(gates, dict) or any(gates.get(k) is not False for k in (
        "independent_source_provenance", "independent_network_identity",
        "complete_candidate_export", "confirmed_reconciliation"
    )):
        raise CIGateError("Report must preserve unverified evidence gates")
    fingerprints = data.get("evidence_fingerprints")
    if not isinstance(fingerprints, dict):
        raise CIGateError("Missing input fingerprints")
    for key in ("source_capture_sha256", "candidate_file_sha256", "scope_manifest_sha256"):
        val = fingerprints.get(key)
        if not isinstance(val, str) or len(val) != 64 or any(c not in "0123456789abcdef" for c in val):
            raise CIGateError("Invalid input fingerprint: " + key)
    summary = data.get("summary")
    if not isinstance(summary, dict):
        raise CIGateError("Missing summary")
    for key in ("exact_xdr_matches", "source_only", "candidate_only",
                "column_integrity_mismatches", "transaction_outcome_mismatches",
                "unmatchable_candidate_rows", "missing_source_ledgers"):
        if type(summary.get(key)) is not int or summary[key] < 0:
            raise CIGateError("Invalid count: " + key)
    if data["status"] == "REVIEW_REQUIRED" and data.get("observed_differences") is not True:
        raise CIGateError("Review status without observed differences")
    return 1 if fail_on_review and data["status"] == "REVIEW_REQUIRED" else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ledgerverity-ci-gate",
        description="Validate an evidence-limited report; optionally fail on review.")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--fail-on-review", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not args.report.is_file() or args.report.stat().st_size > MAX_REPORT_BYTES:
            raise CIGateError("Missing or oversized report")
        obj = json.loads(args.report.read_text(encoding="utf-8"),
                         parse_constant=lambda value: (_ for _ in ()).throw(CIGateError("Nonfinite JSON")))
        result = evaluate_report(obj, args.fail_on_review)
    except (OSError, UnicodeError, json.JSONDecodeError, CIGateError) as exc:
        print(f"ledgerverity-ci-gate: invalid report: {exc}", file=sys.stderr)
        return 2
    if result == 1:
        print("ledgerverity-ci-gate: REVIEW_REQUIRED; local opt-in CI policy, not a proven ETL defect")
    else:
        print("ledgerverity-ci-gate: observational report accepted; historical parity NOT VERIFIED")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
