"""Candidate-format tests. All inputs are synthetic, not production evidence."""
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from ledgerverity.formats import (
    CandidateFormatError, CandidateScope, FORMAT, MAX_LINE_BYTES,
    parse_candidate_row, read_candidate_scope, read_etl_candidate_jsonl,
)

def sample(**override):
    row = {
        "transaction_hash": "a" * 64,
        "transaction_id": "9223372036854775807",
        "successful": True,
        "ledger_sequence": 100,
        "in_successful_contract_call": True,
        "contract_id": "C123",
        "type": 1,
        "type_string": "Contract",
        "topics": ["foo", "bar"],
        "data": {"value": "340282366920938463463374607431768211455"},
        "operation_id": None,
    }
    row.update(override)
    return row

SCOPE = CandidateScope("Test SDF Network ; September 2015", 100, 120, "stellar-etl", "test")

class CandidateFormatTests(unittest.TestCase):
    def test_valid_stellar_etl_shape(self):
        result = parse_candidate_row(sample(), 3, SCOPE)
        self.assertEqual((result.line, result.ledger_sequence), (3, 100))
        self.assertEqual(result.transaction_id, 2**63 - 1)
        self.assertIsNone(result.operation_id)

    def test_numeric_ids_and_uppercase_hash_normalize(self):
        result = parse_candidate_row(sample(transaction_id=1, operation_id="42", transaction_hash="A"*64), 1, SCOPE)
        self.assertEqual((result.transaction_id, result.operation_id), (1, 42))
        self.assertEqual(result.transaction_hash, "a"*64)

    def test_two_identical_rows_are_not_automatically_deduplicated(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "candidate.jsonl"
            p.write_text((json.dumps(sample()) + "\n") * 2, encoding="utf-8")
            self.assertEqual(len(read_etl_candidate_jsonl(p, SCOPE)), 2)

    def test_empty_file_is_not_completeness_proof(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "candidate.jsonl"
            p.write_bytes(b"")
            self.assertEqual(read_etl_candidate_jsonl(p, SCOPE), [])
            self.assertFalse(SCOPE.coverage_verified)

    def test_rejects_missing_field(self):
        invalid = sample()
        invalid.pop("operation_id")
        with self.assertRaisesRegex(CandidateFormatError, "missing fields"):
            parse_candidate_row(invalid, 1, SCOPE)

    def test_rejects_unknown_field(self):
        with self.assertRaisesRegex(CandidateFormatError, "unsupported fields"):
            parse_candidate_row(sample(arbitrary="discard-me"), 1, SCOPE)

    def test_rejects_bad_hash(self):
        with self.assertRaisesRegex(CandidateFormatError, "transaction_hash"):
            parse_candidate_row(sample(transaction_hash="abc"), 1, SCOPE)

    def test_rejects_boolean_integer_confusion(self):
        for field in ("ledger_sequence", "transaction_id", "operation_id", "type"):
            with self.subTest(field=field):
                with self.assertRaises(CandidateFormatError):
                    parse_candidate_row(sample(**{field: True}), 1, SCOPE)

    def test_rejects_incorrect_bool_field(self):
        for field in ("successful", "in_successful_contract_call"):
            with self.subTest(field=field):
                with self.assertRaises(CandidateFormatError):
                    parse_candidate_row(sample(**{field: "false"}), 1, SCOPE)

    def test_rejects_wrong_topics_type(self):
        with self.assertRaisesRegex(CandidateFormatError, "topics"):
            parse_candidate_row(sample(topics="[]"), 1, SCOPE)

    def test_rejects_wrong_optional_type(self):
        for key, val in (("closed_at", 3), ("topics_decoded", {}), ("contract_event_xdr", 1)):
            with self.subTest(key=key), self.assertRaises(CandidateFormatError):
                parse_candidate_row(sample(**{key: val}), 1, SCOPE)

    def test_network_passphrase_does_not_validate_itself(self):
        self.assertFalse(SCOPE.provenance_verified)

    def test_rejects_mixed_out_of_range_rows(self):
        with self.assertRaisesRegex(CandidateFormatError, "outside declared scope"):
            parse_candidate_row(sample(ledger_sequence=121), 1, SCOPE)

    def test_accepts_edge_ledger_sequences(self):
        scope = replace(SCOPE, first_ledger=1, last_ledger=2**32-1)
        self.assertEqual(parse_candidate_row(sample(ledger_sequence=2**32-1), 1, scope).ledger_sequence, 2**32-1)

    def test_rejects_u32_overflow(self):
        with self.assertRaises(CandidateFormatError):
            parse_candidate_row(sample(ledger_sequence=2**32), 1, replace(SCOPE, last_ledger=2**32-1))

    def test_rejects_i64_overflow(self):
        with self.assertRaises(CandidateFormatError):
            parse_candidate_row(sample(transaction_id="9223372036854775808"), 1, SCOPE)

    def test_rejects_leading_zero_integer_strings(self):
        with self.assertRaises(CandidateFormatError):
            parse_candidate_row(sample(transaction_id="001"), 1, SCOPE)

    def test_preserves_huge_integer_as_string_payload(self):
        item = parse_candidate_row(sample(), 1, SCOPE)
        self.assertEqual(item.data["value"], "340282366920938463463374607431768211455")

    def test_rejects_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "dupes.jsonl"
            p.write_text('{"transaction_id":1,"transaction_id":2}\n', encoding="utf-8")
            with self.assertRaisesRegex(CandidateFormatError, "Duplicate JSON key"):
                read_etl_candidate_jsonl(p, SCOPE)

    def test_rejects_float_tokens_before_precision_loss(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "float.jsonl"
            p.write_text(json.dumps(sample()).replace('"value": "340282366920938463463374607431768211455"', '"value": 1.25'), encoding="utf-8")
            with self.assertRaisesRegex(CandidateFormatError, "Floating-point"):
                read_etl_candidate_jsonl(p, SCOPE)

    def test_rejects_nan(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "nan.jsonl"
            p.write_text('{"x":NaN}', encoding="utf-8")
            with self.assertRaises(CandidateFormatError):
                read_etl_candidate_jsonl(p, SCOPE)

    def test_rejects_malformed_utf8(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.jsonl"
            p.write_bytes(b'\xff\n')
            with self.assertRaisesRegex(CandidateFormatError, "UTF-8"):
                read_etl_candidate_jsonl(p, SCOPE)

    def test_rejects_nonobject_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.jsonl"
            p.write_text('[1,2]\n', encoding="utf-8")
            with self.assertRaises(CandidateFormatError):
                read_etl_candidate_jsonl(p, SCOPE)

    def test_rejects_line_overflow(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "big.jsonl"
            p.write_bytes(b' ' * (MAX_LINE_BYTES + 1))
            with self.assertRaisesRegex(CandidateFormatError, "256 KB"):
                read_etl_candidate_jsonl(p, SCOPE)

    def test_extremely_long_numeric_token_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "huge-int.jsonl"
            p.write_text('{"n":' + '8' * 4500 + '}\n', encoding="utf-8")
            with self.assertRaisesRegex(CandidateFormatError, "integer size"):
                read_etl_candidate_jsonl(p, SCOPE)

    def test_manifest_duplicate_fields_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "manifest.json"
            p.write_text('{"format":"wrong","format":"wrong"}', encoding="utf-8")
            with self.assertRaisesRegex(CandidateFormatError, "Duplicate JSON key"):
                read_candidate_scope(p)

    def test_manifest_zero_or_missing_ledger_rejected(self):
        for bad in [0, -1, True, "-1", "01", 2**32]:
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as d:
                p = Path(d) / "scope.json"
                obj = dict(format=FORMAT, network_passphrase=SCOPE.network_passphrase,
                           first_ledger=bad, last_ledger=120, exporter="stellar-etl",
                           source_description="synthetic")
                p.write_text(json.dumps(obj), encoding="utf-8")
                with self.assertRaises(CandidateFormatError):
                    read_candidate_scope(p)

    def test_extra_manifest_fields_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "scope.json"
            obj = dict(format=FORMAT, network_passphrase=SCOPE.network_passphrase,
                       first_ledger=100, last_ledger=120, exporter="stellar-etl",
                       source_description="synthetic", coverage_verified=True)
            p.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaisesRegex(CandidateFormatError, "exactly"):
                read_candidate_scope(p)

    def test_invalid_nonfinite_in_nested_data_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.jsonl"
            p.write_text(json.dumps(sample()).replace('"value": "340282366920938463463374607431768211455"', '"value": Infinity'))
            with self.assertRaisesRegex(CandidateFormatError, "Non-JSON numeric constant"):
                read_etl_candidate_jsonl(p, SCOPE)

    def test_missing_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(CandidateFormatError, "regular file"):
                read_etl_candidate_jsonl(Path(d) / "missing.jsonl", SCOPE)

    def test_manifest_valid_and_unverified(self):
        manifest = dict(format=FORMAT, network_passphrase=SCOPE.network_passphrase,
                        first_ledger=100, last_ledger=120, exporter="stellar-etl",
                        source_description="fixture")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "manifest.json"
            p.write_text(json.dumps(manifest))
            result = read_candidate_scope(p)
            self.assertEqual((result.first_ledger, result.last_ledger), (100, 120))
            self.assertFalse(result.coverage_verified)
            self.assertFalse(result.provenance_verified)

    def test_manifest_rejects_reversed_scope(self):
        manifest = dict(format=FORMAT, network_passphrase=SCOPE.network_passphrase,
                        first_ledger=120, last_ledger=100, exporter="stellar-etl",
                        source_description="fixture")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "manifest.json"
            p.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(CandidateFormatError, "reversed"):
                read_candidate_scope(p)

    def test_manifest_rejects_unrecognized_version(self):
        manifest = dict(format="unknown", network_passphrase=SCOPE.network_passphrase,
                        first_ledger=100, last_ledger=120, exporter="stellar-etl",
                        source_description="fixture")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "manifest.json"
            p.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(CandidateFormatError, "Unsupported candidate format"):
                read_candidate_scope(p)

if __name__ == "__main__":
    unittest.main()
