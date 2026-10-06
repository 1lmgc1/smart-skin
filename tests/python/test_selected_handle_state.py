"""Selected U/V prototype contracts; these are not Rhino or fan-solver tests."""
import copy
import importlib.util
from pathlib import Path
import unittest
from types import SimpleNamespace
from attachment_proof_fixtures import source_model, full_attachment_result, shared_tolerances, edit_result

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('selected_handle_preview_test', ROOT / 'src/SmartSkin.Rhino8/Python/preview.py')
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


def catalog():
    def handle(identifier, guide, axis, direction):
        return {'id': identifier, 'guide_id': guide, 'varying_axis': axis,
                'label': identifier, 'minimum': -1.0, 'maximum': 1.0, 'neutral': 0.0,
                'units': 'model units', 'anchor': [0, 0, 0], 'position': [0, 0, 1],
                'direction': direction, 'mirror_handle_id': identifier}
    return {'schema': preview.HANDLE_EDIT_SCHEMA, 'enabled': True,
            'basis_id': 'synthetic-interior-bump-v1', 'preserves_attachment_order': 2,
            'shared_tolerances': shared_tolerances(),
            'symmetry_tolerance': 1e-6,
            'handles': [handle('u-interior', 'row:0', 'u', [0, 0, 1]),
                        handle('v-interior', 'profile:0', 'v', [0, 1, 0])]}


def proven_result(token):
    # Test-only returned geometry markers include cross-handle influence.
    values = dict(token.values)
    positions = {key: [0., .25 * sum(value for other, value in values.items() if other != key), 1. + values[key]]
                 for key in values}
    return edit_result(token.payload, positions)


