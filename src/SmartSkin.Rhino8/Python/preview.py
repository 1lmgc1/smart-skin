"""Disposable Rhino/Eto preview and new-only transactional commit.

Numerical PreviewState has no Rhino dependency, so its transition invariants
can be tested without pretending that the native GUI has been exercised.
All RhinoCommon/Eto calls execute synchronously on Rhino's command/UI thread.
"""

import math
import time


class PreviewState:
    """Never accept an old preview under a newer visible handle setting."""

    def __init__(self):
        self.requested_h = 1.0
        self.valid_h = None
        self.revision = 0
        self.valid_revision = -1
        self.pending = True
        self.building = False
        self.cancelled = False
        self.closed = False
        self.error = None

    def request(self, handle):
        value = float(handle)
        if not math.isfinite(value) or value < 0.5 or value > 1.5:
            raise ValueError("Shoulder handle factor must be between 0.50 and 1.50.")
        if self.closed or self.cancelled:
            return
        self.requested_h = value
        self.revision += 1
        self.pending = True
        self.error = None

    def begin(self):
        if self.closed or self.cancelled or self.building or not self.pending:
            return None
        self.building = True
        self.pending = False
        return self.revision, self.requested_h

    def complete(self, token, successful, reason=None):
        self.building = False
        if self.closed or self.cancelled:
            return False
        if token[0] != self.revision:
            self.pending = True
            return False
        if successful:
            self.valid_revision, self.valid_h = token
            self.error = None
            return True
        self.error = reason or "The current setting did not produce valid geometry."
        return False

    @property
    def can_accept(self):
        return (not self.closed and not self.cancelled and not self.building
                and not self.pending and self.error is None
                and self.valid_revision == self.revision
                and self.valid_h == self.requested_h)

    def cancel(self):
        self.cancelled = True
        self.pending = False

    def restore_last_valid(self):
        if self.valid_h is None or self.closed or self.cancelled or self.building:
            return False
        self.revision += 1
        self.requested_h = self.valid_h
        self.valid_revision = self.revision
        self.pending = False
        self.error = None
        return True

    def close(self):
        self.closed = True
        self.pending = False


def _homogeneous(descriptor):
    for name in ("homogeneous_cp", "homogeneousCP", "control_points_h"):
        if name in descriptor:
            return descriptor[name]
    raise ValueError("Kernel descriptor omitted homogeneous control points.")


def _rhino_knots(values, degree, count):
    values = [float(value) for value in values]
    if len(values) != count + degree + 1:
        raise ValueError("Kernel knot vector has the wrong length.")
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Kernel knot vector is not finite.")
    if any(a > b for a, b in zip(values, values[1:])):
        raise ValueError("Kernel knots are not monotonic.")
    # openNURBS stores two fewer exterior knots than the standard convention.
    return values[1:-1]


def _control_point(rg, value):
    if len(value) != 4 or not all(math.isfinite(float(x)) for x in value):
        raise ValueError("Kernel returned non-finite homogeneous control points.")
    w = float(value[3])
    if w <= 0.0:
        raise ValueError("Kernel returned a non-positive rational weight.")
    xyz = [float(value[index]) / w for index in range(3)]
    if not all(math.isfinite(component) for component in xyz):
        raise ValueError("Kernel rational control point is outside finite native range.")
    # The four-scalar constructor is homogeneous. Use the Point3d overload
    # explicitly because we have divided by W already.
    return rg.ControlPoint(rg.Point3d(*xyz), w)


def _dispose_all(items):
    for item in items:
        try:
            item.Dispose()
        except Exception:
            pass


def _safe_cleanup(action):
    """A failed/disposed widget must not prevent the remaining cleanup steps."""
    try:
        action()
        return True
    except Exception:
        return False


