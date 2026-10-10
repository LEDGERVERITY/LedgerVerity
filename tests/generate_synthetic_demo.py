"""Generate SYNTHETIC SDK ledger-XDR and ETL-shaped inputs for CI.
NOT real ledger history, ETL export, or independently verified evidence.
"""
from pathlib import Path
import json
import sys
from test_reconcile import FORMAT, P, full_candidate, make_snapshot
from test_transaction_meta import ledger_with_tx

if len(sys.argv) != 3 or sys.argv[2] not in ("exact","source-only"):
    raise SystemExit("Usage: generate_synthetic_demo.py DIRECTORY exact|source-only")
folder=Path(sys.argv[1])
folder.mkdir(parents=True,exist_ok=True)
(folder/"source.json").write_text(json.dumps({"jsonrpc":"2.0","id":1,
    "result":{"ledgers":[ledger_with_tx()]}})+"\n",encoding="utf-8")
rows=full_candidate(make_snapshot())
if sys.argv[2] == "source-only":
    rows=rows[:-1]
(folder/"candidate.jsonl").write_text("".join(json.dumps(r.raw)+"\n" for r in rows),encoding="utf-8")
(folder/"scope.json").write_text(json.dumps({
    "format":FORMAT, "network_passphrase":P,"first_ledger":1234,"last_ledger":1234,
    "exporter":"SYNTHETIC generator, not real stellar-etl",
    "source_description":"SDK-serialized test data, NOT historical source evidence"
})+"\n",encoding="utf-8")
print("Generated "+sys.argv[2]+" SYNTHETIC source/export inputs, not production evidence")
