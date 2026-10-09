import json
import tempfile
import unittest
from pathlib import Path
from ledgerverity.audit import audit, read_jsonl, AuditInputError
from ledgerverity.cli import main


def row(**changes):
    value = dict(transaction_id=1, ledger_sequence=10, type_string="Contract", contract_id="C",
                 topics=["transfer", "A", "B"], data="X", operation_id=11,
                 successful=True, in_successful_contract_call=True)
    value.update(changes)
    return value


class AuditTests(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(audit([row()])["status"], "NO_ISSUES_DETECTED")

    def test_possible_duplicate_requires_different_operation_id_presence(self):
        data = audit([row(), row(operation_id=None)])
        self.assertEqual(data["status"], "REVIEW_REQUIRED")
        self.assertEqual([f["code"] for f in data["findings"]], ["POSSIBLE_DIAGNOSTIC_DUPLICATE"])

    def test_identical_payload_same_operation_identity_not_claimed_duplicate(self):
        self.assertEqual(audit([row(), row()])["status"], "NO_ISSUES_DETECTED")

    def test_different_transaction_is_not_duplicate(self):
        self.assertEqual(audit([row(), row(transaction_id=2, operation_id=None)])["status"], "NO_ISSUES_DETECTED")

    def test_failed_transaction_flag_review(self):
        r = audit([row(successful=False)])
        self.assertIn("POSSIBLE_SUCCESS_FLAG_MISMATCH", [f["code"] for f in r["findings"]])

    def test_duplicate_canonical_event_id_is_error(self):
        r = audit([row(event_id="evt1"), row(event_id="evt1")])
        self.assertEqual(r["status"], "ERRORS")
        self.assertIn("DUPLICATE_EVENT_ID", [f["code"] for f in r["findings"]])

    def test_malformed_row_review(self):
        r = audit([{"transaction_id": "tx1", "topics": []}])
        self.assertEqual(r["status"], "REVIEW_REQUIRED")
        self.assertEqual(len(r["findings"]), 3)

    def test_missing_transaction_id(self):
        self.assertEqual(audit([row(transaction_id=None)])["status"], "ERRORS")

    def test_invalid_json_fails_safely(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.jsonl"
            p.write_text('{invalid', encoding="utf-8")
            with self.assertRaises(AuditInputError):
                read_jsonl(p)

    def test_nonobject_fails_safely(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.jsonl"
            p.write_text('[]\n', encoding="utf-8")
            with self.assertRaises(AuditInputError):
                read_jsonl(p)

    def test_line_limit(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "oversized.jsonl"
            p.write_bytes(b' ' * 256001 + b'\n')
            with self.assertRaises(AuditInputError):
                read_jsonl(p)

    def test_deterministic_findings(self):
        sample = [row(), row(operation_id=None), row(transaction_id=2, successful=False)]
        self.assertEqual(json.dumps(audit(sample), sort_keys=True), json.dumps(audit(sample), sort_keys=True))

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "input.jsonl"
            p.write_text(json.dumps(row()) + '\n', encoding="utf-8")
            self.assertEqual(main([str(p), "--format", "json", "--output", str(Path(d)/"out.json")]), 0)
            result = json.loads((Path(d)/"out.json").read_text())
            self.assertEqual(result["rows_scanned"], 1)
            p.write_text(json.dumps(row(successful=False)) + '\n', encoding="utf-8")
            self.assertEqual(main([str(p), "--output", str(Path(d)/"out.txt")]), 3)
            p.write_text(json.dumps(row(event_id="x"))+'\n'+json.dumps(row(event_id="x"))+'\n')
            self.assertEqual(main([str(p), "--output", str(Path(d)/"out.txt")]), 1)
            p.write_text('{invalid')
            self.assertEqual(main([str(p)]), 2)


if __name__ == "__main__":
    unittest.main()
