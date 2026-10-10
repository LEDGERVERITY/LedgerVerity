"""Phase 06 reporting/CI tests; only SDK-serialized synthetic event data."""
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ledgerverity.cli import main
from ledgerverity.ci_gate import CIGateError, evaluate_report, main as gate_main
from ledgerverity.reporting import ReportingError, render_markdown, annotate_report
from test_reconcile import FORMAT, P, make_snapshot, full_candidate
from test_transaction_meta import ledger_with_tx


class ReportingTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.dir = Path(td.name)
        self.source = self.dir / "source.json"
        self.candidate = self.dir / "candidate.jsonl"
        self.scope = self.dir / "scope.json"
        self.source.write_text(json.dumps({"jsonrpc":"2.0","id":1,
                                            "result":{"ledgers":[ledger_with_tx()]}}))
        self.candidate.write_text("".join(json.dumps(r.raw)+"\n" for r in full_candidate(make_snapshot())))
        self.scope.write_text(json.dumps({
            "format":FORMAT, "network_passphrase":P,
            "first_ledger":1234, "last_ledger":1234,
            "exporter":"synthetic", "source_description":"not real ETL data"
        }))

    def invoke(self,*extra):
        out,err=io.StringIO(),io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code=main(["reconcile","--source",str(self.source),
                       "--candidate",str(self.candidate),"--scope",str(self.scope),*extra])
        return code,out.getvalue(),err.getvalue()

    def report(self):
        rc,out,err=self.invoke("--format","json")
        self.assertEqual((rc,err),(3,""))
        return json.loads(out)

    def test_schema_additive_and_declared_unverified(self):
        r=self.report()
        self.assertEqual(r["schema_version"],1)
        self.assertEqual(r["report_contract"],"ledgerverity.reconciliation-report.v1")
        self.assertEqual(r["status"],"INCONCLUSIVE")
        self.assertEqual(r["summary"]["exact_xdr_matches"],4)
        self.assertFalse(r["reconciliation_proven"])
        self.assertFalse(r["evidence_gates"]["independent_source_provenance"])
        self.assertFalse(r["evidence_gates"]["complete_candidate_export"])

    def test_content_fingerprints_are_real_byte_digests(self):
        r=self.report()["evidence_fingerprints"]
        for field,path in (("source_capture_sha256",self.source),
                           ("candidate_file_sha256",self.candidate),
                           ("scope_manifest_sha256",self.scope)):
            with self.subTest(field=field):
                self.assertEqual(r[field],hashlib.sha256(path.read_bytes()).hexdigest())

    def test_fingerprints_change_when_candidate_bytes_change(self):
        a=self.report()["evidence_fingerprints"]["candidate_file_sha256"]
        self.candidate.write_bytes(self.candidate.read_bytes()+b"\n")
        b=self.report()["evidence_fingerprints"]["candidate_file_sha256"]
        self.assertNotEqual(a,b)

    def test_identical_input_yields_exactly_stable_json(self):
        a=self.invoke("--format","json")[1]
        b=self.invoke("--format","json")[1]
        self.assertEqual(a,b)

    def test_markdown_report_has_all_relevant_evidence_limits(self):
        rc,out,err=self.invoke("--format","markdown")
        self.assertEqual((rc,err),(3,""))
        self.assertIn("NOT VERIFIED",out)
        self.assertIn("SHA-256",out)
        self.assertIn("Exact XDR pairs | 4",out)
        self.assertNotIn("proven defect",out.lower())

    def test_untrusted_manifest_markdown_injection_not_echoed(self):
        obj=json.loads(self.scope.read_text())
        obj["source_description"]="## EVIL-HEADING\n<script>bad</script>"
        obj["exporter"]="[fake](https://evil.invalid)"
        self.scope.write_text(json.dumps(obj))
        rc,out,err=self.invoke("--format","markdown")
        self.assertEqual((rc,err),(3,""))
        self.assertNotIn("EVIL-HEADING",out)
        self.assertNotIn("<script>",out)
        self.assertNotIn("evil.invalid",out)

    def test_missing_candidate_row_produces_actionable_guidance(self):
        self.candidate.write_text("\n".join(self.candidate.read_text().splitlines()[:-1])+"\n")
        report=self.report()
        self.assertEqual(report["status"],"REVIEW_REQUIRED")
        self.assertEqual(report["summary"]["source_only"],1)
        f=next(x for x in report["findings"] if x["code"]=="SOURCE_ONLY_OBSERVATION")
        self.assertEqual(f["classification"],"OBSERVATION_NOT_CONFIRMED")
        self.assertIn("export",f["suggested_check"])
        self.assertFalse(report["reconciliation_proven"])
        self.assertEqual(len(report["review_guidance"]),1)

    def test_markdown_summary_output_matches_markdown_format(self):
        out_path=self.dir/"summary.md"
        rc,out,err=self.invoke("--format","json","--summary-output",str(out_path))
        self.assertEqual((rc,err),(3,""))
        expected=self.invoke("--format","markdown")[1]
        self.assertEqual(out_path.read_text(),expected)
        self.assertTrue(out.startswith("{"))

    def test_write_json_and_summary_outputs(self):
        json_out=self.dir/"report.json"; md_out=self.dir/"summary.md"
        rc,out,err=self.invoke("--format","json","--output",str(json_out),
                                "--summary-output",str(md_out))
        self.assertEqual((rc,out,err),(3,"",""))
        self.assertEqual(json.loads(json_out.read_text())["status"],"INCONCLUSIVE")
        self.assertIn("NOT VERIFIED",md_out.read_text())

    def test_existing_output_file_replaced_deterministically(self):
        out=self.dir/"report.json"
        out.write_text("stale data")
        self.assertEqual(self.invoke("--format","json","--output",str(out))[0],3)
        first=out.read_bytes()
        self.assertEqual(self.invoke("--format","json","--output",str(out))[0],3)
        self.assertEqual(first,out.read_bytes())

    def test_source_overwrite_refused_and_unmodified(self):
        before=self.source.read_bytes()
        rc,out,err=self.invoke("--output",str(self.source))
        self.assertEqual((rc,out),(2,""))
        self.assertIn("must not overwrite",err)
        self.assertEqual(before,self.source.read_bytes())

    def test_candidate_overwrite_refused(self):
        before=self.candidate.read_bytes()
        rc,out,err=self.invoke("--summary-output",str(self.candidate))
        self.assertEqual((rc,out),(2,""))
        self.assertEqual(before,self.candidate.read_bytes())

    def test_scope_overwrite_refused(self):
        before=self.scope.read_bytes()
        rc,out,err=self.invoke("--output",str(self.scope))
        self.assertEqual((rc,out),(2,""))
        self.assertEqual(before,self.scope.read_bytes())

    def test_duplicate_output_target_refused(self):
        p=self.dir/"same.txt"
        rc,out,err=self.invoke("--output",str(p),"--summary-output",str(p))
        self.assertEqual((rc,out),(2,""))
        self.assertIn("must be different",err)

    def test_symlink_alias_to_input_is_refused(self):
        p=self.dir/"source-alias.json"
        try:
            p.symlink_to(self.source)
        except OSError:
            self.skipTest("Symlinks unavailable")
        rc,out,err=self.invoke("--summary-output",str(p))
        self.assertEqual((rc,out),(2,""))
        self.assertIn("must not overwrite",err)

    def test_failed_write_leaves_existing_output_unmodified(self):
        report=self.dir/"existing.json"
        report.write_text("keep-me")
        missing=self.dir/"missing"/"summary.md"
        rc,out,err=self.invoke("--output",str(report),"--summary-output",str(missing))
        self.assertEqual((rc,out),(2,""))
        self.assertEqual(report.read_text(),"keep-me")
        self.assertIn("unable to write",err)

    def test_cannot_write_into_missing_directory(self):
        rc,out,err=self.invoke("--output",str(self.dir/"nope"/"r.json"))
        self.assertEqual((rc,out),(2,""))
        self.assertIn("unable to write",err)

    def test_status_stays_inconclusive_on_exact_match(self):
        r=self.report()
        self.assertEqual(r["summary"]["source_only"],0)
        self.assertEqual(r["status"],"INCONCLUSIVE")

    def test_report_without_valid_source_digest_fails_closed(self):
        from ledgerverity.reconcile import compare_source_candidate
        from ledgerverity.formats import read_candidate_scope,read_etl_candidate_jsonl
        from ledgerverity.source import read_source_capture
        scope=read_candidate_scope(self.scope)
        snap=read_source_capture(self.source,1234,1234,P)
        comp=compare_source_candidate(snap,scope,read_etl_candidate_jsonl(self.candidate,scope))
        self.source.write_bytes(self.source.read_bytes()+b"\n")
        with self.assertRaisesRegex(ReportingError,"changed"):
            annotate_report(comp,self.source,self.candidate,self.scope)

    def test_invalid_proven_claim_cannot_render(self):
        r=self.report()
        r["reconciliation_proven"]=True
        with self.assertRaises(ReportingError):
            render_markdown(r)


