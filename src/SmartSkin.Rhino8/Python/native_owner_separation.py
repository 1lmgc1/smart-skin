"""Bounded Rhino 8 owner-intersection/overlap SCREEN, never a global proof.

Native calls stay on the caller's Rhino command/UI path. Cancellation/deadlines
are observed BETWEEN calls, never by aborting a Rhino call. A positive receipt
means all declared pairs and finite complement screens completed. Small
unsampled coincident regions remain a numerical coverage limitation.

RhinoCommon APIs used (native execution is NOT VERIFIED by adapter mocks):
https://mcneel.github.io/rhinocommon-api-docs/api/RhinoCommon/html/M_Rhino_Geometry_Intersect_Intersection_BrepBrep_1.htm
  bool BrepBrep(Brep, Brep, double, bool, out Curve[], out Point3d[]) (8.12+)
https://developer.rhino3d.com/api/RhinoCommon/html/M_Rhino_Geometry_Intersect_Intersection_CurveBrep.htm
  bool CurveBrep(Curve, Brep, double, out Curve[], out Point3d[]) (5.0+)
https://mcneel.github.io/rhinocommon-api-docs/api/RhinoCommon/html/M_Rhino_Geometry_Intersect_Intersection_CurveCurve.htm
  CurveIntersections CurveCurve(Curve, Curve, double, double) (5.0+)
https://mcneel.github.io/rhinocommon-api-docs/api/RhinoCommon/html/M_Rhino_Geometry_Brep_ClosestPoint_1.htm
  bool ClosestPoint(Point3d, out Point3d, out ComponentIndex, out double,
                    out double, double, out Vector3d) (5.0+)
https://mcneel.github.io/rhinocommon-api-docs/api/RhinoCommon/html/M_Rhino_Geometry_BrepFace_IsPointOnFace_1.htm
  PointFaceRelation IsPointOnFace(double, double, double) (7.0+)
"""
from dataclasses import dataclass
import hashlib
import json
import math
import time


class SeparationError(RuntimeError):
    def __init__(self, code, detail):
        self.code = code
        super().__init__(code + ': ' + detail)


def _fail(code, detail):
    raise SeparationError(code, detail)


def _json(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError):
        _fail('OWNER_SCREEN_BINDING', 'Request, source token and contacts must be finite JSON values.')


