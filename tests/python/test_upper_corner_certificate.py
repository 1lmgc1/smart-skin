"""Redistributable synthetic tests for exact isolated upper-corner regularity."""
import copy
from fractions import Fraction
import importlib.util
import json
from pathlib import Path
import sys
import time
import unittest
from unittest import mock

import numpy as np

SOURCE = Path(__file__).resolve().parents[2] / 'src' / 'SmartSkin.Rhino8' / 'Python'
sys.path.insert(0, str(SOURCE))
import upper_corner_certificate as certificate


def chart(radial_controls=(0., 1.), weights=None, side=0):
    """H=(u*x(r),r,0,W(r)); J has factor r when x(r)=r*f(r)."""
    q = len(radial_controls) - 1
    weights = weights if weights is not None else [1.] * (q + 1)
    return dict(kind='upper_hard_corner', side=side, piece=0,
                approved_physical_corner_id='upper:side%d' % side,
                collapsed_parameter_edge='v=0', degree_u=1, degree_v=q,
                knots_u=[0., 0., 1., 1.],
                knots_v=[0.] * (q + 1) + [1.] * (q + 1),
                domain=[[0., 1.], [0., 1.]],
                homogeneous_cp=[[[u * x, j / q, 0., weights[j]]
                                 for j, x in enumerate(radial_controls)]
                                for u in (0., 1.)])


def quadratic_quotient(center=.5, offset=1 / 64):
    # H_y=3r makes its degree-three controls exactly integral. H_x has
    # x(r)=3r*((r-center)^2+offset), with exactly dyadic Bezier controls.
    c = center
    out = chart((0., c*c + offset,
                 2*c*c - 2*c + 2*offset,
                 3*c*c - 6*c + 3 + 3*offset))
    for row in out['homogeneous_cp']:
        for j, point in enumerate(row):
            point[1] = float(j)
    return out


def certify(record, normal=(0., 0., 1.), sign=1, **kwargs):
    return certificate.certify_isolated_upper_chart(record, normal, sign, **kwargs)


