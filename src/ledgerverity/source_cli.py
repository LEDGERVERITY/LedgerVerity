"""Command handler for offline, read-only original ledger-XDR snapshots."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .source import SourceInputError, read_source_capture


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="ledgerverity inspect-source",
        description="Inspect a SAVED getLedgers XDR response. Does not authenticate its provider or prove ledger parity.",
    )
    parser.add_argument("--input", type=Path, required=True, help="Saved getLedgers JSON-RPC response")
    parser.add_argument("--from-ledger", type=int, required=True)
    parser.add_argument("--to-ledger", type=int, required=True)
    parser.add_argument("--network-passphrase", required=True, help="Caller-declared passphrase, not independently authenticated")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    parser.add_argument("--output", type=Path, help="Report destination (default stdout)")
    args = parser.parse_args(argv)
    try:
        result = read_source_capture(args.input, args.from_ledger, args.to_ledger,
                                     args.network_passphrase).report()
    except SourceInputError as exc:
        print(f"ledgerverity: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        rendered = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    else:
        rendered = (
            "LedgerVerity: INCONCLUSIVE — source not independently authenticated\n"
            f"Captured ledgers: {result['ledgers_parsed']}\n"
            f"Internal ledger range contiguous: {result['ledger_span_contiguous']}\n"
            f"Missing ledger sequences: {result['missing_ledger_sequences']}\n"
            f"Event streams decoded: {result['transaction_event_streams_decoded']}\n"
            "Network identity, historical completeness and ledger parity: NOT VERIFIED\n"
        )
    if args.output is None:
        print(rendered, end="")
        return 3
    try:
        args.output.write_text(rendered, encoding="utf-8")
    except OSError:
        print("ledgerverity: unable to write source report", file=sys.stderr)
        return 2
    return 3
