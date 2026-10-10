"""Read-only source/candidate comparison with deterministic evidence reports."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

from .formats import CandidateFormatError, read_candidate_scope, read_etl_candidate_jsonl
from .reconcile import ReconcileInputError, compare_source_candidate
from .reporting import ReportingError, annotate_report, render_markdown
from .source import SourceInputError, read_source_capture


def _validate_output_paths(inputs: list[Path], outputs: list[Path]) -> None:
    protected = {p.resolve() for p in inputs}
    written = set()
    for p in outputs:
        dest = p.resolve()
        if dest in protected:
            raise ReportingError("Report destination must not overwrite any source/candidate/scope input")
        if dest in written:
            raise ReportingError("Report and summary destinations must be different")
        written.add(dest)


def _atomic_write(dest: Path, body: str) -> None:
    """Do not truncate an existing output on write failure."""
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=dest.parent,
                                         prefix=".ledgerverity-", suffix=".tmp",
                                         delete=False) as handle:
            temp = Path(handle.name)
            handle.write(body)
        os.replace(temp, dest)
    except OSError as exc:
        raise ReportingError("Unable to write reconciliation report") from exc
    finally:
        if temp is not None:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="ledgerverity reconcile",
        description="Compare supplied ledger XDR and ETL exports; observations never prove ETL defects.",
    )
    parser.add_argument("--source", type=Path, required=True, help="Saved getLedgers JSON-RPC response")
    parser.add_argument("--candidate", type=Path, required=True, help="ETL ContractEventOutput JSONL")
    parser.add_argument("--scope", type=Path, required=True, help="Caller-supplied claimed network/range manifest")
    parser.add_argument("--format", choices=("json", "text", "markdown"), default="text")
    parser.add_argument("--output", type=Path, help="Report destination, default stdout")
    parser.add_argument("--summary-output", type=Path,
                        help="Also write fixed, untrusted-text-safe Markdown for a CI job summary")
    args = parser.parse_args(argv)
    try:
        _validate_output_paths([args.source, args.candidate, args.scope],
                               [p for p in (args.output, args.summary_output) if p is not None])
        scope = read_candidate_scope(args.scope)
        source = read_source_capture(args.source, scope.first_ledger, scope.last_ledger,
                                     scope.network_passphrase)
        rows = read_etl_candidate_jsonl(args.candidate, scope)
        report = annotate_report(compare_source_candidate(source, scope, rows),
                                 args.source, args.candidate, args.scope)
        markdown = render_markdown(report)
        if args.format == "json":
            rendered = json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
        elif args.format == "markdown":
            rendered = markdown
        else:
            m = report["summary"]
            rendered = "\n".join([
                f"LedgerVerity: {report['status']}",
                f"Exact DiagnosticEvent XDR pairs: {m['exact_xdr_matches']}",
                f"Original-XDR only: {m['source_only']}",
                f"Candidate ETL only: {m['candidate_only']}",
                f"Inline candidate-field differences: {m['column_integrity_mismatches']}",
                f"Transaction outcome differences: {m['transaction_outcome_mismatches']}",
                f"Unmatchable candidates: {m['unmatchable_candidate_rows']}",
                f"Missing source ledgers: {m['missing_source_ledgers']}",
                f"Findings shown: {len(report['findings'])}/{report['finding_count']}" +
                (" (truncated)" if report["findings_truncated"] else ""),
                "Confirmed ETL defects: NONE VERIFIED",
                "Source/network authenticity, full export coverage, historical parity: NOT VERIFIED",
            ]) + "\n"
        if args.summary_output is not None:
            _atomic_write(args.summary_output, markdown)
        if args.output is not None:
            _atomic_write(args.output, rendered)
        else:
            print(rendered, end="")
    except (CandidateFormatError, SourceInputError, ReconcileInputError,
            ReportingError) as exc:
        print(f"ledgerverity: {exc}", file=sys.stderr)
        return 2
    # Exit 3 for both REVIEW_REQUIRED and INCONCLUSIVE, never proof of parity.
    return 3
