"""Non-native contract tests. These are NOT Rhino GUI or geometry certification."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

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

    def verify_sources(self, doc):
        return next(self.checks), "mock source check"


class CommitTests(unittest.TestCase):
    rhino = SimpleNamespace(DocObjects=SimpleNamespace(ObjectAttributes=FakeAttributes))
    system = SimpleNamespace(Guid=SimpleNamespace(Empty=0))
    geometry = SimpleNamespace(IsValid=True)

    def commit(self, doc, capture=None):
        return preview.commit_new_geometry(doc, capture or FakeCapture(),
                                           [self.geometry, self.geometry], [self.geometry],
                                           1.0, self.rhino, self.system)

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
    def test_full_knot_vectors_are_converted_exactly(self):
        self.assertEqual(preview._rhino_knots([0, 0, 0, 1, 1, 1], 2, 3), [0, 0, 1, 1])

    def test_wrong_nonfinite_and_unsorted_knot_vectors_rejected(self):
        for knots in ([0, 0, 1], [0, 0, float("nan"), 1], [0, 1, 0, 1]):
            with self.assertRaises(ValueError):
                preview._rhino_knots(knots, 1, 2)

    def test_rational_control_point_uses_euclidean_overload(self):
        fake = SimpleNamespace(Point3d=lambda *xyz: xyz, ControlPoint=lambda point, weight: (point, weight))
        self.assertEqual(preview._control_point(fake, [4, 6, 8, 2]), ((2, 3, 4), 2))

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
