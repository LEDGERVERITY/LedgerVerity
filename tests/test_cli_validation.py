"""End-user validation command tests (only synthetic candidate exports)."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from ledgerverity.cli import main
from ledgerverity.formats import FORMAT

def example():
    return {
        'transaction_hash': 'a' * 64, 'transaction_id': '1', 'successful': True,
        'ledger_sequence': 100, 'in_successful_contract_call': True,
        'contract_id': '', 'type': 1, 'type_string': 'Contract',
        'topics': ['transfer'], 'data': {'raw_amount': '340282366920938463463374607431768211455'},
        'operation_id': None,
    }

class ValidationCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.base = Path(self.tempdir.name)
        self.candidate = self.base / 'candidate.jsonl'
        self.manifest = self.base / 'scope.json'
        self.candidate.write_text(json.dumps(example()) + '\n', encoding='utf-8')
        self.manifest.write_text(json.dumps({
            'format': FORMAT, 'network_passphrase': 'Test SDF Network ; September 2015',
            'first_ledger': 100, 'last_ledger': 100, 'exporter': 'stellar-etl',
            'source_description': 'synthetic fixture'
        }), encoding='utf-8')

    def run_command(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(['validate-etl', '--input', str(self.candidate), '--scope', str(self.manifest), *args])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_valid_json_report_is_explicitly_unverified(self):
        status, stdout, stderr = self.run_command('--format', 'json')
        self.assertEqual((status, stderr), (0, ''))
        report = json.loads(stdout)
        self.assertEqual(report['status'], 'CANDIDATE_FORMAT_VALID')
        self.assertEqual(report['rows_scanned'], 1)
        self.assertFalse(report['source_evidence_verified'])
        self.assertFalse(report['coverage_verified'])
        self.assertNotIn('MATCH', json.dumps(report))

    def test_text_report_has_correct_scope_and_disclaimer(self):
        status, stdout, stderr = self.run_command()
        self.assertEqual(status, 0)
        self.assertIn('100..100', stdout)
        self.assertIn('NOT VERIFIED', stdout)
        self.assertEqual(stderr, '')

    def test_invalid_candidate_rejected_on_stderr(self):
        self.candidate.write_text('{invalid', encoding='utf-8')
        status, stdout, stderr = self.run_command('--format', 'json')
        self.assertEqual(status, 2)
        self.assertEqual(stdout, '')
        self.assertIn('invalid JSON', stderr)

    def test_out_of_scope_candidate_rejected(self):
        self.candidate.write_text(json.dumps(example() | {'ledger_sequence': 101}), encoding='utf-8')
        status, stdout, stderr = self.run_command()
        self.assertEqual(status, 2)
        self.assertEqual(stdout, '')
        self.assertIn('outside declared scope', stderr)

    def test_unrecognized_manifest_version_rejected(self):
        data = json.loads(self.manifest.read_text())
        data['format'] = 'not-supported'
        self.manifest.write_text(json.dumps(data))
        status, stdout, stderr = self.run_command()
        self.assertEqual(status, 2)
        self.assertEqual(stdout, '')
        self.assertIn('Unsupported', stderr)

    def test_deterministic_file_report(self):
        report_file = self.base / 'report.json'
        status, stdout, stderr = self.run_command('--format', 'json', '--output', str(report_file))
        self.assertEqual((status, stdout, stderr), (0, '', ''))
        first = report_file.read_bytes()
        self.run_command('--format', 'json', '--output', str(report_file))
        self.assertEqual(first, report_file.read_bytes())

    def test_unwritable_report_is_error(self):
        status, stdout, stderr = self.run_command('--output', str(self.base / 'missing' / 'out.txt'))
        self.assertEqual(status, 2)
        self.assertEqual(stdout, '')
        self.assertIn('unable to write report', stderr)

    def test_empty_input_is_not_completeness_proof(self):
        self.candidate.write_bytes(b'')
        status, stdout, _ = self.run_command('--format', 'json')
        self.assertEqual(status, 0)
        obj = json.loads(stdout)
        self.assertEqual(obj['rows_scanned'], 0)
        self.assertFalse(obj['coverage_verified'])

if __name__ == '__main__':
    unittest.main()