class UpperCornerCertificateTests(unittest.TestCase):
    def assertFails(self, result, reason=None):
        self.assertFalse(result['passed'], result)
        self.assertFalse(result['proof']['local_immersion_certified'])
        if reason is not None:
            self.assertEqual(result['reason'], reason, result)
        self.assertFalse(result['proof']['global_injectivity_certified'])
        self.assertFalse(result['proof']['g2_certified'])
        if 'radial_factor' in result['proof']:
            self.assertFalse(result['proof']['radial_factor'][
                'quotient_strictly_positive_on_closed_square'])

    def test_exact_triangular_chart_covers_closed_quotient_square(self):
        result = certify(chart())
        self.assertTrue(result['passed'], result)
        proof = result['proof']
        self.assertEqual(proof['radial_factor']['factors_removed'], 1)
        self.assertEqual(proof['radial_factor']['exact_radial_multiplicity'], 1)
        self.assertTrue(proof['radial_factor']['exact_zero_constant_power_column'])
        self.assertTrue(proof['radial_factor']['quotient_strictly_positive_on_closed_square'])
        self.assertEqual(proof['excluded_positive_radius'], 0.)
        self.assertEqual(proof['coverage']['domain_covered'], 'entire closed unit square')
        self.assertEqual(proof['signed_projected_Jacobian_over_r_lower_bound'],
                         dict(numerator='1', denominator='1'))
        self.assertFalse(proof['physical_corner_approval_verified'])
        self.assertFalse(proof['global_injectivity_certified'])
        self.assertFalse(proof['g2_certified'])
        json.dumps(result)  # Reports must survive the native JSON boundary.

    def test_both_sides_are_bounded_physical_identities(self):
        self.assertTrue(certify(chart(side=1))['passed'])
        for value in (None, '', 'arbitrary_corner', 'upper:side2',
                      'upper:side0:diagonal', 'upper:side1'):
            record = chart()
            record['approved_physical_corner_id'] = value
            self.assertFails(certify(record), 'missing_or_mismatched_approved_upper_corner')
        for value in (None, True, 2, -1, '0'):
            record = chart()
            record['side'] = value
            self.assertFails(certify(record), 'missing_or_mismatched_approved_upper_corner')

    def test_only_explicit_upper_collapsed_edge_is_supported(self):
        for field, values, reason in (
                ('kind', (None, 'fan', 'collar', 'other_corner'), 'unsupported_chart_kind'),
                ('collapsed_parameter_edge', (None, 'u=0', 'v=1', 'point', 'seam'),
                 'unsupported_collapsed_parameter_edge')):
            for value in values:
                record = chart()
                record[field] = value
                self.assertFails(certify(record), reason)

    def test_constant_homogeneous_row_is_stronger_than_physical_coincidence(self):
        record = chart()
        record['homogeneous_cp'][1][0][3] = 2.
        self.assertFails(certify(record), 'constant_homogeneous_pole_row_required')
        record = chart()
        record['homogeneous_cp'][1][0][0] = np.nextafter(0., 1.)
        self.assertFails(certify(record), 'constant_homogeneous_pole_row_required')

    def test_positive_rational_weights_and_bound(self):
        # S=(ur/(1+r),r/(1+r),0), so J/r=1/(1+r)^3 >= 1/8.
        result = certify(chart(weights=(1., 2.)))
        self.assertTrue(result['passed'], result)
        self.assertEqual(result['proof']['signed_projected_Jacobian_over_r_lower_bound'],
                         dict(numerator='1', denominator='8'))
        for weight in (0., -1.):
            record = chart(weights=(1., weight))
            self.assertFails(certify(record), 'positive_Bernstein_weights_required')

    def test_expected_orientation_and_all_projection_axes(self):
        for axis in range(3):
            record = chart()
            normal = [0., 0., 0.]
            normal[axis] = 2.
            for row in record['homogeneous_cp']:
                for point in row:
                    point[:3] = np.roll(point[:3], (axis + 1) % 3).tolist()
            self.assertTrue(certify(record, normal)['passed'])
            self.assertFails(certify(record, normal, -1), 'nonpositive_exact_quotient_corner')
            self.assertTrue(certify(record, [-x for x in normal], -1)['passed'])
        for value in (True, False, 0, 2, '1', None):
            self.assertFails(certify(chart(), sign=value), 'invalid_expected_orientation_sign')

    def test_nondominant_components_enter_exact_projection(self):
        record = chart()
        for row in record['homogeneous_cp']:
            for point in row:
                point[2] = 2*point[0] + 3*point[1]
        self.assertTrue(certify(record, (1., 2., 4.), -1)['passed'])
        self.assertFails(certify(record, (1., 2., 4.), 1), 'nonpositive_exact_quotient_corner')

    def test_positive_quotient_may_require_subdivision(self):
        result = certify(quadratic_quotient())
        self.assertTrue(result['passed'], result)
        self.assertGreater(result['proof']['coverage']['cells'], 1)
        self.assertGreater(result['proof']['coverage']['maximum_binary_depth'], 0)
        bound = result['proof']['signed_projected_Jacobian_over_r_lower_bound']
        self.assertGreater(Fraction(int(bound['numerator']), int(bound['denominator'])), 0)

    def test_zero_in_interior_is_never_skipped(self):
        self.assertFails(certify(quadratic_quotient(offset=0.)),
                         'nonpositive_exact_quotient_corner')

    def test_negative_finite_box_is_never_skipped(self):
        self.assertFails(certify(quadratic_quotient(offset=-1 / 64)),
                         'nonpositive_exact_quotient_corner')

    def test_tiny_finite_radius_negative_box_fails_closed(self):
        record = quadratic_quotient(center=2.**-18, offset=-2.**-48)
        # Positive endpoints and a tiny negative open interval at positive r.
        # A depth limit is an unresolved rejection, never an epsilon exemption.
        result = certify(record)
        self.assertFails(result)
        self.assertIn(result['reason'], ('unresolved_quotient_at_depth_limit',
                                        'nonpositive_exact_quotient_corner'))
        self.assertEqual(result['proof']['excluded_positive_radius'], 0.)

    def test_quotient_zero_at_pole_or_outer_boundary_is_rejected(self):
        # x=r^2 gives an additional radial factor, which cannot be excused.
        self.assertFails(certify(chart((0., 0., 1.))),
                         'nonpositive_exact_quotient_corner')
        # x=2r(1-r) has a zero at r=1.
        self.assertFails(certify(chart((0., 1., 0.))),
                         'nonpositive_exact_quotient_corner')
        self.assertFails(certify(chart((0., 0.))),
                         'identically_zero_projected_Jacobian')

    def test_angular_zero_and_negative_intervals_are_not_exemptions(self):
        record = chart()
        record.update(degree_u=2, knots_u=[0., 0., 0., 1., 1., 1.])
        record['homogeneous_cp'] = [record['homogeneous_cp'][0],
                                    copy.deepcopy(record['homogeneous_cp'][0]),
                                    record['homogeneous_cp'][1]]
        self.assertFails(certify(record), 'nonpositive_exact_quotient_corner')
        record['homogeneous_cp'][1][1][0] = -1.
        record.update(allowed_zero_uv=[[0., 0.]], exception_seam_ids=['arbitrary'],
                      singularity_epsilon=1.)
        self.assertFails(certify(record), 'nonpositive_exact_quotient_corner')

    def test_exact_radial_coefficient_guard_is_independent(self):
        original = certificate._bernstein_to_power
        calls = []
        def inconsistent_conversion(a, budget):
            out = original(a, budget)
            if not calls:
                out[1, 0] = 1  # Inject a constant-radial-column algebra defect.
            calls.append(True)
            return out
        with mock.patch.object(certificate, '_bernstein_to_power', inconsistent_conversion):
            self.assertFails(certify(chart()), 'radial_factor_not_exact')

    def test_input_domain_and_shape_are_strictly_bounded(self):
        changes = (
            ('degree_u', 41), ('degree_v', True), ('degree_v', 0),
            ('domain', [[0., 1.], [1e-8, 1.]]),
            ('knots_v', [0., 0., .5, 1., 1.]),
            ('knots_u', [0., 0., 2., 2.]),
            ('homogeneous_cp', [[0., 1.]]), ('homogeneous_cp', np.zeros((42, 42, 4))),
        )
        for field, value in changes:
            record = chart()
            record[field] = value
            self.assertFails(certify(record))
        self.assertFails(certify(None), 'unsupported_chart_kind')

    def test_nonfinite_and_nonnumeric_inputs_fail_closed(self):
        for value in (float('nan'), float('inf'), '1', True, None, complex(1)):
            record = chart()
            record['homogeneous_cp'][0][1][0] = value
            self.assertFails(certify(record))
        for value in ((0., 0., 0.), (0., float('nan'), 1.), [1., 2.], 'xyz', [[1.], [2.], [3.]]):
            self.assertFails(certify(chart(), value))

    def test_immediate_cancel_and_expired_deadline_fail_closed(self):
        self.assertFails(certify(chart(), cancelled=lambda: True), 'fan.cancelled')
        self.assertFails(certify(chart(), deadline=time.monotonic()-1), 'fan.elapsed_limit')
        self.assertFails(certify(chart(), deadline=float('nan')), 'fan.invalid_budget')
        self.assertFails(certify(chart(), cancelled=True), 'invalid_cancellation_callback')
        def broken_callback():
            raise RuntimeError('unavailable UI cancellation hook')
        self.assertFails(certify(chart(), cancelled=broken_callback), 'cancellation_callback_failed')

    def test_cancel_polling_is_throttled_but_final_poll_is_mandatory(self):
        calls = []
        clock = lambda: 100.
        original = certificate._fj.ExactWorkBudget
        def budget(**kwargs):
            return original(_clock=clock, **kwargs)
        with mock.patch.object(certificate._fj, 'ExactWorkBudget', budget):
            self.assertTrue(certify(quadratic_quotient(), cancelled=lambda: calls.append(1) or False)['passed'])
        self.assertEqual(len(calls), 2)  # Entry plus mandatory completion only.
        calls.clear()
        def late_cancel():
            calls.append(1)
            return len(calls) == 2
        with mock.patch.object(certificate._fj, 'ExactWorkBudget', budget):
            self.assertFails(certify(chart(), cancelled=late_cancel), 'fan.cancelled')

    def test_deadline_can_stop_in_progress_exact_work(self):
        ticks = []
        def clock():
            ticks.append(1)
            return 100. + len(ticks) / 100.
        original = certificate._fj.ExactWorkBudget
        def budget(**kwargs):
            return original(_clock=clock, **kwargs)
        with mock.patch.object(certificate._fj, 'ExactWorkBudget', budget):
            result = certify(quadratic_quotient(), deadline=100.5)
        self.assertFails(result, 'fan.elapsed_limit')
        self.assertGreater(len(ticks), 10)

    def test_every_resource_exhaustion_is_fail_closed(self):
        for name, value, record, reason in (
                ('_MAX_WORK', 1, chart(), 'fan.work_limit'),
                ('_MAX_BITS', 8, chart((0., .1)), 'fan.fraction_bit_limit'),
                ('_MAX_ELEMENTS', 1, chart(), 'fan.allocation_limit'),
                ('_MAX_LIVE_BYTES', 1, chart(), 'live_memory_budget_exhausted'),
                ('_MAX_PACKED_BITS', 1, chart(), 'packed_memory_budget_exhausted'),
                ('_MAX_DEPTH', 0, quadratic_quotient(), 'unresolved_quotient_at_depth_limit'),
                ('_MAX_CELLS', 1, quadratic_quotient(), 'cell_budget_exhausted')):
            with self.subTest(limit=name), mock.patch.object(certificate, name, value):
                self.assertFails(certify(record), reason)

    def test_input_is_unchanged_and_descriptor_cannot_override_bounds(self):
        record = quadratic_quotient(offset=-1/64)
        record.update(max_depth=1000000, max_cells=1000000,
                      max_work=10**100, accepted=True, radial_factor_verified=True)
        before = copy.deepcopy(record)
        self.assertFails(certify(record))
        self.assertEqual(record, before)

    def test_version_owned_dependency_wins_over_generic_module(self):
        owned = certificate._fj
        spec = importlib.util.spec_from_file_location('certificate_import_test',
                                                      SOURCE / 'upper_corner_certificate.py')
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {'_smartskin_p08e1_fan_shared_jets': owned,
                                           'fan_shared_jets': None}):
            spec.loader.exec_module(module)
        self.assertIs(module._fj, owned)