def _hash(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _interval(value):
    if not isinstance(value, (tuple, list)) or len(value) != 2 or not all(_finite(v) for v in value):
        _fail('OWNER_SCREEN_BINDING', 'A finite, increasing native parameter interval is required.')
    a, b = map(float, value)
    if not a < b:
        _fail('OWNER_SCREEN_BINDING', 'A native parameter interval must have positive length.')
    return a, b


def _source_interval(value):
    if not isinstance(value, (tuple, list)) or len(value) != 2 or not all(_finite(v) for v in value):
        _fail('OWNER_SCREEN_BINDING', 'A finite selected-source interval is required.')
    return _interval(sorted(value))


def _dispose(items):
    for item in items:
        try:
            item.Dispose()
        except Exception:
            pass


def _dispose_native_result(value):
    """A cancellation observed just after allocation must not leak its result."""
    if value is None or isinstance(value, (str, bytes, bool, int, float)):
        return
    if callable(getattr(value, 'Dispose', None)):
        _dispose([value])
        return
    try:
        for item in value:
            _dispose_native_result(item)
    except TypeError:
        pass


def _bounded_items(items, maximum, label):
    out = []
    for value in items:
        if len(out) >= maximum:
            _fail('OWNER_SCREEN_BUDGET', label + ' count exceeds its finite budget.')
        out.append(value)
    return tuple(out)


@dataclass(frozen=True)
class ScreenLimits:
    max_patches: int = 32
    max_owners: int = 16
    max_pairs: int = 512
    max_faces: int = 128
    max_edges: int = 640
    max_control_points: int = 262144
    max_degree: int = 64
    max_curve_points: int = 4096
    max_events: int = 4096
    max_witnesses: int = 8192
    max_native_calls: int = 20000
    max_snapshot_bytes: int = 64 * 1024 * 1024
    seconds: float = 15.0

    def __post_init__(self):
        for key, value in self.__dict__.items():
            if key == 'seconds':
                if not _finite(value) or value <= 0:
                    raise ValueError('The native screen requires a positive finite time budget.')
            elif type(value) is not int or value <= 0:
                raise ValueError('Every native screen work limit must be a positive integer.')


class _Budget:
    def __init__(self, limits, cancelled=None, clock=time.monotonic):
        if cancelled is not None and not callable(cancelled):
            raise ValueError('Cancellation must be callable.')
        self.limits, self.cancelled, self.clock = limits, cancelled, clock
        self.started = clock()
        self.calls = 0

    def check(self):
        if self.cancelled is not None and self.cancelled():
            _fail('OWNER_SCREEN_CANCELLED', 'The current native screen was cancelled or superseded.')
        if self.clock() - self.started > self.limits.seconds:
            _fail('OWNER_SCREEN_BUDGET', 'Time budget expired between supported native operations.')

    def call(self, function, *args):
        self.check()
        if self.calls >= self.limits.max_native_calls:
            _fail('OWNER_SCREEN_BUDGET', 'Native-call budget exhausted; no partial screen can pass.')
        self.calls += 1
        value = function(*args)
        try:
            self.check()
        except Exception:
            _dispose_native_result(value)
            raise
        return value


@dataclass(frozen=True)
class SelectedSpan:
    source_key: str
    edge_index: int
    interval: tuple
    side_evidence: object = None  # Frozen JSON from validated captured owner_side.


@dataclass(frozen=True)
class OwnerSnapshot:
    key: str
    geometry: object
    selected_spans: tuple


@dataclass
class _Prepared:
    bbox: tuple
    curves: tuple
    witnesses: tuple
    faces: int
    edges: int
    control_points: int

    def dispose(self):
        _dispose(self.curves)


class RhinoAdapter:
    """Thin, injectable RhinoCommon binding. Owns no document objects."""
    def __init__(self, rhino):
        self.rg = rhino.Geometry
        self.serialization = rhino.FileIO.SerializationOptions()
        self.serialization.WriteUserData = True
        # Runtime display/analysis caches are not source geometry or attributes.
        self.serialization.WriteRenderMeshes = False
        self.serialization.WriteAnalysisMeshes = False

    def fingerprint(self, geometry, budget):
        raw = budget.call(geometry.ToJSON, self.serialization)
        if not isinstance(raw, str) or not raw:
            _fail('OWNER_SCREEN_NATIVE_FAILURE', 'Native geometry serialization failed.')
        return _hash(raw)

    @staticmethod
    def _point(point):
        values = tuple(float(getattr(point, key)) for key in ('X', 'Y', 'Z'))
        if not all(math.isfinite(v) for v in values):
            _fail('OWNER_SCREEN_NATIVE_FAILURE', 'Native geometry returned a nonfinite point.')
        return values

    @staticmethod
    def _domain(domain):
        return _interval([float(domain.T0), float(domain.T1)])

    def curve_domain(self, curve, budget):
        if curve is None or not budget.call(lambda: curve.IsValid):
            _fail('OWNER_SCREEN_NATIVE_FAILURE', 'An invalid native intersection/boundary curve was returned.')
        nurbs = budget.call(curve.ToNurbsCurve)
        if nurbs is None:
            _fail('OWNER_SCREEN_NATIVE_FAILURE', 'A native curve could not be bounded.')
        try:
            if (nurbs.Points.Count > budget.limits.max_curve_points or
                    nurbs.Degree > budget.limits.max_degree):
                _fail('OWNER_SCREEN_BUDGET', 'Native curve complexity exceeds the screen budget.')
        finally:
            nurbs.Dispose()
        return self._domain(curve.Domain)

    def prepare(self, geometry, tolerance, budget):
        limits = budget.limits
        if geometry is None or not budget.call(lambda: geometry.IsValid):
            _fail('OWNER_SCREEN_NATIVE_FAILURE', 'The screen requires valid copied native Breps.')
        faces, edges = geometry.Faces.Count, geometry.Edges.Count
        if not 1 <= faces <= limits.max_faces or not 1 <= edges <= limits.max_edges:
            _fail('OWNER_SCREEN_BUDGET', 'Native face/edge complexity exceeds the screen budget.')
        box = budget.call(geometry.GetBoundingBox, True)
        if not box.IsValid:
            _fail('OWNER_SCREEN_NATIVE_FAILURE', 'The native bounding box is invalid.')
        bbox = (self._point(box.Min), self._point(box.Max))
        curves, witnesses, control_points = [], [], 0
        try:
            for edge in geometry.Edges:
                curve = budget.call(edge.DuplicateCurve)
                if curve is None:
                    _fail('OWNER_SCREEN_NATIVE_FAILURE', 'Could not copy an actual Brep edge.')
                curves.append(curve)
                self.curve_domain(curve, budget)
            for face in geometry.Faces:
                surface = budget.call(face.ToNurbsSurface)
                if surface is None:
                    _fail('OWNER_SCREEN_NATIVE_FAILURE', 'Could not bound an owning face.')
                try:
                    control_points += surface.Points.CountU * surface.Points.CountV
                    if (control_points > limits.max_control_points or
                            max(surface.Degree(0), surface.Degree(1)) > limits.max_degree):
                        _fail('OWNER_SCREEN_BUDGET', 'Native surface complexity exceeds the screen budget.')
                finally:
                    surface.Dispose()
                ud = self._domain(face.Domain(0)); vd = self._domain(face.Domain(1))
                interior = []
                # Native face parameters, not converted NURBS parameters.
                # A second finite grid is used only for sparse/narrow trims.
                for count in (5, 9):
                    for i in range(count):
                        u = ud[0] + (ud[1] - ud[0]) * (i + .5) / count
                        for j in range(count):
                            v = vd[0] + (vd[1] - vd[0]) * (j + .5) / count
                            # This is topological witness selection, not the
                            # unchanged document-tolerance collision test.
                            # Using model tolerance here erases thin interiors.
                            relation = str(budget.call(face.IsPointOnFace, u, v, 0.0))
                            if relation not in ('Interior', 'Exterior', 'Boundary'):
                                _fail('OWNER_SCREEN_NATIVE_FAILURE', 'Native trim membership is unsupported.')
                            if relation == 'Interior':
                                point = budget.call(face.PointAt, u, v)
                                self._point(point)
                                interior.append(point)
                    if len(interior) >= 4:
                        break
                if len(interior) < 4:
                    _fail('OWNER_SCREEN_TRIM_COVERAGE', 'A face has insufficient bounded actual-trim interior coverage.')
                witnesses.extend(interior)
                if len(witnesses) > limits.max_witnesses:
                    _fail('OWNER_SCREEN_BUDGET', 'Interior-witness budget exceeded.')
            return _Prepared(bbox, tuple(curves), tuple(witnesses), faces, edges, control_points)
        except Exception:
            _dispose(curves)
            raise

    def contact_curves(self, patch, owner, selected, contact, budget):
        source, generated = None, None
        try:
            edge = owner.Edges[selected.edge_index]
            if str(edge.Valence) != 'Naked' or len(list(edge.TrimIndices())) != 1:
                _fail('OWNER_SCREEN_BINDING', 'An allowed source must be the captured unique naked edge.')
            actual = self._domain(edge.Domain)
            interval = _source_interval(contact['native_parameter_interval'])
            if selected.interval[0] < actual[0] or selected.interval[1] > actual[1]:
                _fail('OWNER_SCREEN_BINDING', 'Captured source interval escaped its native edge.')
            source = budget.call(edge.Trim, interval[0], interval[1])
            if patch.Faces.Count != 1:
                _fail('OWNER_SCREEN_BINDING', 'Each generated atlas patch must have exactly one native face.')
            face = patch.Faces[0]
            edge_name = contact['edge']
            axis, side = {'left': (1, 0), 'right': (1, 1),
                          'bottom': (0, 0), 'top': (0, 1)}[edge_name]
            constant = self._domain(face.Domain(1 - axis))[side]
            generated = budget.call(face.IsoCurve, axis, constant)
            if generated is None:
                _fail('OWNER_SCREEN_BINDING', 'A generated exterior trace could not be obtained.')
            gd = self.curve_domain(generated, budget)
            wanted = _interval(contact['generated_parameter_interval'])
            if wanted[0] < gd[0] or wanted[1] > gd[1]:
                _fail('OWNER_SCREEN_BINDING', 'An exterior interval escaped its generated edge.')
            restricted = budget.call(generated.Trim, wanted[0], wanted[1])
            generated.Dispose(); generated = restricted
            self.curve_domain(source, budget); self.curve_domain(generated, budget)
            return source, generated
        except Exception:
            _dispose([source, generated])
            raise

    def contact_points(self, patch, owner, selected, contact, tolerance, budget):
        if patch.Faces.Count != 1:
            _fail('OWNER_SCREEN_BINDING', 'An isolated contact requires one native generated face.')
        face = patch.Faces[0]
        uv = contact['generated_uv']
        if any(uv[axis] not in self._domain(face.Domain(axis)) for axis in (0, 1)):
            _fail('OWNER_SCREEN_BINDING', 'An isolated source contact must be an exact generated atlas corner.')
        edge = owner.Edges[selected.edge_index]
        if str(edge.Valence) != 'Naked' or len(list(edge.TrimIndices())) != 1:
            _fail('OWNER_SCREEN_BINDING', 'An isolated source contact lost its captured naked edge.')
        source = budget.call(edge.PointAt, contact['native_parameter'])
        generated = budget.call(face.PointAt, *uv)
        if math.dist(self._point(source), self._point(generated)) > tolerance:
            _fail('OWNER_SCREEN_BINDING', 'The exact generated/source point contact is not attached.')
        return source, generated

    def same_point(self, point, other, tolerance):
        return math.dist(self._point(point), self._point(other)) <= tolerance

    def _intersection(self, function, args, budget, parameter_curve=None):
        result = budget.call(function, *args)
        accepted_lengths = (3, 4) if parameter_curve is not None else (3,)
        if not isinstance(result, (list, tuple)) or len(result) not in accepted_lengths:
            _dispose_native_result(result)
            _fail('OWNER_SCREEN_NATIVE_FAILURE', 'Unexpected Rhino intersection binding result.')
        ok, curves, points = result[:3]
        try:
            if ok is not True or curves is None or points is None:
                _fail('OWNER_SCREEN_NATIVE_FAILURE', 'The native intersector failed or returned partial/unknown output.')
            if len(curves) + len(points) > budget.limits.max_events:
                _fail('OWNER_SCREEN_BUDGET', 'Native intersection output exceeded its finite event budget.')
            for point in points:
                self._point(point)
            # Rhino 8 also documents CurveBrep with an additional out double[].
            # Python.NET may choose it for the same three explicit inputs.
            # BrepBrep remains strictly the documented three-item result.
            if len(result) == 4:
                parameters = result[3]
                if (parameters is None or len(parameters) != len(points) or
                        len(parameters) > budget.limits.max_events):
                    _fail('OWNER_SCREEN_NATIVE_FAILURE', 'CurveBrep returned malformed point-parameter output.')
                domain = self.curve_domain(parameter_curve, budget)
                if any(not math.isfinite(float(value)) or not domain[0] <= float(value) <= domain[1]
                       for value in parameters):
                    _fail('OWNER_SCREEN_NATIVE_FAILURE', 'CurveBrep returned invalid native curve parameters.')
            return tuple(curves), tuple(points)
        except Exception:
            _dispose(curves if curves is not None else [])
            raise

    def brep_events(self, patch, owner, tolerance, budget):
        return self._intersection(self.rg.Intersect.Intersection.BrepBrep,
                                  (patch, owner, tolerance, False), budget)

    def curve_events(self, curve, other, tolerance, budget):
        return self._intersection(self.rg.Intersect.Intersection.CurveBrep,
                                  (curve, other, tolerance), budget, parameter_curve=curve)

    def overlaps(self, curve, boundary, tolerance, budget):
        events = budget.call(self.rg.Intersect.Intersection.CurveCurve,
                             curve, boundary, tolerance, tolerance)
        if events is None:
            _fail('OWNER_SCREEN_NATIVE_FAILURE', 'Native curve overlap classification failed.')
        try:
            if events.Count > budget.limits.max_events:
                _fail('OWNER_SCREEN_BUDGET', 'Curve overlap event budget exceeded.')
            result = []
            for event in events:
                if event.IsOverlap:
                    result.append(self._domain(event.OverlapA))
                elif not event.IsPoint:
                    _fail('OWNER_SCREEN_NATIVE_FAILURE', 'Unknown curve intersection event kind.')
            return tuple(result)
        finally:
            events.Dispose()

    def point_on_curve(self, point, curve, tolerance, budget):
        result = budget.call(curve.ClosestPoint, point)
        if not isinstance(result, (list, tuple)) or len(result) != 2 or result[0] is not True:
            _fail('OWNER_SCREEN_NATIVE_FAILURE', 'Native curve closest-point classification failed.')
        parameter = float(result[1]); domain = self._domain(curve.Domain)
        if not math.isfinite(parameter) or not domain[0] <= parameter <= domain[1]:
            _fail('OWNER_SCREEN_NATIVE_FAILURE', 'Curve closest point escaped its finite domain.')
        closest = budget.call(curve.PointAt, parameter)
        return math.dist(self._point(point), self._point(closest)) <= tolerance

    def _closest_brep(self, point, geometry, budget):
        # maximumDistance=0 avoids conflating an out-of-range miss with failure.
        result = budget.call(geometry.ClosestPoint, point, 0.0)
        if not isinstance(result, (tuple, list)) or len(result) != 6 or result[0] is not True:
            _fail('OWNER_SCREEN_NATIVE_FAILURE', 'Native trimmed-Brep closest-point query failed.')
        component_type = str(result[2].ComponentIndexType)
        if component_type not in ('BrepFace', 'BrepEdge'):
            _fail('OWNER_SCREEN_NATIVE_FAILURE', 'Closest-point returned an unsupported Brep component.')
        # t is a face parameter only; it is unspecified for an edge result.
        parameters = result[3:5] if component_type == 'BrepFace' else result[3:4]
        if not all(math.isfinite(float(v)) for v in parameters):
            _fail('OWNER_SCREEN_NATIVE_FAILURE', 'Closest-point returned nonfinite component parameters.')
        return math.dist(self._point(point), self._point(result[1])), result

    def distance_to_brep(self, point, geometry, budget):
        return self._closest_brep(point, geometry, budget)[0]

    @staticmethod
    def _dot(a, b):
        return sum(x * y for x, y in zip(a, b))

    @staticmethod
    def _cross(a, b):
        return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

    def _unit(self, values):
        if not isinstance(values, (tuple, list)) or len(values) != 3 or not all(_finite(v) for v in values):
            _fail('OWNER_SCREEN_SIDE_EVIDENCE', 'A captured/native side vector is invalid.')
        length = math.sqrt(self._dot(values, values))
        if not math.isfinite(length) or length <= 0:
            _fail('OWNER_SCREEN_SIDE_EVIDENCE', 'A captured/native side vector is singular.')
        return tuple(v / length for v in values)

    def _native_trim_uv(self, face, trim, point, budget):
        """Locate this exact trim; approximate surface UV is only a seed."""
        mapped = budget.call(face.ClosestPoint, point)
        if not isinstance(mapped, (tuple, list)) or len(mapped) != 3 or mapped[0] is not True:
            _fail('OWNER_SCREEN_NATIVE_FAILURE', 'Could not locate the native boundary frame.')
        u, v = float(mapped[1]), float(mapped[2])
        if not math.isfinite(u) or not math.isfinite(v):
            _fail('OWNER_SCREEN_NATIVE_FAILURE', 'Native surface mapping returned nonfinite parameters.')
        trim_parameter = budget.call(trim.ClosestPoint, self.rg.Point3d(u, v, 0.))
        if (not isinstance(trim_parameter, (tuple, list)) or len(trim_parameter) != 2 or
                trim_parameter[0] is not True or not math.isfinite(float(trim_parameter[1]))):
            _fail('OWNER_SCREEN_NATIVE_FAILURE', 'The exact captured trim could not locate its boundary point.')
        domain = self._domain(trim.Domain)
        if not domain[0] <= float(trim_parameter[1]) <= domain[1]:
            _fail('OWNER_SCREEN_NATIVE_FAILURE', 'The native trim mapping escaped its finite domain.')
        uv = self._point(budget.call(trim.PointAt, float(trim_parameter[1])))[:2]
        return uv

    def _exterior_at_selected_edge(self, point, closest, owner, span, parameter, tolerance, budget):
        """Classify boundary Voronoi proximity, never an intersection event.

        Requires exact current selected-edge binding and captured trim side.
        No distance band or endpoint ball supplies permission by itself.
        """
        if not isinstance(span.side_evidence, str):
            return None
        try:
            evidence = json.loads(span.side_evidence)
        except (TypeError, ValueError):
            return None
        if (not isinstance(evidence, dict) or evidence.get('schema') != 'native-trim-side-v1' or
                evidence.get('edge_inward_cross_sign') not in (-1, 1) or
                type(evidence.get('face_index')) is not int or type(evidence.get('trim_index')) is not int or
                type(evidence.get('face_orientation_reversed')) is not bool):
            return None
        edge = owner.Edges[span.edge_index]
        face_index, trim_index = evidence['face_index'], evidence['trim_index']
        if (not 0 <= face_index < owner.Faces.Count or not 0 <= trim_index < owner.Trims.Count or
                str(edge.Valence) != 'Naked' or list(edge.TrimIndices()) != [trim_index]):
            return None
        face = owner.Faces[face_index]
        captured_trim = owner.Trims[trim_index]
        if (captured_trim.Edge is None or int(captured_trim.Edge.EdgeIndex) != span.edge_index or
                int(captured_trim.Face.FaceIndex) != face_index or
                bool(face.OrientationIsReversed) != evidence['face_orientation_reversed']):
            return None
        domain = self._domain(edge.Domain)
        if not domain[0] <= parameter <= domain[1]:
            return None
        p, q = self._point(point), self._point(closest)
        resolution = 128. * math.ulp(max(1., *(abs(v) for v in p + q)))
        delta = tuple(a-b for a,b in zip(p,q))
        if math.sqrt(self._dot(delta, delta)) <= resolution:
            return None  # A coincident or unresolved point is never "exterior".
        corner = None
        if parameter in domain:
            end = domain.index(parameter)
            corners = [c for c in evidence.get('corners', [])
                       if isinstance(c, dict) and type(c.get('edge_end')) is int and c['edge_end'] == end]
            if len(corners) != 1:
                return None
            corner = corners[0]
            uv = corner.get('uv')
        else:
            uv = self._native_trim_uv(face, captured_trim, closest, budget)
        if not isinstance(uv, (tuple, list)) or len(uv) != 2 or not all(_finite(v) for v in uv):
            return None
        # Both branches use the exact owning trim: the captured endpoint UV,
        # or native Trim.PointAt. No approximate UV membership test replaces
        # that topology. World reconstruction below still must agree.
        evaluation = budget.call(face.Evaluate, *uv, 1)
        if (not isinstance(evaluation, (tuple, list)) or len(evaluation) != 3 or
                evaluation[0] is not True or evaluation[2] is None or len(evaluation[2]) < 2):
            _fail('OWNER_SCREEN_NATIVE_FAILURE', 'Native selected-boundary derivatives are unavailable.')
        if math.dist(self._point(evaluation[1]), q) > max(tolerance * .05, resolution):
            return None
        normal = self._unit(self._cross(self._point(evaluation[2][0]), self._point(evaluation[2][1])))
        if face.OrientationIsReversed:
            normal = tuple(-v for v in normal)
        if corner is not None:
            wedge = corner.get('exterior_wedge', {})
            if not isinstance(wedge, dict) or not _finite(wedge.get('sweep_radians')):
                return None
            sweep = float(wedge['sweep_radians'])
            if not 0. < sweep < 2. * math.pi:
                return None
            captured_normal = self._unit(wedge.get('oriented_normal'))
            start = self._unit(wedge.get('start_ray'))
            if self._dot(normal, captured_normal) < 1.-1e-8 or abs(self._dot(start, normal)) > 1e-8:
                return None
            projection = tuple(d-self._dot(delta, normal)*v for d,v in zip(delta,normal))
            if math.sqrt(self._dot(projection, projection)) <= resolution:
                return None
            direction = self._unit(projection)
            angle = math.atan2(self._dot(normal, self._cross(start, direction)), self._dot(start, direction)) % (2.*math.pi)
            return 'corner_wedge' if 1e-8 < angle < sweep-1e-8 else None
        tangent = self._unit(self._point(budget.call(edge.TangentAt, parameter)))
        inward = self._unit(self._cross(normal, tangent))
        inward = tuple(float(evidence['edge_inward_cross_sign'])*v for v in inward)
        outward_distance = -self._dot(delta, inward)
        return 'edge_conormal' if outward_distance > resolution and outward_distance / math.sqrt(self._dot(delta, delta)) > 1e-8 else None

    def owner_witness_clearance(self, point, owner, finite_contacts, point_contacts, tolerance, budget):
        """Only generated-interior -> original-owner queries get this rule."""
        distance, result = self._closest_brep(point, owner, budget)
        if distance > tolerance:
            return distance, None
        p, q = self._point(point), self._point(result[1])
        resolution = 128. * math.ulp(max(1., *(abs(v) for v in p + q)))
        if distance <= resolution:
            return distance, None
        component = result[2]
        kind = str(component.ComponentIndexType)
        closest = result[1]
        if kind == 'BrepFace':
            index = int(component.Index)
            if not 0 <= index < owner.Faces.Count:
                _fail('OWNER_SCREEN_NATIVE_FAILURE', 'Closest-point face index is invalid.')
            # Some native paths identify a boundary point by its face. Only
            # roundoff-scale agreement with an exact selected trim on THAT
            # face may resolve it as boundary; proximity at model tolerance
            # cannot turn an interior face point into an allowed edge.
        candidates = {}
        for span, contact in tuple(finite_contacts) + tuple(point_contacts):
            candidates[span.source_key] = span
        for span in candidates.values():
            if kind == 'BrepEdge':
                if int(component.Index) != span.edge_index:
                    continue
                parameter = float(result[3])
            else:
                if not isinstance(span.side_evidence, str) or json.loads(span.side_evidence).get('face_index') != int(component.Index):
                    continue
                edge = owner.Edges[span.edge_index]
                mapped = budget.call(edge.ClosestPoint, closest)
                if not isinstance(mapped, (tuple, list)) or len(mapped) != 2 or mapped[0] is not True:
                    _fail('OWNER_SCREEN_NATIVE_FAILURE', 'Could not resolve the returned native face-boundary point.')
                parameter = float(mapped[1])
                edgepoint = budget.call(edge.PointAt, parameter)
                q = self._point(closest)
                resolution = 128. * math.ulp(max(1., *(abs(v) for v in q)))
                if math.dist(self._point(edgepoint), q) > resolution:
                    continue
            if not math.isfinite(parameter) or not span.interval[0] <= parameter <= span.interval[1]:
                continue
            finite_bound = any(s.source_key == span.source_key and
                               _source_interval(c['native_parameter_interval'])[0] <= parameter <= _source_interval(c['native_parameter_interval'])[1]
                               for s,c in finite_contacts)
            point_bound = any(s.source_key == span.source_key and c['native_parameter'] == parameter
                              for s,c in point_contacts)
            if not finite_bound and not point_bound:
                continue
            exterior = self._exterior_at_selected_edge(point, closest, owner, span, parameter, tolerance, budget)
            if exterior is not None:
                return distance, exterior
        for span, contact in point_contacts:
            if self._exterior_adjacent_corner(point, owner, span, contact, result, tolerance, budget):
                return distance, 'adjacent_corner_wedge'
        return distance, None

    def _exterior_adjacent_corner(self, point, owner, span, contact, closest_result, tolerance, budget):
        """Exact incident source-corner binding plus CURRENT adjacent-edge side.

        The vertex wedge alone is insufficient on a curved adjacent edge.
        Its local frame is re-evaluated at the actual native closest point.
        """
        if not isinstance(span.side_evidence, str):
            return False
        evidence = json.loads(span.side_evidence)
        if not isinstance(evidence, dict):
            return False
        selected = owner.Edges[span.edge_index]
        domain = self._domain(selected.Domain)
        parameter = contact['native_parameter']
        if parameter not in domain:
            return False
        corners = [c for c in evidence.get('corners', []) if isinstance(c, dict) and
                   type(c.get('edge_end')) is int and c['edge_end'] == domain.index(parameter)]
        if len(corners) != 1:
            return False
        corner = corners[0]; trim_index = corner.get('adjacent_trim_index')
        if type(trim_index) is not int or not 0 <= trim_index < owner.Trims.Count:
            return False
        trim = owner.Trims[trim_index]; edge = trim.Edge
        if edge is None or trim.Face is None or int(trim.Face.FaceIndex) != evidence.get('face_index'):
            return False
        face = trim.Face
        q = closest_result[1]; component = closest_result[2]
        if str(component.ComponentIndexType) == 'BrepEdge':
            if int(component.Index) != int(edge.EdgeIndex):
                return False
            t = float(closest_result[3])
        else:
            if int(component.Index) != int(face.FaceIndex):
                return False
            mapped = budget.call(edge.ClosestPoint, q)
            if not isinstance(mapped, (tuple, list)) or len(mapped) != 2 or mapped[0] is not True:
                _fail('OWNER_SCREEN_NATIVE_FAILURE', 'Adjacent trim closest-point query failed.')
            t = float(mapped[1])
            native_q = budget.call(edge.PointAt, t)
            resolution = 128.*math.ulp(max(1., *(abs(v) for v in self._point(q))))
            if math.dist(self._point(native_q), self._point(q)) > resolution:
                return False
        adjacent_domain = self._domain(edge.Domain)
        if not adjacent_domain[0] < t < adjacent_domain[1]:
            return False  # Another endpoint needs its own captured sector.
        vertex = budget.call(selected.PointAt, parameter)
        if self._exterior_at_selected_edge(point, vertex, owner, span, parameter, tolerance, budget) != 'corner_wedge':
            return False
        u, v = self._native_trim_uv(face, trim, q, budget)
        values = budget.call(face.Evaluate, u, v, 1)
        if (not isinstance(values, (tuple, list)) or len(values) != 3 or values[0] is not True or
                values[2] is None or len(values[2]) < 2):
            _fail('OWNER_SCREEN_NATIVE_FAILURE', 'Adjacent trim native derivatives are unavailable.')
        p, nearest, origin = self._point(point), self._point(q), self._point(vertex)
        resolution = 128.*math.ulp(max(1., *(abs(x) for x in p + nearest + origin)))
        if math.dist(self._point(values[1]), nearest) > max(tolerance*.05, resolution):
            return False
        endpoints = [a for a in adjacent_domain if math.dist(self._point(budget.call(edge.PointAt, a)), origin) <= max(tolerance*.05, resolution)]
        if len(endpoints) != 1:
            return False
        captured_normal = self._unit(corner['exterior_wedge'].get('oriented_normal'))
        captured_inward = self._unit(corner.get('adjacent_inward_conormal'))
        tangent_at_vertex = self._unit(self._point(budget.call(edge.TangentAt, endpoints[0])))
        alignment = self._dot(captured_inward, self._unit(self._cross(captured_normal, tangent_at_vertex)))
        if abs(alignment) < 1.-1e-8:
            return False
        normal = self._unit(self._cross(self._point(values[2][0]), self._point(values[2][1])))
        if face.OrientationIsReversed:
            normal = tuple(-x for x in normal)
        tangent = self._unit(self._point(budget.call(edge.TangentAt, t)))
        inward = self._unit(self._cross(normal, tangent))
        inward = tuple((1. if alignment > 0 else -1.)*x for x in inward)
        delta = tuple(a-b for a,b in zip(p,nearest))
        outward = -self._dot(delta, inward)
        return outward > resolution and outward/math.sqrt(self._dot(delta,delta)) > 1e-8


def _normal_contacts(ledger, owners, patches_count):
    expected_ledger = {'schema', 'checked', 'source_digest', 'geometry_digest', 'contacts', 'point_contacts',
                       'interval_units', 'internal_seams_are_allowed_contacts'}
    if (not isinstance(ledger, dict) or set(ledger) != expected_ledger or
            ledger.get('schema') != 'smartskin.native-contact-ledger.v1' or ledger.get('checked') is not True or
            ledger.get('internal_seams_are_allowed_contacts') is not False or
            ledger.get('interval_units') != 'actual generated varying-axis and original selected source-curve parameters' or
            any(not isinstance(ledger.get(key), str) or not ledger[key]
                for key in ('source_digest', 'geometry_digest'))):
        _fail('OWNER_SCREEN_BINDING', 'The trusted G0-validated native-exterior ledger is required.')
    contacts = ledger['contacts']
    if not isinstance(contacts, (tuple, list)) or len(contacts) > 512:
        _fail('OWNER_SCREEN_BINDING', 'A finite trusted native-exterior contact ledger is required.')
    by_source = {}
    for owner in owners:
        for span in owner.selected_spans:
            if span.source_key in by_source:
                _fail('OWNER_SCREEN_BINDING', 'Source-edge identity is duplicated.')
            if (not isinstance(span.source_key, str) or not span.source_key or
                    type(span.edge_index) is not int or span.edge_index < 0):
                _fail('OWNER_SCREEN_BINDING', 'Captured source identity is malformed.')
            _interval(span.interval)
            by_source[span.source_key] = (owner, span)
    expected = {'surface_index', 'edge', 'source_key', 'native_parameter_interval', 'generated_parameter_interval'}
    normalized = []
    for contact in contacts:
        if not isinstance(contact, dict) or set(contact) != expected:
            _fail('OWNER_SCREEN_BINDING', 'Only exact trusted native-exterior bindings are accepted.')
        index = contact['surface_index']
        if type(index) is not int or not 0 <= index < patches_count or contact['edge'] not in ('left', 'right', 'bottom', 'top'):
            _fail('OWNER_SCREEN_BINDING', 'The generated exterior-edge identity is invalid.')
        if contact['source_key'] not in by_source:
            _fail('OWNER_SCREEN_BINDING', 'The contact does not name a captured selected native source span.')
        owner, span = by_source[contact['source_key']]
        interval = _source_interval(contact['native_parameter_interval'])
        if interval[0] < span.interval[0] or interval[1] > span.interval[1]:
            _fail('OWNER_SCREEN_BINDING', 'The allowed contact escaped its selected source interval.')
        generated = _interval(contact['generated_parameter_interval'])
        normalized.append(dict(surface_index=index, edge=contact['edge'], source_key=span.source_key,
                               native_parameter_interval=list(map(float, contact['native_parameter_interval'])),
                               generated_parameter_interval=list(generated)))
    points = ledger['point_contacts']
    if not isinstance(points, (tuple, list)) or len(points) > 512:
        _fail('OWNER_SCREEN_BINDING', 'The isolated native-contact list is malformed or unbounded.')
    normalized_points = []
    for point in points:
        if not isinstance(point, dict) or set(point) != {'surface_index', 'generated_uv', 'source_key', 'native_parameter'}:
            _fail('OWNER_SCREEN_BINDING', 'An isolated contact requires exact source and generated parameters.')
        index, parameter = point['surface_index'], point['native_parameter']
        uv = point['generated_uv']
        if (type(index) is not int or not 0 <= index < patches_count or not _finite(parameter) or
                not isinstance(uv, (tuple, list)) or len(uv) != 2 or not all(_finite(v) for v in uv) or
                point['source_key'] not in by_source):
            _fail('OWNER_SCREEN_BINDING', 'The isolated native contact is malformed.')
        owner, span = by_source[point['source_key']]
        endpoints = {v for c in normalized if c['source_key'] == span.source_key
                     for v in c['native_parameter_interval']}
        if not span.interval[0] <= parameter <= span.interval[1] or parameter not in endpoints:
            _fail('OWNER_SCREEN_BINDING', 'An isolated contact must bind an independently checked exterior-trace endpoint.')
        normalized_points.append(dict(surface_index=index, generated_uv=list(map(float, uv)),
                                      source_key=span.source_key, native_parameter=float(parameter)))
    return dict(schema=ledger['schema'], checked=True, interval_units=ledger['interval_units'],
                internal_seams_are_allowed_contacts=False, source_digest=ledger['source_digest'],
                geometry_digest=ledger['geometry_digest'], contacts=normalized,
                point_contacts=normalized_points), by_source


class NativeOwnerContext:
    """Owns independent source copies and reusable native complement witnesses.

    The optional live_check must raise on source/document/tolerance changes.
    Supplied owner geometries transfer disposable ownership to this context.
    """
    def __init__(self, owners, source_token, tolerance, adapter, live_check=None, limits=None):
        self.limits = limits or ScreenLimits()
        self.owners = _bounded_items(owners, self.limits.max_owners, 'Copied-owner')
        self.source_token = _json(source_token)
        self.tolerance = float(tolerance)
        self.adapter = adapter
        self.live_check = live_check
        if not math.isfinite(self.tolerance) or self.tolerance <= 0:
            _fail('OWNER_SCREEN_BINDING', 'Captured tolerance must be positive and finite.')
        if not 1 <= len(self.owners) <= self.limits.max_owners:
            _fail('OWNER_SCREEN_BUDGET', 'Copied-owner count exceeds the bounded screen family.')
        if any(not isinstance(o.key, str) or not o.key for o in self.owners) or len({o.key for o in self.owners}) != len(self.owners):
            _fail('OWNER_SCREEN_BINDING', 'Every copied owner requires one unique stable identity.')
        self._disposed = False
        self._prepared = None
        budget = _Budget(self.limits)
        self._original_fingerprints = tuple(self.adapter.fingerprint(o.geometry, budget) for o in self.owners)

    def check_live(self):
        if self._disposed:
            _fail('OWNER_SCREEN_STALE', 'The copied-source context was disposed.')
        if self.live_check is not None:
            self.live_check()

    def dispose(self):
        if self._disposed:
            return
        self._disposed = True
        if self._prepared:
            for value in self._prepared:
                value.dispose()
        _dispose([o.geometry for o in self.owners])
        self._prepared = None

    def prepare(self, budget):
        self.check_live()
        fingerprints = tuple(self.adapter.fingerprint(o.geometry, budget) for o in self.owners)
        if self._original_fingerprints is not None and fingerprints != self._original_fingerprints:
            _fail('OWNER_SCREEN_STALE', 'A supposedly immutable copied owner changed.')
        if self._prepared is None:
            prepared = []
            try:
                for owner in self.owners:
                    prepared.append(self.adapter.prepare(owner.geometry, self.tolerance, budget))
                    _check_totals(prepared, self.limits)
            except Exception:
                for value in prepared:
                    value.dispose()
                raise
            self._prepared = tuple(prepared)
            self._original_fingerprints = fingerprints
        return self._prepared


def create_owner_context(doc, capture, rhino, cancelled=None, limits=None):
    """Copy only verified owners in Capture.source_proof; never modify sources."""
    limits = limits or ScreenLimits(); budget = _Budget(limits, cancelled)
    tolerance = float(capture.model['absolute_tolerance'])
    doc_serial = int(doc.RuntimeSerialNumber)
    if 'angle_tolerance' in capture.model:
        angle_tolerance = float(capture.model['angle_tolerance'])
    elif 'angle_tolerance_degrees' in capture.model:
        angle_tolerance = math.radians(float(capture.model['angle_tolerance_degrees']))
    else:
        _fail('OWNER_SCREEN_BINDING', 'Captured angular tolerance is required before native screening.')
    if not math.isfinite(angle_tolerance) or angle_tolerance <= 0:
        _fail('OWNER_SCREEN_BINDING', 'Captured angular tolerance must be positive and finite.')
    proof = tuple((oid, int(serial), tuple(digests)) for oid, serial, digests in capture.source_proof)
    model_digest = _hash(_json(capture.model))
    def live_check():
        if (int(doc.RuntimeSerialNumber) != doc_serial or float(doc.ModelAbsoluteTolerance) != tolerance or
                float(doc.ModelAngleToleranceRadians) != angle_tolerance):
            _fail('OWNER_SCREEN_STALE', 'The source document or captured tolerances changed.')
        if (tuple((oid, int(serial), tuple(digests)) for oid, serial, digests in capture.source_proof) != proof or
                _hash(_json(capture.model)) != model_digest):
            _fail('OWNER_SCREEN_STALE', 'Captured source identities or provenance changed.')
        ok, reason = capture.verify_sources(doc)
        if not ok:
            _fail('OWNER_SCREEN_STALE', reason)
    live_check()
    if not 1 <= len(proof) <= limits.max_owners:
        _fail('OWNER_SCREEN_BUDGET', 'Selected owner count exceeds the screen budget.')
    source_map = {}
    for records in capture.model['source_boundaries']['roles'].values():
        for record in records:
            key = record['source_key']
            if key in source_map:
                _fail('OWNER_SCREEN_BINDING', 'Captured source-edge identity occurs more than once.')
            source_map[key] = (_interval(record['original_curve_domain']),
                               _json(record['owner_side']) if isinstance(record.get('owner_side'), dict) else None)
    owners = []; bytes_total = 0
    try:
        for object_id, serial, digests in proof:
            budget.check()
            obj = doc.Objects.FindId(object_id)
            if obj is None or obj.IsDeleted or int(obj.RuntimeSerialNumber) != serial:
                _fail('OWNER_SCREEN_STALE', 'A selected source owner is unavailable.')
            if not callable(getattr(obj.Geometry, 'DuplicateBrep', None)):
                _fail('OWNER_SCREEN_UNSUPPORTED_OWNER', 'This native screen requires original Brep owners; owner conversion is not implicit.')
            bytes_total += int(budget.call(obj.Geometry.MemoryEstimate))
            if bytes_total > limits.max_snapshot_bytes:
                _fail('OWNER_SCREEN_BUDGET', 'Copied-owner memory budget exceeded.')
            copied = budget.call(obj.Geometry.DuplicateBrep)
            if copied is None:
                _fail('OWNER_SCREEN_NATIVE_FAILURE', 'A selected full owner could not be copied.')
            spans = []
            try:
                prefix = str(object_id) + ':'
                for key, (interval, side_evidence) in source_map.items():
                    if key.startswith(prefix):
                        suffix = key[len(prefix):]
                        if not suffix.isdigit():
                            _fail('OWNER_SCREEN_BINDING', 'Captured native edge index is malformed.')
                        index = int(suffix)
                        if not 0 <= index < copied.Edges.Count:
                            _fail('OWNER_SCREEN_BINDING', 'Captured native edge index is unavailable.')
                        spans.append(SelectedSpan(key, index, interval, side_evidence))
                if not spans:
                    _fail('OWNER_SCREEN_BINDING', 'A captured owner has no selected source span.')
                owners.append(OwnerSnapshot(str(object_id), copied, tuple(spans)))
            except Exception:
                copied.Dispose()
                raise
        if sum(len(o.selected_spans) for o in owners) != len(source_map):
            _fail('OWNER_SCREEN_BINDING', 'Not every captured source span belongs to an exact copied owner.')
        live_check()
        token = {'document_serial': doc_serial,
                 'proof': [[str(oid), serial, list(digests)] for oid, serial, digests in proof],
                 'angle_tolerance': angle_tolerance}
        return NativeOwnerContext(owners, token, tolerance, RhinoAdapter(rhino), live_check, limits)
    except Exception:
        _dispose([o.geometry for o in owners])
        raise


def _check_totals(prepared, limits):
    for field, maximum in (('faces', limits.max_faces), ('edges', limits.max_edges),
                           ('control_points', limits.max_control_points)):
        if sum(getattr(p, field) for p in prepared) > maximum:
            _fail('OWNER_SCREEN_BUDGET', 'Aggregate native ' + field + ' exceeds the finite budget.')
    if sum(len(p.witnesses) for p in prepared) > limits.max_witnesses:
        _fail('OWNER_SCREEN_BUDGET', 'Aggregate native witness budget exceeded.')


def _separated(a, b, tolerance):
    for box in (a, b):
        if (len(box) != 2 or any(len(p) != 3 for p in box) or
                not all(_finite(v) for p in box for v in p) or
                any(box[0][axis] > box[1][axis] for axis in range(3))):
            _fail('OWNER_SCREEN_NATIVE_FAILURE', 'Malformed conservative bounding box.')
    return any(a[1][i] + tolerance < b[0][i] or b[1][i] + tolerance < a[0][i] for i in range(3))


def _intersection_intervals(left, right):
    return [(max(a, c), min(b, d)) for a, b in left for c, d in right if max(a, c) < min(b, d)]


def _covers(domain, intervals):
    # No parameter epsilon closes a positive-length gap or extends an endpoint.
    position = domain[0]
    for a, b in sorted(intervals):
        if a < domain[0] or b > domain[1] or not a < b:
            _fail('OWNER_SCREEN_NATIVE_FAILURE', 'An overlap interval escaped its curve domain.')
        if a > position:
            return False
        position = max(position, b)
    return position >= domain[1]


def _classify_events(curves, points, allowed, allowed_points, adapter, tolerance, budget, report):
    try:
        if len(curves) + len(points) > budget.limits.max_events:
            _fail('OWNER_SCREEN_BUDGET', 'Native intersection event budget exceeded.')
        report['curve_events'] += len(curves); report['point_events'] += len(points)
        if report['curve_events'] + report['point_events'] > budget.limits.max_events:
            _fail('OWNER_SCREEN_BUDGET', 'Aggregate native intersection event budget exceeded.')
        for curve in curves:
            domain = adapter.curve_domain(curve, budget)
            intervals = []
            for source, generated in allowed:
                left = adapter.overlaps(curve, source, tolerance, budget)
                right = adapter.overlaps(curve, generated, tolerance, budget)
                intervals.extend(_intersection_intervals(left, right))
            if not _covers(domain, intervals):
                _fail('OWNER_FORBIDDEN_INTERSECTION', 'A complete native intersection/overlap curve is not on intended exterior source contacts.')
        for point in points:
            on_curve = any(adapter.point_on_curve(point, source, tolerance, budget) and
                           adapter.point_on_curve(point, generated, tolerance, budget)
                           for source, generated in allowed)
            on_endpoint = any(adapter.same_point(point, source, tolerance) and
                              adapter.same_point(point, generated, tolerance)
                              for source, generated in allowed_points)
            if not on_curve and not on_endpoint:
                _fail('OWNER_FORBIDDEN_INTERSECTION', 'A native point contact is outside intended exterior source contacts.')
    finally:
        _dispose(curves)


def _binding(patches, context, contacts, request, budget):
    context.check_live()
    owners = [[o.key, context.adapter.fingerprint(o.geometry, budget),
                                   [[s.source_key, s.edge_index, list(s.interval), s.side_evidence] for s in o.selected_spans]]
                                  for o in context.owners]
    if tuple(o[1] for o in owners) != context._original_fingerprints:
        _fail('OWNER_SCREEN_STALE', 'A supposedly immutable copied owner changed.')
    patch_hashes = [context.adapter.fingerprint(p, budget) for p in patches]
    context.check_live()
    return _hash(_json({'source': context.source_token, 'tolerance': context.tolerance,
                       'limits': context.limits.__dict__, 'contacts': contacts, 'request': request,
                       'owners': owners, 'patches': patch_hashes}))


_ISSUER = object()


@dataclass(frozen=True)
class SeparationReceipt:
    _issuer: object
    _digest: str
    _context: object
    _report_json: str

    @property
    def report(self):
        return json.loads(self._report_json)


def verify_receipt(receipt, patches, context, contacts, request=None, cancelled=None):
    """Fast identity/source recheck before EVERY native Add; never trusts flags."""
    if type(receipt) is not SeparationReceipt or receipt._issuer is not _ISSUER or receipt._context is not context:
        _fail('OWNER_SCREEN_STALE', 'A current in-process native-owner screening receipt is required.')
    patches = _bounded_items(patches, context.limits.max_patches, 'Generated-patch')
    normalized, _ = _normal_contacts(contacts, context.owners, len(patches))
    budget = _Budget(context.limits, cancelled)
    if _binding(patches, context, normalized, request, budget) != receipt._digest:
        _fail('OWNER_SCREEN_STALE', 'Geometry, sources, request, contacts, or captured tolerances changed after screening.')
    return True


def screen_native_owners(patches, context, contacts, request=None, cancelled=None):
    """After native conversion, before preview READY or commit-ready state.

    contacts must come from the trusted source-G0-validated atlas exterior
    ledger. Never pass an arbitrary result-side boundary-role declaration.
    Returns an in-process receipt; failure/cancellation never yields one.
    """
    limits = context.limits
    patches = _bounded_items(patches, limits.max_patches, 'Generated-patch')
    if not 1 <= len(patches) <= limits.max_patches or len(patches) * len(context.owners) > limits.max_pairs:
        _fail('OWNER_SCREEN_BUDGET', 'Candidate-owner pair count exceeds the bounded screen family.')
    normalized, by_source = _normal_contacts(contacts, context.owners, len(patches))
    budget = _Budget(limits, cancelled)
    owners_prepared = context.prepare(budget)
    initial = _binding(patches, context, normalized, request, budget)
    prepared = []; contact_geometry = []; grouped = {}; grouped_points = {}
    report = dict(schema='smartskin.native-owner-screen.v1', checked=False,
                  global_injectivity_certified=False, expected_pairs=len(patches) * len(context.owners),
                  completed_pairs=0, bbox_pruned_pairs=0, intersection_pairs=0,
                  curve_events=0, point_events=0, boundary_screens=0,
                  interior_queries=0, interior_witnesses=0, minimum_sampled_clearance=None,
                  exterior_edge_near_witnesses=0, exterior_corner_near_witnesses=0,
                  exterior_adjacent_corner_near_witnesses=0,
                  complement='bidirectional_actual_trim_interior_and_all_native_edges',
                  trim_membership_tolerance=0.0,
                  near_boundary_policy='positive resolved distance; exact current contact; captured native exterior side; adjacent corner also requires exact adjacency and current local frame',
                  coverage_limit='Finite 5x5 face-UV interior grid; sparse faces retry 9x9. Small unsampled coincidences can remain.',
                  native_execution='RhinoCommon adapter; host execution must be separately verified')
    try:
        for patch in patches:
            prepared.append(context.adapter.prepare(patch, context.tolerance, budget))
            _check_totals(tuple(prepared) + owners_prepared, limits)
        report['interior_witnesses'] = sum(len(p.witnesses) for p in tuple(prepared) + owners_prepared)
        for contact in normalized['contacts']:
            owner, selected = by_source[contact['source_key']]
            pair = context.adapter.contact_curves(patches[contact['surface_index']], owner.geometry,
                                                  selected, contact, budget)
            contact_geometry.extend(pair)
            grouped.setdefault((contact['surface_index'], owner.key), []).append(pair)
        for contact in normalized['point_contacts']:
            owner, selected = by_source[contact['source_key']]
            pair = context.adapter.contact_points(patches[contact['surface_index']], owner.geometry,
                                                  selected, contact, context.tolerance, budget)
            grouped_points.setdefault((contact['surface_index'], owner.key), []).append(pair)
        for index, patch in enumerate(patches):
            for owner, other in zip(context.owners, owners_prepared):
                budget.check()
                if _separated(prepared[index].bbox, other.bbox, context.tolerance):
                    report['bbox_pruned_pairs'] += 1
                    report['completed_pairs'] += 1
                    continue
                allowed = grouped.get((index, owner.key), ())
                allowed_points = grouped_points.get((index, owner.key), ())
                finite_bindings = [(by_source[c['source_key']][1], c) for c in normalized['contacts']
                                   if c['surface_index'] == index and by_source[c['source_key']][0].key == owner.key]
                point_bindings = [(by_source[c['source_key']][1], c) for c in normalized['point_contacts']
                                  if c['surface_index'] == index and by_source[c['source_key']][0].key == owner.key]
                curves, points = context.adapter.brep_events(patch, owner.geometry, context.tolerance, budget)
                _classify_events(curves, points, allowed, allowed_points, context.adapter, context.tolerance, budget, report)
                report['intersection_pairs'] += 1
                # Explicit overlap complement, even when BrepBrep returned no events.
                for boundaries, target in ((prepared[index].curves, owner.geometry), (other.curves, patch)):
                    for curve in boundaries:
                        curves, points = context.adapter.curve_events(curve, target, context.tolerance, budget)
                        _classify_events(curves, points, allowed, allowed_points, context.adapter, context.tolerance, budget, report)
                        report['boundary_screens'] += 1
                for generated_side, witnesses, target in ((True, prepared[index].witnesses, owner.geometry),
                                                          (False, other.witnesses, patch)):
                    for point in witnesses:
                        exterior = None
                        classifier = getattr(context.adapter, 'owner_witness_clearance', None)
                        if generated_side and callable(classifier):
                            distance, exterior = classifier(point, target, finite_bindings, point_bindings,
                                                            context.tolerance, budget)
                        else:
                            distance = context.adapter.distance_to_brep(point, target, budget)
                        if not _finite(distance) or distance < 0:
                            _fail('OWNER_SCREEN_NATIVE_FAILURE', 'Invalid native interior clearance.')
                        report['interior_queries'] += 1
                        previous = report['minimum_sampled_clearance']
                        report['minimum_sampled_clearance'] = distance if previous is None else min(previous, distance)
                        if exterior not in (None, 'edge_conormal', 'corner_wedge', 'adjacent_corner_wedge'):
                            _fail('OWNER_SCREEN_NATIVE_FAILURE', 'Unsupported native exterior-side classification.')
                        if exterior == 'edge_conormal': report['exterior_edge_near_witnesses'] += 1
                        if exterior == 'corner_wedge': report['exterior_corner_near_witnesses'] += 1
                        if exterior == 'adjacent_corner_wedge': report['exterior_adjacent_corner_near_witnesses'] += 1
                        if distance <= context.tolerance and exterior is None:
                            _fail('OWNER_INTERIOR_OVERLAP', 'A native actual-trim interior witness touches another surface; no boundary exemption applies.')
                report['completed_pairs'] += 1
        if report['completed_pairs'] != report['expected_pairs']:
            _fail('OWNER_SCREEN_PARTIAL', 'Not every generated-patch/captured-owner pair was screened.')
        if _binding(patches, context, normalized, request, budget) != initial:
            _fail('OWNER_SCREEN_STALE', 'The exact geometry/source/request binding changed while screening.')
        report.update(checked=True, native_calls=budget.calls, seconds=budget.clock() - budget.started,
                      tolerance=context.tolerance, work_limits=limits.__dict__)
        return SeparationReceipt(_ISSUER, initial, context, _json(report))
    finally:
        _dispose(contact_geometry)
        for value in prepared:
            value.dispose()
