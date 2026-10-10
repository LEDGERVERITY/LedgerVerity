"""SDK-serialized synthetic TransactionMetaV3/V4 inside original LedgerCloseMeta XDR.

This checks the production decoder path, not a hand-constructed event report.
"""
import unittest
from stellar_sdk import xdr

from ledgerverity.source import _decode_ledger, SourceSnapshot
from test_source_xdr import make_record
from test_canonical import event_xdr

P = "Test SDF Network ; September 2015"
TX = b"\xab"*32
CHANGES = xdr.LedgerEntryChanges([])


def ledger_with_tx(meta_version=4, success=True):
    rec = make_record(1234, version=2 if meta_version == 4 else 1)
    original = xdr.LedgerCloseMeta.from_xdr(rec["metadataXdr"])
    evt = xdr.ContractEvent.from_xdr(event_xdr())
    diag = xdr.DiagnosticEvent(in_successful_contract_call=not success, event=evt)
    if meta_version == 4:
        meta = xdr.TransactionMeta(v=4, v4=xdr.TransactionMetaV4(
            ext=xdr.ExtensionPoint(0),
            tx_changes_before=CHANGES,
            operations=[
                xdr.OperationMetaV2(ext=xdr.ExtensionPoint(0), changes=CHANGES, events=[]),
                xdr.OperationMetaV2(ext=xdr.ExtensionPoint(0), changes=CHANGES, events=[evt,evt]),
            ],
            tx_changes_after=CHANGES,
            soroban_meta=None,
            events=[xdr.TransactionEvent(
                stage=xdr.TransactionEventStage.TRANSACTION_EVENT_STAGE_BEFORE_ALL_TXS, event=evt
            )],
            diagnostic_events=[diag],
        ))
    else:
        meta = xdr.TransactionMeta(v=3, v3=xdr.TransactionMetaV3(
            ext=xdr.ExtensionPoint(0), tx_changes_before=CHANGES,
            operations=[], tx_changes_after=CHANGES,
            soroban_meta=xdr.SorobanTransactionMeta(
                ext=xdr.SorobanTransactionMetaExt(0),
                events=[evt, evt],
                return_value=xdr.SCVal(type=xdr.SCValType.SCV_VOID),
                diagnostic_events=[diag],
            )
        ))
    code = xdr.TransactionResultCode.txSUCCESS if success else xdr.TransactionResultCode.txFAILED
    result = xdr.TransactionResultPair(
        transaction_hash=xdr.Hash(TX),
        result=xdr.TransactionResult(
            fee_charged=xdr.Int64(100),
            result=xdr.TransactionResultResult(code=code, results=[]),
            ext=xdr.TransactionResultExt(0),
        ),
    )
    if meta_version == 4:
        original.v2.tx_processing = [xdr.TransactionResultMetaV1(
            ext=xdr.ExtensionPoint(0), result=result,
            fee_processing=CHANGES, tx_apply_processing=meta,
            post_tx_apply_fee_processing=CHANGES,
        )]
    else:
        original.v1.tx_processing = [xdr.TransactionResultMeta(
            result=result, fee_processing=CHANGES, tx_apply_processing=meta,
        )]
    rec["metadataXdr"] = original.to_xdr()
    return rec


def snapshot(rec):
    decoded = _decode_ledger(rec)
    return SourceSnapshot(P, 1234, 1234, (decoded,), (), "a"*64)


class TransactionMetaTests(unittest.TestCase):
    def test_v4_event_paths_include_distinct_ordinal_and_stage(self):
        ledger = _decode_ledger(ledger_with_tx())
        self.assertEqual([e.stream for e in ledger.events],
                         ["transaction", "operation", "operation", "diagnostic"])
        self.assertEqual([e.ordinal_in_stream for e in ledger.events], [0, 0, 1, 0])
        self.assertEqual([e.operation_ordinal for e in ledger.events], [None, 1, 1, None])
        self.assertEqual(ledger.events[0].stage, "TRANSACTION_EVENT_STAGE_BEFORE_ALL_TXS")
        self.assertEqual([e.tx_success for e in ledger.events], [True] * 4)
        self.assertFalse(ledger.events[-1].diagnostic_success)

    def test_v4_report_keeps_equal_payloads_separate(self):
        r = snapshot(ledger_with_tx()).report()
        events = r["source_local_event_semantics"]
        self.assertEqual(len(events), 4)
        self.assertEqual(len({e["source_locator_sha256"] for e in events}), 4)
        self.assertEqual(len({e["contract_event_sha256"] for e in events}), 1)
        self.assertFalse(r["event_completeness_verified"])
        self.assertEqual(r["status"], "INCONCLUSIVE")

    def test_v4_failed_transaction_not_confused_with_diagnostic(self):
        r = snapshot(ledger_with_tx(success=False)).report()
        for e in r["source_local_event_semantics"]:
            self.assertFalse(e["transaction_success"])
        self.assertTrue(r["source_local_event_semantics"][-1]["diagnostic_in_successful_contract_call"])
        self.assertIsNone(r["source_local_event_semantics"][0]["diagnostic_in_successful_contract_call"])

    def test_v3_real_serialized_contract_and_diagnostics(self):
        ledger = _decode_ledger(ledger_with_tx(meta_version=3))
        self.assertEqual(ledger.meta_version, 1)
        self.assertEqual([e.stream for e in ledger.events], ["contract", "contract", "diagnostic"])
        self.assertEqual([e.ordinal_in_stream for e in ledger.events], [0, 1, 0])
        self.assertEqual(ledger.events[0].tx_success, True)
        self.assertEqual(snapshot(ledger_with_tx(meta_version=3)).report()["status"], "INCONCLUSIVE")

    def test_v3_failed_contract_diagnostic_does_not_invent_success(self):
        r = snapshot(ledger_with_tx(meta_version=3, success=False)).report()
        self.assertEqual(r["source_local_event_semantics"][-1]["transaction_success"], False)
        self.assertEqual(r["source_local_event_semantics"][-1]["diagnostic_in_successful_contract_call"], True)


if __name__ == "__main__":
    unittest.main()
