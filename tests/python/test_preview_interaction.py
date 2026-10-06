"""Headless interaction/callback tests; native Rhino UI execution is NOT VERIFIED."""
import ast
import copy
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest import mock

from test_selected_handle_state import preview as p, catalog, proven_result
from attachment_proof_fixtures import source_model, mock_verify_atlas


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


class GuideSelectorTests(unittest.TestCase):
    def setUp(self):
        self.edits = p.HandleEditState(catalog(), True)
        self.groups = [{'id': 'boundary:0', 'label': 'Upper attachment'},
                       {'id': 'row:0', 'label': 'U row 1'}, {'id': 'profile:0', 'label': 'V profile 1'}]

    def test_initial_default_is_first_editable_catalogue_guide(self):
        labels, index = p.guide_selector_choices(self.groups, self.edits)
        self.assertEqual(index, 1)
        self.assertEqual(labels[0], 'Upper attachment (read-only)')
        self.assertEqual(labels[1], 'U row 1')

    def test_explicit_structural_selection_is_preserved_for_inspection(self):
        self.edits.select_guide('boundary:0')
        labels, index = p.guide_selector_choices(self.groups, self.edits)
        self.assertEqual(index, 0)
        self.assertIn('read-only', labels[0])

    def test_default_skips_locked_handle_but_preserves_explicit_locked_selection(self):
        self.edits.handles['u-interior']['locked_reason'] = 'No supported motion.'
        self.assertEqual(p.guide_selector_choices(self.groups, self.edits)[1], 2)
        self.edits.select_guide('row:0')
        self.assertEqual(p.guide_selector_choices(self.groups, self.edits)[1], 1)

    def test_empty_and_removed_selections_have_bounded_fallback(self):
        self.assertEqual(p.guide_selector_choices([], self.edits), ([], -1))
        self.edits.select_guide('removed')
        self.assertEqual(p.guide_selector_choices(self.groups, self.edits)[1], 1)


