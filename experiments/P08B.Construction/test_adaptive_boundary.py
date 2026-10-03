"""Actual fits and independent dense references; no licensed Rhino runtime/UI."""
import ast
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch as mock_patch
import numpy as np
from scipy.interpolate import BSpline
import adaptive_boundary as ab
from mixed_kernel import *
from adaptive_fixture import localized_boundaries


class AdaptiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sides = localized_boundaries()
        cls.result = ab.adaptive_coons(cls.sides)

    def test_previous_10_and_16_underresolve_local_detail(self):
        for n in (10, 16):
            e = measure(construct_coons(self.sides, n=n), self.sides)
            self.assertFalse(e['position_sampled_ok'])
            self.assertGreater(e['edges']['top_first']['gap'], .01)

    def test_adaptive_fit_reaches_tighter_target_without_tolerance_change(self):
        r = self.result
        self.assertTrue(r.evidence['target_sampled_met'])
        self.assertLessEqual(r.evidence['gap'], .0025)
        self.assertEqual(r.evidence['document_tolerance'], .01)
        self.assertLessEqual(r.patch.n, 32)
        self.assertFalse(r.commit_allowed)

    def test_actual_nonuniform_knots_not_only_larger_uniform_grid(self):
        K = self.result.patch.K
        spans = [b-a for a, b in ab.knot_spans(K)]
        self.assertGreater(max(spans)/min(spans), 2)
        self.assertEqual(len(K[4:-4]), len(set(K[4:-4])))
        self.assertEqual(K[:4], [0.]*4)
        self.assertEqual(K[-4:], [1.]*4)

    def test_independent_dense_scipy_position_not_validation_or_fit_grid(self):
        p = self.result.patch
        curves = {'bottom': [row[0] for row in p.net], 'top': [row[-1] for row in p.net],
                  'left': p.net[0], 'right': p.net[-1]}
        maximum = 0.
        for side in SIDES:
            native = BSpline(p.K, np.asarray(curves[side]), p.p)
            for i in range(2001):
                t = (i+.2718281828)/2001
                target = self.sides[side](t).point
                maximum = max(maximum, np.linalg.norm(native(t)-target))
        self.assertLess(maximum, .0025)

    def test_same_basis_matches_scipy_on_nonuniform_knots(self):
        p = self.result.patch
        reference = BSpline(p.K, np.eye(p.n), p.p)
        for t in (0., .017, .081, .171, .456, .919, .997, 1.):
            b = basis(p.n, p.p, t, p.K)
            for d in range(3):
                np.testing.assert_allclose(b[d], reference(t, nu=d), atol=2e-9, rtol=1e-11)

    def test_independent_numpy_constrained_lsq(self):
        f = self.sides['top']; p = self.result.patch
        first, last = f(0).point, f(1).point
        sites = ab.fit_sites(f, p.K)
        X = BSpline(p.K, np.eye(p.n), p.p)(sites)
        Y = np.array([f(t).point for t in sites])-X[:, :1]*first-X[:, -1:]*last
        expected = np.linalg.lstsq(X[:, 1:-1], Y, rcond=None)[0]
        actual = ab.fit_curve(f, p.K, p.p, first, last)
        np.testing.assert_allclose(actual[1:-1], expected, atol=2e-13)

    def test_fit_and_validation_have_distinct_interior_grids(self):
        K = self.result.patch.K; f = self.sides['top']
        train = set(ab.fit_sites(f, K)); validation = set(ab.validation_sites(f, K))
        self.assertGreater(len(validation-train), 250)
        self.assertIn(.5, validation)
        for a, b in ab.knot_spans(K):
            self.assertGreaterEqual(sum(a<t<b for t in train), 3)

    def test_all_six_original_intervals_and_roles_remain(self):
        sources = [r for s in self.result.evidence['sides'].values() for r in s['sources'].values()]
        self.assertEqual(len(sources), 6)
        self.assertEqual(sum(e['preferred']==0 for e in sources), 4)
        self.assertEqual(sum(e['preferred']==2 for e in sources), 2)
        self.assertTrue(all(e['count']>0 for e in sources))

    def test_coons_uses_same_fitted_boundary_all_four_sides(self):
        r = self.result; p = r.patch
        for side in SIDES:
            for t in r.validation_sites[side][::3]:
                actual = p.eval(*side_uv(side, t))[0]
                self.assertLessEqual(norm(sub(actual, self.sides[side](t).point)), .0025)

    def test_refinement_never_moves_adaptively_fitted_boundary_rows(self):
        p = self.result.patch; frozen = p.boundary_snapshot()
        for curvature in (False, True):
            p, unused = refine(p, self.sides, curvature=curvature)
            self.assertEqual(p.boundary_snapshot(), frozen)

    def test_budget_exhaustion_is_not_accepted_or_zero_gap(self):
        r = ab.adaptive_coons(self.sides, max_rounds=0)
        self.assertFalse(r.evidence['document_sampled_met'])
        self.assertGreater(r.evidence['gap'], .01)
        self.assertEqual(r.reason, 'BOUNDARY_FIT_BUDGET_REACHED')
        self.assertFalse(r.commit_allowed)

    def test_limits_and_nonfinite_inputs_fail(self):
        for kwargs in ({'max_controls':33}, {'max_rounds':13}, {'tolerance':float('nan')},
                       {'tolerance':0}, {'target_fraction':1}):
            with self.assertRaises(ValueError): ab.adaptive_coons(self.sides, **kwargs)

    def test_cancellation_observed_without_eating_exception(self):
        count = [0]
        class Cancelled(RuntimeError): pass
        def checkpoint():
            count[0] += 1
            if count[0]>13: raise Cancelled()
        with self.assertRaises(Cancelled): ab.adaptive_coons(self.sides, checkpoint=checkpoint)

    def test_later_refit_failure_preserves_fitted_baseline_not_geometry_pass(self):
        original = ab.fit_curve; count = [0]
        def later(*args, **kwargs):
            count[0] += 1
            if count[0]>4: raise ValueError('test rank failure')
            return original(*args, **kwargs)
        with mock_patch.object(ab, 'fit_curve', side_effect=later):
            r = ab.adaptive_coons(self.sides)
        self.assertEqual(r.patch.n, 10)
        self.assertFalse(r.evidence['document_sampled_met'])
        self.assertIn('previous_fitted_baseline_retained', r.reason)
        self.assertFalse(r.commit_allowed)

    def test_open_corner_not_healed_by_changing_tolerance(self):
        sides = dict(self.sides); source = sides['top']
        def bad(t):
            s = source(t)
            return Support(add(s.point, (0, 0, .1)), s.normal, s.H, s.key, s.preferred)
        sides['top'] = bad
        with self.assertRaisesRegex(ValueError, 'OPEN_BOUNDARY_CORNER'):
            ab.adaptive_coons(sides)

    def test_simple_polynomial_requires_no_adaptation(self):
        sides = dict(self.sides)
        for side in SIDES:
            def f(t, side=side):
                u, v = side_uv(side, t)
                return Support((u, v, 0), (0,0,1), ((0,0,0),)*3, side, 0)
            sides[side] = f
        r = ab.adaptive_coons(sides)
        self.assertEqual(len(r.history), 1)
        self.assertLess(r.evidence['gap'], 1e-12)

    def test_no_mutation_of_original_parameters_or_kernel(self):
        before = {s: tuple(f.parameters) for s,f in self.sides.items()}
        ab.adaptive_coons(self.sides, max_rounds=1)
        self.assertEqual(before, {s: tuple(f.parameters) for s,f in self.sides.items()})
        d = Path(__file__).with_name('mixed_kernel.py').read_bytes()
        self.assertEqual(hashlib.sha1(b'blob '+str(len(d)).encode()+b'\0'+d).hexdigest(), '5aa42ba1500badfd96fdb4a8675bd214f57b33dd')

    def test_python2_grammar_and_no_runtime_or_document_calls(self):
        try:
            from lib2to3.refactor import RefactoringTool
        except ImportError:
            self.skipTest("Requires lib2to3; mandatory CI Python3.11 has it")
        p = Path(__file__).with_name('adaptive_boundary.py'); s = p.read_text()
        RefactoringTool([]).refactor_string(s, str(p))
        for forbidden in ('import Rhino', 'import numpy', 'import scipy', 'Objects.', 'RunScript('):
            self.assertNotIn(forbidden, s)

    def test_adapter_native_gate_source_stays_unchanged(self):
        s=Path(__file__).with_name('rhino_prototype.py').read_text()
        cls=next(n for n in ast.parse(s).body if isinstance(n,ast.ClassDef) and n.name=='Experiment')
        names=('make_brep','gap','native_evidence','candidate','close')
        methods=[ast.get_source_segment(s,n) for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names]
        self.assertEqual(hashlib.sha256('\n\n'.join(methods).encode()).hexdigest(), 'f38db43871a39649271c1a6e47f2170100769dc70bb4afa6804ae88166fbfe5d')
        self.assertIn("fit=adaptive_coons(sides",s)
        self.assertIn("'STAGE_SKIPPED'",s)
        self.assertIn("'JET_START'",s)

if __name__=='__main__': unittest.main(verbosity=2)
