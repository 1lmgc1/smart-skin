# -*- coding: utf-8 -*-
"""P08A.2: geometry-read-only audit with a user-selected streaming TXT report.
Run in Rhino 8 with _RunPythonScript. IronPython 2.7 / Python 3 syntax compatible.
Private calls are pinned to one exact assembly and never invoke commit methods.
This is NOT a new solver and never enables acceptance or edits RhinoDoc geometry.
Only the report TXT selected in the save dialog is written; there are no network calls.
"""
from __future__ import print_function
import io
import os
import math
import time
import traceback

AUDIT_ID = "P08A.2"
EXPECTED_VERSION = "0.0.14-p07f2"
EXPECTED_COMMIT = "a9b8281f9475fb29d38839614b1781ff21b26677"
MAX_SECONDS = 45.0
MAX_EDGES = 8
MAX_SAMPLES = 8192
SAMPLES_PER_EDGE = 65


def finite(x):
    return not (math.isnan(float(x)) or math.isinf(float(x)))


def normal_plane_angle(a, b):
    """Unoriented tangent-plane angle; opposite face orientations are equivalent."""
    aa = sum(x * x for x in a)
    bb = sum(x * x for x in b)
    if not all(finite(x) for x in tuple(a) + tuple(b)) or aa <= 0 or bb <= 0:
        return None
    dot = sum(x * y for x, y in zip(a, b)) / math.sqrt(aa * bb)
    return math.degrees(math.acos(max(0.0, min(1.0, abs(dot)))))


def native_pair_summary(forward, reverse):
    """An unavailable direction is NEVER silently turned into zero or a pass."""
    good = [x for x in (forward, reverse) if x is not None and finite(x) and x >= 0]
    return len(good) == 2, max(good) if good else None


def clean(value):
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return "%.12g" % value if finite(value) else "n/a"
    return text_value(value).replace("\r", " ").replace("\n", " ").replace("|", "/")


try:
    TEXT_TYPE = unicode
except NameError:
    TEXT_TYPE = str


def text_value(value):
    """Keep Russian paths and .NET/Python Unicode messages intact in both engines."""
    if isinstance(value, TEXT_TYPE):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return TEXT_TYPE(value)


def txt_path(path):
    path = text_value(path)
    # Never turn an explicitly chosen model/script path into an overwrite target.
    # A non-TXT name becomes name.ext.txt instead of replacing its extension.
    return path if path.lower().endswith(".txt") else path + u".txt"


class TextReport(object):
    """Full UTF-8/BOM report, flushed per record; console is only a progress display.

    Memory retains the same records for a user-directed retry if file I/O fails.
    Write errors do not interrupt geometry disposal or the final safety checks.
    """
    def __init__(self, path, console=None):
        self.path = txt_path(path)
        self.console = console
        self.lines = []
        self.error = None
        self.closed = False
        self.stream = io.open(self.path, "w", encoding="utf-8-sig", newline="")

    def say(self, message):
        if self.console is not None:
            try:
                self.console(text_value(message))
            except Exception:
                # Console display must not prevent the TXT from being saved.
                pass

    def write(self, message):
        text = text_value(message).replace("\r\n", "\n").replace("\r", "\n")
        text = text.rstrip("\n") + u"\n"
        self.lines.append(text)
        if self.error is None:
            try:
                self.stream.write(text.replace("\n", "\r\n"))
                self.stream.flush()
            except Exception as error:
                self.error = text_value(error)
                self.say("SMARTSKIN_P08A_FILE_ERROR | partial TXT; choose another path at the end")

    def emit(self, kind, **data):
        text = u"SMARTSKIN_P08A_" + text_value(kind) + u" | " + u" | ".join(
            text_value(key) + u"=" + clean(data[key]) for key in sorted(data))
        self.write(text)
        if kind in ("IDENTITY", "INPUT", "MATCH_START", "COMPLETE", "STOP", "SAFETY"):
            # Do not copy long diagnostics back into Rhino's bounded command history.
            progress = u"SMARTSKIN_P08A_" + text_value(kind)
            if kind == "MATCH_START":
                progress += u" | " + clean(data.get("label"))
            self.say(progress + u" | details in TXT")
        return text

    def close(self):
        if self.closed:
            return
        try:
            self.stream.close()
        except Exception as error:
            if self.error is None:
                self.error = text_value(error)
        finally:
            self.closed = True


