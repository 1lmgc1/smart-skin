"""Non-native contract tests. These are NOT Rhino GUI or geometry certification."""
import importlib.util
import copy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock
from attachment_proof_fixtures import (source_model, full_attachment_result, edit_result, shared_tolerances,
                                     mock_verify_atlas, native_screen_fixture)
from attachment_proof_fixtures import add_test_descriptors

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("smart_skin_preview_test", ROOT / "src/SmartSkin.Rhino8/Python/preview.py")
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


class PreviewStateTests(unittest.TestCase):
    def ready(self):
        state = preview.PreviewState()
        token = state.begin()
        self.assertTrue(state.complete(token, True))
        self.assertTrue(state.can_accept)
        return state

    def test_initial_pending_cannot_accept(self):
        self.assertFalse(preview.PreviewState().can_accept)

    def test_pending_slider_change_cannot_accept_stale_preview(self):
        state = self.ready()
        state.request(1.25)
        self.assertFalse(state.can_accept)
        token = state.begin()
        self.assertIsNone(state.begin(), "reentrant rebuild must not start")
        self.assertTrue(state.complete(token, True))
        self.assertEqual(state.valid_h, 1.25)
        self.assertTrue(state.can_accept)

    def test_failed_setting_requires_explicit_visible_restore(self):
        state = self.ready()
        state.request(1.5)
        self.assertFalse(state.complete(state.begin(), False, "fold"))
        self.assertEqual(state.valid_h, 1.0)
        self.assertFalse(state.can_accept)
        self.assertTrue(state.restore_last_valid())
        self.assertEqual(state.requested_h, 1.0)
        self.assertTrue(state.can_accept)

    def test_no_restore_without_last_valid(self):
        state = preview.PreviewState()
        state.complete(state.begin(), False, "invalid")
        self.assertFalse(state.restore_last_valid())
        self.assertFalse(state.can_accept)

    def test_newer_request_wins_over_completed_old_evaluation(self):
        state = self.ready()
        state.request(0.75)
        token = state.begin()
        state.request(1.25)
        self.assertFalse(state.complete(token, True))
        self.assertTrue(state.pending)
        self.assertEqual(state.valid_h, 1.0)
        self.assertFalse(state.can_accept)

    def test_cancel_during_evaluation_cannot_publish(self):
        state = self.ready()
        state.request(0.5)
        token = state.begin()
        state.cancel()
        self.assertFalse(state.complete(token, True))
        self.assertFalse(state.can_accept)
        self.assertFalse(state.restore_last_valid())

    def test_new_slider_value_cooperatively_aborts_obsolete_work(self):
        state = self.ready()
        state.request(0.75)
        token = state.begin()
        self.assertFalse(state.superseded(token))
        state.request(1.25)
        self.assertTrue(state.superseded(token))
        self.assertFalse(state.complete(token, False, "superseded"))
        self.assertTrue(state.pending)
        self.assertIsNone(state.error)
        self.assertEqual(state.requested_h, 1.25)
        self.assertEqual(state.valid_h, 1.0)

    def test_close_and_escape_abort_current_work(self):
        for method in ("close", "cancel"):
            state = preview.PreviewState()
            token = state.begin()
            getattr(state, method)()
            self.assertTrue(state.superseded(token))

    def test_closed_state_ignores_queued_changes(self):
        state = self.ready()
        state.close()
        state.request(1.4)
        self.assertEqual(state.requested_h, 1.0)
        self.assertIsNone(state.begin())
        self.assertFalse(state.can_accept)

    def test_handle_bounds_and_finite_input(self):
        for value in (0.49, 1.51, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                preview.PreviewState().request(value)


class FakeAttributes:
    def SetUserString(self, key, value):
        return True

    def Dispose(self):
        pass


class FakeTable:
    def __init__(self, fail_add=0, fail_delete=False):
        self.objects = {1: SimpleNamespace(IsDeleted=False)}
        self.add_calls = 0
        self.deleted = []
        self.fail_add = fail_add
        self.fail_delete = fail_delete

    def AddBrep(self, geometry, attributes):
        self.add_calls += 1
        if self.add_calls == self.fail_add:
            return 0
        identifier = 100 + self.add_calls
        self.objects[identifier] = SimpleNamespace(IsDeleted=False)
        return identifier

    AddCurve = AddBrep

    def FindId(self, identifier):
        return self.objects.get(identifier)

    def Delete(self, identifier, quiet):
        self.deleted.append(identifier)
        if self.fail_delete:
            return False
        self.objects[identifier].IsDeleted = True
        return True


class FakeDoc:
    def __init__(self, active=True, **kwargs):
        self.Objects = FakeTable(**kwargs)
        self.Views = SimpleNamespace(Redraw=lambda: None)
        self.UndoRecordingEnabled = True
        self.UndoRecordingIsActive = active
        self.CurrentUndoRecordSerialNumber = 5 if active else 0
        self.started = self.ended = 0

    def BeginUndoRecord(self, description):
        self.started += 1
        self.UndoRecordingIsActive = True
        self.CurrentUndoRecordSerialNumber = 8
        return 8

    def EndUndoRecord(self, serial):
        self.ended += 1
        self.UndoRecordingIsActive = False
        return True


class FakeCapture:
    def __init__(self, checks=(True, True)):
        self.checks = iter(checks)
        self.model = source_model()

    def verify_sources(self, doc):
        return next(self.checks), "mock source check"


class CommitTests(unittest.TestCase):
    rhino = SimpleNamespace(DocObjects=SimpleNamespace(ObjectAttributes=FakeAttributes))
    system = SimpleNamespace(Guid=SimpleNamespace(Empty=0))
    geometry = SimpleNamespace(IsValid=True)

    def setUp(self):
        from test_native_owner_separation import n
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(preview, '_native_owner_api', return_value=n).start()
        mock.patch.object(preview, '_verify_atlas_separation', side_effect=mock_verify_atlas).start()
        self.geometry = SimpleNamespace(IsValid=True)

    def commit(self, doc, capture=None):
        attachment_result = full_attachment_result(preview.ATTACHMENT_PROOF_SCHEMA)
        return self.commit_result(doc, attachment_result, capture)

    def prepared_edit_state(self, edit_request):
        handles = [{'id': key, 'guide_id': 'profile:' + str(index), 'mirror_handle_id': key,
                    'varying_axis': 'v', 'minimum': -1., 'maximum': 1., 'neutral': 0., 'units': 'model units',
                    'anchor': [0., 0., 0.], 'position': [0., 0., 1.], 'direction': [0., 0., 1.]}
                   for index, key in enumerate(edit_request['values'])]
        edit_state = preview.HandleEditState({'schema': preview.HANDLE_EDIT_SCHEMA, 'enabled': True,
                    'basis_id': edit_request['basis_id'], 'preserves_attachment_order': 2,
                    'symmetry_tolerance': 1e-6,
                    'shared_tolerances': shared_tolerances(), 'handles': handles}, True)
        edit_state.values = dict(edit_request['values'])
        token = edit_state.snapshot(edit_request['revision'])
        edit_state.accept(token, edit_result(edit_request))
        return edit_state

    def commit_result(self, doc, attachment_result, capture=None, edit_request=None, edit_state=None, cancelled=None):
        capture = capture or FakeCapture()
        if edit_request is not None and edit_state is None:
            edit_state = self.prepared_edit_state(edit_request)
        screened_result = edit_result(edit_request) if edit_request is not None else full_attachment_result()
        add_test_descriptors(attachment_result, [self.geometry, self.geometry], [self.geometry])
        for key in ('patches', 'surfaces', 'guides'):
            screened_result[key] = copy.deepcopy(attachment_result[key])
        screen = native_screen_fixture(preview, capture, [self.geometry, self.geometry], screened_result, edit_request,
                                       guides=[self.geometry])
        self.addCleanup(screen.close)
        return preview.commit_new_geometry(doc, capture,
                                           [self.geometry, self.geometry], [self.geometry],
                                           1.0, self.rhino, self.system, attachment_result=attachment_result,
                                           edit_request=edit_request, edit_state=edit_state, cancelled=cancelled, native_screen=screen)

    def test_oversized_direct_helper_inputs_add_nothing(self):
        for breps, guides in (([self.geometry] * (preview.MAX_PREVIEW_PATCHES + 1), []),
                              ([self.geometry], [self.geometry] * (preview.MAX_PREVIEW_GUIDES + 1))):
            doc = FakeDoc()
            with self.assertRaisesRegex(RuntimeError, 'count budget'):
                preview.commit_new_geometry(doc, FakeCapture(), breps, guides, 1., self.rhino, self.system,
                                            attachment_result=full_attachment_result())
            self.assertEqual(doc.Objects.add_calls, 0)
            self.assertEqual(doc.started, 0)
            self.assertFalse(doc.Objects.objects[1].IsDeleted)

    def test_infinite_direct_iterable_is_stopped_by_count_budget(self):
        import itertools
        doc = FakeDoc()
        with self.assertRaisesRegex(RuntimeError, 'count budget'):
            preview.commit_new_geometry(doc, FakeCapture(), itertools.repeat(self.geometry), [],
                                        1., self.rhino, self.system, attachment_result=full_attachment_result())
        self.assertEqual(doc.Objects.add_calls, 0)

    def test_cancel_before_commit_adds_nothing(self):
        doc = FakeDoc()
        with self.assertRaisesRegex(RuntimeError, 'Commit cancelled'):
            self.commit_result(doc, full_attachment_result(), cancelled=lambda: True)
        self.assertEqual(doc.Objects.add_calls, 0)
        self.assertEqual(doc.started, 0)

    def test_esc_during_add_rolls_back_only_own_ids(self):
        for event_point in ('first', 'last'):
            doc, stopped = FakeDoc(), [False]
            method = 'AddBrep' if event_point == 'first' else 'AddCurve'
            original_add = getattr(doc.Objects, method)
            def escape_during_add(geometry, attributes):
                identifier = original_add(geometry, attributes)
                stopped[0] = True
                return identifier
            setattr(doc.Objects, method, escape_during_add)
            with self.assertRaisesRegex(RuntimeError, 'Commit cancelled'):
                self.commit_result(doc, full_attachment_result(), cancelled=lambda: stopped[0])
            self.assertEqual(doc.Objects.add_calls, 1 if event_point == 'first' else 3)
            self.assertEqual(doc.Objects.deleted, [101] if event_point == 'first' else [103, 102, 101])
            self.assertFalse(doc.Objects.objects[1].IsDeleted)

    def test_native_add_callback_cannot_expand_frozen_commit_input(self):
        doc = FakeDoc()
        breps = [self.geometry]
        original_add = doc.Objects.AddBrep
        def append_during_add(geometry, attributes):
            breps.extend([self.geometry] * (preview.MAX_PREVIEW_PATCHES + 1))
            return original_add(geometry, attributes)
        doc.Objects.AddBrep = append_during_add
        capture, result = FakeCapture(), full_attachment_result()
        screen = native_screen_fixture(preview, capture, breps, result)
        self.addCleanup(screen.close)
        counts = preview.commit_new_geometry(doc, capture, breps, [], 1., self.rhino, self.system,
                                             attachment_result=result, native_screen=screen)
        self.assertEqual(counts, (1, 0))
        self.assertEqual(doc.Objects.add_calls, 1)

    def test_invalid_fatal_or_no_commit_disposition_cannot_be_overridden_by_attachment_flags(self):
        for changes in ({'valid': False}, {'geometry_valid': False}, {'fatal': True},
                        {'experimental_commit_allowed': True}, {'commit_allowed': False},
                        {'commit_disposition': 'inspection_only'}, {'preview_only': True}):
            doc, result = FakeDoc(), full_attachment_result()
            result.update(changes)
            with self.assertRaisesRegex(RuntimeError, 'Geometry acceptance blocked'):
                self.commit_result(doc, result)
            self.assertEqual(doc.Objects.add_calls, 0)
            self.assertFalse(doc.Objects.objects[1].IsDeleted)

    def test_geometry_disposition_rechecked_after_final_native_add(self):
        doc, result = FakeDoc(), full_attachment_result()
        original_add = doc.Objects.AddCurve
        def invalidate_after_final_add(geometry, attributes):
            identifier = original_add(geometry, attributes)
            result['fatal'] = True
            return identifier
        doc.Objects.AddCurve = invalidate_after_final_add
        with self.assertRaisesRegex(RuntimeError, 'Geometry acceptance blocked'):
            self.commit_result(doc, result)
        self.assertEqual(doc.Objects.add_calls, 3)
        self.assertEqual(doc.Objects.deleted, [103, 102, 101])
        self.assertFalse(doc.Objects.objects[1].IsDeleted)

    def test_reentrant_handle_request_rolls_back_before_next_add(self):
        for mode in ('changed_value', 'same_value', 'new_revision'):
            doc = FakeDoc()
            request, result = self.edit_request_and_result()
            state = self.prepared_edit_state(request)
            state.select_guide('profile:0')
            original_add = doc.Objects.AddBrep
            def request_during_native_add(geometry, attributes):
                identifier = original_add(geometry, attributes)
                state.set_selected_value(.5 if mode == 'changed_value' else .25)
                if mode == 'new_revision': state.snapshot(request['revision'] + 1)
                return identifier
            doc.Objects.AddBrep = request_during_native_add
            with self.assertRaisesRegex(RuntimeError, 'Selected-handle acceptance blocked'):
                self.commit_result(doc, result, edit_request=request, edit_state=state)
            self.assertEqual(doc.Objects.add_calls, 1)
            self.assertEqual(doc.Objects.deleted, [101])
            self.assertFalse(doc.Objects.objects[1].IsDeleted)

    def test_missing_proof_has_no_partial_fallback(self):
        doc = FakeDoc()
        with self.assertRaisesRegex(RuntimeError, "Attachment acceptance blocked"):
            preview.commit_new_geometry(doc, FakeCapture(), [self.geometry], [], 1.0, self.rhino, self.system)
        self.assertEqual(doc.Objects.add_calls, 0)
        self.assertEqual(doc.started, 0)

    def test_wrong_corner_internal_point_finite_band_and_forged_allowlist_never_add(self):
        corner = preview.approved_upper_source_corners(source_model())["upper:side0"]
        variants = []
        for changes in ({"upper_native_parameter": 15.0}, {"upper_native_parameter": 10.0 + 1e-12},
                        {"corner_id": "internal-seam:start", "role": "internal_junction"},
                        {"side_role": "lower"}, {"upper_source_key": "synthetic-unapproved-edge"}):
            result = full_attachment_result()
            result["attachment_proof"]["excluded_points"] = [dict(corner, **changes)]
            variants.append(result)
        band = full_attachment_result()
        band["attachment_proof"]["excluded_intervals"] = [[10.0, 10.0 + 1e-9]]
        variants.append(band)
        forged = full_attachment_result()
        forged["attachment_proof"]["approved_corners"] = [{"corner_id": "internal-seam:start"}]
        variants.append(forged)
        for result in variants:
            doc = FakeDoc()
            with self.assertRaisesRegex(RuntimeError, "Attachment acceptance blocked"):
                self.commit_result(doc, result)
            self.assertEqual(doc.Objects.add_calls, 0)
            self.assertFalse(doc.Objects.objects[1].IsDeleted)

    def test_approved_captured_upper_corner_can_be_declared(self):
        result = full_attachment_result()
        result["attachment_proof"]["excluded_points"] = list(preview.approved_upper_source_corners(source_model()).values())
        self.assertEqual(self.commit_result(FakeDoc(), result), (2, 1))

    def test_proof_is_rechecked_before_each_add_and_rolls_back_only_new_ids(self):
        doc, result = FakeDoc(), full_attachment_result()
        original_add = doc.Objects.AddBrep
        def invalidate_after_add(geometry, attributes):
            identifier = original_add(geometry, attributes)
            result["attachment_proof"]["source_full_finite_boundary_pass"] = False
            return identifier
        doc.Objects.AddBrep = invalidate_after_add
        with self.assertRaisesRegex(RuntimeError, "Attachment acceptance blocked"):
            self.commit_result(doc, result)
        self.assertEqual(doc.Objects.add_calls, 1)
        self.assertEqual(doc.Objects.deleted, [101])
        self.assertFalse(doc.Objects.objects[1].IsDeleted)

    def edit_request_and_result(self):
        request = {"schema": preview.HANDLE_EDIT_SCHEMA, "basis_id": "synthetic-basis", "revision": 7,
                   "values": {"synthetic-handle": .25}}
        result = edit_result(request)
        return request, result

    def test_edit_request_and_both_jet_proofs_are_mandatory_before_add(self):
        for case in ("echo", "source", "shared", "missing_request", "stale_positions", "changed_positions", "looser_tolerance",
                     "symmetry", "symmetry_unknown", "symmetry_looser"):
            doc = FakeDoc()
            request, result = self.edit_request_and_result()
            if case == "echo": result["edit_request"]["values"]["synthetic-handle"] = .5
            elif case == "source": result["edit_proof"]["source_2jets_unchanged"] = False
            elif case == "shared": result["edit_proof"]["shared_2jets_compatible"] = False
            elif case == "missing_request": request = None
            elif case == "stale_positions": result["handle_positions_request"]["revision"] -= 1
            elif case == "changed_positions": result["handle_positions"]["synthetic-handle"][2] = 99.
            elif case == "looser_tolerance": result["edit_proof"]["shared_tolerances"]["position"] = .1
            elif case == "symmetry": result["edit_proof"]["symmetry_residual"] = .1
            elif case == "symmetry_unknown": result["edit_proof"]["symmetry_checked"] = False
            elif case == "symmetry_looser": result["edit_proof"]["symmetry_tolerance"] = .1
            with self.assertRaises(RuntimeError):
                self.commit_result(doc, result, edit_request=request)
            self.assertEqual(doc.Objects.add_calls, 0)

    def test_edit_proof_rechecked_between_native_additions(self):
        doc = FakeDoc()
        request, result = self.edit_request_and_result()
        original_add = doc.Objects.AddBrep
        def invalidate_after_add(geometry, attributes):
            identifier = original_add(geometry, attributes)
            result["edit_proof"]["shared_2jets_compatible"] = False
            return identifier
        doc.Objects.AddBrep = invalidate_after_add
        with self.assertRaisesRegex(RuntimeError, "Selected-handle acceptance blocked"):
            self.commit_result(doc, result, edit_request=request)
        self.assertEqual(doc.Objects.add_calls, 1)
        self.assertEqual(doc.Objects.deleted, [101])

    def test_active_command_undo_reused_once(self):
        doc = FakeDoc()
        self.assertEqual(self.commit(doc), (2, 1))
        self.assertEqual((doc.started, doc.ended), (0, 0))
        self.assertFalse(doc.Objects.objects[1].IsDeleted)

    def test_owned_undo_started_and_closed_once(self):
        doc = FakeDoc(active=False)
        self.commit(doc)
        self.assertEqual((doc.started, doc.ended), (1, 1))

    def test_partial_add_failure_rolls_back_only_new_ids(self):
        doc = FakeDoc(fail_add=3)
        with self.assertRaisesRegex(RuntimeError, "could not add"):
            self.commit(doc)
        self.assertEqual(doc.Objects.deleted, [102, 101])
        self.assertFalse(doc.Objects.objects[1].IsDeleted)

    def test_changed_source_before_commit_adds_nothing(self):
        doc = FakeDoc()
        with self.assertRaisesRegex(RuntimeError, "Sources changed"):
            self.commit(doc, FakeCapture((False,)))
        self.assertEqual(doc.Objects.add_calls, 0)

    def test_changed_source_postcheck_rolls_back_new_additions(self):
        doc = FakeDoc()
        with self.assertRaisesRegex(RuntimeError, "Source proof changed"):
            self.commit(doc, FakeCapture((True, False)))
        self.assertEqual(doc.Objects.deleted, [103, 102, 101])
        self.assertFalse(doc.Objects.objects[1].IsDeleted)

    def test_rollback_failure_is_not_reported_as_success(self):
        doc = FakeDoc(fail_add=2, fail_delete=True)
        with self.assertRaisesRegex(RuntimeError, "rollback was incomplete"):
            self.commit(doc)

    def test_disabled_undo_adds_nothing(self):
        doc = FakeDoc()
        doc.UndoRecordingEnabled = False
        with self.assertRaisesRegex(RuntimeError, "Undo recording"):
            self.commit(doc)
        self.assertEqual(doc.Objects.add_calls, 0)

    def test_owned_undo_closes_on_failure(self):
        doc = FakeDoc(active=False, fail_add=2)
        with self.assertRaises(RuntimeError):
            self.commit(doc)
        self.assertEqual((doc.started, doc.ended), (1, 1))

    def test_failed_undo_end_rolls_back_own_additions(self):
        doc = FakeDoc(active=False)
        doc.EndUndoRecord = lambda serial: False
        with self.assertRaisesRegex(RuntimeError, "undo scope could not be closed"):
            self.commit(doc)
        self.assertEqual(doc.Objects.deleted, [103, 102, 101])
        self.assertFalse(doc.Objects.objects[1].IsDeleted)


class DescriptorTests(unittest.TestCase):
    def test_ordinary_grid_curvature_is_separate_from_hard_corner_growth(self):
        text = preview._metric_text({'report': {'sampled_max_curvature': 12.,
            'hard_corner_curvature': {'unbounded_growth_allowed': True,
                                     'logarithmic_sampled_max_curvature': 1.25e10}}})
        self.assertIn('Maximum ordinary-grid curvature: 12', text)
        self.assertIn('hard-corner approach curvature: 1.25e+10', text)
        self.assertIn('not globally bounded', text)

    def test_explicit_brep_orientation_metadata_is_applied_without_parameter_changes(self):
        flips = []
        brep = SimpleNamespace(IsValid=True, Flip=lambda: flips.append(True))
        descriptor = {'orientation_reversed': True, 'domain': [[0, 1], [0, 1]]}
        before = copy.deepcopy(descriptor)
        preview._apply_brep_orientation(brep, descriptor)
        self.assertEqual(flips, [True])
        self.assertEqual(descriptor, before)
        preview._apply_brep_orientation(brep, {'orientation_reversed': False})
        self.assertEqual(flips, [True])
        with self.assertRaises(ValueError):
            preview._apply_brep_orientation(brep, {'orientation_reversed': 'false'})

    def test_full_knot_vectors_are_converted_exactly(self):
        self.assertEqual(preview._rhino_knots([0, 0, 0, 1, 1, 1], 2, 3), [0, 0, 1, 1])

    def test_wrong_nonfinite_and_unsorted_knot_vectors_rejected(self):
        for knots in ([0, 0, 1], [0, 0, float("nan"), 1], [0, 1, 0, 1]):
            with self.assertRaises(ValueError):
                preview._rhino_knots(knots, 1, 2)

    def test_rational_control_point_preserves_homogeneous_coefficients(self):
        fake = SimpleNamespace(ControlPoint=lambda *xyzw: xyzw)
        self.assertEqual(preview._control_point(fake, [4, 6, 8, 2]), (4, 6, 8, 2))
        # This exact input loses one ULP through Euclidean division/multiplication.
        original = [0.7, 1.1, -3.1, 0.3]
        self.assertNotEqual((original[0] / original[3]) * original[3], original[0])
        converted = preview._control_point(fake, original)
        self.assertEqual(tuple(x.hex() for x in converted), tuple(x.hex() for x in original))

    def test_native_homogeneous_readback_rejects_one_ulp_change(self):
        point = SimpleNamespace(X=0.7, Y=1.1, Z=-3.1, Weight=0.3)
        preview._assert_native_control_point(point, [0.7, 1.1, -3.1, 0.3])
        point.X = (point.X / point.Weight) * point.Weight
        with self.assertRaisesRegex(ValueError, "homogeneous control coefficient"):
            preview._assert_native_control_point(point, [0.7, 1.1, -3.1, 0.3])

    def test_nonpositive_or_nonfinite_weight_rejected(self):
        for cp in ([1, 2, 3, 0], [1, 2, 3, -1], [float("nan"), 1, 1, 1]):
            with self.assertRaises(ValueError):
                preview._control_point(None, cp)

    def test_dehomogenization_overflow_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite native range"):
            preview._control_point(None, [1e308, 1, 1, 1e-320])

    def test_partial_metrics_disclose_real_residuals_and_intervals(self):
        text = preview._metric_text({"report": {
            "full_boundary_pass": False, "source_angle_degrees": 2.5,
            "upper_curvature_error": 0.0123, "sample_count": 451,
            "upper_failure_intervals": [{"side": 0, "u_interval": [0.0, 0.1]}]}})
        self.assertIn("FAIL | global G2: NOT VERIFIED", text)
        self.assertIn("normal deg 2.5", text)
        self.assertIn("W residual 0.0123", text)
        self.assertIn("Upper failing parameter intervals", text)


class LoaderTests(unittest.TestCase):
    def entry(self):
        spec = importlib.util.spec_from_file_location("smart_skin_entry_test", ROOT / "src/SmartSkin.Rhino8/Python/smart_skin.py")
        entry = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(entry)
        return entry

    def test_exact_dependency_versions_accepted(self):
        versions = {"numpy": "1.26.4", "scipy": "1.13.1", "mpmath": "1.3.0"}
        self.entry()._verify_dependency_versions(lambda name: SimpleNamespace(__version__=versions[name]))

    def test_cached_other_dependency_version_blocked(self):
        versions = {"numpy": "1.26.4", "scipy": "1.14.0", "mpmath": "1.3.0"}
        with self.assertRaisesRegex(RuntimeError, "scipy 1.14.0; Smart Skin requires 1.13.1"):
            self.entry()._verify_dependency_versions(lambda name: SimpleNamespace(__version__=versions[name]))

    def test_missing_dependency_has_clean_blocked_diagnosis(self):
        def missing(name):
            raise ModuleNotFoundError("Private Python search paths must not be exposed.")
        with self.assertRaisesRegex(RuntimeError, "numpy==1.26.4 is unavailable") as caught:
            self.entry()._verify_dependency_versions(missing)
        self.assertNotIn("Private Python", str(caught.exception))

    def test_owned_modules_reload_without_writing_install_bytecode(self):
        entry = self.entry()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            helper = path / "test_helper.py"
            helper.write_text("value = 42\n")
            with mock.patch.object(entry, "__file__", str(path / "smart_skin.py")):
                with mock.patch.dict("sys.modules"):
                    self.assertEqual(entry._load_local("test_helper").value, 42)
                    helper.write_text("value = 17\n")
                    self.assertEqual(entry._load_local("test_helper").value, 17)
            self.assertFalse((path / "__pycache__").exists())


if __name__ == "__main__":
    unittest.main()