class SelectedHandleTests(unittest.TestCase):
    def controller(self):
        return preview.HandleEditState(catalog(), evaluator_available=True)

    def mirrored_controller(self):
        data = catalog()
        partner = copy.deepcopy(data['handles'][1])
        partner.update(id='v-mirror', guide_id='profile:4', mirror_handle_id='v-interior')
        data['handles'][1]['mirror_handle_id'] = 'v-mirror'
        data['handles'].append(partner)
        return preview.HandleEditState(data, True)

    def test_mirror_pair_updates_atomically_and_retains_other_values(self):
        state = self.mirrored_controller()
        state.select_guide('profile:0')
        state.set_selected_value(.6)
        self.assertEqual(state.values, {'u-interior': 0., 'v-interior': .6, 'v-mirror': .6})
        state.select_guide('profile:4')
        state.set_selected_value(-.2)
        self.assertEqual(state.values['v-interior'], -.2)
        self.assertEqual(state.values['v-mirror'], -.2)

    def test_locked_mirror_partner_cannot_partially_change_pair(self):
        state = self.mirrored_controller()
        state.handles['v-mirror']['locked_reason'] = 'Mirrored source lock.'
        state.select_guide('profile:0')
        before = dict(state.values)
        with self.assertRaisesRegex(ValueError, 'Mirrored source lock'):
            state.set_selected_value(.5)
        self.assertEqual(state.values, before)

    def test_asymmetric_pair_and_nonreciprocal_catalog_fail_closed(self):
        state = self.mirrored_controller()
        state.values['v-mirror'] = .2
        with self.assertRaisesRegex(ValueError, 'Mirrored handle values must be equal'):
            state.snapshot(1)
        data = catalog()
        data['handles'][0]['mirror_handle_id'] = 'v-interior'
        with self.assertRaisesRegex(ValueError, 'reciprocal'):
            preview.HandleEditState(data, True)

    def test_moved_shared_trace_is_allowed_when_postedit_two_jets_are_compatible(self):
        state = self.controller()
        token = state.snapshot(1)
        result = proven_result(token)
        result['shared_trace_moved'] = True
        result['edit_proof']['shared_2jets_unchanged'] = False
        state.verify_result(token, result)

    def test_shared_g0_g1_g2_residual_failures_cannot_be_relaxed(self):
        state = self.controller()
        token = state.snapshot(1)
        for metric in preview.SHARED_METRICS:
            result = proven_result(token)
            result['edit_proof']['shared_residuals'][metric] = 2 * result['edit_proof']['shared_tolerances'][metric]
            with self.assertRaisesRegex(ValueError, 'exceeds'):
                state.verify_result(token, result)
            result['edit_proof']['shared_tolerances'][metric] *= 4
            with self.assertRaisesRegex(ValueError, 'changed the prepared'):
                state.verify_result(token, result)

    def test_equal_mirrored_values_do_not_substitute_for_geometric_symmetry(self):
        state = self.mirrored_controller()
        state.select_guide('profile:0')
        state.set_selected_value(.5)
        token = state.snapshot(1)
        self.assertEqual(state.values['v-interior'], state.values['v-mirror'])
        for changes in ({'symmetry_checked': False}, {'symmetry_compatible': False},
                        {'symmetry_residual': 1e-3}, {'symmetry_residual': float('nan')},
                        {'symmetry_tolerance': float('inf')}):
            result = proven_result(token)
            result['edit_proof'].update(changes)
            with self.assertRaisesRegex(ValueError, 'symmetry'):
                state.verify_result(token, result)

    def test_geometric_symmetry_tolerance_cannot_be_loosened(self):
        state = self.controller()
        token = state.snapshot(1)
        result = proven_result(token)
        result['edit_proof']['symmetry_tolerance'] = .1
        with self.assertRaisesRegex(ValueError, 'changed the prepared geometric symmetry'):
            state.verify_result(token, result)

    def test_failed_fresh_symmetry_does_not_replace_last_displayed_geometry(self):
        state = self.controller()
        state.select_guide('row:0')
        old = state.snapshot(1)
        old_result = proven_result(old)
        state.accept(old, old_result)
        state.set_selected_value(.5)
        new = state.snapshot(2)
        result = proven_result(new)
        result['edit_proof']['symmetry_checked'] = False
        with self.assertRaisesRegex(ValueError, 'symmetry'):
            state.accept(new, result)
        self.assertEqual(state.display_handle()[1], (0., 0., 1.))
        state.restore_last_valid()
        state.verify_displayed_result(old, old_result)

    def test_actual_positions_include_cross_handle_and_mirror_motion(self):
        state = self.mirrored_controller()
        state.select_guide('row:0')
        self.assertIsNone(state.display_handle())
        state.set_selected_value(.8)
        token = state.snapshot(1)
        result = proven_result(token)
        result['handle_positions']['v-mirror'] = [-2., .4, 3.]
        state.accept(token, result)
        state.select_guide('profile:0')
        self.assertEqual(state.values['v-interior'], 0.)
        self.assertEqual(state.display_handle()[1], (0., .2, 1.))
        state.select_guide('profile:4')
        self.assertEqual(state.display_handle()[1], (-2., .4, 3.))

    def test_missing_nonfinite_and_stale_actual_positions_are_rejected(self):
        state = self.controller()
        token = state.snapshot(4)
        for case in ('missing', 'stale', 'missing_id', 'nonfinite'):
            result = proven_result(token)
            if case == 'missing': del result['handle_positions_request']
            elif case == 'stale': result['handle_positions_request']['revision'] = 3
            elif case == 'missing_id': del result['handle_positions']['v-interior']
            else: result['handle_positions']['v-interior'][0] = float('nan')
            with self.assertRaises(ValueError):
                state.verify_result(token, result)

    def test_result_position_mutation_cannot_change_display_or_be_accepted(self):
        state = self.controller()
        state.select_guide('row:0')
        token = state.snapshot(1)
        result = proven_result(token)
        state.accept(token, result)
        result['handle_positions']['u-interior'][2] = 99.
        self.assertEqual(state.display_handle()[1], (0., 0., 1.))
        with self.assertRaisesRegex(ValueError, 'displayed accepted preview'):
            state.verify_displayed_result(token, result)

    def test_absent_engine_capability_disables_edits(self):
        state = preview.HandleEditState()
        self.assertFalse(state.enabled)
        self.assertIn('no verified constrained edit basis', state.reason)
        state.select_guide('row:0')
        with self.assertRaises(ValueError):
            state.set_selected_value(.5)
        with self.assertRaises(ValueError):
            state.snapshot(1)

    def test_capability_without_actual_evaluator_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            preview.HandleEditState(catalog(), evaluator_available=False)

    def test_capability_requires_explicit_second_order_constraint(self):
        data = catalog()
        data['preserves_attachment_order'] = 1
        with self.assertRaises(ValueError):
            preview.HandleEditState(data, True)

    def test_one_selected_handle_does_not_change_other_values(self):
        state = self.controller()
        state.select_guide('row:0')
        state.set_selected_value(.6)
        self.assertEqual(state.values, {'u-interior': .6, 'v-interior': 0.0})
        state.select_guide('profile:0')
        state.set_selected_value(-.4)
        self.assertEqual(state.values, {'u-interior': .6, 'v-interior': -.4})
        state.select_guide('row:0')
        self.assertEqual(state.values[state.selected_handle], .6)

    def test_request_has_no_global_h_alias_and_is_immutable(self):
        state = self.controller()
        state.select_guide('row:0')
        state.set_selected_value(.6)
        token = state.snapshot(7)
        payload = token.payload
        self.assertNotIn('h', payload)
        self.assertEqual(payload['revision'], 7)
        payload['values']['u-interior'] = -.9
        state.set_selected_value(.2)
        self.assertEqual(dict(token.values)['u-interior'], .6)
        self.assertEqual(token.payload['values']['u-interior'], .6)

    def test_cross_guide_handle_selection_is_rejected(self):
        state = self.controller()
        state.select_guide('row:0')
        with self.assertRaisesRegex(ValueError, 'does not belong'):
            state.select_handle('v-interior')

    def test_locked_handle_cannot_move(self):
        data = catalog()
        data['handles'][0]['locked_reason'] = 'Boundary two-jet is fixed.'
        state = preview.HandleEditState(data, True)
        state.select_guide('row:0')
        with self.assertRaisesRegex(ValueError, 'two-jet is fixed'):
            state.set_selected_value(.5)

    def test_out_of_range_or_nonfinite_values_cannot_move(self):
        state = self.controller()
        state.select_guide('row:0')
        for value in (-1.1, 1.1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                state.set_selected_value(value)

    def test_result_must_echo_exact_snapshot(self):
        state = self.controller()
        token = state.snapshot(3)
        result = proven_result(token)
        result['edit_request']['values']['u-interior'] = .3
        with self.assertRaisesRegex(ValueError, 'does not match'):
            state.verify_result(token, result)

    def test_every_current_attachment_proof_is_required(self):
        state = self.controller()
        token = state.snapshot(3)
        state.verify_result(token, proven_result(token))
        for key in ('checked', 'source_2jets_unchanged', 'shared_2jets_compatible'):
            for invalid in (False, None, 1):
                result = proven_result(token)
                result['edit_proof'][key] = invalid
                with self.assertRaisesRegex(ValueError, 'was not verified'):
                    state.verify_result(token, result)

    def test_restoring_preview_restores_every_handle_value(self):
        state = self.controller()
        state.select_guide('row:0')
        state.set_selected_value(.2)
        token = state.snapshot(1)
        state.accept(token, proven_result(token))
        state.select_guide('profile:0')
        state.set_selected_value(.9)
        self.assertTrue(state.restore_last_valid())
        self.assertEqual(state.values, {'u-interior': .2, 'v-interior': 0.0})

    def test_visible_handle_uses_visible_geometry_not_pending_slider(self):
        state = self.controller()
        state.select_guide('row:0')
        token = state.snapshot(1)
        state.accept(token, proven_result(token))
        state.set_selected_value(.8)
        self.assertEqual(state.display_handle()[1], (0.0, 0.0, 1.0))
        token = state.snapshot(2)
        state.accept(token, proven_result(token))
        self.assertEqual(state.display_handle()[1], (0.0, 0.0, 1.8))

    def test_new_local_edit_cancels_old_work_using_existing_revision_guard(self):
        edits, state = self.controller(), preview.PreviewState()
        edits.select_guide('row:0')
        edits.set_selected_value(.2)
        state.request(1.0)
        old_state_token = state.begin()
        old_edit = edits.snapshot(old_state_token[0])
        edits.set_selected_value(.8)
        state.request(1.0)
        self.assertTrue(state.superseded(old_state_token))
        self.assertFalse(state.complete(old_state_token, True))
        self.assertFalse(state.can_accept)
        self.assertEqual(old_edit.payload['values']['u-interior'], .2)
        new_state_token = state.begin()
        new_edit = edits.snapshot(new_state_token[0])
        edits.verify_result(new_edit, proven_result(new_edit))
        self.assertTrue(state.complete(new_state_token, True))
        edits.accept(new_edit, proven_result(new_edit))
        self.assertTrue(state.can_accept)

    def test_duplicate_handle_ids_are_rejected(self):
        data = catalog()
        data['handles'].append(copy.deepcopy(data['handles'][0]))
        with self.assertRaisesRegex(ValueError, 'unique'):
            preview.HandleEditState(data, True)

    def test_current_guide_pieces_group_to_actual_uv_selection(self):
        descriptors = [{'kind': 'profile', 'piece': p} for p in range(5)]
        for row in range(9):
            descriptors += [{'kind': 'row_collar', 'row': row, 'side': side} for side in range(2)]
            descriptors += [{'kind': 'row_middle', 'row': row, 'piece': p} for p in range(4)]
        groups = preview.group_uv_guides(descriptors)
        self.assertEqual(len(groups), 14)
        self.assertEqual(len([g for g in groups if g['varying_axis'] == 'u']), 9)
        self.assertEqual(len([g for g in groups if g['varying_axis'] == 'v']), 5)
        self.assertEqual(next(g['indices'] for g in groups if g['id'] == 'row:0'), [5, 6, 7, 8, 9, 10])

    def test_selected_request_calls_actual_edit_api_not_global_h(self):
        state = self.controller()
        state.select_guide('row:0')
        state.set_selected_value(.6)
        requests = []
        def evaluate_edit(request, cancelled):
            requests.append(request)
            return proven_result(state.snapshot(request['revision']))
        def global_h(*args, **kwargs):
            self.fail('A selected-handle request must never fall back to global h.')
        model = SimpleNamespace(evaluate=global_h, evaluate_edit=evaluate_edit)
        output, token = preview.evaluate_preview_request(model, state, 5, lambda: False)
        self.assertEqual(requests[0]['values']['u-interior'], .6)
        self.assertEqual(token.revision, 5)
        self.assertEqual(output['edit_request'], token.payload)

    def test_failed_local_api_is_not_silently_retried_as_global(self):
        state = self.controller()
        def failed(*args, **kwargs):
            raise RuntimeError('Local basis failed.')
        def global_h(*args, **kwargs):
            self.fail('A failed local edit must not become a global edit.')
        with self.assertRaisesRegex(RuntimeError, 'Local basis failed'):
            preview.evaluate_preview_request(SimpleNamespace(evaluate=global_h, evaluate_edit=failed), state, 3, lambda: False)

    def test_missing_capability_uses_fixed_inspection_baseline_only(self):
        calls = []
        def baseline(h, cancelled):
            calls.append(h)
            return {'valid': True}
        output, token = preview.evaluate_preview_request(SimpleNamespace(evaluate=baseline), preview.HandleEditState(), 3, lambda: False)
        self.assertEqual(calls, [1.0])
        self.assertIsNone(token)
        self.assertFalse(preview.attachment_acceptance(output)[0])


class AttachmentAcceptanceTests(unittest.TestCase):
    def test_exception_registry_comes_from_captured_source_roles_and_native_parameters(self):
        approved = preview.approved_upper_source_corners(source_model())
        self.assertEqual(set(approved), {'upper:side0', 'upper:side1'})
        self.assertEqual(approved['upper:side0']['upper_source_key'], 'synthetic-upper-edge')
        self.assertEqual(approved['upper:side0']['upper_native_parameter'], 10.0)
        self.assertEqual(approved['upper:side0']['side_native_parameter'], -2.0)
        self.assertEqual(approved['upper:side1']['upper_native_parameter'], 20.0)
        self.assertEqual(approved['upper:side1']['side_native_parameter'], 12.0)

    def test_full_proof_without_capture_binding_still_cannot_authorize_exceptions(self):
        output = full_attachment_result()
        self.assertFalse(preview.attachment_acceptance(output)[0])
        model = source_model()
        model['source_boundaries']['complete'] = False
        self.assertFalse(preview.attachment_acceptance(output, model)[0])

    def test_incident_source_endpoints_must_describe_the_same_physical_vertex(self):
        model = source_model()
        model['source_boundaries']['roles']['side0'][0]['reference_corners'][0]['point'] = [0, .1, 0]
        allowed, reason = preview.attachment_acceptance(full_attachment_result(), model)
        self.assertFalse(allowed)
        self.assertIn('do not meet', reason)

    def test_interior_upper_chain_native_endpoint_is_not_an_approved_corner(self):
        model = source_model()
        roles = model['source_boundaries']['roles']
        left, right = copy.deepcopy(roles['upper'][0]), copy.deepcopy(roles['upper'][0])
        left['source_key'] = 'synthetic-upper-left'
        left['original_curve_domain'] = left['traversal_domain'] = [10.0, 15.0]
        left['reference_corners'][1].update(edge_parameter=15.0, point=[1, 0, 0])
        right['source_key'] = 'synthetic-upper-right'
        right['original_curve_domain'] = right['traversal_domain'] = [15.0, 20.0]
        right['reference_corners'][0].update(edge_parameter=15.0, point=[1, 0, 0])
        roles['upper'] = [left, right]
        model['source_boundaries']['source_edge_count'] = 5
        approved = preview.approved_upper_source_corners(model)
        self.assertEqual(approved['upper:side1']['upper_source_key'], 'synthetic-upper-right')
        output = full_attachment_result()
        interior = dict(approved['upper:side0'], upper_native_parameter=15.0)
        output['attachment_proof']['excluded_points'] = [interior]
        self.assertFalse(preview.attachment_acceptance(output, model)[0])

    def test_result_side_allowlist_cannot_expand_approved_source_vertices(self):
        output = full_attachment_result()
        output['attachment_proof']['approved_corners'] = [{'corner_id': 'unrelated-seam:end'}]
        allowed, reason = preview.attachment_acceptance(output, source_model())
        self.assertFalse(allowed)
        self.assertIn('result-side allowlists', reason)

    def test_old_partial_gate_cannot_authorize_baseline_acceptance(self):
        output = {'valid': True, 'experimental_commit_allowed': True,
                  'report': {'checked': True, 'fatal': False, 'full_boundary_pass': False}}
        self.assertFalse(preview.attachment_acceptance(output)[0])

    def test_preserving_bad_baseline_does_not_prove_attachments(self):
        state = preview.HandleEditState(catalog(), True)
        output = proven_result(state.snapshot(1))
        self.assertFalse(preview.attachment_acceptance(output)[0])

    def test_explicit_full_finite_boundary_proof_is_required(self):
        output = full_attachment_result()
        self.assertTrue(preview.attachment_acceptance(output, source_model())[0])
        for key in ('checked', 'source_full_finite_boundary_pass', 'shared_full_finite_boundary_pass'):
            trial = copy.deepcopy(output)
            trial['attachment_proof'][key] = False
            self.assertFalse(preview.attachment_acceptance(trial, source_model())[0])

    def test_finite_width_endpoint_exclusion_is_rejected(self):
        output = full_attachment_result()
        output['attachment_proof']['excluded_intervals'] = [[0.0, .000001]]
        allowed, reason = preview.attachment_acceptance(output, source_model())
        self.assertFalse(allowed)
        self.assertIn('Finite-width', reason)

    def test_broader_corner_policy_is_rejected(self):
        output = full_attachment_result()
        output['attachment_proof']['corner_policy'] = 'source_end_strips'
        self.assertFalse(preview.attachment_acceptance(output, source_model())[0])

    def test_transaction_blocks_partial_result_before_any_document_add(self):
        class NeverWriteDoc:
            def __getattr__(self, name):
                raise AssertionError('The document must not be touched after a missing attachment proof.')
        capture = SimpleNamespace(verify_sources=lambda doc: (True, ''))
        with self.assertRaisesRegex(RuntimeError, 'Attachment acceptance blocked'):
            preview.commit_new_geometry(NeverWriteDoc(), capture, [object()], [], 1.0, None, None,
                                        attachment_result={'valid': True})


class SyntheticBoundarySafeBasisTests(unittest.TestCase):
    """One degree-(6,6) synthetic interior bump, NOT the native fan solver.

    Only Bernstein control point (3,3) changes. Three outer control rows on
    every side remain exactly zero, so all boundary partials through order two
    vanish. Existing shared boundary traces remain untouched on adjacent
    synthetic patches. This cannot prove nonzero shared-guide editing.
    """

    @staticmethod
    def derivative(t, order):
        # B_(3,6)(t) = 20 t^3 (1-t)^3. Exact integer coefficients.
        coefficients = [0, 0, 0, 20, -60, 60, -20]
        for _ in range(order):
            coefficients = [i * value for i, value in enumerate(coefficients)][1:]
        return sum(value * t ** power for power, value in enumerate(coefficients))

    @classmethod
    def delta(cls, u, v, du=0, dv=0, value=1.0):
        return value * cls.derivative(u, du) * cls.derivative(v, dv)

    def test_one_handle_changes_real_interior_geometry(self):
        self.assertGreater(abs(self.delta(.5, .5, value=.8)), .01)
        self.assertEqual(self.delta(.5, .5, value=0), 0)
        self.assertNotEqual(self.delta(.25, .5, value=.8), self.delta(.5, .5, value=.8))

    def test_all_four_fixed_boundaries_keep_two_jets_exactly(self):
        for t in (0, .125, .5, .875, 1):
            for du in range(3):
                for dv in range(3):
                    for u, v in ((0, t), (1, t), (t, 0), (t, 1)):
                        self.assertEqual(self.delta(u, v, du, dv), 0)

    def test_adjacent_patch_shared_two_jets_do_not_change(self):
        for t in (0, .125, .5, .875, 1):
            for du in range(3):
                for dv in range(3):
                    self.assertEqual(self.delta(1, t, du, dv, .8), self.delta(0, t, du, dv, -.3))

    def test_other_handle_remains_independent(self):
        selected_patch = self.delta(.5, .5, value=.8)
        other_patch = self.delta(.5, .5, value=0)
        self.assertNotEqual(selected_patch, other_patch)
        self.assertEqual(other_patch, 0)


class SyntheticMovedSharedTraceTests(unittest.TestCase):
    """A global polynomial restricted to two adjacent synthetic graph patches.

    This checks the revised contract's meaning, not the native-fan engine:
    interior shared traces may move with compatible jets on both incident
    patches, while the outer source boundary two-jets stay fixed.
    """
    @staticmethod
    def delta(x, v, dx=0, dv=0):
        coefficients = [1, 0, -3, 0, 3, 0, -1]  # (1-x*x)^3
        for _ in range(dx):
            coefficients = [i * value for i, value in enumerate(coefficients)][1:]
        return .8 * sum(value * x ** power for power, value in enumerate(coefficients)) * SyntheticBoundarySafeBasisTests.derivative(v, dv)

    def test_shared_trace_moves_instead_of_being_frozen(self):
        self.assertNotEqual(self.delta(0., .5), 0.)

    def test_both_patch_restrictions_have_identical_postedit_shared_two_jets(self):
        # Left chart x=u-1, right chart x=u, so dx/du=1 on both.
        for v in (.1, .3, .5, .9):
            for du in range(3):
                for dv in range(3):
                    self.assertEqual(self.delta(1.-1., v, du, dv), self.delta(0., v, du, dv))

    def test_original_outer_boundary_two_jets_remain_zero(self):
        for t in (0., .2, .5, .8, 1.):
            for dx in range(3):
                for dv in range(3):
                    for x, v in ((-1., t), (1., t), (2*t-1., 0.), (2*t-1., 1.)):
                        self.assertEqual(self.delta(x, v, dx, dv), 0.)


if __name__ == '__main__':
    unittest.main()
