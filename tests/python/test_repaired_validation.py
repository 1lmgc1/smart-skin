"""Synthetic repaired-atlas checks. NOT VERIFIED in licensed Rhino.

No fixture contains a user model, source identifier, native capture transcript,
or a fabricated production attachment proof.
"""
import copy
import pathlib
import sys
import types
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'src/SmartSkin.Rhino8/Python'))
import repaired_validation as rv
import skin_kernel as sk


def plane(x0, x1, y0=0., y1=1., **metadata):
    out = dict(degree_u=1, degree_v=1, knots_u=[0., 0., 1., 1.], knots_v=[0., 0., 1., 1.],
               domain=[[0., 1.], [0., 1.]], homogeneous_cp=[[[x, y, 0., 1.] for y in (y0, y1)] for x in (x0, x1)])
    out.update(metadata)
    return out


def line(a, b):
    return dict(degree=1, knots=[0., 0., 1., 1.], domain=[0., 1.],
                homogeneous_cp=[list(a) + [1.], list(b) + [1.]])


def owner(sign, reversed=False):
    # Numeric orientation input only. Deliberately NOT complete Rhino capture.
    return dict(edge_inward_cross_sign=sign, face_orientation_reversed=reversed)


def fixture():
    model = types.SimpleNamespace(tolerance=1e-5, scale=6., v0=0., v1=1.,
                                  spec=dict(absolute_tolerance=1e-5, angle_tolerance=1e-3, curvature_tolerance=1e-6))
    surfaces = [plane(0., 1., kind='collar', side=0, piece=0),
                plane(6., 5., kind='collar', side=1, piece=0)]
    surfaces += [plane(float(i + 1), float(i + 2), kind='middle', side=None, piece=i) for i in range(4)]
    roles = dict(
        side0=[dict(source_key='synthetic-left', curve=line([0., 0., 0.], [0., 1., 0.]), surface=plane(-1., 0.), owner_side=owner(1),
                    parameter_map=dict(boundary_chart_u=0., edge_parameter_from_chart_v=[1., 0.], native_uv_from_chart_uv=dict(matrix=[[-1., 0.], [0., 1.]], offset=[1., 0.])))],
        side1=[dict(source_key='synthetic-right', curve=line([6., 0., 0.], [6., 1., 0.]), surface=plane(6., 7.), owner_side=owner(-1),
                    parameter_map=dict(boundary_chart_u=0., edge_parameter_from_chart_v=[1., 0.], native_uv_from_chart_uv=dict(matrix=[[1., 0.], [0., 1.]], offset=[0., 0.])))],
        upper=[dict(source_key='synthetic-upper', curve=line([0., 0., 0.], [6., 0., 0.]), surface=plane(0., 6., -1., 0.), owner_side=owner(-1))],
        lower=[dict(source_key='synthetic-lower', curve=line([0., 1., 0.], [6., 1., 0.]), surface=plane(0., 6., 1., 2.), owner_side=owner(1))])
    guides = [dict(line([float(i + 1), 0., 0.], [float(i + 1), 1., 0.]), kind='profile', piece=i) for i in range(5)]
    return model, dict(surfaces=surfaces, guides=guides, network={}), roles


