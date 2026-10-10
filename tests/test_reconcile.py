"""Phase 05 end-to-end tests: only SDK-serialized synthetic XDR.

No fake event is described as a confirmed ETL discrepancy. The candidate
rows are generated from the same synthetic source using verified ETL rules.
"""
import base64
import contextlib
from dataclasses import replace
import io
import json
import tempfile
import unittest
from pathlib import Path

from stellar_sdk import StrKey, xdr

from ledgerverity.cli import main
from ledgerverity.formats import FORMAT, CandidateScope, parse_candidate_row
from ledgerverity.reconcile import (
    ReconcileInputError, _toid, compare_source_candidate,
)
from ledgerverity.source import DecodedLedger, SourceEvent, SourceSnapshot, _decode_ledger
from test_transaction_meta import ledger_with_tx
from test_canonical import source as small_source, event_xdr

P = "Test SDF Network ; September 2015"
SCOPE = CandidateScope(P,1234,1234,"stellar-etl","synthetic fixture")
TX = "ab" * 32


def make_snapshot(success=True, meta_version=4):
    ledger = _decode_ledger(ledger_with_tx(meta_version=meta_version, success=success))
    return SourceSnapshot(P,1234,1234,(ledger,),(),"f"*64)


def candidate(ev, line=1, **changes):
    obj = xdr.ContractEvent.from_xdr(ev.contract_event_xdr)
    flag = ev.diagnostic_success if ev.stream == "diagnostic" else True
    diag = xdr.DiagnosticEvent(in_successful_contract_call=flag, event=obj)
    topics = obj.body.v0.topics
    op = ev.operation_ordinal if ev.stream == "operation" else None
    row = {
        "transaction_hash": ev.tx_hash, "transaction_id": str(_toid(ev.ledger, ev.tx_ordinal, None)),
        "successful": ev.tx_success, "ledger_sequence": ev.ledger,
        "in_successful_contract_call": flag,
        "contract_id": StrKey.encode_contract(obj.contract_id.contract_id.hash)
                       if obj.contract_id else "",
        "type": int(obj.type), "type_string": obj.type.name,
        "topics": [base64.b64encode(x.to_xdr_bytes()).decode() for x in topics],
        "data": base64.b64encode(obj.body.v0.data.to_xdr_bytes()).decode(),
        "operation_id": str(_toid(ev.ledger, ev.tx_ordinal, op)) if op is not None else None,
        "contract_event_xdr": diag.to_xdr(),
    }
    row.update(changes)
    return parse_candidate_row(row,line,SCOPE)


def full_candidate(snapshot):
    return [candidate(ev, i+1) for i,ev in
            enumerate([ev for ld in snapshot.ledgers for ev in ld.events])]


