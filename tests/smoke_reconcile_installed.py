"""Smoke for the installed CLI; generates only synthetic original/candidate XDR."""
import json
from pathlib import Path
import subprocess
import tempfile
from test_reconcile import FORMAT, P, full_candidate, make_snapshot
from test_transaction_meta import ledger_with_tx

with tempfile.TemporaryDirectory() as d:
    p=Path(d)
    src=p/"source.json"; candidate=p/"candidate.jsonl"; scope=p/"scope.json"
    src.write_text(json.dumps({"jsonrpc":"2.0","id":1,"result":{"ledgers":[ledger_with_tx()]}}))
    records=full_candidate(make_snapshot())
    candidate.write_text("".join(json.dumps(x.raw)+"\n" for x in records))
    scope.write_text(json.dumps({
        "format":FORMAT,"network_passphrase":P,"first_ledger":1234,"last_ledger":1234,
        "exporter":"synthetic","source_description":"synthetic only"}))
    args=["ledgerverity","reconcile","--source",str(src),
          "--candidate",str(candidate),"--scope",str(scope),"--format","json"]
    first=subprocess.run(args,capture_output=True,text=True,timeout=20)
    assert first.returncode==3,(first.returncode,first.stderr)
    obj=json.loads(first.stdout)
    assert obj["summary"]["exact_xdr_matches"]==4 and obj["status"]=="INCONCLUSIVE"
    assert obj["reconciliation_proven"] is False
    candidate.write_text("".join(json.dumps(x.raw)+"\n" for x in records[:-1]))
    second=subprocess.run(args,capture_output=True,text=True,timeout=20)
    assert second.returncode==3,(second.returncode,second.stderr)
    changed=json.loads(second.stdout)
    assert changed["summary"]["source_only"]==1 and changed["status"]=="REVIEW_REQUIRED"
    assert changed["reconciliation_proven"] is False
    print("Synthetic installed CLI: exact and source-only observations validated.")