def make_native_geometry(output, rg, cancelled):
    """Convert exact rational descriptors. Never fit sampled/polyline guides."""
    breps, guides = [], []
    try:
        patches = output.get("patches", output.get("surfaces", []))
        guide_specs = output.get("guides", [])
        if not patches or len(patches) > 128 or len(guide_specs) > 128:
            raise ValueError("Kernel output exceeded the bounded preview contract.")
        for patch in patches:
            if cancelled():
                raise RuntimeError("Preview cancelled.")
            cp = _homogeneous(patch)
            nu, nv = len(cp), len(cp[0])
            du, dv = int(patch["degree_u"]), int(patch["degree_v"])
            if not 1 <= du <= 64 or not 1 <= dv <= 64 or nu * nv > 16384:
                raise ValueError("Kernel surface exceeds native preview limits.")
            if any(len(row) != nv for row in cp):
                raise ValueError("Kernel surface control net is not rectangular.")
            ku = _rhino_knots(patch["knots_u"], du, nu)
            kv = _rhino_knots(patch["knots_v"], dv, nv)
            surface = rg.NurbsSurface.Create(3, True, du + 1, dv + 1, nu, nv)
            if surface is None:
                raise RuntimeError("Rhino could not allocate a preview surface.")
            try:
                for i, knot in enumerate(ku):
                    surface.KnotsU[i] = knot
                for j, knot in enumerate(kv):
                    surface.KnotsV[j] = knot
                for i in range(nu):
                    if i % 8 == 0 and cancelled():
                        raise RuntimeError("Preview cancelled.")
                    for j in range(nv):
                        if not surface.Points.SetControlPoint(i, j, _control_point(rg, cp[i][j])):
                            raise ValueError("Rhino rejected a surface control point.")
                if not surface.IsValid:
                    raise ValueError("Rhino native NURBS surface validation failed.")
                brep = surface.ToBrep()
                if brep is None or not brep.IsValid:
                    if brep is not None:
                        brep.Dispose()
                    raise ValueError("Rhino native preview Brep validation failed.")
                breps.append(brep)
            finally:
                surface.Dispose()
        for descriptor in guide_specs:
            if cancelled():
                raise RuntimeError("Preview cancelled.")
            if not isinstance(descriptor, dict):
                raise ValueError("Kernel guides must be exact NURBS descriptors.")
            cp = _homogeneous(descriptor)
            degree = int(descriptor["degree"])
            if not 1 <= degree <= 64 or len(cp) > 4096:
                raise ValueError("Kernel guide exceeds native preview limits.")
            knots = _rhino_knots(descriptor["knots"], degree, len(cp))
            curve = rg.NurbsCurve(3, True, degree + 1, len(cp))
            try:
                for i, knot in enumerate(knots):
                    curve.Knots[i] = knot
                for i, point in enumerate(cp):
                    control = _control_point(rg, point)
                    if not curve.Points.SetPoint(i, control.Location, control.Weight):
                        raise ValueError("Rhino rejected a guide control point.")
                if not curve.IsValid:
                    raise ValueError("Rhino native guide validation failed.")
                guides.append(curve)
            except Exception:
                curve.Dispose()
                raise
        return breps, guides
    except Exception:
        _dispose_all(breps + guides)
        raise


def _rollback_new_additions(doc, additions):
    complete = True
    for identifier in reversed(additions):
        try:
            obj = doc.Objects.FindId(identifier)
            if obj is not None and not obj.IsDeleted:
                complete = bool(doc.Objects.Delete(identifier, True)) and complete
        except Exception:
            complete = False
    for identifier in additions:
        try:
            obj = doc.Objects.FindId(identifier)
            complete = (obj is None or obj.IsDeleted) and complete
        except Exception:
            complete = False
    return complete