class RepairedValidationTests(unittest.TestCase):
    def test_complete_numeric_atlas_is_honest_about_missing_separation(self):
        model, result, roles = fixture()
        before = copy.deepcopy((result, roles))
        report = rv.validate_repaired_numeric(model, result, roles)
        self.assertTrue(report['checked'], report['reason'])
        self.assertTrue(report['numeric_source_finite_samples_pass'], report['failures'])
        self.assertTrue(report['numeric_shared_finite_samples_pass'], report['failures'])
        self.assertTrue(report['orientation']['compatible'])
        self.assertEqual(report['orientation']['orientation_reversed'], [False, True, False, False, False, False])
        self.assertGreater(report['minimum_native_outward_cosine'], .99)
        self.assertEqual(report['pending_gates'], ['bounded_native_parent_separation'])
        self.assertFalse(report['full_boundary_pass'])
        self.assertFalse(report['source_full_finite_boundary_pass'])
        self.assertFalse(report['shared_full_finite_boundary_pass'])
        self.assertNotIn('attachment_proof', report)
        self.assertEqual((result, roles), before)

    def test_unknown_kind_fails_closed(self):
        model, result, roles = fixture(); result['surfaces'][0]['kind'] = 'unvalidated_extension'
        report = rv.validate_repaired_numeric(model, result, roles)
        self.assertFalse(report['checked']); self.assertIn('Unknown repaired surface kind', report['reason'])

    def test_unknown_role_fails_closed(self):
        model, result, roles = fixture()
        result['surfaces'][0]['boundary_roles'] = {'bottom': dict(role='not_a_contract')}
        report = rv.validate_repaired_numeric(model, result, roles)
        self.assertFalse(report['checked']); self.assertIn('Unknown repaired boundary role', report['reason'])

    def test_lower_point_cannot_receive_exception(self):
        model, result, roles = fixture()
        result['surfaces'][0]['boundary_roles'] = {'top': dict(role='approved_source_vertex', physical_dimension=0, corner_id='lower:side0')}
        report = rv.validate_repaired_numeric(model, result, roles)
        self.assertFalse(report['checked']); self.assertIn('Only the collapsed upper source point', report['reason'])

    def test_missing_native_role_is_rejected(self):
        model, result, roles = fixture(); roles.pop('lower')
        report = rv.validate_repaired_numeric(model, result, roles)
        self.assertFalse(report['checked']); self.assertFalse(report['full_boundary_pass'])

    def test_actual_selected_curve_is_checked_not_just_parent_plane(self):
        model, result, roles = fixture()
        roles['upper'][0]['curve'] = line([0., -.1, 0.], [6., -.1, 0.])
        report = rv.validate_repaired_numeric(model, result, roles)
        self.assertTrue(report['checked'], report['reason'])
        self.assertFalse(report['numeric_source_finite_samples_pass'])
        self.assertIn('SOURCE_LOCUS', {f['code'] for f in report['failures']})

    def test_same_side_native_arrival_is_rejected(self):
        model, result, roles = fixture(); roles['side0'][0]['owner_side']['edge_inward_cross_sign'] *= -1
        report = rv.validate_repaired_numeric(model, result, roles)
        self.assertIn('NATIVE_OUTWARD_SIDE', {f['code'] for f in report['failures']})
        self.assertFalse(report['numeric_source_finite_samples_pass'])

    def test_missing_owner_evidence_is_pending_never_fabricated(self):
        model, result, roles = fixture()
        for records in roles.values():
            for record in records: record.pop('owner_side')
        report = rv.validate_repaired_numeric(model, result, roles)
        self.assertTrue(report['checked'], report['reason'])
        self.assertIn('native_outward_side_capture', report['pending_gates'])
        self.assertFalse(report['native_provenance_verified'])

    def test_off_skin_guide_is_rejected(self):
        model, result, roles = fixture(); result['guides'][0]['homogeneous_cp'][0][2] = .1
        report = rv.validate_repaired_numeric(model, result, roles)
        self.assertIn('GUIDE_NOT_ON_SKIN', {f['code'] for f in report['failures']})
        self.assertFalse(report['guide_coverage']['compatible'])

    def test_production_requires_actual_capture(self):
        model, result, roles = fixture()
        with self.assertRaises(Exception) as caught:
            rv.validate_repaired(model, result)
        self.assertIn('NATIVE_BOUNDARY_EVIDENCE', str(caught.exception))

    def test_cancellation_is_not_converted_to_pass(self):
        model, result, roles = fixture()
        with self.assertRaises(sk.Cancelled):
            rv.validate_repaired_numeric(model, result, roles, cancelled=lambda: True)

    def test_source_contact_ledger_uses_actual_generated_edge_units(self):
        model, result, roles = fixture()
        for surface in result['surfaces']:
            surface['domain'][0] = [-2., 3.]
            surface['knots_u'] = [-2., -2., 3., 3.]
        report = rv.validate_repaired_numeric(model, result, roles)
        self.assertTrue(report['numeric_source_finite_samples_pass'], report['reason'])
        ledger = report['native_contact_ledger']
        self.assertTrue(ledger['checked'])
        self.assertFalse(ledger['internal_seams_are_allowed_contacts'])
        for contact in ledger['contacts']:
            self.assertEqual(set(contact), {'surface_index', 'edge', 'source_key', 'native_parameter_interval', 'generated_parameter_interval'})
            if contact['edge'] in ('bottom', 'top'):
                self.assertEqual(contact['generated_parameter_interval'], [-2., 3.])
        self.assertTrue(ledger['point_contacts'])
        self.assertTrue(report['atlas_adjacency']['checked'])
        self.assertEqual(len(report['atlas_adjacency']['shared_edges']), 5)
        for pair in report['atlas_adjacency']['shared_edges']:
            self.assertTrue(all(0. <= t <= 1. for interval in pair['normalized_intervals'] for t in interval))
            self.assertIn(pair['normal_orientation'], (-1, 1))
        self.assertNotIn('attachment_proof', report)

    def test_missing_displayed_profile_is_not_guide_coverage(self):
        model, result, roles = fixture(); result['guides'].pop()
        report = rv.validate_repaired_numeric(model, result, roles)
        self.assertIn('GUIDE_PROFILE_COVERAGE', {f['code'] for f in report['failures']})
        self.assertFalse(report['guide_coverage']['compatible'])

    def test_new_shared_guide_requires_both_coincident_bindings(self):
        model, result, roles = fixture()
        role = dict(role='new_shared_2jet', seam_id='synthetic-shared', parameter_interval=[0., 1.])
        result['surfaces'][0]['boundary_roles'] = dict(right=role)
        result['surfaces'][2]['boundary_roles'] = dict(left=copy.deepcopy(role))
        result['guides'][0]['guide_id'] = 'synthetic-shared'
        report = rv.validate_repaired_numeric(model, result, roles)
        self.assertIn('GUIDE_SHARED_COVERAGE', {f['code'] for f in report['failures']})
        result['guides'][0]['coincident_bindings'] = [dict(surface_index=0, varying_axis='v', constant_parameter=1.)]
        report = rv.validate_repaired_numeric(model, result, roles)
        self.assertTrue(report['guide_coverage']['compatible'], report['failures'])

    def test_network_cannot_declare_an_internal_seam_native(self):
        model, result, roles = fixture()
        result['network']['repaired_boundary_roles'] = [dict(surface_index=2, edge='right', role='native_lower')]
        report = rv.validate_repaired_numeric(model, result, roles)
        self.assertIn('GUIDE_NATIVE_ROLE_COVERAGE', {f['code'] for f in report['failures']})

    def test_two_stage_wrapper_never_fabricates_native_screen_receipt(self):
        # This tests only the wrapper contract with explicit mocks. It is not
        # native evidence and does not test or bypass production capture.
        model, result, _ = fixture()
        model.spec['source_boundaries'] = dict(roles={})
        approved = {}
        result['surfaces'] = []
        for side in (0, 1):
            key = 'upper:side' + str(side)
            binding = dict(corner_id=key, role='upper_source_corner', side_role='side' + str(side),
                           upper_source_key='synthetic-upper', upper_native_parameter=float(side),
                           side_source_key='synthetic-side' + str(side), side_native_parameter=0.)
            approved[key] = dict(binding=binding, point=[float(side), 0., 0.])
            result['surfaces'] += [dict(kind='upper_hard_corner', approved_physical_corner_id=key,
                                        source_corner_binding=copy.deepcopy(binding)) for _ in range(2)]
        report = dict(checked=True, fatal=True, failures=[], reason='pending',
                      numeric_source_finite_samples_pass=True, numeric_shared_finite_samples_pass=True,
                      numeric_geometry_samples_pass=True, geometry_valid=False,
                      orientation=dict(compatible=True, orientation_reversed=[False, True, True, False]),
                      guide_coverage=dict(compatible=True), native_contact_ledger=dict(checked=True),
                      pending_gates=['bounded_native_parent_separation'], upper_radial_certificates=[dict(passed=True) for _ in range(4)])
        family = rv._module('native_family')
        with mock.patch.object(family, 'require_native_provenance', return_value=True), \
             mock.patch.object(sk, '_approved_upper_corner_bindings', return_value=approved), \
             mock.patch.object(rv, 'validate_repaired_numeric', return_value=report):
            checked = rv.validate_repaired(model, result)
        self.assertTrue(checked['full_boundary_pass'])
        self.assertFalse(checked['fatal'])
        self.assertEqual(checked['disposition'], 'native_screen_pending')
        self.assertFalse(checked['experimental_commit_allowed'])
        self.assertNotIn('native_separation_proof', checked)
        self.assertEqual(checked['attachment_proof']['excluded_points'], [approved[k]['binding'] for k in sorted(approved)])
        self.assertEqual(set(checked['attachment_proof']), {'schema', 'checked', 'source_full_finite_boundary_pass',
                         'shared_full_finite_boundary_pass', 'corner_policy', 'excluded_intervals', 'excluded_points'})
        self.assertEqual([s['orientation_reversed'] for s in checked['surfaces']], [False, True, True, False])
        self.assertEqual(checked['report']['geometry_digest'],rv._digest(checked['surfaces']))
        self.assertEqual(checked['native_contact_ledger']['geometry_digest'],rv._digest(checked['surfaces']))

    def test_every_repeated_knot_uses_two_limits(self):
        model, result, roles = fixture()
        record = result['surfaces'][0]
        record['homogeneous_cp'] = [[[x, y, 0., 1.] for y in (0., .5, 1.)] for x in (0., 1.)]
        record['knots_v'] = [0., 0., .5, 1., 1.]
        validator = rv._Validator(model, result, roles, None, None)
        validator.ledger()
        seen = []
        original = validator.jets
        def spy(index, u, v, precise=False):
            if index == 0: seen.append(v)
            return original(index, u, v, precise)
        validator.jets = spy
        validator.compare_shared()
        self.assertIn(np.nextafter(.5, -np.inf), seen)
        self.assertIn(np.nextafter(.5, np.inf), seen)


if __name__ == '__main__': unittest.main()
