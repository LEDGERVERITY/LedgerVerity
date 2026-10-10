"""Real serialized *synthetic* Stellar event XDR, not historical ledger evidence."""
import base64
import unittest
from dataclasses import replace
from stellar_sdk import xdr

from ledgerverity.canonical import describe_source_event, source_locator, token_movement
from ledgerverity.source import SourceEvent, SourceInputError, SourceSnapshot, DecodedLedger

NETWORK = "Test SDF Network ; September 2015"
TX = "a" * 64
CID = xdr.ContractID(xdr.Hash(b"\x11" * 32))


def sym(name):
    return xdr.SCVal(type=xdr.SCValType.SCV_SYMBOL, sym=xdr.SCSymbol(name.encode("ascii")))


def addr():
    return xdr.SCVal(type=xdr.SCValType.SCV_ADDRESS,
        address=xdr.SCAddress(type=xdr.SCAddressType.SC_ADDRESS_TYPE_CONTRACT, contract_id=CID))


def i128(value):
    assert -(1 << 127) <= value < (1 << 127)
    if value < 0:
        value += 1 << 128
    hi = value >> 64
    if hi >= (1 << 63):
        hi -= (1 << 64)
    return xdr.SCVal(type=xdr.SCValType.SCV_I128,
        i128=xdr.Int128Parts(hi=xdr.Int64(hi), lo=xdr.Uint64(value & ((1 << 64)-1))))


def data_map(entries):
    return xdr.SCVal(type=xdr.SCValType.SCV_MAP,
        map=xdr.SCMap([xdr.SCMapEntry(key=sym(k), val=v) for k,v in entries]))


def event_xdr(kind="transfer", value=None, topics=None, event_type=xdr.ContractEventType.CONTRACT, contract=True):
    if value is None:
        value = i128(5)
    if topics is None:
        topics = [sym(kind), addr(), addr()] if kind == "transfer" else [sym(kind), addr()]
    event = xdr.ContractEvent(ext=xdr.ExtensionPoint(0),
        contract_id=CID if contract else None,
        type=event_type,
        body=xdr.ContractEventBody(v=0, v0=xdr.ContractEventV0(topics=topics, data=value)))
    return event.to_xdr()


def source(xdr_blob=None, **changes):
    data = SourceEvent(
        ledger=100, tx_hash=TX, tx_ordinal=1, stream="operation",
        ordinal_in_stream=0, operation_ordinal=0, stage=None,
        contract_event_xdr=xdr_blob or event_xdr(), tx_success=True,
    )
    return replace(data, **changes)


