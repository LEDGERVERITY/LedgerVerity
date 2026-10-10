"""CLI for conservative candidate-vs-original-XDR comparison."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .formats import CandidateFormatError, read_candidate_scope, read_etl_candidate_jsonl
from .reconcile import ReconcileInputError, compare_source_candidate
from .source import SourceInputError, read_source_capture


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="ledgerverity reconcile",
        description="Compare a local original-XDR RPC capture with ETL candidate JSONL; observations are not confirmed ETL defects.",
    )
    parser.add_argument("--source", type=Path, required=True, help="Saved getLedgers JSON-RPC response")
    parser.add_argument("--candidate", type=Path, required=True, help="ETL ContractEventOutput JSONL candidate")
    parser.add_argument("--scope", type=Path, required=True, help="Caller-supplied network/range claim JSON")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    parser.add_argument("--output", type=Path, help="Report path, default stdout")
    args = parser.parse_args(argv)

    try:
        scope = read_candidate_scope(args.scope)
        source = read_source_capture(args.source, scope.first_ledger, scope.last_ledger,
                                     scope.network_passphrase)
        candidate = read_etl_candidate_jsonl(args.candidate, scope)
        report = compare_source_candidate(source, scope, candidate)
    except (CandidateFormatError, SourceInputError, ReconcileInputError) as exc:
        print(f"ledgerverity: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        output = json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    else:
        m = report["summary"]
        output = "\n".join([
            f"LedgerVerity: {report['status']}",
            f"Exactly paired XDR records: {m['exact_xdr_matches']}",
            f"Original-XDR only: {m['source_only']}",
            f"Candidate ETL only: {m['candidate_only']}",
            f"Inline-field differences: {m['column_integrity_mismatches']}",
            f"Transaction outcome differences: {m['transaction_outcome_mismatches']}",
            f"Unmatchable candidate rows: {m['unmatchable_candidate_rows']}",
            f"Missing source ledgers: {m['missing_source_ledgers']}",
            "Confirmed discrepancies: NONE (provider/coverage not independently verified)",
            "Source/network authenticity, export completeness and consensus proof: NOT VERIFIED",
        ]) + "\n"

    if args.output is None:
        print(output, end="")
    else:
        try:
            args.output.write_text(output, encoding="utf-8")
        except OSError:
            print("ledgerverity: unable to write reconciliation report", file=sys.stderr)
            return 2
    # 3 means review or insufficient evidence, never successful reconciliation.
    return 3