def choose_report(console):
    """Ask BEFORE binding/selection; a rejected path never starts the audit."""
    import rhinoscriptsyntax as rs
    name = "SmartSkin_ContextAudit_" + time.strftime("%Y%m%d_%H%M%S") + ".txt"
    while True:
        path = rs.SaveFileName(
            u"Smart Skin — сохранить отчёт аудита", "Text files (*.txt)|*.txt||",
            None, name, "txt")
        if not path:
            return None
        path = txt_path(path)
        if os.path.exists(path):
            # Also covers extension normalization, not just the native dialog's name.
            answer = rs.MessageBox(
                u"Этот TXT уже существует. Заменить его?\n\n" + path,
                4 | 32 | 256, u"Smart Skin — подтверждение перезаписи")
            if answer != 6:
                continue
        try:
            return TextReport(path, console)
        except Exception as error:
            rs.MessageBox(
                u"Не удалось открыть TXT для записи. Выберите другой путь.\n\n"
                + path + u"\n\n" + text_value(error),
                0 | 16, u"Smart Skin — ошибка сохранения")


class AuditStop(Exception):
    pass


class ContextAudit(object):
    def __init__(self, report):
        import clr
        import System
        import Rhino
        import scriptcontext
        self.clr, self.S, self.R, self.sc = clr, System, Rhino, scriptcontext
        self.doc = Rhino.RhinoDoc.ActiveDoc
        self.report = report
        self.start = time.time()
        self.samples = 0
        self.owned = []
        self.refs = []
        self.source_copies = []
        self.before = None
        self.output = []
        self.contexts = []
        self.flags = System.Reflection.BindingFlags
        self.static_flags = self.flags.Public | self.flags.NonPublic | self.flags.Static
        self.instance_flags = self.flags.Public | self.flags.NonPublic | self.flags.Instance
        self.bind()

    def emit(self, kind, **data):
        self.output.append(self.report.emit(kind, **data))

    def checkpoint(self):
        if self.report.error is not None:
            raise AuditStop("TXT_WRITE_FAILED; partial log retained; choose a new report path")
        if self.sc.escape_test(False):
            raise AuditStop("CANCELLED")
        if time.time() - self.start > MAX_SECONDS:
            raise AuditStop("TIME_BUDGET_REACHED; native calls are not force-aborted")

    def own(self, value):
        if value is not None:
            self.owned.append(value)
        return value

    def method(self, typ, name, count):
        methods = [m for m in typ.GetMethods(self.static_flags)
                   if m.Name == name and len(m.GetParameters()) == count]
        if len(methods) != 1:
            raise AuditStop("PINNED_API_NOT_FOUND: " + name)
        return methods[0]

    def invoke(self, method, *values):
        args = self.S.Array[self.S.Object](list(values))
        try:
            result = method.Invoke(None, args)
        except self.S.Reflection.TargetInvocationException as error:
            inner = error.InnerException
            raise AuditStop("NATIVE_EXCEPTION: " + str(inner if inner is not None else error))
        return result, args

    def prop(self, obj, name):
        prop = obj.GetType().GetProperty(name, self.instance_flags)
        if prop is None:
            raise AuditStop("PINNED_PROPERTY_NOT_FOUND: " + name)
        return prop.GetValue(obj, None)

    def bind(self):
        assemblies = [a for a in self.S.AppDomain.CurrentDomain.GetAssemblies()
                      if a.GetName().Name == "SmartSkin.Rhino8"]
        if len(assemblies) != 1:
            raise AuditStop("Run SmartSurfaceVersion once, then rerun this audit; no second RHP is loaded here.")
        assembly = assemblies[0]
        info = [a.InformationalVersion for a in assembly.GetCustomAttributes(False)
                if a.GetType().FullName == "System.Reflection.AssemblyInformationalVersionAttribute"]
        if len(info) != 1 or not info[0].startswith(EXPECTED_VERSION + "+" + EXPECTED_COMMIT):
            raise AuditStop("WRONG_PLUGIN_BUILD: expected " + EXPECTED_VERSION + "+" + EXPECTED_COMMIT)
        self.builder = assembly.GetType("SmartSkin.Rhino8.RhinoCandidateBuilder", True)
        self.verifier = assembly.GetType("SmartSkin.Rhino8.BoundaryMatchVerifier", True)
        metrics = assembly.GetType("SmartSkin.Rhino8.RhinoDocumentMetrics", True)
        self.count_method = self.method(metrics, "ActiveObjectCount", 1)
        self.order_method = self.method(self.builder, "OrderClosedEdgeLoop", 3)
        self.context_method = self.method(self.builder, "BuildBoundaryContext", 7)
        self.boundary_method = self.method(self.builder, "JoinBoundary", 2)
        self.seed_method = self.method(self.builder, "CreateSeedCap", 3)
        self.seed_edge_method = self.method(self.builder, "FindSeedBoundaryEdge", 3)
        self.join_loop_method = self.method(self.verifier, "JoinLoop", 2)
        self.face_method = self.method(self.verifier, "FaceParameters", 5)
        self.distance_method = self.method(self.clr.GetClrType(self.R.Geometry.Curve),
                                           "GetDistancesBetweenCurves", 9)
        edge_type = self.clr.GetClrType(self.R.Geometry.BrepEdge)
        candidates = []
        for m in self.clr.GetClrType(self.R.Geometry.Brep).GetMethods(self.static_flags):
            if m.Name != "CreateFromMatch":
                continue
            p = m.GetParameters()
            if len(p) == 5 and p[0].ParameterType == edge_type and p[1].ParameterType.IsGenericType:
                candidates.append(m)
        if len(candidates) != 1:
            raise AuditStop("PINNED_API_NOT_FOUND: CreateFromMatch(IEnumerable<Curve>)")
        self.match_method = candidates[0]
        self.tol = float(self.doc.ModelAbsoluteTolerance)
        self.angle = float(self.doc.ModelAngleToleranceRadians)
        if not finite(self.tol) or self.tol <= 0 or not finite(self.angle) or self.angle <= 0:
            raise AuditStop("INVALID_DOCUMENT_TOLERANCES")
        self.emit("IDENTITY", audit=AUDIT_ID, version=EXPECTED_VERSION, commit=EXPECTED_COMMIT,
                  rhino=self.R.RhinoApp.Version, abs_tol=self.tol,
                  angle_deg=math.degrees(self.angle), unit=self.doc.ModelUnitSystem,
                  mode="GEOMETRY_READ_ONLY;no_accept;no_document_write;selected_TXT_only")

    def active_count(self):
        return int(self.invoke(self.count_method, self.doc)[0])

    def select(self):
        go = self.R.Input.Custom.GetObject()
        try:
            go.SetCommandPrompt("Smart Skin AUDIT: select the same opening Brep edges; Enter to inspect copies only")
            go.GeometryFilter = self.R.DocObjects.ObjectType.Curve
            go.SubObjectSelect = True
            go.GroupSelect = False
            go.GetMultiple(1, 0)
            if go.CommandResult() != self.R.Commands.Result.Success:
                raise AuditStop("SELECTION_CANCELLED")
            if go.ObjectCount < 5 or go.ObjectCount > MAX_EDGES:
                raise AuditStop("Select five to eight opening edges, not whole objects or detached curves.")
            # Own the ObjRefs until all private factory calls and comparisons finish.
            self.refs = [go.Object(i) for i in range(go.ObjectCount)]
            self.go = go
        except Exception:
            go.Dispose()
            raise
        self.before = self.active_count()
        seen = set()
        for ref in self.refs:
            edge = ref.Edge()
            if edge is None or edge.Valence != self.R.Geometry.EdgeAdjacency.Naked or edge.TrimCount != 1:
                raise AuditStop("INPUT_NOT_A_NAKED_BREP_EDGE")
            if str(ref.ObjectId) not in seen:
                seen.add(str(ref.ObjectId))
                self.source_copies.append((ref, self.own(edge.Brep.DuplicateBrep())))
        self.emit("INPUT", edges=len(self.refs), parents=len(self.source_copies), objects=self.before)

    def new_context(self, label):
        self.checkpoint()
        refs = self.S.Collections.Generic.List[self.R.DocObjects.ObjRef]()
        curves = self.S.Collections.Generic.List[self.R.Geometry.Curve]()
        for ref in self.refs:
            refs.Add(ref)
            curves.Add(self.own(ref.Edge().DuplicateCurve()))
        ordered, out = self.invoke(self.order_method, curves, self.S.Double(self.tol), self.S.Int32(0))
        if ordered is None:
            raise AuditStop("ORDER_FAILED")
        context, out = self.invoke(self.context_method, refs, ordered, self.S.Double(self.tol),
                                   self.S.Double(self.angle), False, None, None)
        if context is None:
            raise AuditStop("CONTEXT_FAILED: " + str(out[5]) + "; " + str(out[6]))
        self.contexts.append(context)
        shell = self.prop(context, "Shell")
        edges = list(self.prop(context, "TargetEdges"))
        source_indices = list(self.prop(ordered, "SourceIndices"))
        sources = [self.refs[int(i)].Edge() for i in source_indices]
        oc = self.prop(ordered, "Curves")
        boundary = self.own(self.invoke(self.boundary_method, oc, self.S.Double(self.tol))[0])
        if boundary is None:
            raise AuditStop("BOUNDARY_FAILED")
        seed = self.own(self.invoke(self.seed_method, boundary, oc, self.S.Double(self.tol))[0])
        if seed is None:
            raise AuditStop("SEED_FAILED")
        seed_edge = self.invoke(self.seed_edge_method, seed, boundary, self.S.Double(self.tol))[0]
        if seed_edge is None:
            raise AuditStop("SEED_EDGE_MISSING")
        self.emit("CONTEXT", label=label, faces=shell.Faces.Count, edges=shell.Edges.Count,
                  targets=len(edges), valid=shell.IsValid, seed_faces=seed.Faces.Count,
                  seed_edges=seed.Edges.Count, seed_valid=seed.IsValid,
                  seed_algorithm="INSTALLED_P07F2_RADIAL_LOFT", isolated_variant=True)
        return context, shell, edges, sources, source_indices, oc, seed, seed_edge

    def face_data(self, edge, parameter):
        ok, args = self.invoke(self.face_method, edge, self.S.Double(parameter), None,
                               self.S.Double(float("nan")), self.S.Double(float("nan")))
        if not ok:
            return None
        face, u, v = args[2], float(args[3]), float(args[4])
        normal = face.NormalAt(u, v)
        if face.OrientationIsReversed:
            normal.Reverse()
        curvature = face.CurvatureAt(u, v)
        kappas = None if curvature is None else [float(curvature.Kappa(0)), float(curvature.Kappa(1))]
        point = face.PointAt(u, v)
        return face, u, v, (float(normal.X), float(normal.Y), float(normal.Z)), kappas, point

    def nearest(self, point, edges):
        hits = []
        for edge in edges:
            ok, parameter = edge.ClosestPoint(point)
            if not ok:
                raise AuditStop("NEAREST_POINT_UNAVAILABLE; not treated as zero")
            gap = float(point.DistanceTo(edge.PointAt(parameter)))
            if not finite(gap):
                raise AuditStop("NONFINITE_NEAREST_POINT")
            hits.append((gap, edge, float(parameter)))
        if not hits:
            raise AuditStop("EMPTY_BOUNDARY")
        hits.sort(key=lambda hit: hit[0])
        return hits[0]

    def point_token(self, point):
        return ",".join(clean(float(v)) for v in (point.X, point.Y, point.Z))

    def native_gap(self, a, b, label, direction):
        self.checkpoint()
        values = [a, b, self.S.Double(max(self.tol * 0.1, 1e-9))]
        values.extend([self.S.Double(float("nan"))] * 6)
        ok, args = self.invoke(self.distance_method, *values)
        gap = float(args[3]) if ok and finite(args[3]) and float(args[3]) >= 0 else None
        data = dict(label=label, direction=direction, api_ok=bool(ok), native_max=gap,
                    parameter_a=float(args[4]) if ok else None, parameter_b=float(args[5]) if ok else None)
        if gap is not None and finite(args[4]) and finite(args[5]):
            pa, pb = a.PointAt(float(args[4])), b.PointAt(float(args[5]))
            data["witness_pair_distance"] = float(pa.DistanceTo(pb))
            found, tb = b.ClosestPoint(pa)
            data["witness_a_to_b_nearest"] = float(pa.DistanceTo(b.PointAt(tb))) if found else None
            data["witness_a"] = self.point_token(pa)
            data["witness_b"] = self.point_token(pb)
        self.emit("NATIVE_DISTANCE", **data)
        return gap

    def sample_gap(self, sources, targets, label, direction, with_frames=False):
        overall = 0.0
        for source in sources:
            self.checkpoint()
            worst = None
            max_normal = 0.0
            max_face_residual = 0.0
            frames = 0
            for i in range(SAMPLES_PER_EDGE):
                self.checkpoint()
                self.samples += 1
                if self.samples > MAX_SAMPLES:
                    raise AuditStop("SAMPLE_BUDGET_REACHED")
                ok, t = source.NormalizedLengthParameter(float(i) / (SAMPLES_PER_EDGE - 1))
                if not ok:
                    raise AuditStop("SAMPLE_PARAMETERIZATION_FAILED")
                p = source.PointAt(t)
                gap, target, tt = self.nearest(p, targets)
                if worst is None or gap > worst[0]:
                    worst = (gap, float(t), target.EdgeIndex, tt, p)
                if with_frames and 0 < i < SAMPLES_PER_EDGE - 1:
                    sf, tf = self.face_data(source, t), self.face_data(target, tt)
                    if sf is not None and tf is not None:
                        angle = normal_plane_angle(sf[3], tf[3])
                        if angle is not None:
                            max_normal = max(max_normal, angle)
                            max_face_residual = max(max_face_residual, float(p.DistanceTo(sf[5])),
                                                    float(target.PointAt(tt).DistanceTo(tf[5])))
                            frames += 1
            overall = max(overall, worst[0])
            self.emit("SAMPLED_DISTANCE", label=label, direction=direction, source_edge=source.EdgeIndex,
                      sampled_max_nearest=worst[0], source_parameter=worst[1], target_edge=worst[2],
                      target_parameter=worst[3], witness=self.point_token(worst[4]), samples=SAMPLES_PER_EDGE,
                      normal_plane_max_deg=max_normal if frames else None, frame_samples=frames,
                      edge_to_face_sampled_residual=max_face_residual if frames else None,
                      acceptance="NEVER;finite_samples_are_not_a_certified_global_bound")
        return overall

    def join_loop(self, edges):
        array = self.S.Array[self.R.Geometry.BrepEdge](list(edges))
        return self.own(self.invoke(self.join_loop_method, array, self.S.Double(self.tol))[0])

    def compare_boundaries(self, cap, targets, label, with_frames=False):
        cap_edges = [e for e in cap.Edges if e.Valence == self.R.Geometry.EdgeAdjacency.Naked]
        ca, cb = self.join_loop(cap_edges), self.join_loop(targets)
        if ca is None or cb is None:
            self.emit("BOUNDARY_COMPARE", label=label, state="LOOP_UNAVAILABLE", cap_edges=len(cap_edges))
            return
        f = self.native_gap(ca, cb, label, "CAP_TO_TARGET")
        r = self.native_gap(cb, ca, label, "TARGET_TO_CAP")
        complete, maximum = native_pair_summary(f, r)
        sf = self.sample_gap(cap_edges, targets, label, "CAP_TO_TARGET", with_frames)
        sr = self.sample_gap(targets, cap_edges, label, "TARGET_TO_CAP", with_frames)
        self.emit("BOUNDARY_COMPARE", label=label, native_both_available=complete, native_max=maximum,
                  sampled_max_nearest=max(sf, sr), native_allowed=self.tol, cap_edges=len(cap_edges),
                  state="DIAGNOSTIC_ONLY;not_a_GEOMETRY_PASS")

    def same_surface(self, first, second):
        a, b = first.DuplicateSurface(), second.DuplicateSurface()
        try:
            return a is not None and b is not None and self.R.Geometry.GeometryBase.GeometryEquals(a, b)
        finally:
            if a is not None:
                a.Dispose()
            if b is not None:
                b.Dispose()

    def audit_mapping(self, pack):
        context, shell, edges, sources, source_indices, ordered, seed, seed_edge = pack
        for slot, (source, target) in enumerate(zip(sources, edges)):
            self.checkpoint()
            st, tt = source.TrimIndices(), target.TrimIndices()
            sf, tf = source.Brep.Trims[st[0]].Face, target.Brep.Trims[tt[0]].Face
            candidates = []
            # A bounded endpoint test finds plausible full-edge alternatives, not arbitrary subedges.
            for e in shell.Edges:
                if e.Valence != self.R.Geometry.EdgeAdjacency.Naked or e.TrimCount != 1:
                    continue
                d0 = max(source.PointAtStart.DistanceTo(e.PointAtStart), source.PointAtEnd.DistanceTo(e.PointAtEnd))
                d1 = max(source.PointAtStart.DistanceTo(e.PointAtEnd), source.PointAtEnd.DistanceTo(e.PointAtStart))
                if min(d0, d1) <= 2 * self.tol:
                    ef = e.Brep.Trims[e.TrimIndices()[0]].Face
                    candidates.append(str(e.EdgeIndex) + ":face=" + str(ef.FaceIndex)
                                      + ":surface_equal=" + str(self.same_surface(sf, ef)))
            mapped_surface_equal = self.same_surface(sf, tf)
            self.emit("MAP", slot=slot, selection_index=int(source_indices[slot]),
                      source_object=self.refs[int(source_indices[slot])].ObjectId,
                      source_edge=source.EdgeIndex, source_trim=int(st[0]), source_face=sf.FaceIndex,
                      mapped_edge=target.EdgeIndex, mapped_trim=int(tt[0]), mapped_face=tf.FaceIndex,
                      source_orientation_reversed=sf.OrientationIsReversed,
                      mapped_orientation_reversed=tf.OrientationIsReversed,
                      surface_equal=mapped_surface_equal, source_trim_iso=source.Brep.Trims[st[0]].IsoStatus,
                      mapped_trim_iso=target.Brep.Trims[tt[0]].IsoStatus,
                      source_edge_tolerance=float(source.Tolerance),
                      mapped_edge_tolerance=float(target.Tolerance),
                      source_degree_uv="%s,%s" % (sf.Degree(0), sf.Degree(1)),
                      mapped_degree_uv="%s,%s" % (tf.Degree(0), tf.Degree(1)),
                      endpoint_alternatives=";".join(candidates), alternative_count=len(candidates))
            ok, parameter = source.NormalizedLengthParameter(0.5)
            if ok:
                gap, nearest_edge, tp = self.nearest(source.PointAt(parameter), [target])
                a, b = self.face_data(source, parameter), self.face_data(nearest_edge, tp)
                self.emit("MAP_FRAME", slot=slot, source_frame_available=a is not None,
                          mapped_frame_available=b is not None,
                          source_uv=",".join(clean(x) for x in a[1:3]) if a else None,
                          mapped_uv=",".join(clean(x) for x in b[1:3]) if b else None,
                          source_normal=",".join(clean(x) for x in a[3]) if a else None,
                          mapped_normal=",".join(clean(x) for x in b[3]) if b else None,
                          source_principal_curvatures=",".join(clean(x) for x in a[4]) if a and a[4] else None,
                          mapped_principal_curvatures=",".join(clean(x) for x in b[4]) if b and b[4] else None)
            self.native_gap(source, target, "MAP_%s" % slot, "SOURCE_TO_CONTEXT")
            self.native_gap(target, source, "MAP_%s" % slot, "CONTEXT_TO_SOURCE")
            self.sample_gap([source], [target], "MAP_%s" % slot, "SOURCE_TO_CONTEXT", True)
            self.sample_gap([target], [source], "MAP_%s" % slot, "CONTEXT_TO_SOURCE", True)
        self.emit("MAPPING_SCOPE", selected=len(sources), mapped=len(edges),
                  note="Factory output inspected; alternatives are endpoint-filtered, not a proof of uniqueness")

    def audit_corners(self, pack):
        sources, ordered = pack[3], pack[5]
        for i, source in enumerate(sources):
            j = (i + 1) % len(sources)
            other = sources[j]
            pa, pb = ordered[i].PointAtEnd, ordered[j].PointAtStart
            oka, ta = source.ClosestPoint(pa)
            okb, tb = other.ClosestPoint(pb)
            a = self.face_data(source, ta) if oka else None
            b = self.face_data(other, tb) if okb else None
            angle = normal_plane_angle(a[3], b[3]) if a is not None and b is not None else None
            self.emit("CORNER", corner=i, source_slots="%s,%s" % (i, j),
                      endpoint_gap=float(pa.DistanceTo(pb)), point=self.point_token(pa),
                      normal_plane_angle_deg=angle, document_angle_deg=math.degrees(self.angle),
                      regular_G1_corner="REVIEW_SUPPORT_LIMITS" if angle is not None and angle > math.degrees(self.angle)
                      else "NOT_DISPROVED" if angle is not None else "NOT_MEASURED",
                      scope="necessary_corner_condition_only;no_automatic_continuity_change")

    def native_variant(self, reverse):
        label = "REVERSE_ON" if reverse else "REVERSE_OFF"
        pack = self.new_context(label)
        context, shell, edges, sources, source_indices, ordered, seed, seed_edge = pack
        before_shell, before_seed = self.own(shell.DuplicateBrep()), self.own(seed.DuplicateBrep())
        settings = self.R.Geometry.MatchSrfSettings(self.R.Geometry.Continuity.G2_continuous,
                                                    getattr(self.R.Geometry.Continuity, "None"))
        settings.Average = False
        settings.MatchClosestPoints = False
        settings.PreserveIso = self.R.Geometry.PreserveIsoCurveMethod.Automatic
        settings.ReverseMatchDirection = reverse
        settings.ReverseAverageTargetDirection = False
        settings.EnableRefinement(True, self.tol, self.angle, 5.0)
        targets = self.S.Array[self.R.Geometry.Curve](edges)
        self.emit("MATCH_START", label=label, target_types=";".join(e.GetType().FullName for e in edges),
                  supports=len(edges), seed_edge=seed_edge.EdgeIndex, continuity="G2", fresh_copies=True,
                  same_initial_seed=self.R.Geometry.GeometryBase.GeometryEquals(seed, self.base_seed),
                  same_initial_context=self.R.Geometry.GeometryBase.GeometryEquals(shell, self.base_shell))
        self.checkpoint()
        tick = time.time()
        ok, out = self.invoke(self.match_method, seed_edge, targets, settings, None, None)
        cap, changed = self.own(out[3]), self.own(out[4])
        self.emit("MATCH_RETURN", label=label, native_ok=bool(ok), returned_brep=cap is not None,
                  returned_valid=cap.IsValid if cap is not None else None,
                  elapsed_ms=int(1000 * (time.time() - tick)),
                  context_unchanged=self.R.Geometry.GeometryBase.GeometryEquals(shell, before_shell),
                  seed_unchanged=self.R.Geometry.GeometryBase.GeometryEquals(seed, before_seed))
        if cap is not None and cap.IsValid and cap.Faces.Count <= 128 and cap.Edges.Count <= 512:
            # G0 diagnostics are independent of passing the production verifier's G0 gate.
            # Any frame data here remain sampled diagnostics, never a G2 certification.
            self.compare_boundaries(cap, edges, label + "_CONTEXT", True)
            self.compare_boundaries(cap, sources, label + "_ORIGINAL", False)
        else:
            self.emit("MATCH_DIAGNOSIS", label=label, state="NO_VALID_BOUNDED_CAP_FOR_DISTANCE_AUDIT")

    def run(self):
        self.select()
        self.start = time.time()
        pack = self.new_context("BASELINE")
        self.base_shell, self.base_seed = pack[1], pack[6]
        self.audit_mapping(pack)
        self.audit_corners(pack)
        self.compare_boundaries(pack[6], pack[2], "SEED_VS_CONTEXT", True)
        self.native_variant(False)
        self.native_variant(True)
        self.emit("COMPLETE", state="AUDIT_COMPLETED_NOT_GEOMETRY_ACCEPTED", samples=self.samples)

    def close(self):
        unchanged = True
        try:
            for ref, snapshot in self.source_copies:
                owner = ref.Edge().Brep
                equal = self.R.Geometry.GeometryBase.GeometryEquals(owner, snapshot)
                unchanged = unchanged and bool(equal)
                self.emit("SOURCE_CHECK", object_id=ref.ObjectId, geometry_equal=bool(equal))
            if self.before is not None:
                after = self.active_count()
                self.emit("SAFETY", objects_before=self.before, objects_after=after,
                          selected_parent_geometry_equal=unchanged,
                          count_equal=after == self.before, added_by_audit=0,
                          note="selection highlighting may change; no document geometry API writes")
        finally:
            for value in reversed(self.owned):
                try:
                    value.Dispose()
                except Exception as error:
                    self.emit("CLEANUP_WARNING", error=error)
            for context in reversed(self.contexts):
                # IDisposable invocation works even though BoundaryContext is a private nested type.
                try:
                    method = context.GetType().GetMethod("Dispose", self.instance_flags)
                    method.Invoke(context, None)
                except Exception as error:
                    self.emit("CLEANUP_WARNING", error=error)
            if hasattr(self, "go"):
                self.go.Dispose()