def altered(snapshot, **kw):
    return replace(snapshot,**kw)


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = make_snapshot()
        self.rows = full_candidate(self.snapshot)

    def compare(self,snapshot=None,rows=None,scope=SCOPE):
        return compare_source_candidate(snapshot or self.snapshot, scope,
                                        self.rows if rows is None else rows)

    def test_exact_synthetic_export_same_multiset(self):
        r=self.compare()
        self.assertEqual(r["summary"]["source_events"],4)
        self.assertEqual(r["summary"]["exact_xdr_matches"],4)
        self.assertEqual(r["summary"]["candidate_rows"],4)
        self.assertEqual(r["summary"]["source_only"],0)
        self.assertEqual(r["summary"]["candidate_only"],0)
        self.assertEqual(r["status"],"INCONCLUSIVE")
        self.assertFalse(r["reconciliation_proven"])
        self.assertFalse(r["source_provenance_verified"])
        self.assertFalse(r["candidate_export_coverage_verified"])

    def test_duplicate_looking_operation_payloads_both_matched(self):
        self.assertEqual(self.rows[1].raw["contract_event_xdr"],self.rows[2].raw["contract_event_xdr"])
        self.assertEqual(self.compare()["summary"]["exact_xdr_matches"],4)

    def test_missing_one_of_two_identical_operation_rows(self):
        r=self.compare(rows=self.rows[:2]+self.rows[3:])
        self.assertEqual(r["summary"]["source_only"],1)
        self.assertEqual(r["summary"]["exact_xdr_matches"],3)
        self.assertEqual(r["status"],"REVIEW_REQUIRED")
        self.assertTrue(any(f["code"]=="SOURCE_ONLY_OBSERVATION" for f in r["findings"]))
        self.assertFalse(r["reconciliation_proven"])

    def test_extra_indistinguishable_candidate_row_not_a_confirmed_duplicate(self):
        r=self.compare(rows=self.rows+[self.rows[1]])
        self.assertEqual(r["summary"]["candidate_only"],1)
        self.assertEqual(r["summary"]["exact_xdr_matches"],4)
        self.assertEqual(r["status"],"REVIEW_REQUIRED")
        self.assertFalse(r["reconciliation_proven"])

    def test_one_different_payload_produces_two_unpaired_observations(self):
        changed = candidate(self.snapshot.ledgers[0].events[1],2,
                            contract_event_xdr=self.rows[0].raw["contract_event_xdr"])
        r=self.compare(rows=[self.rows[0],changed,*self.rows[2:]])
        self.assertGreater(r["summary"]["source_only"],0)
        self.assertGreater(r["summary"]["candidate_only"],0)
        self.assertTrue(r["observed_differences"])

    def test_unmatched_candidate_has_explicit_candidate_line(self):
        r=self.compare(rows=self.rows+[self.rows[1]])
        self.assertIn("candidate_line",next(f for f in r["findings"] if f["code"]=="CANDIDATE_ONLY_OBSERVATION"))

    def test_missing_xdr_cannot_claim_missing_original_event(self):
        changed=candidate(self.snapshot.ledgers[0].events[1],2,contract_event_xdr=None)
        r=self.compare(rows=[self.rows[0],changed,*self.rows[2:]])
        self.assertEqual(r["status"],"INCONCLUSIVE")
        self.assertEqual(r["summary"]["unmatchable_candidate_rows"],1)
        self.assertFalse(r["reconciliation_proven"])

    def test_empty_candidate_is_not_a_verified_outage(self):
        r=self.compare(rows=[])
        self.assertEqual(r["summary"]["source_only"],4)
        self.assertEqual(r["status"],"REVIEW_REQUIRED")
        self.assertFalse(r["candidate_export_coverage_verified"])

    def test_source_and_candidate_empty_remains_inconclusive(self):
        ld=replace(self.snapshot.ledgers[0],events=())
        r=self.compare(snapshot=replace(self.snapshot,ledgers=(ld,)),rows=[])
        self.assertEqual(r["summary"]["exact_xdr_matches"],0)
        self.assertEqual(r["status"],"INCONCLUSIVE")

    def test_wrong_transaction_success_flag_is_observed(self):
        rows=self.rows.copy()
        rows[0]=candidate(self.snapshot.ledgers[0].events[0],1,successful=False)
        r=self.compare(rows=rows)
        self.assertEqual(r["summary"]["transaction_outcome_mismatches"],1)
        self.assertEqual(r["summary"]["exact_xdr_matches"],4)
        self.assertEqual(r["status"],"REVIEW_REQUIRED")

    def test_wrong_diagnostic_flag_changes_wrapper_and_field(self):
        ev=self.snapshot.ledgers[0].events[-1]
        rows=self.rows.copy()
        rows[-1]=candidate(ev,4,in_successful_contract_call=not ev.diagnostic_success)
        r=self.compare(rows=rows)
        self.assertEqual(r["summary"]["column_integrity_mismatches"],1)
        self.assertEqual(r["summary"]["exact_xdr_matches"],4)
        self.assertEqual(r["status"],"REVIEW_REQUIRED")

    def test_wrong_contract_id_inline_is_not_silently_ignored(self):
        rows=self.rows.copy()
        rows[0]=candidate(self.snapshot.ledgers[0].events[0],1,contract_id="not-the-contract")
        r=self.compare(rows=rows)
        self.assertEqual(r["summary"]["column_integrity_mismatches"],1)
        fields=[f["fields"] for f in r["findings"] if f["code"]=="COLUMN_INTEGRITY_DIFFERENCE"][0]
        self.assertIn("contract_id",fields)

    def test_wrong_event_type_inline_is_detected(self):
        rows=self.rows.copy()
        rows[0]=candidate(self.snapshot.ledgers[0].events[0],1,type=2)
        self.assertEqual(self.compare(rows=rows)["summary"]["column_integrity_mismatches"],1)

    def test_wrong_topics_and_data_inline_are_detected(self):
        rows=self.rows.copy()
        rows[0]=candidate(self.snapshot.ledgers[0].events[0],1,topics=[],data="wrong")
        r=self.compare(rows=rows)
        self.assertEqual(r["summary"]["column_integrity_mismatches"],1)
        fields=[f["fields"] for f in r["findings"] if f["code"]=="COLUMN_INTEGRITY_DIFFERENCE"][0]
        self.assertIn("topics",fields)
        self.assertIn("data",fields)

    def test_invalid_packed_toid_gives_inconclusive_not_source_defect(self):
        rows=self.rows.copy()
        rows[0]=candidate(self.snapshot.ledgers[0].events[0],1,transaction_id="1")
        r=self.compare(rows=rows)
        self.assertEqual(r["status"],"INCONCLUSIVE")
        self.assertEqual(r["summary"]["column_integrity_mismatches"],1)

    def test_missing_operation_id_breaks_only_operation_placement(self):
        rows=self.rows.copy()
        rows[1]=candidate(self.snapshot.ledgers[0].events[1],2,operation_id=None)
        r=self.compare(rows=rows)
        self.assertEqual(r["summary"]["source_only"],1)
        self.assertGreaterEqual(r["summary"]["candidate_only"],1)

    def test_no_operation_id_on_diagnostic_is_valid(self):
        self.assertIsNone(self.rows[-1].operation_id)
        self.assertEqual(self.compare()["summary"]["exact_xdr_matches"],4)

    def test_wrong_network_claim_is_rejected(self):
        with self.assertRaisesRegex(ReconcileInputError,"network claim"):
            self.compare(scope=replace(SCOPE,network_passphrase="Public Global Stellar Network"))

    def test_wrong_ledger_range_is_rejected(self):
        with self.assertRaisesRegex(ReconcileInputError,"ledger range"):
            self.compare(scope=replace(SCOPE,last_ledger=1235))

    def test_gap_in_source_forces_inconclusive(self):
        missing=replace(self.snapshot,first_ledger=1234,last_ledger=1235,gaps=(1235,))
        scope=replace(SCOPE,last_ledger=1235)
        result=self.compare(snapshot=missing,scope=scope)
        self.assertFalse(result["source_range_observed_complete"])
        self.assertEqual(result["status"],"INCONCLUSIVE")

    def test_unsupported_transaction_meta_forces_inconclusive(self):
        ld=replace(self.snapshot.ledgers[0],unsupported_tx_versions=(9,))
        result=self.compare(snapshot=replace(self.snapshot,ledgers=(ld,)))
        self.assertFalse(result["source_range_observed_complete"])
        self.assertEqual(result["status"],"INCONCLUSIVE")

    def test_unknown_source_transaction_success_rejected(self):
        ev=replace(self.snapshot.ledgers[0].events[0],tx_success=None)
        ld=replace(self.snapshot.ledgers[0],events=(ev,*self.snapshot.ledgers[0].events[1:]))
        with self.assertRaises(ReconcileInputError):
            self.compare(snapshot=replace(self.snapshot,ledgers=(ld,)))

    def test_bad_source_duplicate_locator_is_rejected(self):
        ev=self.snapshot.ledgers[0].events[0]
        ld=replace(self.snapshot.ledgers[0],events=(ev,ev))
        with self.assertRaisesRegex(Exception,"Repeated source-local"):
            self.compare(snapshot=replace(self.snapshot,ledgers=(ld,)))

    def test_raw_candidate_diagnostic_xdr_is_not_contract_xdr(self):
        wrapper=xdr.DiagnosticEvent.from_xdr(self.rows[0].raw["contract_event_xdr"])
        self.assertEqual(wrapper.event.to_xdr(),self.snapshot.ledgers[0].events[0].contract_event_xdr)

    def test_invalid_base64_diagnostic_xdr_is_input_error(self):
        rows=self.rows.copy()
        rows[0]=candidate(self.snapshot.ledgers[0].events[0],1,contract_event_xdr="abcd")
        with self.assertRaisesRegex(ReconcileInputError,"DiagnosticEvent"):
            self.compare(rows=rows)

    def test_truncated_diagnostic_xdr_is_input_error(self):
        blob=base64.b64encode(b"bad").decode()
        rows=self.rows.copy()
        rows[0]=candidate(self.snapshot.ledgers[0].events[0],1,contract_event_xdr=blob)
        with self.assertRaises(ReconcileInputError):
            self.compare(rows=rows)

    def test_noncanonical_base64_diagnostic_xdr_fails_closed(self):
        rows=self.rows.copy()
        rows[0]=candidate(self.snapshot.ledgers[0].events[0],1,
                          contract_event_xdr=self.rows[0].raw["contract_event_xdr"]+"\\n")
        with self.assertRaises(ReconcileInputError):
            self.compare(rows=rows)

    def test_ineligible_toid_ranges_explicitly_rejected(self):
        cases=[(0,1,None),(2**31,1,None),(1,0,None),(1,2**20,None),(1,1,4095)]
        for case in cases:
            with self.subTest(case=case),self.assertRaises(ReconcileInputError):
                _toid(*case)

    def test_known_toid_bit_layout(self):
        self.assertEqual(_toid(1,1,None),2**32+4096)
        self.assertEqual(_toid(1,1,0),2**32+4097)
        self.assertEqual(_toid(1,1,1),2**32+4098)

    def test_v3_legacy_contract_and_diagnostics_match(self):
        source=make_snapshot(meta_version=3)
        rows=full_candidate(source)
        r=self.compare(snapshot=source,rows=rows)
        self.assertEqual(r["summary"]["exact_xdr_matches"],3)
        self.assertEqual(r["status"],"INCONCLUSIVE")

    def test_failed_transaction_still_matches_xdr_but_no_certification(self):
        snap=make_snapshot(success=False)
        r=self.compare(snapshot=snap,rows=full_candidate(snap))
        self.assertEqual(r["summary"]["transaction_outcome_mismatches"],0)
        self.assertEqual(r["status"],"INCONCLUSIVE")

    def test_deterministic_report_when_candidate_order_changes(self):
        r1=self.compare(rows=self.rows)
        r2=self.compare(rows=list(reversed(self.rows)))
        self.assertEqual(r1["summary"],r2["summary"])
        self.assertEqual(r1["status"],r2["status"])

    def test_large_findings_bounded_to_100(self):
        rows=self.rows+([self.rows[0]] * 130)
        r=self.compare(rows=rows)
        self.assertEqual(r["summary"]["candidate_only"],130)
        self.assertEqual(len(r["findings"]),100)
        self.assertTrue(r["findings_truncated"])

    def test_no_network_requests_for_direct_comparison(self):
        from unittest.mock import patch
        with patch("urllib.request.urlopen",side_effect=AssertionError("Network access!")):
            self.assertEqual(self.compare()["summary"]["exact_xdr_matches"],4)


class ReconcileCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)
        self.source_path=self.folder/"source.json"
        self.candidate_path=self.folder/"candidate.jsonl"
        self.scope_path=self.folder/"scope.json"
        ledger=ledger_with_tx()
        self.source_path.write_text(json.dumps({"jsonrpc":"2.0","id":1,"result":{"ledgers":[ledger]}}))
        snapshot=make_snapshot()
        self.candidate_path.write_text("\n".join(json.dumps(r.raw) for r in full_candidate(snapshot))+"\n")
        self.scope_path.write_text(json.dumps({
            "format":FORMAT, "network_passphrase":P,"first_ledger":1234,
            "last_ledger":1234,"exporter":"stellar-etl","source_description":"synthetic testing",
        }))

    def run_cli(self,*extra):
        out,err=io.StringIO(),io.StringIO()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            rc=main(["reconcile","--source",str(self.source_path),
                     "--candidate",str(self.candidate_path),
                     "--scope",str(self.scope_path),*extra])
        return rc,out.getvalue(),err.getvalue()

    def test_end_to_end_cli_json_on_synthetic_xdr(self):
        rc,out,err=self.run_cli("--format","json")
        self.assertEqual((rc,err),(3,""))
        obj=json.loads(out)
        self.assertEqual(obj["summary"]["exact_xdr_matches"],4)
        self.assertEqual(obj["status"],"INCONCLUSIVE")
        self.assertFalse(obj["reconciliation_proven"])

    def test_cli_text_no_false_success_claim(self):
        rc,out,err=self.run_cli()
        self.assertEqual(rc,3)
        self.assertEqual(err,"")
        self.assertIn("NOT VERIFIED",out)
        self.assertIn("Confirmed discrepancies: NONE",out)

    def test_cli_missing_row_review_only(self):
        rows=self.candidate_path.read_text().splitlines()
        self.candidate_path.write_text("\n".join(rows[:-1])+"\n")
        rc,out,_=self.run_cli("--format","json")
        self.assertEqual(rc,3)
        self.assertEqual(json.loads(out)["status"],"REVIEW_REQUIRED")

    def test_cli_invalid_scope_exit_two(self):
        obj=json.loads(self.scope_path.read_text())
        obj["first_ledger"]=0
        self.scope_path.write_text(json.dumps(obj))
        rc,out,err=self.run_cli()
        self.assertEqual(rc,2)
        self.assertEqual(out,"")
        self.assertTrue(err.startswith("ledgerverity:"))

    def test_cli_malformed_source_exit_two(self):
        self.source_path.write_text("{x")
        rc,out,err=self.run_cli()
        self.assertEqual(rc,2)
        self.assertEqual(out,"")
        self.assertIn("invalid JSON",err)

    def test_cli_malformed_candidate_exit_two(self):
        self.candidate_path.write_text("{x")
        rc,out,err=self.run_cli()
        self.assertEqual(rc,2)
        self.assertEqual(out,"")
        self.assertIn("invalid JSON",err)

    def test_cli_output_file_stable(self):
        p=self.folder/"report.json"
        rc,out,err=self.run_cli("--output",str(p),"--format","json")
        self.assertEqual((rc,out,err),(3,"",""))
        first=p.read_bytes()
        self.assertEqual(self.run_cli("--output",str(p),"--format","json")[0],3)
        self.assertEqual(p.read_bytes(),first)

    def test_cli_bad_output_path_exit_two(self):
        p=self.folder/"missing"/"report.json"
        rc,out,err=self.run_cli("--output",str(p))
        self.assertEqual(rc,2)
        self.assertEqual(out,"")
        self.assertIn("unable to write",err)


if __name__=="__main__":
    unittest.main()