class NativeConfirmationTests(unittest.TestCase):
    def test_consumed_pick_during_getter_cannot_become_confirmation_but_later_enter_can(self):
        state, screen = p.PreviewState(), p.NativeScreenState({})
        selection = NS(selection_generation=0)
        def pick_then_nothing():
            selection.selection_generation += 1
            return 'Nothing'
        self.assertFalse(p.get_preview_decision(NS(Get=pick_then_nothing), state, screen, selection)[1])
        self.assertTrue(p.get_preview_decision(NS(Get=lambda: 'Nothing'), state, screen, selection)[1])

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
        s.edit_events_received = 0
        s.pending_edit_diagnostic = None
        s.checking_retry_sources = False
        s.selection_generation = 0
        s.reset_work_counters()
        s.state = p.PreviewState()
        s.state.complete(s.state.begin(), True)
        s.attachment_ready = True
        s.native_screen = p.NativeScreenState({})
        s.native_screen.context = NS(check_live=mock.Mock())
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
        self.assertEqual(self.session.selection_generation, 1)
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

    def test_actual_pick_callback_during_getter_drops_conditional_nothing_result(self):
        def get():
            self.mouse.OnMouseDown(self.event)
            self.assertTrue(self.event.Cancel)
            return 'Nothing'
        result, current = p.get_preview_decision(NS(Get=get), self.session.state,
                                                self.session.native_screen, self.session)
        self.assertEqual(result, 'Nothing')
        self.assertFalse(current)
        self.assertTrue(p.get_preview_decision(NS(Get=lambda: 'Nothing'), self.session.state,
                                               self.session.native_screen, self.session)[1])

    def test_consumed_mouse_up_in_next_getter_cannot_confirm_either(self):
        self.mouse.OnMouseDown(self.event)
        self.event.Cancel = False
        def up_then_nothing():
            self.mouse.OnMouseUp(self.event)
            self.assertTrue(self.event.Cancel)
            return 'Nothing'
        self.assertFalse(p.get_preview_decision(NS(Get=up_then_nothing), self.session.state,
                                                self.session.native_screen, self.session)[1])
        self.assertTrue(p.get_preview_decision(NS(Get=lambda: 'Nothing'), self.session.state,
                                               self.session.native_screen, self.session)[1])

    def test_pick_display_failure_still_revokes_same_getter_confirmation(self):
        self.session.update_selection_display = mock.Mock(side_effect=RuntimeError('Synthetic redraw failure.'))
        def get():
            self.mouse.OnMouseDown(self.event)
            return 'Nothing'
        self.assertFalse(p.get_preview_decision(NS(Get=get), self.session.state,
                                                self.session.native_screen, self.session)[1])
        self.assertFalse(self.event.Cancel)
        self.assertTrue(self.picker.disposed)
        self.assertEqual(self.session.selection_generation, 1)

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
        self.assertEqual(s.event_pumps, 1)
        self.assertEqual(s.cancel_checkpoints, 2)

    def configure_pump(self):
        s = self.session
        s.deadline = None
        s.timed_out = False
        s.pumping_events = False
        s.refresh_progress = mock.Mock()
        self.rhino.RhinoApp.Wait = mock.Mock()
        return s

    def test_thousand_checkpoints_inside_cadence_pump_once_but_check_cancel_every_time(self):
        s = self.configure_pump()
        with mock.patch.object(p.time, 'monotonic', return_value=100.):
            for _ in range(1000):
                self.assertFalse(s.cancelled())
            s.state.cancel()
            self.assertTrue(s.cancelled())
        self.assertEqual(s.cancel_checkpoints, 1001)
        self.assertEqual(s.event_pumps, 1)
        self.assertEqual(self.rhino.RhinoApp.Wait.call_count, 1)

    def test_pump_runs_again_after_25ms_but_not_before(self):
        s = self.configure_pump()
        now = [100.]
        with mock.patch.object(p.time, 'monotonic', side_effect=lambda: now[0]):
            self.assertFalse(s.cancelled())
            now[0] += .024
            self.assertFalse(s.cancelled())
            self.assertEqual(s.event_pumps, 1)
            now[0] += .002
            self.assertFalse(s.cancelled())
        self.assertEqual(s.event_pumps, 2)

    def test_expired_deadline_is_checked_inside_throttle_interval(self):
        s = self.configure_pump()
        s.last_event_pump = 100.
        s.deadline = 100.001
        with mock.patch.object(p.time, 'monotonic', return_value=100.002):
            self.assertTrue(s.cancelled())
        self.assertTrue(s.timed_out)
        self.assertEqual(s.event_pumps, 0)

    def test_long_event_pump_records_time_and_rechecks_deadline(self):
        s = self.configure_pump()
        s.deadline = 101.
        with mock.patch.object(p.time, 'monotonic', side_effect=[100., 100., 102., 102.]):
            self.assertTrue(s.cancelled())
        self.assertTrue(s.timed_out)
        self.assertEqual(s.event_pump_seconds, 2.)
        self.assertIn('ui_pumps=1', s.work_diagnostic())

    def test_progress_update_cannot_hide_deadline_expiry_when_pump_is_throttled(self):
        s = self.configure_pump()
        s.last_event_pump = 100.
        s.deadline = 100.01
        with mock.patch.object(p.time, 'monotonic', side_effect=[100.001, 100.02]):
            self.assertTrue(s.cancelled())
        self.assertTrue(s.timed_out)
        self.assertEqual(s.event_pumps, 0)

    def test_pump_exception_resets_reentrancy_and_keeps_elapsed_counter(self):
        s = self.configure_pump()
        self.rhino.RhinoApp.Wait.side_effect = RuntimeError('Synthetic pump failure.')
        with mock.patch.object(p.time, 'monotonic', side_effect=[100., 100., 100.5]):
            with self.assertRaisesRegex(RuntimeError, 'pump failure'):
                s.cancelled()
        self.assertFalse(s.pumping_events)
        self.assertEqual(s.event_pump_seconds, .5)

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

    def test_new_revision_is_observed_inside_event_pump_throttle_interval(self):
        s = self.configure_pump()
        s.mouse = self.mouse
        s.prepared = NS()
        s.timer = NS(Start=mock.Mock())
        s.set_stage = lambda name: setattr(s, 'stage_name', name)
        s.state.request(1.)
        def supersede(prepared, edits, revision, cancelled, *args):
            self.assertFalse(cancelled())
            s.state.request(1.)
            self.assertTrue(cancelled())
            raise RuntimeError('Superseded request.')
        with mock.patch.dict(s.rebuild.__func__.__globals__, evaluate_preview_cycle=supersede), \
                mock.patch.object(p.time, 'monotonic', return_value=100.):
            s.rebuild()
        self.assertEqual(s.event_pumps, 1)
        self.assertEqual(s.cancel_checkpoints, 2)
        self.assertTrue(s.state.pending)
        self.assertIsNone(s.state.error)
        self.assertFalse(s.state.can_accept)

    def configure_real_controls(self):
        s = self.session
        s.mouse = self.mouse
        s.handle_selector = NS(DataStore=[], Enabled=False, SelectedIndex=-1)
        s.slider = NS(Value=500, Enabled=False)
        s.value = NS(Text='')
        s.handle_note = NS(Text='')
        s.limitation = NS(Text='')
        s.attachment_reason = 'Synthetic checked attachment.'
        s.refresh_handle_controls = type(s).refresh_handle_controls.__get__(s)
        s.edits.select_guide('row:0')
        s.refresh_handle_controls()
        s.timer = NS(Stop=mock.Mock(), Start=mock.Mock())
        s.prepared = NS()
        s.set_stage = lambda name: setattr(s, 'stage_name', name)
        return s

    def reject_slider_edit(self):
        s = self.configure_real_controls()
        s.slider.Value = 750
        s.on_change(None, None)
        with mock.patch.dict(s.rebuild.__func__.__globals__,
                             evaluate_preview_cycle=mock.Mock(side_effect=ValueError('Synthetic range rejection.'))):
            s.on_tick(None, None)
        self.assertEqual(s.edits.values['u-interior'], 0.)
        self.assertIsNone(s.native_screen.receipt)
        self.assertTrue(s.slider.Enabled, 'A rejected request must not lock out the next smaller edit.')
        self.assertFalse(s.mouse.Enabled, 'Receipt-less viewport picking stays disabled.')
        return s

    def test_rejected_edit_can_request_smaller_value_then_show_new_freshly_screened_geometry(self):
        s = self.reject_slider_edit()
        self.capture.model = source_model()
        received = []
        def evaluate_edit(request, cancelled):
            received.append(request)
            token = p.HandleEditToken(request['revision'], request['basis_id'], tuple(sorted(request['values'].items())))
            result = proven_result(token)
            result['guides'] = [{'guide_id': 'row:0', 'varying_axis': 'u'},
                                {'guide_id': 'profile:0', 'varying_axis': 'v'}]
            return result
        s.prepared.evaluate_edit = evaluate_edit
        self.doc.Objects = NS(AddBrep=mock.Mock(side_effect=AssertionError('Recovery must not add objects.')),
                              AddCurve=mock.Mock(side_effect=AssertionError('Recovery must not add objects.')))
        new_breps, new_guides = [object()], [object(), object()]
        fresh_receipt = object()
        def screen(*args, **kwargs):
            self.assertAlmostEqual(kwargs['request']['values']['u-interior'], .2)
            s.native_screen.receipt = fresh_receipt
        s.native_screen.screen = mock.Mock(side_effect=screen)
        def replace(breps, guides):
            s.conduit.breps, s.conduit.guides = breps, guides
        s.conduit.replace = mock.Mock(side_effect=replace)
        s.rescreen_restored_preview = mock.Mock(side_effect=AssertionError('No automatic restored rescreen.'))
        s.slider.Value = 600
        s.on_change(None, None)
        self.assertAlmostEqual(s.edits.values['u-interior'], .2)
        s.native_screen.context.check_live.assert_called_once()
        self.assertTrue(s.state.pending)
        self.assertFalse(s.state.can_accept)
        with mock.patch.dict(s.rebuild.__func__.__globals__,
                             make_native_geometry=mock.Mock(return_value=(new_breps, new_guides, object())),
                             _verify_atlas_separation=mock_verify_atlas):
            s.on_tick(None, None)
        self.assertEqual(len(received), 1)
        self.assertAlmostEqual(received[0]['values']['u-interior'], .2)
        self.assertIs(s.native_screen.receipt, fresh_receipt)
        s.native_screen.screen.assert_called_once()
        s.conduit.replace.assert_called_once_with(new_breps, new_guides)
        self.assertIs(s.conduit.breps, new_breps)
        self.assertAlmostEqual(s.conduit.handle_display[1][2], 1.2)
        self.assertTrue(s.state.can_accept)
        self.assertTrue(s.slider.Enabled)
        self.assertFalse(getattr(s, 'accept_requested', False))
        self.doc.Objects.AddBrep.assert_not_called()
        self.doc.Objects.AddCurve.assert_not_called()
        s.rescreen_restored_preview.assert_not_called()
        self.assertTrue(any('EDIT_REQUEST' in line and 'value=0.2' in line for line in self.logs))
        self.assertTrue(any('P08E1_READY' in line and 'nonzero_handles=1' in line for line in self.logs))

    def test_source_or_tolerance_change_blocks_first_restored_retry_before_queuing(self):
        s = self.reject_slider_edit()
        starts = s.timer.Start.call_count
        s.native_screen.context.check_live.side_effect = RuntimeError('Captured tolerance changed.')
        s.slider.Value = 600
        s.on_change(None, None)
        self.assertFalse(s.slider.Enabled)
        self.assertFalse(s.state.can_accept)
        self.assertFalse(s.state.pending)
        self.assertEqual(s.edits.values['u-interior'], 0.)
        self.assertEqual(s.timer.Start.call_count, starts)
        self.assertIsNone(s.native_screen.receipt)
        self.assertFalse(s.prepare_acceptance())
        self.assertIn('proof could not be revalidated', s.status.Text)
        self.assertIn('RuntimeError', s.status.Text)
        self.assertFalse(s.checking_retry_sources)

    def test_native_proof_failure_is_not_reported_as_proven_source_mutation(self):
        s = self.reject_slider_edit()
        s.native_screen.context.check_live.side_effect = OSError('Sensitive native detail is not for logs.')
        s.slider.Value = 600
        s.on_change(None, None)
        self.assertIn('proof could not be revalidated', s.status.Text)
        self.assertIn('OSError', s.status.Text)
        self.assertNotIn('changed', s.status.Text)
        self.assertFalse(any('Sensitive native detail' in line for line in self.logs))

    def test_reentrant_slider_event_during_retry_source_check_queues_latest_value_once(self):
        s = self.reject_slider_edit()
        before = s.edit_events_received
        def nested_change():
            s.slider.Value = 610
            s.on_change(None, None)
        s.native_screen.context.check_live.side_effect = nested_change
        s.slider.Value = 600
        s.on_change(None, None)
        s.native_screen.context.check_live.assert_called_once()
        self.assertAlmostEqual(s.edits.values['u-interior'], .22)
        self.assertEqual(s.edit_events_received, before + 1)
        self.assertFalse(s.checking_retry_sources)

    def test_cancel_during_retry_source_check_cannot_queue_a_request(self):
        s = self.reject_slider_edit()
        before = s.edit_events_received
        s.native_screen.context.check_live.side_effect = s.state.cancel
        s.slider.Value = 600
        s.on_change(None, None)
        self.assertEqual(s.edits.values['u-interior'], 0.)
        self.assertEqual(s.edit_events_received, before)
        self.assertFalse(s.state.pending)

    def test_initial_failure_never_enables_editing_without_a_displayed_valid_result(self):
        s = self.configure_real_controls()
        s.valid_edit_token = None
        s.output = None
        s.native_screen.invalidate()
        s.refresh_handle_controls()
        self.assertFalse(s.slider.Enabled)
        self.assertFalse(s.may_request_edit())
        previous = dict(s.edits.values)
        s.slider.Enabled = True
        s.slider.Value = 800
        s.on_change(None, None)
        self.assertEqual(s.edits.values, previous)
        self.assertEqual(s.edit_events_received, 0)

    def test_scalar_summary_distinguishes_neutral_from_nonzero_without_geometry_or_basis_data(self):
        zero = p.HandleEditToken(0, 'not-for-logs', (('profile:2:lift', 0.),))
        moved = p.HandleEditToken(3, 'not-for-logs', (('profile:2:lift', -.125),))
        self.assertIn('nonzero_handles=0', p.edit_value_summary(zero))
        self.assertIn('request_revision=3', p.edit_value_summary(moved))
        self.assertIn('max_abs_value=0.125', p.edit_value_summary(moved))
        self.assertNotIn('not-for-logs', p.edit_value_summary(moved))

    def test_input_diagnostic_exists_before_timer_and_coalesces_drag_events(self):
        s = self.configure_real_controls()
        s.slider.Value = 600
        s.on_change(None, None)
        s.slider.Value = 650
        s.on_change(None, None)
        lines = [line for line in self.logs if 'EDIT_INPUT' in line]
        self.assertEqual(len(lines), 1)
        self.assertIn('value=0.2', lines[0])
        self.assertFalse(any('EDIT_REQUEST' in line for line in self.logs), 'Timer has not fired yet.')
        self.assertAlmostEqual(s.pending_edit_diagnostic[2], .3)
        self.assertEqual(s.edit_events_received, 2)

    def test_default_profile_uses_unlocked_shoulder_but_preserves_deliberate_locked_handle(self):
        s = self.configure_real_controls()
        data = catalog()
        normal = data['handles'][1]
        shoulder = copy.deepcopy(normal)
        normal['locked_reason'] = 'Normal lift unavailable.'
        shoulder.update(id='v-shoulder', label='Upper shoulder', mirror_handle_id='v-shoulder')
        data['handles'] = [normal, shoulder]
        s.edits = p.HandleEditState(data, True)
        s.valid_edit_token = s.edits.snapshot(0)
        s.output = proven_result(s.valid_edit_token)
        s.edits.accept(s.valid_edit_token, s.output)
        groups = [{'id': 'profile:0', 'label': 'V profile 1', 'indices': []}]
        s.refresh_guide_choices(groups)
        self.assertEqual(s.edits.selected_handle, 'v-shoulder')
        self.assertTrue(s.slider.Enabled)
        s.edits.select_handle('v-interior')
        s.refresh_guide_choices(groups)
        self.assertEqual(s.edits.selected_handle, 'v-interior')
        self.assertFalse(s.slider.Enabled)


if __name__ == '__main__':
    unittest.main()