class CanonicalEventTests(unittest.TestCase):
    def describe(self, blob=None, **changes):
        return describe_source_event(source(blob, **changes), NETWORK)

    def test_scoped_locator_and_separate_content_hash(self):
        r = self.describe()
        self.assertEqual(r["source_locator"]["transaction_ordinal_1based"], 1)
        self.assertEqual(r["source_locator"]["event_ordinal_in_stream_0based"], 0)
        self.assertEqual(len(r["source_locator_sha256"]), 64)
        self.assertFalse(r["locator_consensus_anchored"])

    def test_same_payload_separate_event_positions_are_not_deduplicated(self):
        a = self.describe()
        b = self.describe(ordinal_in_stream=1)
        self.assertNotEqual(a["source_locator_sha256"], b["source_locator_sha256"])
        self.assertEqual(a["contract_event_sha256"], b["contract_event_sha256"])

    def test_streams_and_operation_positions_are_distinct(self):
        a = self.describe()
        b = self.describe(operation_ordinal=1)
        c = self.describe(stream="diagnostic", operation_ordinal=None, diagnostic_success=True)
        self.assertEqual(len({a["source_locator_sha256"], b["source_locator_sha256"], c["source_locator_sha256"]}), 3)
        self.assertEqual(c["diagnostic_in_successful_contract_call"], True)

    def test_network_claim_namespaces_location_without_authentication(self):
        a = self.describe()["source_locator_sha256"]
        b = describe_source_event(source(), "Public Global Stellar Network ; September 2015")["source_locator_sha256"]
        self.assertNotEqual(a, b)

    def test_transaction_stage_kept_distinct_from_success(self):
        rec = self.describe(stream="transaction", operation_ordinal=None,
            stage="TRANSACTION_EVENT_STAGE_BEFORE_ALL_TXS", tx_success=False)
        self.assertFalse(rec["transaction_success"])
        self.assertEqual(rec["transaction_event_stage"], "TRANSACTION_EVENT_STAGE_BEFORE_ALL_TXS")
        self.assertIsNone(rec["diagnostic_in_successful_contract_call"])

    def test_failed_transaction_diagnostic_flag_remains_independent(self):
        rec = self.describe(stream="diagnostic", operation_ordinal=None,
            tx_success=False, diagnostic_success=True)
        self.assertFalse(rec["transaction_success"])
        self.assertTrue(rec["diagnostic_in_successful_contract_call"])
        self.assertTrue(rec["semantics_known"])

    def test_unknown_tx_outcome_remains_unknown(self):
        rec = self.describe(tx_success=None)
        self.assertIsNone(rec["transaction_success"])
        self.assertFalse(rec["semantics_known"])

    def test_missing_diagnostic_flag_incomplete(self):
        rec = self.describe(stream="diagnostic", operation_ordinal=None, diagnostic_success=None)
        self.assertFalse(rec["semantics_known"])

    def test_invalid_locator_components_rejected(self):
        bad = [
            {"ledger": 0}, {"tx_ordinal": 0}, {"ordinal_in_stream": -1},
            {"operation_ordinal": None}, {"operation_ordinal": True},
            {"stream": "bogus"}, {"tx_hash": "xyz"},
            {"stream": "transaction", "operation_ordinal": None, "stage": None},
            {"stage": "TRANSACTION_EVENT_STAGE_AFTER_TX"},
        ]
        for changes in bad:
            with self.subTest(changes=changes), self.assertRaises(SourceInputError):
                source_locator(source(**changes), NETWORK)

    def test_unknown_stage_rejected(self):
        with self.assertRaises(SourceInputError):
            self.describe(stream="transaction", operation_ordinal=None, stage="unknown")

    def test_diagnostic_flag_on_non_diagnostic_is_input_error(self):
        with self.assertRaises(SourceInputError):
            self.describe(diagnostic_success=True)

    def test_invalid_transaction_success_type_rejected(self):
        with self.assertRaises(SourceInputError):
            self.describe(tx_success="true")

    def test_malformed_base64_rejected(self):
        with self.assertRaises(SourceInputError):
            describe_source_event(source("NOT/XDR@@"), NETWORK)

    def test_non_xdr_bytes_rejected(self):
        with self.assertRaises(SourceInputError):
            describe_source_event(source(base64.b64encode(b"bad").decode()), NETWORK)

    def test_transfer_i128_exact_large_amount(self):
        result = self.describe(event_xdr(value=i128((1 << 127) - 1)))["token_movement"]
        self.assertEqual(result["amount_raw"], str((1 << 127) - 1))
        self.assertEqual(result["status"], "SUPPORTED_SUBSET")
        self.assertEqual(result["encoding"], "i128")
        self.assertEqual(len(result["participant_xdr_sha256"]), 2)

    def test_zero_i128_valid(self):
        result = self.describe(event_xdr(value=i128(0)))["token_movement"]
        self.assertEqual(result["amount_raw"], "0")

    def test_negative_amount_never_reported_as_valid_movement(self):
        result = self.describe(event_xdr(value=i128(-1)))["token_movement"]
        self.assertEqual(result["status"], "INCONCLUSIVE")

    def test_single_value_vec_form(self):
        payload = xdr.SCVal(type=xdr.SCValType.SCV_VEC, vec=xdr.SCVec([i128(77)]))
        result = self.describe(event_xdr(value=payload))["token_movement"]
        self.assertEqual((result["amount_raw"], result["encoding"]), ("77", "vec_i128"))

    def test_short_vec_cannot_infer_amount(self):
        payload = xdr.SCVal(type=xdr.SCValType.SCV_VEC, vec=xdr.SCVec([]))
        self.assertEqual(self.describe(event_xdr(value=payload))["token_movement"]["status"], "INCONCLUSIVE")

    def test_map_amount_and_muxed_u64(self):
        val = xdr.SCVal(type=xdr.SCValType.SCV_U64, u64=xdr.Uint64((1<<64)-1))
        res = self.describe(event_xdr(value=data_map([("amount", i128(125)),("to_muxed_id", val)])))["token_movement"]
        self.assertEqual(res["amount_raw"], "125")
        self.assertEqual(res["to_muxed_id"], {"type": "u64", "value": str((1<<64)-1)})

    def test_map_extra_extension_explicit_partial(self):
        res = self.describe(event_xdr(value=data_map([("amount", i128(1)),("other", sym("opaque"))])))["token_movement"]
        self.assertEqual(res["status"], "PARTIAL")
        self.assertEqual(res["extension_keys"], ["other"])

    def test_extra_topics_explicit_partial(self):
        res = self.describe(event_xdr(topics=[sym("transfer"), addr(), addr(), sym("addon")]))["token_movement"]
        self.assertEqual(res["status"], "PARTIAL")
        self.assertEqual(res["extra_topic_count"], 1)

    def test_map_duplicate_keys_ambiguous(self):
        res = self.describe(event_xdr(value=data_map([("amount", i128(1)),("amount", i128(2))])))["token_movement"]
        self.assertEqual(res["status"], "INCONCLUSIVE")

    def test_missing_amount_map_inconclusive(self):
        res = self.describe(event_xdr(value=data_map([("memo", sym("x"))])))["token_movement"]
        self.assertEqual(res["status"], "INCONCLUSIVE")

    def test_muxed_bytes32_and_legacy_string(self):
        data = [
            xdr.SCVal(type=xdr.SCValType.SCV_BYTES, bytes=xdr.SCBytes(b"a"*32)),
            xdr.SCVal(type=xdr.SCValType.SCV_STRING, str=xdr.SCString(b"memo")),
        ]
        for v in data:
            with self.subTest(type=v.type):
                res = self.describe(event_xdr(value=data_map([("amount", i128(9)),("to_muxed_id", v)])))["token_movement"]
                self.assertEqual(res["status"], "SUPPORTED_SUBSET")
                self.assertIn(res["to_muxed_id"]["type"], {"bytes32", "string"})

    def test_invalid_muxed_blob_never_silently_accepted(self):
        v=xdr.SCVal(type=xdr.SCValType.SCV_BYTES, bytes=xdr.SCBytes(b"small"))
        res=self.describe(event_xdr(value=data_map([("amount", i128(1)),("to_muxed_id", v)])))["token_movement"]
        self.assertEqual(res["status"], "INCONCLUSIVE")

    def test_supported_other_movement_topics(self):
        for kind in ("mint", "burn", "clawback"):
            with self.subTest(kind=kind):
                res=self.describe(event_xdr(kind=kind))["token_movement"]
                self.assertEqual(res["status"], "SUPPORTED_SUBSET")
                self.assertEqual(res["kind"], kind)

    def test_unrecognized_topic_is_not_a_movement(self):
        res=self.describe(event_xdr(kind="approve"))["token_movement"]
        self.assertEqual(res["status"], "NOT_APPLICABLE")

    def test_wrong_address_type_is_inconclusive(self):
        res=self.describe(event_xdr(topics=[sym("transfer"), sym("bad"), addr()]))["token_movement"]
        self.assertEqual(res["status"], "INCONCLUSIVE")

    def test_system_event_not_forced_into_token_semantics(self):
        res=self.describe(event_xdr(event_type=xdr.ContractEventType.SYSTEM, contract=False))["token_movement"]
        self.assertEqual(res["status"], "NOT_APPLICABLE")

    def test_duplicate_source_locator_is_error(self):
        ev = source()
        snap = SourceSnapshot(NETWORK, 100,100,
            (DecodedLedger(100,"b"*64,"0"*64,23,2,(ev,ev),()),),(), "e"*64)
        with self.assertRaisesRegex(SourceInputError,"Repeated source-local"):
            snap.report()

    def test_two_same_payload_distinct_positions_both_reported(self):
        ev = source()
        snap = SourceSnapshot(NETWORK,100,100,
            (DecodedLedger(100,"b"*64,"0"*64,23,2,(ev,replace(ev, ordinal_in_stream=1)),()),),(),"f"*64)
        report=snap.report()
        self.assertEqual(report["schema_version"],2)
        self.assertEqual(len(report["source_local_event_semantics"]),2)
        self.assertFalse(report["event_completeness_verified"])
        self.assertEqual(report["status"],"INCONCLUSIVE")


if __name__ == "__main__":
    unittest.main()