def run_to_report(report, audit_factory=ContextAudit):
    """Keep STOP/traceback and SAFETY in the same report, including early failures."""
    audit = None
    state = "STOPPED"
    report.emit("REPORT_BEGIN", audit=AUDIT_ID, expected_version=EXPECTED_VERSION,
                expected_commit=EXPECTED_COMMIT, path=report.path,
                encoding="UTF-8-BOM", flush="EACH_RECORD",
                local_time=time.strftime("%Y-%m-%dT%H:%M:%S"))
    try:
        audit = audit_factory(report)
        audit.run()
        state = "COMPLETE"
    except BaseException as error:
        report.emit("STOP", error=error, exception_type=type(error).__name__)
        if not isinstance(error, AuditStop):
            report.write("SMARTSKIN_P08A_TRACEBACK\n" + traceback.format_exc())
    finally:
        try:
            if audit is not None:
                audit.close()
                if audit.before is None:
                    report.emit("SAFETY", state="NO_SELECTION_SNAPSHOT;geometry_audit_not_started",
                                added_by_audit=0)
            else:
                report.emit("SAFETY", state="INITIALIZATION_STOPPED;geometry_audit_not_started",
                            added_by_audit=0)
        except BaseException as error:
            state = "STOPPED"
            report.emit("SAFETY", state="CHECK_FAILED;do_not_infer_geometry_unchanged", error=error)
            report.write("SMARTSKIN_P08A_CLEANUP_TRACEBACK\n" + traceback.format_exc())
        finally:
            report.emit("REPORT_END", audit=AUDIT_ID, state=state,
                        geometry_acceptance="NEVER", file_write_error=report.error)
            report.close()


def finish_report(report):
    """Offer another explicit destination on I/O failure, without repeating geometry."""
    current = report
    while current.error is not None:
        current.say("SMARTSKIN_P08A_FILE_INCOMPLETE | " + current.path)
        replacement = choose_report(current.console)
        if replacement is None:
            current.say("SMARTSKIN_P08A_FILE_INCOMPLETE | save retry cancelled; prior TXT may be partial")
            return
        for line in current.lines:
            replacement.write(line)
        replacement.emit("REPORT_RECOVERED", previous_path=current.path,
                         previous_io_error=current.error, new_path=replacement.path,
                         geometry_rerun=False)
        replacement.close()
        current = replacement
    current.say("SMARTSKIN_P08A_SAVED | " + current.path)


def main():
    import Rhino
    console = Rhino.RhinoApp.WriteLine
    report = choose_report(console)
    if report is None:
        console("SMARTSKIN_P08A_CANCELLED | no TXT path selected; audit not started")
        return
    report.say("SMARTSKIN_P08A_LOGGING | " + report.path)
    run_to_report(report)
    finish_report(report)


if __name__ == "__main__":
    main()
