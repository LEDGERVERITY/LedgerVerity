"""Phase 03 source-snapshot input tests. All constructed snapshots are synthetic.

Protocol-specific XDR integration against a genuine provider is still required
before the full source-evidence milestone can be marked verified.
"""
import contextlib
import io
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from ledgerverity.source import (
    DecodedLedger, SourceInputError, SourceEvent, SourceSnapshot,
    _bytes, _decode_ledger, read_source_capture,
)
from ledgerverity.cli import main

HASH1 = "a" * 64
HASH2 = "b" * 64
HASH0 = "0" * 64
PASSPHRASE = "Test SDF Network ; September 2015"


def item(seq, hash_):
    return {
        "sequence": seq,
        "hash": hash_,
        "headerXdr": "AAAAAA==", "metadataXdr": "AAAAAQ==",
    }


def capture(items):
    return {"jsonrpc": "2.0", "id": 1, "result": {"ledgers": items, "latestLedger": 20, "oldestLedger": 1}}


def decoded(item_):
    seq = item_["sequence"]
    return DecodedLedger(seq, item_["hash"], HASH0 if seq == 10 else HASH1,
                         22, 1, (), ())


class SourceInputTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "source.json"
        self.path.write_text(json.dumps(capture([item(10, HASH1), item(11, HASH2)])), encoding="utf-8")

    def read(self, start=10, end=11):
        with patch("ledgerverity.source._decode_ledger", side_effect=decoded):
            return read_source_capture(self.path, start, end, PASSPHRASE)

    def test_contiguous_capture_not_trusted_or_complete(self):
        s = self.read()
        r = s.report()
        self.assertTrue(s.span_contiguous)
        self.assertEqual(r["ledgers_parsed"], 2)
        self.assertEqual(r["status"], "INCONCLUSIVE")
        for key in ["source_provenance_verified", "network_identity_verified",
                    "event_completeness_verified", "ledger_chain_anchored"]:
            self.assertFalse(r[key])
        self.assertTrue(r["header_hashes_checked"])
        self.assertTrue(r["adjacent_hash_links_checked"])

    def test_out_of_order_entries_sorted_for_chain(self):
        self.path.write_text(json.dumps(capture([item(11, HASH2), item(10, HASH1)])))
        self.assertEqual([l.sequence for l in self.read().ledgers], [10, 11])

    def test_source_snapshot_contains_capture_checksum(self):
        import hashlib
        self.assertEqual(self.read().captured_sha256, hashlib.sha256(self.path.read_bytes()).hexdigest())

    def test_missing_ledger_yields_inconclusive_not_clean(self):
        self.path.write_text(json.dumps(capture([item(10, HASH1)])))
        r = self.read().report()
        self.assertEqual(r["missing_ledger_sequences"], [11])
        self.assertFalse(r["ledger_span_contiguous"])

    def test_empty_ledger_list_is_inconclusive(self):
        self.path.write_text(json.dumps(capture([])))
        r = self.read().report()
        self.assertEqual(r["ledgers_parsed"], 0)
        self.assertEqual(r["missing_ledger_sequences"], [10, 11])
        self.assertFalse(r["header_hashes_checked"])
        self.assertFalse(r["adjacent_hash_links_checked"])

    def test_broken_adjacent_header_link_rejected(self):
        with patch("ledgerverity.source._decode_ledger", side_effect=[
            DecodedLedger(10, HASH1, HASH0, 22, 1, (), ()),
            DecodedLedger(11, HASH2, HASH0, 22, 1, (), ()),
        ]):
            with self.assertRaisesRegex(SourceInputError, "breaks"):
                read_source_capture(self.path, 10, 11, PASSPHRASE)

    def test_no_link_claim_across_missing_ledger(self):
        self.path.write_text(json.dumps(capture([item(10, HASH1), item(12, HASH2)])))
        self.assertEqual(self.read(10, 12).gaps, (11,))

    def test_reject_duplicate_sequence(self):
        self.path.write_text(json.dumps(capture([item(10, HASH1), item(10, HASH1)])))
        with self.assertRaisesRegex(SourceInputError, "Repeated"):
            self.read()

    def test_reject_out_of_scope_sequence(self):
        self.path.write_text(json.dumps(capture([item(10, HASH1), item(12, HASH2)])))
        with self.assertRaisesRegex(SourceInputError, "out-of-scope"):
            self.read()

    def test_reject_bad_api_envelope(self):
        for data in ({}, {"jsonrpc": "2.0", "error": {"code": -1}, "result": {"ledgers": []}},
                     {"jsonrpc": "1.0", "result": {"ledgers": []}}):
            with self.subTest(data=data):
                self.path.write_text(json.dumps(data))
                with self.assertRaises(SourceInputError):
                    self.read()

    def test_rejects_duplicate_json_keys(self):
        self.path.write_text('{"jsonrpc":"2.0","jsonrpc":"2.0"}')
        with self.assertRaisesRegex(SourceInputError, "Duplicate JSON key"):
            self.read()

    def test_reject_malformed_json(self):
        self.path.write_bytes(b"{bad")
        with self.assertRaises(SourceInputError):
            self.read()

    def test_reject_invalid_utf8(self):
        self.path.write_bytes(b"\xff")
        with self.assertRaises(SourceInputError):
            self.read()

    def test_reject_float_json(self):
        self.path.write_text('{"jsonrpc":"2.0","result":{"ledgers":[],"latestLedger":1.5}}')
        with self.assertRaises(SourceInputError):
            self.read()

    def test_reject_invalid_ledger_scope(self):
        for first, last in [(0, 1), (3, 2), (1, 30), (True, 2), (-1, 3), (1, 2**32)]:
            with self.subTest(first=first, last=last):
                with self.assertRaises(SourceInputError):
                    self.read(first, last)

    def test_reject_missing_or_empty_network_claim(self):
        with patch("ledgerverity.source._decode_ledger", side_effect=decoded):
            for claim in ("", " ", None):
                with self.subTest(claim=claim):
                    with self.assertRaises(SourceInputError):
                        read_source_capture(self.path, 10, 11, claim)

    def test_reject_more_than_25_entries(self):
        self.path.write_text(json.dumps(capture([item(10, HASH1)] * 26)))
        with self.assertRaisesRegex(SourceInputError, "25 ledgers"):
            self.read()

    def test_reject_oversized_capture(self):
        self.path.write_bytes(b" " * (12_000_001))
        with self.assertRaisesRegex(SourceInputError, "12 MB"):
            self.read()

    def test_xdr_base64_strictness(self):
        for bad in (None, 123, "!!!", "AQ==\n", "AQ", "AAAAA", "A==="):
            with self.subTest(bad=bad), self.assertRaises(SourceInputError):
                _bytes(bad, "xdr")
        self.assertEqual(_bytes("AQ==", "xdr"), b"\x01")

    def test_reject_malformed_xdr_via_sdk(self):
        with self.assertRaisesRegex(SourceInputError, "invalid or unsupported XDR"):
            _decode_ledger(item(10, HASH1))

    def test_reject_malformed_header_and_hash_before_decode(self):
        with self.assertRaisesRegex(SourceInputError, "hash"):
            _decode_ledger({**item(10, HASH1), "hash": "zzz"})

    def test_unsupported_tx_meta_versions_prohibit_stream_completeness(self):
        s = SourceSnapshot(PASSPHRASE, 10, 10,
            (DecodedLedger(10, HASH1, HASH0, 22, 1, (), (9,)),), (), "f"*64)
        self.assertFalse(s.report()["transaction_event_streams_decoded"])
        self.assertEqual(s.report()["ledger_headers"][0]["unsupported_transaction_metadata_versions"], [9])

    def test_diagnostic_and_contract_streams_never_deduplicate(self):
        import base64
        from stellar_sdk import xdr
        ev = xdr.ContractEvent(
            ext=xdr.ExtensionPoint(0), contract_id=None,
            type=xdr.ContractEventType.SYSTEM,
            body=xdr.ContractEventBody(v=0, v0=xdr.ContractEventV0(
                topics=[], data=xdr.SCVal(type=xdr.SCValType.SCV_VOID)
            ))
        ).to_xdr()
        items = (
            SourceEvent(10, HASH1, 1, "contract", 0, None, None, ev),
            SourceEvent(10, HASH1, 1, "diagnostic", 0, None, None, ev),
        )
        snap = SourceSnapshot(PASSPHRASE, 10, 10,
                              (DecodedLedger(10, HASH1, HASH0, 22, 1, items, ()),), (), "f"*64)
        self.assertEqual(snap.report()["event_counts_by_stream"]["contract"], 1)
        self.assertEqual(snap.report()["event_counts_by_stream"]["diagnostic"], 1)
        self.assertEqual(len(snap.report()["events"]), 2)

    def test_cli_emits_stable_inconclusive_json(self):
        out = io.StringIO()
        with patch("ledgerverity.source._decode_ledger", side_effect=decoded), contextlib.redirect_stdout(out):
            exit_code = main(["inspect-source", "--input", str(self.path), "--from-ledger", "10",
                              "--to-ledger", "11", "--network-passphrase", PASSPHRASE,
                              "--format", "json"])
        self.assertEqual(exit_code, 3)
        r = json.loads(out.getvalue())
        self.assertFalse(r["network_identity_verified"])
        self.assertEqual(r["missing_ledger_sequences"], [])

    def test_cli_malformed_input_exits_two_no_false_report(self):
        self.path.write_text('invalid')
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["inspect-source", "--input", str(self.path), "--from-ledger", "10",
                         "--to-ledger", "11", "--network-passphrase", PASSPHRASE, "--format", "json"])
        self.assertEqual(code, 2)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("ledgerverity:", err.getvalue())

    def test_cli_file_report_and_unwritable_destination(self):
        path = Path(self.directory.name) / "report.json"
        def invoke(p):
            with patch("ledgerverity.source._decode_ledger", side_effect=decoded):
                return main(["inspect-source", "--input", str(self.path), "--from-ledger", "10",
                             "--to-ledger", "11", "--network-passphrase", PASSPHRASE, "--format", "json",
                             "--output", str(p)])
        self.assertEqual(invoke(path), 3)
        report = path.read_text()
        self.assertEqual(invoke(path), 3)
        self.assertEqual(path.read_text(), report)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(invoke(path / "missing"), 2)
        self.assertIn("unable to write", err.getvalue())


if __name__ == "__main__":
    unittest.main()
