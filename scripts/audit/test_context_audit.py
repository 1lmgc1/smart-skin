"""Pure helper and source-contract checks. These do NOT run Rhino native geometry."""
import importlib.util
import math
from pathlib import Path
import unittest

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
        # lib2to3 is only a grammar check, not an IronPython runtime test.
        try:
            from lib2to3.refactor import RefactoringTool
        except ImportError:
            self.skipTest('Grammar checker unavailable here; required in Python 3.11 CI')
        RefactoringTool([]).refactor_string(SOURCE.read_text(encoding='utf-8'), str(SOURCE))

if __name__ == '__main__':
    unittest.main(verbosity=2)