def commit_new_geometry(doc, capture, breps, guides, handle, rhino, system):
    """One undo scope, rollback only IDs created here; originals are untouched."""
    ok, reason = capture.verify_sources(doc)
    if not ok:
        raise RuntimeError("Sources changed during preview: " + reason)
    if not breps:
        raise RuntimeError("There is no valid current preview to add.")
    if not doc.UndoRecordingEnabled:
        raise RuntimeError("Undo recording is disabled; no result was added.")
    owns_record = not doc.UndoRecordingIsActive
    serial = (doc.BeginUndoRecord("Smart Skin experimental FULLCYCLE") if owns_record
              else doc.CurrentUndoRecordSerialNumber)
    if serial == 0:
        raise RuntimeError("A single undo record could not be established.")
    additions = []
    try:
        for kind, objects in (("skin", breps), ("guide", guides)):
            for index, geometry in enumerate(objects):
                if not geometry.IsValid:
                    raise RuntimeError("A native result became invalid before commit.")
                attributes = rhino.DocObjects.ObjectAttributes()
                try:
                    attributes.Name = "Smart Skin {0} {1}".format(kind, index + 1)
                    attributes.SetUserString("SmartSkin.Route", "FULLCYCLE_EXPERIMENTAL_PARTIAL")
                    attributes.SetUserString("SmartSkin.ShoulderHandleFactor", "{:.2f}".format(handle))
                    identifier = (doc.Objects.AddBrep(geometry, attributes) if kind == "skin"
                                  else doc.Objects.AddCurve(geometry, attributes))
                finally:
                    attributes.Dispose()
                if identifier == system.Guid.Empty:
                    raise RuntimeError("Rhino could not add every result; rolling back this attempt.")
                additions.append(identifier)
        ok, reason = capture.verify_sources(doc)
        if not ok:
            raise RuntimeError("Source proof changed at commit: " + reason)
        if doc.CurrentUndoRecordSerialNumber != serial or not doc.UndoRecordingIsActive:
            raise RuntimeError("The undo scope changed during commit.")
        if any(doc.Objects.FindId(identifier) is None or doc.Objects.FindId(identifier).IsDeleted
               for identifier in additions):
            raise RuntimeError("The complete new result could not be verified.")
    except Exception as original:
        rollback_ok = _rollback_new_additions(doc, additions)
        if not rollback_ok:
            raise RuntimeError("New-only rollback was incomplete. Use Undo once and inspect the result.") from original
        raise
    finally:
        try:
            if owns_record:
                try:
                    ended = bool(doc.EndUndoRecord(serial))
                except Exception:
                    ended = False
                if not ended:
                    restored = _rollback_new_additions(doc, additions)
                    raise RuntimeError("The single undo scope could not be closed. " +
                                       ("New additions were removed." if restored else
                                        "New-only rollback was incomplete; inspect the result and use Undo."))
        finally:
            _safe_cleanup(doc.Views.Redraw)
    return len(breps), len(guides)


def _number(value):
    try:
        value = float(value)
        return "{:.4g}".format(value) if math.isfinite(value) else "not finite"
    except (TypeError, ValueError):
        return "not reported"


def _metric_text(output):
    metrics = output.get("metrics", output.get("report", {}))
    # Bound displayed text and prefer measured quantities. No value is called
    # a global G2 certificate, even when all numerical samples happen to pass.
    lines = []
    if isinstance(metrics, dict):
        if "sample_count" in metrics:
            lines.append("Finite samples: " + _number(metrics["sample_count"]))
        if "full_boundary_pass" in metrics:
            lines.append("Finite boundary check: " + ("PASS" if metrics["full_boundary_pass"] else "FAIL")
                         + " | global G2: NOT VERIFIED")
        for label, prefix in (("Source", "source"), ("Upper boundary", "upper"),
                              ("Lower boundary", "lower"), ("Internal seams", "seam")):
            parts = []
            for suffix, caption in (("position_error", "gap"), ("angle_degrees", "normal deg"),
                                    ("curvature_error", "W residual")):
                key = prefix + "_" + suffix
                if key in metrics:
                    parts.append(caption + " " + _number(metrics[key]))
            if parts:
                lines.append(label + ": " + " | ".join(parts))
        if "position_tolerance" in metrics:
            lines.append("Limits: gap {0} | normal deg {1} | W {2}".format(
                _number(metrics.get("position_tolerance")),
                _number(metrics.get("angle_tolerance_degrees")),
                _number(metrics.get("curvature_tolerance"))))
        for key, caption in (("minimum_sampled_sine", "Minimum sampled tangent sine"),
                             ("minimum_sampled_jacobian", "Minimum sampled Jacobian"),
                             ("minimum_orientation_dot_h1", "Minimum orientation dot versus handle 1.00"),
                             ("sampled_max_curvature", "Maximum sampled curvature")):
            if key in metrics:
                lines.append(caption + ": " + _number(metrics[key]))
        if "corner_policy" in metrics:
            lines.append(str(metrics["corner_policy"])[:300])
        for key in ("failing_intervals", "finite_corner_failures"):
            if key in metrics:
                lines.append(key.replace("_", " ") + ": " + str(metrics[key])[:400])
        for key, caption in (("upper_failure_intervals", "Upper failing parameter intervals"),
                             ("source_failure_intervals", "Source-end failing parameter intervals")):
            intervals = metrics.get(key, [])
            if intervals:
                lines.append(caption + ":")
                for interval in intervals[:8]:
                    lines.append("  " + str(interval)[:360])
                if len(intervals) > 8:
                    lines.append("  {0} additional failing intervals reported.".format(len(intervals) - 8))
    for warning in output.get("warnings", [])[:4]:
        lines.append(str(warning)[:200])
    return "\n".join(lines)


