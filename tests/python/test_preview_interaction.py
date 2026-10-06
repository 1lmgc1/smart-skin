"""Headless interaction/callback tests; native Rhino UI execution is NOT VERIFIED."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest import mock

from test_selected_handle_state import preview as p, catalog, proven_result


class Curve(str):
    Domain = NS(T0=0., T1=1.)


class Picker:
    def __init__(self, hits=None):
        self.hits = hits or {}
        self.calls = []
        self.disposed = False

    def PickFrustumTest(self, item):
        self.calls.append(item)
        return self.hits.get(item, (False, 0., 0., 0.) if isinstance(item, str) else (False, 0., 0.))

    def SetPickTransform(self, transform):
        self.transform = transform

    def UpdateClippingPlanes(self):
        self.clipping_updated = True

    def Dispose(self):
        self.disposed = True


class NativePickTests(unittest.TestCase):
    groups = [{'id': 'row:0', 'indices': [0, 1]}, {'id': 'profile:0', 'indices': [2]}]

    def test_any_piece_selects_its_complete_guide_group(self):
        picker = Picker({'second': (True, .6, 4., 2.)})
        self.assertEqual(p.pick_native_preview(picker, [Curve('first'), Curve('second'), Curve('third')], self.groups, {}, lambda: False),
                         ('guide', 'row:0'))

    def test_visible_handle_marker_has_priority_over_its_incident_guide(self):
        picker = Picker({'first': (True, .5, 10., 0.), (0, 0, 0): (True, 3., 1.)})
        self.assertEqual(p.pick_native_preview(picker, [Curve('first'), Curve('second'), Curve('third')], self.groups,
                                              {'handle': (0, 0, 0)}, lambda: False), ('handle', 'handle'))

    def test_distance_then_nearer_depth_deterministically_breaks_guide_ties(self):
        picker = Picker({'first': (True, .2, 1., 2.), 'third': (True, .8, 5., 2.)})
        self.assertEqual(p.pick_native_preview(picker, [Curve('first'), Curve('second'), Curve('third')], self.groups, {}, lambda: False),
                         ('guide', 'profile:0'))

    def test_miss_does_not_select(self):
        self.assertIsNone(p.pick_native_preview(Picker(), [Curve('first'), Curve('second'), Curve('third')], self.groups, {}, lambda: False))

    def test_expired_or_superseded_scan_never_returns_partial_winner(self):
        picker = Picker({'first': (True, .2, 1., 0.)})
        with self.assertRaisesRegex(RuntimeError, 'cancelled, superseded'):
            p.pick_native_preview(picker, [Curve('first'), Curve('second'), Curve('third')], self.groups, {}, lambda: len(picker.calls) >= 1)

    def test_oversize_or_bad_mapping_rejected_before_native_tests(self):
        picker = Picker()
        with self.assertRaises(ValueError):
            p.pick_native_preview(picker, [Curve('curve')] * 129, [], {}, lambda: False)
        with self.assertRaises(ValueError):
            p.pick_native_preview(picker, [Curve('curve')], [{'id': 'x', 'indices': [1]}], {}, lambda: False)
        self.assertEqual(picker.calls, [])

    def test_bad_native_tuple_and_nonfinite_distance_do_not_select(self):
        for values in ((True, .2, 2.), (True, .2, 2., float('nan')), (True, .2, 2., -1.)):
            with self.assertRaises(RuntimeError):
                p.pick_native_preview(Picker({'curve': values}), [Curve('curve')], [{'id': 'x', 'indices': [0]}], {}, lambda: False)

    def test_curve_parameter_must_be_finite_and_inside_its_exact_domain(self):
        for parameter in (float('nan'), -.001, 1.001):
            with self.assertRaisesRegex(RuntimeError, 'guide domain'):
                p.pick_native_preview(Picker({'curve': (True, parameter, 1., 0.)}), [Curve('curve')],
                                      [{'id': 'x', 'indices': [0]}], {}, lambda: False)


class NativeConfirmationTests(unittest.TestCase):
    def test_timer_rebuild_during_getter_cannot_accept_newly_displayed_result(self):
        state = p.PreviewState()
        state.complete(state.begin(), True)
        screen = p.NativeScreenState({})
        state.request(1.)
        def timer_then_enter():
            screen.invalidate()
            state.complete(state.begin(), True)
            return 'Nothing'
        result, current = p.get_preview_decision(NS(Get=timer_then_enter), state, screen)
        self.assertEqual(result, 'Nothing')
        self.assertTrue(state.can_accept)
        self.assertFalse(current, 'A confirmation from before the new native screen must be discarded.')

    def test_new_slider_revision_during_getter_revokes_old_confirmation(self):
        state = p.PreviewState()
        def change_then_enter():
            state.request(1.)
            return 'Nothing'
        self.assertFalse(p.get_preview_decision(NS(Get=change_then_enter), state, p.NativeScreenState({}))[1])

    def test_pending_enter_without_intervening_rebuild_can_still_flush_current_value(self):
        state = p.PreviewState()
        self.assertTrue(state.pending)
        self.assertTrue(p.get_preview_decision(NS(Get=lambda: 'Nothing'), state, p.NativeScreenState({}))[1])


def runtime_classes(rhino, doc, capture):
    """Execute unchanged nested class definitions with host substitutes.

    Tests call the real callbacks without constructing Eto or claiming a GUI run.
    """
    tree = ast.parse(Path(p.__file__).read_text())
    run = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'run')
    classes = [node for node in run.body if isinstance(node, ast.ClassDef) and node.name in ('PreviewMouse', 'Session')]
    namespace = dict(vars(p), Rhino=rhino, doc=doc, capture=capture)
    exec(compile(ast.Module(body=classes, type_ignores=[]), p.__file__, 'exec'), namespace)
    return namespace['PreviewMouse'], namespace['Session']


class SessionPickTests(unittest.TestCase):
    def setUp(self):
        self.doc = NS(RuntimeSerialNumber=7, Views=NS(Redraw=lambda: None))
        self.capture = NS(model={}, verify_sources=lambda doc: (True, 'unchanged'))
        self.picker = Picker({'curve': (True, .5, 1., 0.)})
        self.logs = []
        self.rhino = NS(UI=NS(MouseCallback=object, MouseButton=NS(Left=1, Right=2, Middle=3)),
                        Input=NS(Custom=NS(PickContext=lambda: self.picker, PickStyle=NS(PointPick=1), PickMode=NS(Wireframe=1))),
                        Geometry=NS(Point3d=lambda *xyz: tuple(xyz)),
                        Display=NS(RhinoPageView=type('PageView', (), {})),
                        RhinoApp=NS(WriteLine=self.logs.append))
        self.Mouse, Session = runtime_classes(self.rhino, self.doc, self.capture)
        self.session = Session.__new__(Session)
        s = self.session
        s.disposed = False
        s.state = p.PreviewState()
        s.state.complete(s.state.begin(), True)
        s.attachment_ready = True
        s.native_screen = p.NativeScreenState({})
        s.native_screen.receipt = object()
        s.edits = p.HandleEditState(catalog(), True)
        s.valid_edit_token = s.edits.snapshot(0)
        s.output = proven_result(s.valid_edit_token)
        s.edits.accept(s.valid_edit_token, s.output)
        s.guide_groups = [{'id': 'row:0', 'indices': [0]}]
        s.conduit = NS(guides=[Curve('curve')], handle_points={}, selected_guide_indices=set(), handle_display=None)
        s.guide_selector = NS(SelectedIndex=-1)
        s.suppress_changes = False
        s.status = NS(Text='READY')
        s.refresh_handle_controls = mock.Mock()
        self.mouse = self.Mouse(s)
        self.viewport = NS(Id=42, GetPickTransform=lambda point: NS(IsValid=True), ClientToWorld=lambda point: NS(IsValid=True))
        self.view = NS(Document=self.doc, ActiveViewport=self.viewport, InDynamicViewChange=False)
        self.event = NS(View=self.view, MouseButton=1, CtrlKeyDown=False, ShiftKeyDown=False, Cancel=False, ViewportPoint=(4, 8))

    def test_ready_left_click_selects_guide_and_consumes_matching_up_without_editing_values(self):
        before = dict(self.session.edits.values)
        self.mouse.OnMouseDown(self.event)
        self.assertTrue(self.event.Cancel)
        self.assertEqual(self.session.edits.selected_guide, 'row:0')
        self.assertEqual(self.session.guide_selector.SelectedIndex, 0)
        self.assertEqual(self.session.edits.values, before)
        self.assertEqual(self.session.state.revision, 0)
        self.assertTrue(self.picker.disposed)
        self.event.Cancel = False
        self.mouse.OnMouseUp(self.event)
        self.assertTrue(self.event.Cancel)
        self.event.Cancel = False
        self.mouse.OnMouseUp(self.event)
        self.assertFalse(self.event.Cancel)

    def test_right_middle_ctrl_shift_and_dynamic_navigation_pass_through(self):
        for key, value in [('MouseButton', 2), ('MouseButton', 3), ('CtrlKeyDown', True), ('ShiftKeyDown', True)]:
            event = NS(**vars(self.event)); setattr(event, key, value)
            self.mouse.OnMouseDown(event)
            self.assertFalse(event.Cancel)
        self.view.InDynamicViewChange = True
        self.mouse.OnMouseDown(self.event)
        self.assertFalse(self.event.Cancel)
        self.assertEqual(self.picker.calls, [])

    def test_pending_build_cancel_closed_and_missing_receipt_never_pick(self):
        for key in ('pending', 'building', 'cancelled', 'closed'):
            setattr(self.session.state, key, True)
            self.assertFalse(self.session.pick_viewport(self.event))
            setattr(self.session.state, key, False)
        self.session.native_screen.invalidate()
        self.assertFalse(self.session.pick_viewport(self.event))
        self.assertEqual(self.picker.calls, [])

    def test_other_document_and_page_views_are_not_intercepted(self):
        self.view.Document = NS(RuntimeSerialNumber=9)
        self.assertFalse(self.session.pick_viewport(self.event))
        page = self.rhino.Display.RhinoPageView()
        page.Document = self.doc; page.InDynamicViewChange = False
        self.event.View = page
        self.assertFalse(self.session.pick_viewport(self.event))
        self.assertEqual(self.picker.calls, [])

    def test_changed_originals_revoke_receipt_without_picking_or_adding(self):
        self.capture.verify_sources = lambda doc: (False, 'Owner changed.')
        self.assertFalse(self.session.pick_viewport(self.event))
        self.assertIsNone(self.session.native_screen.receipt)
        self.assertFalse(self.session.state.can_accept)
        self.assertEqual(self.picker.calls, [])

    def test_native_failure_is_disposed_and_leaves_list_selection_available(self):
        self.picker.hits[Curve('curve')] = (True, .2, 1., float('inf'))
        self.mouse.OnMouseDown(self.event)
        self.assertFalse(self.event.Cancel)
        self.assertTrue(self.picker.disposed)
        self.assertIn('Use the Guide and Handle lists', self.session.status.Text)
        self.assertTrue(self.session.state.can_accept)

    def test_mouse_disposal_removes_hook_and_consumed_click(self):
        self.mouse.Enabled = True
        self.mouse.consumed_viewport = 42
        self.mouse.close()
        self.assertFalse(self.mouse.Enabled)
        self.assertIsNone(self.mouse.consumed_viewport)

    def test_identical_document_wrapper_is_accepted_by_runtime_serial(self):
        self.view.Document = NS(RuntimeSerialNumber=self.doc.RuntimeSerialNumber)
        self.assertTrue(self.session.pick_viewport(self.event))

    def test_obsolete_handle_request_never_hits_native_geometry(self):
        self.session.edits.select_guide('row:0')
        self.session.edits.set_selected_value(.2)
        self.assertFalse(self.session.pick_viewport(self.event))
        self.assertEqual(self.picker.calls, [])

    def test_visible_handle_click_selects_its_guide_and_own_handle(self):
        self.session.guide_groups.append({'id': 'profile:0', 'indices': []})
        self.session.conduit.handle_points = {'v-interior': (0, 0, 1)}
        self.picker.hits[(0, 0, 1)] = (True, 3., .5)
        self.assertTrue(self.session.pick_viewport(self.event))
        self.assertEqual(self.session.edits.selected_guide, 'profile:0')
        self.assertEqual(self.session.edits.selected_handle, 'v-interior')
        self.assertEqual(self.session.guide_selector.SelectedIndex, 1)

    def test_callback_failure_does_not_leave_changes_suppressed(self):
        self.session.refresh_handle_controls.side_effect = RuntimeError('Synthetic control failure.')
        self.assertFalse(self.session.pick_viewport(self.event))
        self.assertFalse(self.session.suppress_changes)
        self.assertTrue(self.picker.disposed)

    def test_cooperative_event_pump_cannot_reenter_itself(self):
        s = self.session
        s.deadline = None
        s.pumping_events = False
        s.refresh_progress = mock.Mock()
        calls = []
        def pump():
            calls.append('pump')
            self.assertFalse(s.cancelled())
        self.rhino.RhinoApp.Wait = pump
        self.assertFalse(s.cancelled())
        self.assertEqual(calls, ['pump'])
        self.assertFalse(s.pumping_events)

    def test_progress_reports_elapsed_stage_without_invented_percentage_and_is_throttled(self):
        s = self.session
        s.state.building = True
        s.build_started = 100.
        s.build_budget = 180.
        s.progress_updated = 0.
        s.stage_name = 'BASELINE GEOMETRY AND CHECKS'
        prompts = []
        self.rhino.RhinoApp.SetCommandPrompt = prompts.append
        with mock.patch.object(p.time, 'monotonic', side_effect=[100., 100.2, 100.6]):
            s.refresh_progress()
            initial = s.status.Text
            s.refresh_progress()
            self.assertEqual(s.status.Text, initial)
            s.refresh_progress()
        self.assertEqual(len(prompts), 2)
        self.assertIn('Elapsed 0.6 s / 180 s', s.status.Text)
        self.assertIn('BASELINE GEOMETRY AND CHECKS', s.status.Text)
        self.assertNotIn('%', s.status.Text)

    def test_close_during_pick_failure_does_not_touch_disposed_control(self):
        class ClosedControl:
            def __setattr__(self, key, value):
                raise AssertionError('Disposed control was touched.')
        def close_and_fail(item):
            self.session.disposed = True
            self.session.status = ClosedControl()
            raise RuntimeError('Closed during native operation.')
        self.picker.PickFrustumTest = close_and_fail
        self.assertFalse(self.session.pick_viewport(self.event))
        self.assertTrue(self.picker.disposed)
        self.assertEqual(self.logs, [])

    def test_disposed_mouse_callbacks_do_not_read_invalid_native_event(self):
        self.session.disposed = True
        self.mouse.OnMouseDown(None)
        self.mouse.OnMouseUp(None)
        self.assertEqual(self.picker.calls, [])

    def test_rejected_edit_is_logged_even_after_restoration_changes_revision(self):
        s = self.session
        s.mouse = self.mouse
        s.prepared = NS()
        s.timer = NS(Start=mock.Mock())
        s.set_stage = lambda name: setattr(s, 'stage_name', name)
        s.state.request(1.)
        requested_revision = s.state.revision
        # Methods compiled from the source keep their own globals mapping.
        with mock.patch.dict(s.rebuild.__func__.__globals__,
                             evaluate_preview_cycle=mock.Mock(side_effect=ValueError('Synthetic rejected edit.'))):
            s.rebuild()
        self.assertGreater(s.state.revision, requested_revision)
        self.assertIsNone(s.native_screen.receipt)
        self.assertTrue(any('SMARTSKIN_P08E1_REJECTED' in line and 'Synthetic rejected edit.' in line for line in self.logs))
        self.assertIn('restored preview', p.preview_command_prompt(s.state, True, s.native_screen.receipt is not None))


if __name__ == '__main__':
    unittest.main()