class GateTests(ReportingTests):
    def test_default_gate_treats_review_as_observation_not_proof(self):
        self.candidate.write_text("\n".join(self.candidate.read_text().splitlines()[:-1])+"\n")
        self.assertEqual(evaluate_report(self.report()),0)

    def test_opt_in_review_failure_is_policy_not_proof(self):
        self.candidate.write_text("\n".join(self.candidate.read_text().splitlines()[:-1])+"\n")
        self.assertEqual(evaluate_report(self.report(),fail_on_review=True),1)

    def test_clean_inconclusive_not_a_certification(self):
        self.assertEqual(evaluate_report(self.report(),True),0)
        self.assertFalse(self.report()["reconciliation_proven"])

    def test_gate_rejects_forged_proven_status(self):
        r=self.report()
        r["reconciliation_proven"]=True
        with self.assertRaises(CIGateError):
            evaluate_report(r)

    def test_gate_rejects_missing_evidence_gates(self):
        r=self.report()
        del r["evidence_gates"]
        with self.assertRaises(CIGateError):
            evaluate_report(r)

    def test_gate_rejects_forged_source_provenance(self):
        r=self.report()
        r["evidence_gates"]["independent_source_provenance"]=True
        with self.assertRaises(CIGateError):
            evaluate_report(r)

    def test_gate_rejects_malformed_hash(self):
        r=self.report()
        r["evidence_fingerprints"]["candidate_file_sha256"]="not-a-hash"
        with self.assertRaises(CIGateError):
            evaluate_report(r)

    def test_gate_rejects_invalid_report_status(self):
        r=self.report()
        r["status"]="PARITY_VERIFIED"
        with self.assertRaises(CIGateError):
            evaluate_report(r)

    def test_gate_rejects_boolean_counts(self):
        r=self.report()
        r["summary"]["exact_xdr_matches"]=True
        with self.assertRaises(CIGateError):
            evaluate_report(r)

    def test_gate_rejects_review_without_observations(self):
        r=self.report()
        r["status"]="REVIEW_REQUIRED"
        with self.assertRaises(CIGateError):
            evaluate_report(r)

    def test_installed_gate_cli_exit_codes(self):
        report=self.dir/"report.json"
        report.write_text(json.dumps(self.report()))
        stdout,stderr=io.StringIO(),io.StringIO()
        with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
            rc=gate_main(["--report",str(report)])
        self.assertEqual((rc,stderr.getvalue()),(0,""))
        self.assertIn("NOT VERIFIED",stdout.getvalue())

    def test_gate_rejects_malformed_json(self):
        p=self.dir/"broken.json";p.write_text("{")
        stderr=io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result=gate_main(["--report",str(p)])
        self.assertEqual(result,2)
        self.assertIn("invalid report",stderr.getvalue())

    def test_gate_rejects_nonfinite_json(self):
        p=self.dir/"nan.json";p.write_text('{"value":NaN}')
        self.assertEqual(gate_main(["--report",str(p)]),2)

    def test_gate_rejects_oversized_file(self):
        p=self.dir/"large.json";p.write_bytes(b" "*(2_000_001))
        self.assertEqual(gate_main(["--report",str(p)]),2)


if __name__ == "__main__":
    unittest.main()