class ExactIntegerKernelTests(unittest.TestCase):
    def test_signed_convolution_matches_schoolbook(self):
        rng = np.random.default_rng(20261006)
        for shape_a, shape_b in (((2, 3), (3, 2)), ((1, 3), (4, 1)), ((3, 3), (2, 4))):
            for _ in range(8):
                a = rng.integers(-7, 8, shape_a).astype(object)
                b = rng.integers(-7, 8, shape_b).astype(object)
                expected = np.zeros((shape_a[0]+shape_b[0]-1,
                                     shape_a[1]+shape_b[1]-1), dtype=object)
                for i in range(shape_a[0]):
                    for j in range(shape_a[1]):
                        expected[i:i+shape_b[0], j:j+shape_b[1]] += a[i, j]*b
                result = certificate._convolve(a, b, certificate._Budget(None, None))
                np.testing.assert_array_equal(result, certificate._trim(expected))

    def test_integer_bernstein_power_round_trip(self):
        rng = np.random.default_rng(57)
        for shape in ((1, 1), (2, 3), (4, 5)):
            coeff = rng.integers(-5, 6, shape).astype(object)
            budget = certificate._Budget(None, None)
            power = certificate._bernstein_to_power(coeff, budget)
            restored, scale = certificate._power_to_bernstein(power, budget)
            np.testing.assert_array_equal(restored, coeff * scale)


if __name__ == '__main__':
    unittest.main()
