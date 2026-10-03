"""Helper/I/O/mock-dialog tests only. These do NOT execute Rhino native geometry."""
import ast
import codecs
import hashlib
import importlib.util
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).with_name('SmartSkin_ContextAudit.py')
spec = importlib.util.spec_from_file_location('audit', SOURCE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

class AuditMathTests(unittest.TestCase):
    def test_equal_normals(self):
        self.assertAlmostEqual(audit.normal_plane_angle((0, 0, 1), (0, 0, 2)), 0)
    def test_opposite_orientations_same_plane(self):
        self.assertAlmostEqual(audit.normal_plane_angle((0, 0, 1), (0, 0, -1)), 0)
    def test_orthogonal_supports(self):
        self.assertAlmostEqual(audit.normal_plane_angle((1, 0, 0), (0, 1, 0)), 90)
    def test_known_angle(self):
        self.assertAlmostEqual(audit.normal_plane_angle((1, 0, 0), (math.sqrt(3), 1, 0)), 30)
    def test_invalid_normals(self):
        self.assertIsNone(audit.normal_plane_angle((0, 0, 0), (1, 0, 0)))
        self.assertIsNone(audit.normal_plane_angle((float('nan'), 0, 0), (1, 0, 0)))
    def test_both_native_directions(self):
        self.assertEqual(audit.native_pair_summary(0.01, 0.03), (True, 0.03))
    def test_partial_native_measurement_is_not_complete(self):
        self.assertEqual(audit.native_pair_summary(None, 0.03), (False, 0.03))
        self.assertEqual(audit.native_pair_summary(0.03, None), (False, 0.03))
    def test_no_measurement_is_not_zero(self):
        self.assertEqual(audit.native_pair_summary(None, None), (False, None))
        self.assertEqual(audit.native_pair_summary(float('nan'), -1), (False, None))
    def test_identity_pinned(self):
        self.assertEqual(audit.AUDIT_ID, 'P08A.2')
        self.assertEqual(audit.EXPECTED_VERSION, '0.0.14-p07f2')
        self.assertEqual(audit.EXPECTED_COMMIT, 'a9b8281f9475fb29d38839614b1781ff21b26677')
    def test_no_document_write_calls(self):
        text = SOURCE.read_text(encoding='utf-8')
        for forbidden in ('Objects.Add', 'Objects.Delete', 'Objects.Replace', 'doc.WriteFile',
                          'RunScript(', 'SetTolerancesBoxesAndFlags(', 'os.system(', 'subprocess'):
            self.assertNotIn(forbidden, text)
        self.assertIn('"BuildBoundaryContext", 7', text)
        self.assertIn('"SourceIndices"', text)
    def test_python2_grammar(self):
        # This is a grammar check, not an IronPython runtime test.
        try:
            from lib2to3.refactor import RefactoringTool
        except ImportError:
            self.skipTest('Grammar checker unavailable here; required in Python 3.11 CI')
        RefactoringTool([]).refactor_string(SOURCE.read_text(encoding='utf-8'), str(SOURCE))
    def test_geometry_method_source_unchanged(self):
        text = SOURCE.read_text(encoding='utf-8')
        cls = next(n for n in ast.parse(text).body if isinstance(n, ast.ClassDef) and n.name == 'ContextAudit')
        methods = [ast.get_source_segment(text, n) for n in cls.body
                   if isinstance(n, ast.FunctionDef) and n.name not in ('__init__', 'emit', 'checkpoint', 'bind')]
        digest = hashlib.sha256('\n\n'.join(methods).encode('utf-8')).hexdigest()
        self.assertEqual(digest, 'af0bd223e870a638351ab0cd98ceb99228fca62937b14134b26dc58b82bc2af5')

class TextReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='SmartSkin_')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.console = []
    def report(self, name='отчёт.txt'):
        report = audit.TextReport(str(self.root / name), self.console.append)
        self.addCleanup(report.close)
        return report
    def read(self, report):
        return Path(report.path).read_text(encoding='utf-8-sig')
    def test_unicode_bom_and_crlf(self):
        r = self.report()
        r.emit('MAP', name='Ребро → грань', message='שלום')
        r.close()
        data = Path(r.path).read_bytes()
        self.assertTrue(data.startswith(codecs.BOM_UTF8))
        self.assertIn('Ребро → грань', data.decode('utf-8-sig'))
        self.assertIn('שלום', data.decode('utf-8-sig'))
        self.assertTrue(data.endswith(b'\r\n'))
    def test_flush_before_close(self):
        r = self.report()
        r.emit('MAP', value=123)
        self.assertIn('value=123', self.read(r))
        self.assertFalse(r.closed)
    def test_full_large_record_not_truncated_in_txt(self):
        r = self.report()
        text = 'данные_' * 20000
        r.emit('MAP', diagnostic=text)
        r.emit('STOP', error=text)
        self.assertIn(text, self.read(r))
        self.assertNotIn(text, '\n'.join(self.console))
        self.assertTrue(all(len(line) < 160 for line in self.console))
    def test_txt_extension_does_not_overwrite_other_extension(self):
        self.assertEqual(audit.txt_path('model.3dm'), 'model.3dm.txt')
        self.assertEqual(audit.txt_path('report.TXT'), 'report.TXT')
        self.assertEqual(audit.txt_path('отчёт'), 'отчёт.txt')
    def test_stop_and_safety_recorded_and_file_closed(self):
        class StoppedAudit:
            before = 10
            def __init__(self, report): self.report = report
            def run(self): raise audit.AuditStop('CANCELLED: остановка')
            def close(self): self.report.emit('SAFETY', objects_before=10, objects_after=10)
        r = self.report()
        audit.run_to_report(r, StoppedAudit)
        self.assertTrue(r.closed)
        text = self.read(r)
        self.assertIn('SMARTSKIN_P08A_STOP', text)
        self.assertIn('остановка', text)
        self.assertIn('SMARTSKIN_P08A_SAFETY', text)
        self.assertIn('state=STOPPED', text)
        self.assertIsNone(r.error)
    def test_constructor_error_and_full_traceback_saved(self):
        def broken(report): raise RuntimeError('Ошибка загрузки')
        r = self.report()
        audit.run_to_report(r, broken)
        text = self.read(r)
        self.assertIn('SMARTSKIN_P08A_TRACEBACK', text)
        self.assertIn('RuntimeError: Ошибка загрузки', text)
        self.assertIn('INITIALIZATION_STOPPED', text)
        self.assertTrue(r.closed)
    def test_safety_failure_does_not_claim_unchanged(self):
        class BadCleanup:
            before = 10
            def __init__(self, report): pass
            def run(self): pass
            def close(self): raise RuntimeError('cleanup failed')
        r = self.report()
        audit.run_to_report(r, BadCleanup)
        self.assertIn('CHECK_FAILED;do_not_infer_geometry_unchanged', self.read(r))
        self.assertIn('state=STOPPED', self.read(r))
        self.assertTrue(r.closed)
    def test_success_footer_after_safety(self):
        class GoodAudit:
            before = 10
            def __init__(self, report): self.report = report
            def run(self): self.report.emit('COMPLETE', result='diagnostic_only')
            def close(self): self.report.emit('SAFETY', objects_before=10, objects_after=10)
        r = self.report()
        audit.run_to_report(r, GoodAudit)
        text = self.read(r)
        self.assertLess(text.index('SMARTSKIN_P08A_SAFETY'), text.index('SMARTSKIN_P08A_REPORT_END'))
        self.assertIn('state=COMPLETE', text)
    def test_console_failure_does_not_lose_txt(self):
        r = self.report()
        r.console = Mock(side_effect=RuntimeError('console unavailable'))
        r.emit('STOP', error='test')
        r.close()
        self.assertIsNone(r.error)
        self.assertIn('error=test', self.read(r))
    def test_file_failure_retains_records_and_can_save_elsewhere(self):
        r = self.report('partial.txt')
        r.write('first')
        r.stream.close()  # Simulates failure of the stream on the next write.
        r.emit('STOP', error='aborted')
        r.emit('SAFETY', objects_before=10, objects_after=10)
        r.close()
        self.assertIsNotNone(r.error)
        self.assertNotIn('SMARTSKIN_P08A_SAFETY', self.read(r))
        replacement = self.report('recovered.txt')
        with patch.object(audit, 'choose_report', return_value=replacement):
            audit.finish_report(r)
        text = self.read(replacement)
        self.assertIn('first', text)
        self.assertIn('SMARTSKIN_P08A_STOP', text)
        self.assertIn('SMARTSKIN_P08A_SAFETY', text)
        self.assertIn('SMARTSKIN_P08A_REPORT_RECOVERED', text)
        self.assertIn('SMARTSKIN_P08A_SAVED', self.console[-1])
    def test_save_dialog_cancel_never_starts_audit(self):
        rs = SimpleNamespace(SaveFileName=Mock(return_value=None))
        rhino = SimpleNamespace(RhinoApp=SimpleNamespace(WriteLine=self.console.append))
        with patch.dict('sys.modules', {'rhinoscriptsyntax': rs, 'Rhino': rhino}):
            with patch.object(audit, 'run_to_report') as run:
                audit.main()
                run.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])
    def test_existing_file_declined_is_preserved(self):
        p = self.root / 'existing.txt'
        p.write_text('original')
        rs = SimpleNamespace(SaveFileName=Mock(side_effect=[str(p), None]), MessageBox=Mock(return_value=7))
        with patch.dict('sys.modules', {'rhinoscriptsyntax': rs}):
            self.assertIsNone(audit.choose_report(self.console.append))
        self.assertEqual(p.read_text(), 'original')
    def test_existing_file_can_be_explicitly_replaced(self):
        p = self.root / 'existing.txt'
        p.write_text('original')
        rs = SimpleNamespace(SaveFileName=Mock(return_value=str(p)), MessageBox=Mock(return_value=6))
        with patch.dict('sys.modules', {'rhinoscriptsyntax': rs}):
            r = audit.choose_report(self.console.append)
        self.addCleanup(r.close)
        r.write('replacement')
        r.close()
        self.assertEqual(self.read(r), 'replacement\n')
    def test_bad_path_reprompts_before_audit(self):
        paths = [str(self.root / 'missing_directory' / 'bad.txt'), str(self.root / 'ok.txt')]
        rs = SimpleNamespace(SaveFileName=Mock(side_effect=paths), MessageBox=Mock(return_value=1))
        with patch.dict('sys.modules', {'rhinoscriptsyntax': rs}):
            r = audit.choose_report(self.console.append)
        self.addCleanup(r.close)
        self.assertEqual(r.path, paths[1])
        self.assertEqual(rs.MessageBox.call_count, 1)

if __name__ == '__main__':
    unittest.main(verbosity=2)
