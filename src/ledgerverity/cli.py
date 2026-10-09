"""CLI entry point for the initial LedgerVerity experimental checks."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .audit import AuditInputError, audit, read_jsonl


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ledgerverity", description="Inspect Stellar ETL contract-event exports")
    parser.add_argument("input", type=Path, help="Input JSONL of normalized event rows")
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
    if args.output:
        try:
            args.output.write_text(rendered, encoding="utf-8")
        except OSError:
            print("ledgerverity: unable to write report", file=sys.stderr)
            return 2
    else:
        print(rendered, end="")
    return 1 if report["summary"]["errors"] else 3 if report["summary"]["review"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
