"""Full SDK XDR encode/decode tests built from SYNTHETIC ledger metadata.

These are real serialized XDR objects, but NOT real historical ledgers or
consensus-attested evidence. No network access occurs during normal tests.
"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from stellar_sdk import xdr

from ledgerverity.source import SourceInputError, _decode_ledger, read_source_capture

P = "Test SDF Network ; September 2015"
ZERO = b"\x00" * 32


def make_record(seq: int, previous_hash: bytes = ZERO, version: int = 1) -> dict:
    header = xdr.LedgerHeader(
        ledger_version=xdr.Uint32(22 if version == 1 else 23),
        previous_ledger_hash=xdr.Hash(previous_hash),
        scp_value=xdr.StellarValue(
            tx_set_hash=xdr.Hash(ZERO),
            close_time=xdr.TimePoint(xdr.Uint64(1710000000)),
            upgrades=[],
            ext=xdr.StellarValueExt(v=xdr.StellarValueType.STELLAR_VALUE_BASIC),
        ),
        tx_set_result_hash=xdr.Hash(ZERO),
        bucket_list_hash=xdr.Hash(ZERO),
        ledger_seq=xdr.Uint32(seq),
        total_coins=xdr.Int64(0),
        fee_pool=xdr.Int64(0),
        inflation_seq=xdr.Uint32(0),
        id_pool=xdr.Uint64(0),
        base_fee=xdr.Uint32(100),
        base_reserve=xdr.Uint32(100),
        max_tx_set_size=xdr.Uint32(1000),
        skip_list=[xdr.Hash(ZERO) for _ in range(4)],
        ext=xdr.LedgerHeaderExt(v=0),
    )
    digest = hashlib.sha256(header.to_xdr_bytes()).digest()
    header_entry = xdr.LedgerHeaderHistoryEntry(
        hash=xdr.Hash(digest), header=header, ext=xdr.LedgerHeaderHistoryEntryExt(v=0)
    )
    tx_set = xdr.GeneralizedTransactionSet(
        v=1, v1_tx_set=xdr.TransactionSetV1(previous_ledger_hash=xdr.Hash(previous_hash), phases=[])
    )
    common = dict(
        ext=xdr.LedgerCloseMetaExt(v=0),
        ledger_header=header_entry,
        tx_set=tx_set,
        tx_processing=[],
        upgrades_processing=[],
        scp_info=[],
        total_byte_size_of_live_soroban_state=xdr.Uint64(0),
        evicted_keys=[],
    )
    if version == 1:
        meta = xdr.LedgerCloseMeta(v=1, v1=xdr.LedgerCloseMetaV1(**common, unused=[]))
    elif version == 2:
        meta = xdr.LedgerCloseMeta(v=2, v2=xdr.LedgerCloseMetaV2(**common))
    else:
        raise ValueError("fixture only supports v1/v2")
    return {
        "sequence": seq, "hash": digest.hex(),
        "headerXdr": header_entry.to_xdr(),
        "metadataXdr": meta.to_xdr(),
    }


class SourceXdrRoundtripTests(unittest.TestCase):
    def test_v1_roundtrip_metadata_and_header(self):
        decoded = _decode_ledger(make_record(1234))
        self.assertEqual((decoded.sequence, decoded.meta_version, decoded.protocol), (1234, 1, 22))
        self.assertEqual(decoded.events, ())
        self.assertEqual(decoded.unsupported_tx_versions, ())

    def test_v2_roundtrip_metadata_and_header(self):
        decoded = _decode_ledger(make_record(1234, version=2))
        self.assertEqual((decoded.sequence, decoded.meta_version, decoded.protocol), (1234, 2, 23))

    def test_two_real_xdr_objects_link(self):
        first = make_record(1234)
        second = make_record(1235, previous_hash=bytes.fromhex(first["hash"]))
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / "source.json"
            file.write_text(json.dumps({"jsonrpc":"2.0", "id":1, "result":{"ledgers":[second, first]}}))
            s = read_source_capture(file, 1234, 1235, P)
            self.assertTrue(s.span_contiguous)
            self.assertEqual([e.sequence for e in s.ledgers], [1234, 1235])
            self.assertFalse(s.report()["event_completeness_verified"])

    def test_reject_tampered_reported_hash(self):
        record = make_record(1200)
        record["hash"] = "b" * 64
        with self.assertRaisesRegex(SourceInputError, "hash does not match"):
            _decode_ledger(record)

    def test_reject_different_header_metadata(self):
        record = make_record(1200)
        changed = make_record(1201)
        record["headerXdr"] = changed["headerXdr"]
        with self.assertRaisesRegex(SourceInputError, "mismatch"):
            _decode_ledger(record)

    def test_reject_inconsistent_declared_sequence(self):
        record = make_record(1200)
        record["sequence"] = 1201
        with self.assertRaisesRegex(SourceInputError, "XDR ledger sequence mismatch"):
            _decode_ledger(record)

    def test_reject_trailing_garbage(self):
        record = make_record(1200)
        import base64
        record["metadataXdr"] = base64.b64encode(
            base64.b64decode(record["metadataXdr"]) + b"TRAIL"
        ).decode()
        with self.assertRaisesRegex(SourceInputError, "invalid or unsupported XDR"):
            _decode_ledger(record)

    def test_reject_mismatch_in_history_hash(self):
        record = make_record(1200)
        h = xdr.LedgerHeaderHistoryEntry.from_xdr(record["headerXdr"])
        h.hash = xdr.Hash(b"\x01" * 32)
        record["headerXdr"] = h.to_xdr()
        record["metadataXdr"] = xdr.LedgerCloseMeta(
            v=1,
            v1=xdr.LedgerCloseMetaV1(
                ext=xdr.LedgerCloseMetaExt(0), ledger_header=h,
                tx_set=xdr.GeneralizedTransactionSet(
                    v=1, v1_tx_set=xdr.TransactionSetV1(xdr.Hash(ZERO), [])),
                tx_processing=[], upgrades_processing=[], scp_info=[],
                total_byte_size_of_live_soroban_state=xdr.Uint64(0),
                evicted_keys=[], unused=[],
            )).to_xdr()
        with self.assertRaisesRegex(SourceInputError, "hash does not match"):
            _decode_ledger(record)


if __name__ == "__main__":
    unittest.main()