def run(doc, capture, kernel):
    """Called only by the supported Rhino CPython command path."""
    import Rhino
    import System
    import Eto.Forms as forms
    import Eto.Drawing as drawing
    import System.Drawing as system_drawing
    from Rhino.Geometry import BoundingBox

    class Conduit(Rhino.Display.DisplayConduit):
        def __init__(self):
            super().__init__()
            self.closed = False
            self.breps, self.guides = [], []
            self.material = Rhino.Display.DisplayMaterial(system_drawing.Color.FromArgb(65, 195, 215))
            self.material.Transparency = 0.35

        def CalculateBoundingBox(self, event):
            if self.closed:
                return
            box = BoundingBox.Empty
            for item in self.breps + self.guides:
                box.Union(item.GetBoundingBox(True))
            if box.IsValid:
                event.IncludeBoundingBox(box)

        def PostDrawObjects(self, event):
            if self.closed:
                return
            for brep in self.breps:
                event.Display.DrawBrepShaded(brep, self.material)
                event.Display.DrawBrepWires(brep, system_drawing.Color.DarkCyan, 1)
            for curve in self.guides:
                event.Display.DrawCurve(curve, system_drawing.Color.Orange, 2)

        def replace(self, breps, guides):
            previous = self.breps + self.guides
            self.breps, self.guides = breps, guides
            _dispose_all(previous)

        def close(self):
            if self.closed:
                return
            self.closed = True
            _safe_cleanup(lambda: setattr(self, "Enabled", False))
            _safe_cleanup(lambda: self.replace([], []))
            _safe_cleanup(self.material.Dispose)

    class Session:
        def __init__(self):
            self.state = PreviewState()
            self.prepared = None
            self.output = None
            self.accept_requested = False
            self.closing_for_command = False
            self.suppress_changes = False
            self.disposed = False
            self.deadline = None
            self.timed_out = False
            self.conduit = Conduit()
            self.form = forms.Form()
            self.form.Title = "Smart Skin | native FULLCYCLE preview"
            self.form.ClientSize = drawing.Size(570, 620)
            self.form.Resizable = True
            self.form.Minimizable = False
            self.form.Maximizable = False
            self.form.ShowActivated = False
            self.form.Owner = Rhino.UI.RhinoEtoApp.MainWindowForDocument(doc)
            self.slider = forms.Slider()
            self.slider.MinValue = 50
            self.slider.MaxValue = 150
            self.slider.Value = 100
            self.slider.TickFrequency = 10
            self.slider.Width = 280
            self.slider.ToolTip = "Scales both shoulder handles symmetrically. This is geometry, not a tolerance."
            self.value = forms.Label()
            self.value.Text = "1.00"
            self.value.Width = 55
            self.status = forms.TextArea()
            self.status.ReadOnly = True
            self.status.Wrap = True
            self.status.Height = 300
            self.status.Text = "Preparing native source-edge data..."
            limitation = forms.Label()
            limitation.Text = ("EXPERIMENTAL PARTIAL CONTINUITY\n"
                               "Finite upper corners AND source-side end strips have G1/G2 failures. Numerical samples "
                               "and valid Breps do not certify full-boundary G2 continuity.")
            limitation.Wrap = forms.WrapMode.Word
            instruction = forms.Label()
            instruction.Text = ("Enter / Space / right-click: accept the displayed experimental result.\n"
                                "Esc or closing this window: discard preview. Sources stay unchanged.")
            instruction.Wrap = forms.WrapMode.Word
            layout = forms.DynamicLayout()
            layout.Padding = drawing.Padding(16)
            layout.Spacing = drawing.Size(8, 10)
            caption = forms.Label()
            caption.Text = "Shoulder curvature / handle factor (both sides)"
            layout.AddRow(caption)
            row = forms.DynamicLayout()
            row.Spacing = drawing.Size(8, 0)
            row.AddRow(self.slider, self.value)
            layout.AddRow(row)
            layout.AddRow(limitation)
            layout.AddRow(self.status)
            layout.AddRow(instruction)
            self.form.Content = layout
            self.timer = forms.UITimer()
            self.timer.Interval = 0.25
            self.slider.ValueChanged += self.on_change
            self.timer.Elapsed += self.on_tick
            self.form.Closing += self.on_closing
            self.form.KeyDown += self.on_key
            self.slider.KeyDown += self.on_key
            self.status.KeyDown += self.on_key
            Rhino.RhinoApp.EscapeKeyPressed += self.on_escape
            self.conduit.Enabled = True

        def cancelled(self):
            # Pump only at explicit bounded kernel/native checkpoints. This
            # permits Esc and newer slider input; revision guards reject stale
            # results and the rebuilding guard prevents nested evaluations.
            if self.state.closed or self.state.cancelled:
                return True
            Rhino.RhinoApp.Wait()
            if self.deadline is not None and time.monotonic() >= self.deadline:
                self.timed_out = True
                return True
            return self.state.closed or self.state.cancelled

        def on_escape(self, sender, event):
            if self.disposed or self.state.closed:
                return
            self.state.cancel()
            self.timer.Stop()

        def on_closing(self, sender, event):
            if self.disposed or self.state.closed:
                return
            self.timer.Stop()
            if not self.closing_for_command:
                self.state.cancel()

        def on_key(self, sender, event):
            if self.disposed or self.state.closed or self.state.cancelled:
                return
            if event.Key == forms.Keys.Escape:
                event.Handled = True
                self.on_escape(sender, event)
            elif event.Key == forms.Keys.Enter or event.Key == forms.Keys.Space:
                event.Handled = True
                if self.prepare_acceptance():
                    self.accept_requested = True

        def on_change(self, sender, event):
            if self.suppress_changes or self.disposed or self.state.cancelled or self.state.closed:
                return
            self.accept_requested = False
            self.state.request(self.slider.Value / 100.0)
            self.value.Text = "{:.2f}".format(self.state.requested_h)
            self.timer.Stop()
            self.status.Text = "UPDATING: waiting for the new setting. Acceptance is disabled."
            self.timer.Start()

        def on_tick(self, sender, event):
            if self.disposed or self.state.closed or self.state.cancelled:
                return
            self.timer.Stop()
            self.rebuild()

        def rebuild(self):
            token = self.state.begin()
            if token is None:
                return
            started = time.monotonic()
            self.deadline = started + 60.0
            self.timed_out = False
            breps, guides = [], []
            try:
                self.status.Text = "UPDATING: building native skin and exact NURBS guides..."
                if self.prepared is None:
                    # Input mapping contains only owned generic numerical data.
                    self.prepared = kernel.prepare(capture.model, cancelled=self.cancelled)
                result = self.prepared.evaluate(token[1], cancelled=self.cancelled)
                if (not result.get("valid", False) or result.get("fatal", False)
                        or not result.get("experimental_commit_allowed", True)):
                    raise ValueError(result.get("reason", "Numerical geometry/regularity checks failed."))
                breps, guides = make_native_geometry(result, Rhino.Geometry, self.cancelled)
                if self.state.complete(token, True):
                    self.conduit.replace(breps, guides)
                    breps, guides = [], []
                    self.output = result
                    self.status.Text = ("READY: experimental partial result at handle {0:.2f}\n"
                                        "{1} native patches + {2} exact guides | {3:.2f} s\n{4}").format(
                                            token[1], len(self.conduit.breps), len(self.conduit.guides),
                                            time.monotonic() - started, _metric_text(result))
                elif not self.state.cancelled:
                    self.status.Text = "UPDATING: a newer handle setting is pending."
            except Exception as error:
                reason = ("The 60-second build budget expired between supported operations."
                          if self.timed_out else str(error)
                          if isinstance(error, (ValueError, RuntimeError)) else type(error).__name__)
                self.state.complete(token, False, reason)
                if not self.state.closed and not self.state.cancelled:
                    # Only a rejected CURRENT revision may reset the slider.
                    # A newer request arriving while computing keeps priority.
                    if token[0] == self.state.revision and self.state.restore_last_valid():
                        self.suppress_changes = True
                        try:
                            self.slider.Value = int(round(self.state.valid_h * 100))
                            self.value.Text = "{:.2f}".format(self.state.valid_h)
                        finally:
                            self.suppress_changes = False
                        self.status.Text = ("REJECTED handle {0:.2f}: {1}\n"
                                            "Slider and preview restored to {2:.2f}. Enter accepts this restored "
                                            "EXPERIMENTAL PARTIAL result.\n{3}").format(
                                                token[1], reason, self.state.valid_h, _metric_text(self.output))
                    else:
                        self.status.Text = "BLOCKED: " + reason + "\nNo current result can be accepted."
            finally:
                self.deadline = None
                _dispose_all(breps + guides)
                if self.state.pending and not self.state.cancelled and not self.state.closed:
                    self.timer.Start()
                doc.Views.Redraw()

        def prepare_acceptance(self):
            if self.disposed or self.state.closed or self.state.cancelled or self.state.building:
                return False
            self.timer.Stop()
            requested_revision = self.state.revision
            if self.state.pending:
                self.rebuild()
            # A failed pending setting may have visibly restored the previous
            # slider value. Require a NEW confirmation of that restored value.
            if self.state.revision != requested_revision:
                return False
            if not self.state.can_accept:
                return False
            ok, reason = capture.verify_sources(doc)
            if not ok:
                self.state.error = "Source proof changed."
                self.status.Text = "BLOCKED: sources changed during preview. " + reason
                return False
            return True

        def close(self):
            if self.disposed:
                return
            self.disposed = True
            self.closing_for_command = True
            self.state.close()
            # Every unsubscribe/dispose is isolated: a queued event or an
            # already disposed Eto control cannot strand the native conduit.
            def unhook_escape():
                Rhino.RhinoApp.EscapeKeyPressed -= self.on_escape
            def unhook_slider():
                self.slider.ValueChanged -= self.on_change
                self.slider.KeyDown -= self.on_key
            def unhook_timer():
                self.timer.Elapsed -= self.on_tick
            def unhook_form():
                self.form.Closing -= self.on_closing
                self.form.KeyDown -= self.on_key
            def unhook_status():
                self.status.KeyDown -= self.on_key
            for action in (unhook_escape, self.timer.Stop, self.conduit.close,
                           unhook_slider, unhook_timer, unhook_form, unhook_status,
                           self.form.Close, self.form.Dispose, self.timer.Dispose,
                           doc.Views.Redraw):
                _safe_cleanup(action)

    session = Session()
    decision = None
    try:
        session.form.Show()
        session.rebuild()
        decision = Rhino.Input.Custom.GetOption()
        decision.SetCommandPrompt("Smart Skin EXPERIMENTAL PARTIAL: Enter/Space/right-click accepts upper-corner and source-end G1/G2 failures; Esc cancels")
        decision.AcceptNothing(True)
        decision.SetWaitDuration(100)
        while not session.state.cancelled and session.form.Visible:
            if session.accept_requested:
                # Recheck even after a form key event. A queued value change or
                # altered source cannot exploit an earlier acceptance request.
                if session.prepare_acceptance():
                    break
                session.accept_requested = False
            result = decision.Get()
            if session.state.cancelled or not session.form.Visible:
                break
            if result == Rhino.Input.GetResult.Timeout:
                continue
            if result == Rhino.Input.GetResult.Nothing:
                if session.prepare_acceptance():
                    session.accept_requested = True
                    break
                continue
            session.state.cancel()
        if session.accept_requested and session.prepare_acceptance():
            skin_count, guide_count = commit_new_geometry(
                doc, capture, session.conduit.breps, session.conduit.guides,
                session.state.valid_h, Rhino, System)
            Rhino.RhinoApp.WriteLine("SMARTSKIN_P08E1 ACCEPTED_EXPERIMENTAL_PARTIAL | skin={0} | guides={1} | handle={2:.2f} | sources=unchanged | full_G2=NOT_VERIFIED".format(
                skin_count, guide_count, session.state.valid_h))
            return True
        Rhino.RhinoApp.WriteLine("SMARTSKIN_P08E1 CANCELLED | added=0 | sources=unchanged")
        return False
    finally:
        if decision is not None:
            _safe_cleanup(decision.Dispose)
        session.close()
