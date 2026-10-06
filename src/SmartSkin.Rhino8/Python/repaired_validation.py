"""Read-only, fail-closed validation of the repaired native cap atlas.

The numeric entry point accepts explicit original boundary records. It never
manufactures Rhino capture provenance. Finite sampling covers every declared
span and both limits of repeated knots; it is not a global collision or an
all-real-parameters G2 certificate. The only omitted parameter set is the exact
collapsed upper source vertex, separately bound and certified below.
"""
import copy
import hashlib
import importlib
import json
import math
import time
from collections import defaultdict

import numpy as np
from scipy.optimize import minimize_scalar, least_squares
from scipy.interpolate import BSpline


def _module(name):
    try:
        return importlib.import_module('_smartskin_p08e1_' + name)
    except ModuleNotFoundError as error:
        if error.name != '_smartskin_p08e1_' + name:
            raise
        return importlib.import_module(name)


_KINDS = {'collar', 'middle', 'lower_bridge', 'lower_chart', 'upper_hard_corner'}
_ROLES = {'native_source_side', 'native_upper', 'native_lower',
          'retained_body_2jet', 'new_shared_2jet', 'approved_source_vertex'}
_EDGES = ('left', 'right', 'bottom', 'top')


def _digest(value):
    def default(x):
        if isinstance(x, np.ndarray): return x.tolist()
        if isinstance(x, np.generic): return x.item()
        raise TypeError(type(x).__name__)
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False, default=default).encode()).hexdigest()


def _domain(record):
    d = np.asarray(record['domain'], float)
    if d.shape != (2, 2) or not np.isfinite(d).all() or np.any(d[:, 1] <= d[:, 0]):
        raise ValueError('Invalid surface domain.')
    return d


def _edge_uv(record, edge, parameter):
    d = _domain(record)
    t = float(parameter)
    if edge == 'left': return d[0, 0], d[1, 0] + t * (d[1, 1] - d[1, 0])
    if edge == 'right': return d[0, 1], d[1, 0] + t * (d[1, 1] - d[1, 0])
    if edge == 'bottom': return d[0, 0] + t * (d[0, 1] - d[0, 0]), d[1, 0]
    if edge == 'top': return d[0, 0] + t * (d[0, 1] - d[0, 0]), d[1, 1]
    raise ValueError('Unknown chart edge: ' + str(edge))


def _edge_axis(edge):
    if edge not in _EDGES: raise ValueError('Unknown chart edge.')
    return 1 if edge in ('left', 'right') else 0


def _edge_inward(jets, edge):
    if edge == 'left': return jets[1]
    if edge == 'right': return -jets[1]
    if edge == 'bottom': return jets[2]
    if edge == 'top': return -jets[2]
    raise ValueError('Unknown chart edge.')


def _edge_fraction(record, edge, value):
    lo, hi = _domain(record)[_edge_axis(edge)]
    return (float(value) - lo) / (hi - lo)


def _stations(record, axis, count=5, logarithmic=False):
    lo, hi = _domain(record)[axis]
    knots = record['knots_u' if axis == 0 else 'knots_v']
    breaks = sorted(set([float(lo), float(hi)] + [float(x) for x in knots if lo < x < hi]))
    out = set()
    for a, b in zip(breaks[:-1], breaks[1:]):
        out.update(float(x) for x in np.linspace(a, b, count))
    for k in breaks[1:-1]:
        out.update((float(np.nextafter(k, -np.inf)), float(np.nextafter(k, np.inf))))
    if logarithmic:
        out.update(float(lo + (hi - lo) * q) for q in np.logspace(-12, -1, 12))
    return sorted(out)


def _covered(intervals, tolerance=2e-9):
    end = 0.
    for a, b in sorted((min(a, b), max(a, b)) for a, b in intervals):
        if a > end + tolerance: return False
        end = max(end, b)
    return end >= 1. - tolerance


class _Validator:
    def __init__(self, model, result, source_roles, approved_corners, cancelled):
        self.sk, self.nf = _module('skin_kernel'), _module('native_family')
        self.model, self.result = model, result
        self.roles, self.approved = source_roles, approved_corners or {}
        self.cancelled = cancelled
        self.deadline = time.monotonic() + 30.
        self.tol = float(model.tolerance)
        self.angle = float(model.spec.get('angle_tolerance', math.radians(
            model.spec.get('angle_tolerance_degrees', .1))))
        if 'angle_tolerance_degrees' in model.spec:
            self.angle = math.radians(float(model.spec['angle_tolerance_degrees']))
        self.curv = float(model.spec.get('curvature_tolerance', max(1e-5 / model.scale, 1e-8)))
        if not all(math.isfinite(x) and x > 0 for x in (self.tol, self.angle, self.curv)):
            raise ValueError('Positive finite physical tolerances are required.')
        if self.angle >= math.pi / 2: raise ValueError('Normal-angle tolerance is unbounded.')
        self.surfaces = result.get('surfaces', [])
        if not 1 <= len(self.surfaces) <= 64: raise ValueError('Repaired atlas surface-count budget exceeded.')
        self.evaluators, self.precise = {}, {}
        self.failures, self.pending, self.pairs, self.native_edges = [], [], [], []
        self.coverage, self.seams = defaultdict(list), defaultdict(list)
        self.pair_keys, self.source_coverage = set(), defaultdict(list)
        self.samples = self.precise_samples = 0
        self.minimum_sine, self.minimum_jacobian = 1., math.inf
        self.maximum_curvature, self.minimum_outward = 0., math.inf
        self.ordinary_curvature = self.upper_grid_curvature = self.upper_log_curvature = 0.
        self.metrics = {name: dict(position=0., angle=0., curvature=0., count=0)
                        for name in ('side', 'upper', 'lower', 'shared')}
        self.orientation_edges = []
        self.certificates = []
        self.contacts = []
        self.contact_vertices = []
        self.curves, self.native_surfaces, self.parent_cache = {}, {}, {}
        if set(source_roles) != {'side0', 'side1', 'upper', 'lower'}:
            raise ValueError('Exactly four explicit original source role chains are required.')
        self.keys = {}
        for role, records in source_roles.items():
            if not records or (role.startswith('side') and len(records) != 1):
                raise ValueError('Incomplete native role chain: ' + role)
            for record in records:
                key = record.get('source_key', record.get('key'))
                if not isinstance(key, str) or not key or key in self.keys:
                    raise ValueError('Source records need unique immutable keys.')
                self.keys[key] = record
                self.curves[key] = self.nf.Curve(record['curve'])
                self.native_surfaces[key] = self.nf.Surface(record['surface'])
        for index, record in enumerate(self.surfaces):
            self.check()
            if record.get('kind') not in _KINDS:
                raise ValueError('Unknown repaired surface kind: ' + str(record.get('kind')))
            d = _domain(record)
            cp = np.asarray(record['homogeneous_cp'], float)
            pu, pv = int(record['degree_u']), int(record['degree_v'])
            if cp.ndim != 3 or cp.shape[2] != 4 or cp.shape[0] * cp.shape[1] > 16384:
                raise ValueError('Repaired control-net budget exceeded.')
            if not 1 <= min(pu, pv) or max(pu, pv) > 40 or not np.isfinite(cp).all() or np.min(cp[:, :, 3]) <= 0:
                raise ValueError('Invalid repaired homogeneous coefficients.')
            for axis, degree, count in ((0, pu, cp.shape[0]), (1, pv, cp.shape[1])):
                knots = np.asarray(record['knots_u' if axis == 0 else 'knots_v'], float)
                if len(knots) != count + degree + 1 or not np.isfinite(knots).all() or np.any(np.diff(knots) < 0):
                    raise ValueError('Invalid repaired knot vector.')
                if not np.array_equal(d[axis], [knots[degree], knots[-degree - 1]]):
                    raise ValueError('Repaired domain does not equal its active knot domain.')
            if record['kind'] in ('lower_chart', 'upper_hard_corner') and not np.array_equal(d, [[0., 1.], [0., 1.]]):
                raise ValueError('Corner chart must retain the normalized unit square.')
            if record['kind'] in ('lower_chart', 'lower_bridge', 'upper_hard_corner'):
                if set(record.get('boundary_roles', {})) != set(_EDGES):
                    raise ValueError('Every repaired corner/bridge edge must have an explicit role.')
                if not isinstance(record.get('native_parameter_map'), dict) and record['kind'] != 'lower_bridge':
                    raise ValueError('Missing repaired chart native parameter map.')
            self.evaluators[index] = self.sk._Evaluator(record)
        if sum(np.asarray(s['homogeneous_cp']).shape[0] * np.asarray(s['homogeneous_cp']).shape[1] for s in self.surfaces) > 262144:
            raise ValueError('Aggregate repaired control-net budget exceeded.')

    def check(self):
        self.sk._check(self.cancelled)
        if time.monotonic() > self.deadline:
            raise ValueError('Repaired validation exceeded its bounded 30-second pass.')

    def fail(self, code, detail, **where):
        item = dict(code=code, detail=detail, **where)
        if len(self.failures) < 200 and item not in self.failures: self.failures.append(item)

    def jets(self, index, u, v, precise=False):
        self.check()
        if precise:
            if index not in self.precise:
                self.precise[index] = self.sk._PreciseEvaluator(self.surfaces[index], self.cancelled)
            self.precise_samples += 1
            return self.precise[index].jets(float(u), float(v))
        return self.evaluators[index].jets(float(u), float(v))

    def edge_jets(self, index, edge, t, precise=False):
        return self.jets(index, *_edge_uv(self.surfaces[index], edge, t), precise=precise)

    def collapsed(self, index, u, v):
        return self.surfaces[index]['kind'] == 'upper_hard_corner' and float(v) == 0.

    def geometry(self, index, u, v):
        if self.collapsed(index, u, v): return None
        values = self.jets(index, u, v)
        geom, sine = self.sk._geometry(values)
        a, b = values[1:3]
        area = float(np.linalg.norm(np.cross(a, b)))
        self.minimum_sine = min(self.minimum_sine, sine)
        self.minimum_jacobian = min(self.minimum_jacobian, area)
        self.samples += 1
        # A small raw J at a positive upper radius is expected. High precision
        # re-evaluates stored coefficients; it never substitutes construction.
        need_precise = (geom is None or min(np.linalg.norm(a), np.linalg.norm(b)) < 1e-8 or
                        max(np.linalg.norm(a), np.linalg.norm(b)) > 1e5 * max(min(np.linalg.norm(a), np.linalg.norm(b)), 1e-300))
        if need_precise:
            g = self.sk._precise_geometry(self.jets(index, u, v, True))
            geom = None if g is None else (np.asarray(g[0], float).ravel(), np.asarray(g[1].tolist(), float))
        if geom is None or not all(np.isfinite(x).all() for x in geom):
            self.fail('SINGULAR_FINITE_FRAME', 'A finite chart station has no regular tangent frame.', surface=index, uv=[u, v])
            return None
        curvature = float(np.linalg.norm(geom[1], 2))
        self.maximum_curvature = max(self.maximum_curvature, curvature)
        if self.surfaces[index]['kind'] != 'upper_hard_corner':
            self.ordinary_curvature = max(self.ordinary_curvature, curvature)
        elif float(v) >= .25:
            self.upper_grid_curvature = max(self.upper_grid_curvature, curvature)
        else:
            self.upper_log_curvature = max(self.upper_log_curvature, curvature)
        return geom

    def compare(self, first, second, category, precise_first=None, precise_second=None, location=None):
        ga, _ = self.sk._geometry(first)
        gb, _ = self.sk._geometry(second)
        a, k = self.sk._compare_geometry(ga, gb)
        if (not math.isfinite(k) or a > math.degrees(self.angle) * .25 or k > self.curv * .25) and precise_first and precise_second:
            pa, pb = precise_first(), precise_second()
            a, k = self.sk._precise_compare(pa, pb)
            pga, pgb = self.sk._precise_geometry(pa), self.sk._precise_geometry(pb)
            ga = None if pga is None else (np.asarray(pga[0], float).ravel(), np.asarray(pga[1].tolist(), float))
            gb = None if pgb is None else (np.asarray(pgb[0], float).ravel(), np.asarray(pgb[1].tolist(), float))
        angle = math.radians(a)
        position = float(np.linalg.norm(np.asarray(first[0], float).ravel() - np.asarray(second[0], float).ravel()))
        metrics = self.metrics[category]
        metrics['position'] = max(metrics['position'], position)
        metrics['angle'] = max(metrics['angle'], angle)
        metrics['curvature'] = max(metrics['curvature'], k)
        metrics['count'] += 1
        if position > self.tol or angle > self.angle or k > self.curv:
            self.fail(category.upper() + '_G2', 'Physical position/normal/full shape-operator residual exceeds tolerance.',
                      residuals=[position, angle, k], **(location or {}))
        return ga, gb

    def add_pair(self, first, edge0, interval0, second, edge1, interval1, label):
        a, b = tuple(map(float, interval0)), tuple(map(float, interval1))
        if first == second and edge0 == edge1 and a == b: return
        if min(a + b) < -1e-9 or max(a + b) > 1 + 1e-9:
            raise ValueError('Shared role maps outside an actual retained edge.')
        key = tuple(sorted(((first, edge0, a), (second, edge1, b))))
        self.coverage[first, edge0].append(a)
        self.coverage[second, edge1].append(b)
        if key not in self.pair_keys:
            self.pair_keys.add(key)
            self.pairs.append((first, edge0, a, second, edge1, b, label))

    def target_edge(self, role):
        matches = [i for i, s in enumerate(self.surfaces)
                   if s.get('kind') == role.get('kind') and s.get('piece') == role.get('piece')
                   and (role.get('kind') == 'middle' or s.get('side') == role.get('side'))]
        if len(matches) != 1: raise ValueError('Retained body role target is missing or ambiguous.')
        index = matches[0]
        axis = role.get('fixed_axis')
        if axis not in ('u', 'v'): raise ValueError('Retained body role has no fixed axis.')
        ai = 0 if axis == 'u' else 1
        fixed = float(role['fixed_parameter']); d = _domain(self.surfaces[index])
        if abs(fixed - d[ai, 0]) <= 1e-10:
            edge = 'left' if ai == 0 else 'bottom'
        elif abs(fixed - d[ai, 1]) <= 1e-10:
            edge = 'right' if ai == 0 else 'top'
        else: raise ValueError('Retained role does not target an actual chart edge.')
        interval = tuple(_edge_fraction(self.surfaces[index], edge, t) for t in role['parameter_interval'])
        return index, edge, interval

    def ledger(self):
        for i, surface in enumerate(self.surfaces):
            self.check()
            roles = surface.get('boundary_roles', {})
            for edge, role in roles.items():
                if edge not in _EDGES or role.get('role') not in _ROLES:
                    raise ValueError('Unknown repaired boundary role or edge.')
                kind = role['role']
                if kind.startswith('native_'):
                    self.native_edges.append((i, edge, role))
                    self.coverage[i, edge].append((0., 1.))
                elif kind == 'new_shared_2jet':
                    seam = role.get('seam_id')
                    if not isinstance(seam, str) or not seam: raise ValueError('Unnamed shared edge.')
                    self.seams[seam].append((i, edge))
                elif kind == 'retained_body_2jet':
                    if 'counterparts' in role:
                        if surface['kind'] != 'lower_bridge' or edge != 'left': raise ValueError('Unsupported retained counterpart list.')
                        for target in role['counterparts']:
                            hits = [j for j, s in enumerate(self.surfaces) if s.get('surface_id') == target.get('surface_id')]
                            if len(hits) != 1 or target.get('edge') not in _EDGES: raise ValueError('Missing bridge counterpart.')
                            counterpart = self.surfaces[hits[0]].get('boundary_roles', {}).get(target['edge'], {})
                            if counterpart.get('role') != 'retained_body_2jet' or counterpart.get('kind') != 'lower_bridge' or counterpart.get('side') != surface.get('side') or counterpart.get('piece') != surface.get('piece') or counterpart.get('parameter_interval') != target.get('native_v_interval'):
                                raise ValueError('Bridge counterpart does not reciprocate its complete retained interval.')
                        continue  # reciprocal chart role performs the actual comparison
                    j, e, interval = self.target_edge(role)
                    self.add_pair(i, edge, (0., 1.), j, e, interval, 'explicit-retained')
                elif kind == 'approved_source_vertex':
                    if surface['kind'] != 'upper_hard_corner' or edge != 'bottom' or role.get('physical_dimension') != 0:
                        raise ValueError('Only the collapsed upper source point can be exempted.')
                    self.coverage[i, edge].append((0., 1.))
            if surface['kind'] in ('collar', 'middle'):
                d = _domain(surface)
                if surface['kind'] == 'collar' and surface.get('piece') == 0:
                    self.native_edges.append((i, 'left', dict(role='native_source_side', side=surface['side'], parameter_interval=d[1].tolist())))
                    self.coverage[i, 'left'].append((0., 1.))
                if d[1, 0] == self.model.v0:
                    self.native_edges.append((i, 'bottom', dict(role='native_upper', side=surface.get('side'))))
                    self.coverage[i, 'bottom'].append((0., 1.))
                if d[1, 1] == self.model.v1:
                    self.native_edges.append((i, 'top', dict(role='native_lower', side=surface.get('side'))))
                    self.coverage[i, 'top'].append((0., 1.))
        for seam, ends in self.seams.items():
            if len(ends) != 2: raise ValueError('Shared seam needs exactly two chart edges: ' + seam)
            (i, e), (j, f) = ends
            p, q = [self.edge_jets(i, e, t)[0] for t in (0., 1.)], [self.edge_jets(j, f, t)[0] for t in (0., 1.)]
            direct = np.linalg.norm(p[0] - q[0]) + np.linalg.norm(p[1] - q[1])
            reverse = np.linalg.norm(p[0] - q[1]) + np.linalg.norm(p[1] - q[0])
            self.add_pair(i, e, (0., 1.), j, f, (0., 1.) if direct <= reverse else (1., 0.), seam)
        # Ordinary retained seams participate too, including lower bridges and
        # partial collar domains. Pair only their actual V-domain intersections.
        ordinary = [(i, s) for i, s in enumerate(self.surfaces) if s['kind'] in ('collar', 'middle', 'lower_bridge')]
        for i, a in ordinary:
            for j, b in ordinary:
                if i >= j: continue
                ea = eb = None
                if a['kind'] == b['kind'] == 'middle' and abs(a['piece'] - b['piece']) == 1:
                    ea, eb = ('right', 'left') if a['piece'] < b['piece'] else ('left', 'right')
                elif a['kind'] != 'middle' and b['kind'] != 'middle' and a.get('side') == b.get('side') and abs(a['piece'] - b['piece']) == 1:
                    ea, eb = ('right', 'left') if a['piece'] < b['piece'] else ('left', 'right')
                elif (a['kind'] == 'middle') != (b['kind'] == 'middle'):
                    mid, col = (a, b) if a['kind'] == 'middle' else (b, a)
                    side = col.get('side'); maximum = max(s['piece'] for _, s in ordinary if s['kind'] != 'middle' and s.get('side') == side)
                    if col['piece'] == maximum and mid['piece'] == (0 if side == 0 else 3):
                        cm, mm = 'right', ('left' if side == 0 else 'right')
                        ea, eb = (mm, cm) if a['kind'] == 'middle' else (cm, mm)
                if ea is None: continue
                da, db = _domain(a)[1], _domain(b)[1]
                lo, hi = max(da[0], db[0]), min(da[1], db[1])
                if hi > lo:
                    self.add_pair(i, ea, tuple(_edge_fraction(a, ea, x) for x in (lo, hi)), j, eb,
                                  tuple(_edge_fraction(b, eb, x) for x in (lo, hi)), 'ordinary-retained')
        for i in range(len(self.surfaces)):
            for edge in _EDGES:
                if not _covered(self.coverage[i, edge]):
                    self.fail('UNCOVERED_CHART_EDGE', 'An actual finite chart edge is absent from the role ledger.', surface=i, edge=edge)

    def compare_shared(self):
        for i, e, a, j, f, b, label in self.pairs:
            self.check()
            stations = set(np.linspace(0., 1., 17))
            for index, edge, interval in ((i, e, a), (j, f, b)):
                if interval[1] == interval[0]: raise ValueError('Collapsed finite shared interval.')
                for v in _stations(self.surfaces[index], _edge_axis(edge), 5, self.surfaces[index]['kind'] == 'upper_hard_corner' and edge in ('left', 'right')):
                    q = (_edge_fraction(self.surfaces[index], edge, v) - interval[0]) / (interval[1] - interval[0])
                    if 0 <= q <= 1: stations.add(q)
            signs = []
            for t in sorted(stations):
                ta, tb = a[0] + t * (a[1] - a[0]), b[0] + t * (b[1] - b[0])
                uv, xy = _edge_uv(self.surfaces[i], e, ta), _edge_uv(self.surfaces[j], f, tb)
                first, second = self.jets(i, *uv), self.jets(j, *xy)
                if self.collapsed(i, *uv) or self.collapsed(j, *xy):
                    if not (self.collapsed(i, *uv) and self.collapsed(j, *xy)):
                        self.fail('ONE_SIDED_COLLAPSE', 'A regular shared neighbor cannot receive a collapsed-point exemption.', surface=i, neighbor=j)
                    continue
                ga, gb = self.compare(first, second, 'shared', lambda: self.jets(i, *uv, precise=True),
                                      lambda: self.jets(j, *xy, precise=True), dict(surface=i, edge=e, neighbor=j, seam=label, parameter=float(t)))
                if ga is not None and gb is not None: signs.append(1 if ga[0] @ gb[0] >= 0 else -1)
            if not signs or min(signs) != max(signs):
                self.fail('SHARED_ORIENTATION', 'The neighboring chart orientation is singular or changes across the seam.', surface=i, neighbor=j)
            else: self.orientation_edges.append((i, j, signs[0]))
        # Every internal knot is checked on both one-sided limits in either
        # parameter direction, including non-C2 encoded composite strips.
        for i, s in enumerate(self.surfaces):
            for axis in (0, 1):
                lo, hi = _domain(s)[axis]
                knots = sorted(set(x for x in s['knots_u' if axis == 0 else 'knots_v'] if lo < x < hi))
                for knot in knots:
                    for t in _stations(s, 1 - axis, 5, s['kind'] == 'upper_hard_corner' and axis == 0):
                        p = [0., 0.]; q = [0., 0.]
                        p[axis], q[axis] = float(np.nextafter(knot, -np.inf)), float(np.nextafter(knot, np.inf))
                        p[1 - axis] = q[1 - axis] = t
                        if self.collapsed(i, *p): continue
                        self.compare(self.jets(i, *p), self.jets(i, *q), 'shared',
                                     lambda: self.jets(i, *p, precise=True), lambda: self.jets(i, *q, precise=True),
                                     dict(surface=i, internal_axis=axis, knot=float(knot)))

    def _closest_curve(self, key, point):
        curve = self.curves[key]; lo, hi = curve.domain
        breaks = sorted(set([lo, hi] + [float(k) for k in curve.knots if lo < k < hi]))
        values = [(float(np.linalg.norm(curve(t) - point)), float(t)) for t in breaks]
        for a, b in zip(breaks[:-1], breaks[1:]):
            # Segment grid brackets protect against choosing an unrelated local
            # minimizer of a high-order rational curve span.
            grid = np.linspace(a, b, 9)
            distance = [float(np.linalg.norm(curve(t) - point)) for t in grid]
            for k in range(1, 8):
                if distance[k] <= min(distance[k - 1], distance[k + 1]):
                    fit = minimize_scalar(lambda t: float(np.sum((curve(t) - point) ** 2)), bounds=(grid[k - 1], grid[k + 1]), method='bounded', options={'xatol': 1e-14, 'maxiter': 80})
                    values.append((float(np.linalg.norm(curve(fit.x) - point)), float(fit.x)))
            # Boundary minima also require their full adjacent bracket.
            for a0, b0 in ((grid[0], grid[1]), (grid[-2], grid[-1])):
                fit = minimize_scalar(lambda t: float(np.sum((curve(t) - point) ** 2)), bounds=(a0, b0), method='bounded', options={'xatol': 1e-14, 'maxiter': 80})
                values.append((float(np.linalg.norm(curve(fit.x) - point)), float(fit.x)))
        return min(values)

    def source_at(self, role, point, chart_v=None):
        name = ('side%d' % role['side']) if role['role'] == 'native_source_side' else role['role'].removeprefix('native_')
        records = self.roles[name]
        if name.startswith('side'):
            record = records[0]; key = record.get('source_key', record.get('key'))
            mapping = record.get('parameter_map')
            if not isinstance(mapping, dict): raise ValueError('Explicit native side parameter map is required.')
            if chart_v is None: raise ValueError('Missing side-boundary chart parameter.')
            a, b = mapping['edge_parameter_from_chart_v']; t = a * chart_v + b
            matrix = np.asarray(mapping['native_uv_from_chart_uv']['matrix'], float)
            uv = matrix @ np.asarray([mapping['boundary_chart_u'], chart_v]) + mapping['native_uv_from_chart_uv']['offset']
            values = self.native_surfaces[key].jet(*uv)
            distance = float(np.linalg.norm(self.curves[key](t) - point))
        else:
            matches = []
            for record in records:
                key = record.get('source_key', record.get('key'))
                if role.get('source_key') and role['source_key'] != key: continue
                distance, t = self._closest_curve(key, point)
                matches.append((distance, key, t, record))
            if not matches: raise ValueError('Native source key is not present on the selected role chain.')
            distance, key, t, record = min(matches, key=lambda x: x[:3])
            curve_point = self.curves[key](t)
            cache_key = key, float(t)
            if cache_key not in self.parent_cache:
                values, uv = self.parent_uv(key, curve_point)
                self.parent_cache[cache_key] = (values, uv)
            values, uv = self.parent_cache[cache_key]
        if distance > self.tol:
            self.fail('SOURCE_LOCUS', 'Candidate trace is not on its actual selected native curve chain.', source_role=name, distance=distance)
        return name, key, t, record, values, np.asarray(uv, float), distance

    def parent_uv(self, key, point):
        """Bounded immutable-parent inversion, including natural-boundary roots.

        Midpoint Newton solves affine parents exactly and avoids the bound-active
        stagnation of an optimizer initialized on the wrong natural edge.
        """
        surface = self.native_surfaces[key]
        lo = np.asarray([surface.ud[0], surface.vd[0]], float)
        hi = np.asarray([surface.ud[1], surface.vd[1]], float)
        uv = (lo + hi) / 2
        for _ in range(12):
            values = surface.jet(*uv)
            error = values[0] - point
            if np.linalg.norm(error) <= max(self.tol * 1e-5, 1e-11): return values, uv
            J = np.column_stack(values[1:3])
            step = np.linalg.lstsq(J, error, rcond=None)[0]
            trial = np.clip(uv - step, lo, hi)
            if np.array_equal(trial, uv): break
            uv = trial
        def residual(q): return surface.jet(*(lo + (hi - lo) * q))[0] - point
        fit = least_squares(residual, np.clip((uv - lo) / (hi - lo), 1e-8, 1 - 1e-8),
                            bounds=(np.zeros(2), np.ones(2)), max_nfev=60,
                            xtol=1e-13, ftol=1e-13, gtol=1e-13)
        uv = lo + (hi - lo) * fit.x
        values = surface.jet(*uv)
        if np.linalg.norm(values[0] - point) > max(self.tol * .05, 1e-9):
            raise ValueError('Selected source curve cannot be mapped to its immutable parent.')
        return values, uv

    def source_endpoint_stations(self, index, edge, role):
        """Insert original selected-chain vertices wherever they cross a trace.

        This closes source-domain coverage at native edge transitions, rather
        than assuming a finite uniform grid lands on every selected vertex.
        """
        if role['role'] == 'native_source_side': return [], []
        records = self.roles[role['role'].removeprefix('native_')]
        endpoints = []
        for record in records:
            key = record.get('source_key', record.get('key'))
            if role.get('source_key') and role['source_key'] != key: continue
            for parameter in self.curves[key].domain:
                endpoints.append((key, float(parameter), self.curves[key](parameter)))
        stations = []
        threshold = max(min(self.tol * .01, self.model.scale * 1e-8), 1e-11)
        grid = np.linspace(0., 1., 17)
        points = [self.edge_jets(index, edge, q)[0] for q in grid]
        for key, parameter, point in endpoints:
            distances = np.asarray([np.linalg.norm(p - point) for p in points])
            candidates = [(distances[0], 0.), (distances[-1], 1.)]
            for k in range(1, len(grid) - 1):
                if distances[k] <= min(distances[k - 1], distances[k + 1]):
                    fit = minimize_scalar(lambda q: float(np.sum((self.edge_jets(index, edge, q)[0] - point) ** 2)),
                                          bounds=(grid[k - 1], grid[k + 1]), method='bounded',
                                          options={'xatol': 1e-14, 'maxiter': 80})
                    candidates.append((math.sqrt(max(0., fit.fun)), float(fit.x)))
            for a0, b0 in ((grid[0], grid[1]), (grid[-2], grid[-1])):
                fit = minimize_scalar(lambda q: float(np.sum((self.edge_jets(index, edge, q)[0] - point) ** 2)),
                                      bounds=(a0, b0), method='bounded', options={'xatol': 1e-14, 'maxiter': 80})
                candidates.append((math.sqrt(max(0., fit.fun)), float(fit.x)))
            distance, t = min(candidates)
            if distance <= threshold: stations.append(t)
        return stations, endpoints

    def compare_native(self):
        for i, edge, role in self.native_edges:
            self.check()
            s = self.surfaces[i]
            vals = _stations(s, _edge_axis(edge), 9, s['kind'] == 'upper_hard_corner')
            ts = set(_edge_fraction(s, edge, x) for x in vals)
            ts.update(np.linspace(0., 1., 25))
            endpoint_stations, endpoints = self.source_endpoint_stations(i, edge, role)
            ts.update(endpoint_stations)
            observed = defaultdict(list)
            mapped = defaultdict(list)
            for t in sorted(ts):
                uv = _edge_uv(s, edge, t)
                values = self.jets(i, *uv)
                chart_v = None
                if role['role'] == 'native_source_side':
                    a, b = role['parameter_interval']; chart_v = a + t * (b - a)
                name, key, parameter, record, parent, native_uv, distance = self.source_at(role, values[0], chart_v)
                observed[key].append(parameter)
                mapped[key].append((float(t), float(parameter)))
                # A shared original source vertex belongs to BOTH selected
                # edges, even when the closest-curve tie chooses one owner.
                endpoint_threshold = max(min(self.tol * .01, self.model.scale * 1e-8), 1e-11)
                for endpoint_key, endpoint_parameter, endpoint in endpoints:
                    if np.linalg.norm(values[0] - endpoint) <= endpoint_threshold:
                        observed[endpoint_key].append(endpoint_parameter)
                        mapped[endpoint_key].append((float(t), float(endpoint_parameter)))
                        if endpoint_key != key and not self.collapsed(i, *uv):
                            other_parent, other_uv = self.parent_uv(endpoint_key, endpoint)
                            if endpoint_key not in self.precise:
                                self.precise[endpoint_key] = self.sk._PreciseEvaluator(self.keys[endpoint_key]['surface'], self.cancelled)
                            self.compare(values, other_parent, name, lambda: self.jets(i, *uv, precise=True),
                                         lambda: self.precise[endpoint_key].jets(*other_uv),
                                         dict(surface=i, edge=edge, source_role=name, native_chain_vertex=True))
                if self.collapsed(i, *uv): continue
                if key not in self.precise:
                    self.precise[key] = self.sk._PreciseEvaluator(record['surface'], self.cancelled)
                category = 'side' if name.startswith('side') else name
                self.compare(values, parent, category, lambda: self.jets(i, *uv, precise=True),
                             lambda: self.precise[key].jets(*native_uv), dict(surface=i, edge=edge, parameter=float(t), source_role=name))
                owner = record.get('owner_side')
                if not isinstance(owner, dict) or owner.get('edge_inward_cross_sign') not in (-1, 1) or type(owner.get('face_orientation_reversed')) is not bool:
                    if 'native_outward_side_capture' not in self.pending: self.pending.append('native_outward_side_capture')
                else:
                    normal = np.cross(parent[1], parent[2]); normal /= np.linalg.norm(normal)
                    if owner['face_orientation_reversed']: normal = -normal
                    tangent = self.curves[key](parameter, 1); tangent /= np.linalg.norm(tangent)
                    inward = owner['edge_inward_cross_sign'] * np.cross(normal, tangent)
                    arrival = _edge_inward(values, edge)
                    conormal = arrival - tangent * (arrival @ tangent)
                    length = np.linalg.norm(conormal)
                    sign = float(conormal @ (-inward) / length) if length > 0 else -math.inf
                    self.minimum_outward = min(self.minimum_outward, sign)
                    if sign <= 1e-8:
                        self.fail('NATIVE_OUTWARD_SIDE', 'New cap enters the occupied native trim side.', surface=i, edge=edge, source_role=name, signed_outward_cosine=sign)
            for key, parameters in observed.items():
                # Original-chain endpoint insertions also split the trusted
                # exterior contact ledger into actual native owner spans.
                samples = sorted(mapped[key])
                start, finish = samples[0], samples[-1]
                curve = self.curves[key]; lo, hi = curve.domain
                self.source_coverage[key].append(((min(parameters) - lo) / (hi - lo), (max(parameters) - lo) / (hi - lo)))
                ordered = np.asarray([x[1] for x in samples], float)
                changes = np.diff(ordered)
                nonzero = changes[np.abs(changes) > 1e-7 * (hi - lo)]
                if len(nonzero) and min(nonzero) < 0 < max(nonzero):
                    self.fail('SOURCE_TRACE_BACKTRACK', 'A candidate source trace reverses direction on its selected native curve.', surface=i, edge=edge)
                axis_domain = _domain(s)[_edge_axis(edge)]
                generated = [float(axis_domain[0] + x[0] * (axis_domain[1] - axis_domain[0])) for x in (start, finish)]
                for endpoint in (start, finish):
                    self.contact_vertices.append((key, float(endpoint[1]), curve(endpoint[1])))
                if finish[0] - start[0] > 1e-12:
                    self.contacts.append(dict(surface_index=i, edge=edge, source_key=key,
                                              native_parameter_interval=[float(start[1]), float(finish[1])],
                                              generated_parameter_interval=generated))
        for key in self.keys:
            if not _covered(self.source_coverage[key], tolerance=1e-6):
                self.fail('SOURCE_COVERAGE', 'Selected native edge domain is not fully covered by the atlas traces.', source_role=next(r for r, records in self.roles.items() if self.keys[key] in records), intervals=self.source_coverage[key])

    def contact_ledger(self):
        """Only checked exterior source traces and their incident atlas vertices.

        An internal shared seam never becomes an allowed finite parent contact.
        Zero-dimensional endpoint contacts remain separate and are NOT regular
        lower-corner or internal-junction continuity exemptions.
        """
        point_contacts = []
        seen = set()
        threshold = max(min(self.tol * .01, self.model.scale * 1e-8), 1e-11)
        for i, surface in enumerate(self.surfaces):
            d = _domain(surface)
            for u in d[0]:
                for v in d[1]:
                    point = self.jets(i, u, v)[0]
                    for key, parameter, native_point in self.contact_vertices:
                        if np.linalg.norm(point - native_point) <= threshold:
                            identity = (i, float(u), float(v), key)
                            if identity not in seen:
                                seen.add(identity)
                                point_contacts.append(dict(surface_index=i, generated_uv=[float(u), float(v)],
                                                           source_key=key, native_parameter=float(parameter)))
        return dict(schema='smartskin.native-contact-ledger.v1',
                    checked=not any(f['code'] in ('SOURCE_LOCUS', 'SOURCE_COVERAGE', 'SOURCE_TRACE_BACKTRACK', 'UNCOVERED_CHART_EDGE') for f in self.failures),
                    source_digest=_digest(self.roles), geometry_digest=_digest(self.surfaces),
                    contacts=self.contacts, point_contacts=point_contacts,
                    interval_units='actual generated varying-axis and original selected source-curve parameters',
                    internal_seams_are_allowed_contacts=False)

    def regularity_and_points(self):
        for i, s in enumerate(self.surfaces):
            self.check()
            us = _stations(s, 0, 5)
            vs = _stations(s, 1, 5, s['kind'] == 'upper_hard_corner')
            for u in us:
                for v in vs:
                    if not self.collapsed(i, u, v): self.geometry(i, u, v)
            if s['kind'] != 'upper_hard_corner': continue
            identity = s.get('approved_physical_corner_id')
            binding = self.approved.get(identity)
            if identity not in ('upper:side0', 'upper:side1') or not isinstance(binding, dict):
                self.fail('UNAPPROVED_COLLAPSED_POINT', 'Collapsed chart is not bound to a caller-approved original upper source intersection.', surface=i)
                continue
            side = int(identity[-1])
            if s.get('side') != side or s.get('boundary_roles', {}).get('bottom', {}).get('corner_id') != identity:
                self.fail('COLLAPSED_BINDING', 'Collapsed role and chart identity disagree.', surface=i)
                continue
            if binding.get('binding') is not None and s.get('source_corner_binding') != binding['binding']:
                self.fail('COLLAPSED_BINDING', 'Chart binding is not the replay-derived original source binding.', surface=i)
                continue
            cp = np.asarray(s['homogeneous_cp'], float)
            pole = cp[:, 0, :3] / cp[:, 0, 3, None]
            if np.max(np.linalg.norm(pole - np.asarray(binding['point'], float), axis=1)) > self.tol:
                self.fail('COLLAPSED_LOCUS', 'Collapsed chart point differs from its approved physical source vertex.', surface=i)
                continue
            # Derive a useful common projection from actual finite chart normals;
            # the exact certificate then proves positivity over the whole square.
            companions = [j for j, r in enumerate(self.surfaces) if r['kind'] == 'upper_hard_corner' and r.get('approved_physical_corner_id') == identity]
            if len(companions) != 2:
                self.fail('UPPER_ATLAS', 'Each approved upper point requires exactly two charts.', surface=i)
                continue
            first, second = companions
            ga = self.sk._geometry(self.jets(first, 0., .5))[0]
            gb = self.sk._geometry(self.jets(second, 0., .5))[0]
            if ga is None or gb is None:
                self.fail('UPPER_REFERENCE_FRAME', 'Cannot derive a finite upper projection.', surface=i)
                continue
            normal = ga[0] - gb[0]
            if np.linalg.norm(normal) == 0: normal = ga[0]
            normal /= np.linalg.norm(normal)
            current = self.sk._geometry(self.jets(i, .5, .5))[0]
            sign = 1 if current is not None and current[0] @ normal > 0 else -1
            cert = _module('upper_corner_certificate').certify_isolated_upper_chart(s, normal, sign, cancelled=self.cancelled, deadline=self.deadline)
            self.certificates.append(dict(surface_index=i, **cert))
            if not cert.get('passed'):
                self.fail('UPPER_RADIAL_REGULARITY', cert.get('reason', 'Exact radial certificate is missing.'), surface=i)

    def orientation(self):
        graph = defaultdict(list)
        for i, j, sign in self.orientation_edges:
            graph[i].append((j, sign)); graph[j].append((i, sign))
        assigned = {}
        components = 0
        for start in range(len(self.surfaces)):
            if start in assigned: continue
            components += 1; assigned[start] = 1; stack = [start]
            while stack:
                i = stack.pop()
                for j, sign in graph[i]:
                    expected = assigned[i] * sign
                    if j in assigned and assigned[j] != expected:
                        self.fail('NONORIENTABLE_ATLAS', 'Adjacent finite chart normals have inconsistent orientation parity.', surface=i, neighbor=j)
                    elif j not in assigned:
                        assigned[j] = expected; stack.append(j)
        if components != 1:
            self.fail('DISCONNECTED_ATLAS', 'The shared-edge ledger does not connect the complete new cap.', components=components)
        return dict(checked=True, compatible=components == 1 and not any(f['code'] in ('NONORIENTABLE_ATLAS', 'SHARED_ORIENTATION') for f in self.failures),
                    components=components, orientation_reversed=[assigned[i] < 0 for i in range(len(self.surfaces))],
                    convention='consistent adjacent chart normals; global sign chosen by the first chart')

    def guide_binding(self, guide):
        if isinstance(guide.get('binding'), dict): return guide['binding']
        kind = guide.get('kind')
        if kind == 'profile':
            piece = int(guide['piece']); target = min(piece, 3)
            matches = [i for i, s in enumerate(self.surfaces) if s['kind'] == 'middle' and s.get('piece') == target]
            if len(matches) != 1: raise ValueError('Generated profile has no unique owning middle chart.')
            d = _domain(self.surfaces[matches[0]])
            return dict(surface_index=matches[0], varying_axis='v', constant_parameter=float(d[0, 1 if piece == 4 else 0]))
        if kind in ('row_collar', 'row_middle'):
            matches = [i for i, s in enumerate(self.surfaces) if s['kind'] == kind.removeprefix('row_') and s.get('piece') == guide.get('piece') and s.get('side') == guide.get('side')]
            if len(matches) != 1: raise ValueError('Generated row has no unique chart owner.')
            return dict(surface_index=matches[0], varying_axis='u', constant_parameter=float(guide['native_v']))
        raise ValueError('Generated guide has no explicit supported on-skin binding.')

    def guides(self):
        maximum = 0.; count = 0
        covered_bindings = defaultdict(set)
        profiles, rows = set(), set()
        guides = self.result.get('guides')
        if not isinstance(guides, list) or not guides:
            self.fail('GUIDE_COVERAGE', 'Generated on-skin guides are missing.')
            return dict(checked=False, compatible=False, maximum_position_error=math.inf, binding_count=0)
        for guide in guides:
            self.check()
            bindings = [self.guide_binding(guide)] + guide.get('coincident_bindings', [])
            if guide.get('kind') == 'profile': profiles.add(guide.get('piece'))
            if guide.get('kind') in ('row_collar', 'row_middle'):
                rows.add((guide.get('kind').removeprefix('row_'), guide.get('side'), guide.get('piece'), float(guide['native_v'])))
            for binding in bindings:
                i = binding.get('surface_index'); axis = binding.get('varying_axis'); fixed = binding.get('constant_parameter')
                if type(i) is not int or not 0 <= i < len(self.surfaces) or axis not in ('u', 'v') or not math.isfinite(float(fixed)):
                    raise ValueError('Malformed guide isocurve binding.')
                d = _domain(self.surfaces[i]); ai = 0 if axis == 'u' else 1
                domain = np.asarray(guide['domain'], float)
                if domain.shape != (2,) or domain[0] < d[ai, 0] - 1e-12 or domain[1] > d[ai, 1] + 1e-12 or not d[1 - ai, 0] <= fixed <= d[1 - ai, 1]:
                    raise ValueError('Guide binding lies outside its owner chart.')
                for t in np.linspace(*domain, 17):
                    cp = np.asarray(guide['homogeneous_cp'], float)
                    h = BSpline(guide['knots'], cp, int(guide['degree']), extrapolate=False)(t)
                    point = h[:3] / h[3]
                    uv = (t, fixed) if ai == 0 else (fixed, t)
                    error = float(np.linalg.norm(point - self.jets(i, *uv)[0]))
                    maximum = max(maximum, error)
                count += 1
                if guide.get('guide_id'):
                    covered_bindings[guide['guide_id']].add((i, axis, float(fixed)))
        if profiles != set(range(5)):
            self.fail('GUIDE_PROFILE_COVERAGE', 'The five generated profile guides are not all present.')
        network = self.result.get('network', {})
        for v in network.get('native_v', []):
            for surface in self.surfaces:
                if surface['kind'] in ('collar', 'middle') and _domain(surface)[1, 0] <= v <= _domain(surface)[1, 1]:
                    if (surface['kind'], surface.get('side'), surface.get('piece'), float(v)) not in rows:
                        self.fail('GUIDE_ROW_COVERAGE', 'A displayed generated row omits a retained chart.', native_v=float(v))
        for seam, ends in self.seams.items():
            required = set()
            for i, edge in ends:
                uv = _edge_uv(self.surfaces[i], edge, .5)
                axis = 'v' if _edge_axis(edge) == 1 else 'u'
                required.add((i, axis, float(uv[0 if axis == 'v' else 1])))
            if not required.issubset(covered_bindings[seam]):
                self.fail('GUIDE_SHARED_COVERAGE', 'A new shared guide lacks both actual coincident chart bindings.', seam=seam)
        expected_roles, expected_collapsed = set(), set()
        for i, surface in enumerate(self.surfaces):
            for edge, role in surface.get('boundary_roles', {}).items():
                if role['role'] in ('native_source_side', 'native_upper', 'native_lower', 'retained_body_2jet'):
                    expected_roles.add((i, edge, role['role']))
                elif role['role'] == 'approved_source_vertex':
                    expected_collapsed.add((i, edge, role['corner_id']))
        listed_roles = [(x.get('surface_index'), x.get('edge'), x.get('role')) for x in network.get('repaired_boundary_roles', [])]
        listed_collapsed = [(x.get('surface_index'), x.get('edge'), x.get('corner_id')) for x in network.get('collapsed_boundary_bindings', [])]
        if len(set(listed_roles)) != len(listed_roles) or set(listed_roles) != expected_roles:
            self.fail('GUIDE_NATIVE_ROLE_COVERAGE', 'Repaired native/retained role coverage is incomplete or contains an unrecognized exemption.')
        if len(set(listed_collapsed)) != len(listed_collapsed) or set(listed_collapsed) != expected_collapsed:
            self.fail('GUIDE_COLLAPSED_COVERAGE', 'Collapsed bindings must name exactly the approved zero-dimensional upper edges.')
        if maximum > self.tol: self.fail('GUIDE_NOT_ON_SKIN', 'A generated guide does not lie on its declared final skin.', distance=maximum)
        return dict(checked=True, compatible=maximum <= self.tol and not any(f['code'].startswith('GUIDE_') for f in self.failures), maximum_position_error=maximum, binding_count=count,
                    method='all generated primary/coincident isocurve bindings; finite per-curve stations',
                    native_edges_require_duplicate_guides=False)

    def adjacency_ledger(self, compatible):
        signs = {(i, j): sign for i, j, sign in self.orientation_edges}
        pairs = []
        for i, e, a, j, f, b, label in self.pairs:
            pairs.append(dict(surface_indices=[i, j], edges=[e, f],
                              normalized_intervals=[list(a), list(b)],
                              parameter_orientation=1 if (a[1] - a[0]) * (b[1] - b[0]) > 0 else -1,
                              normal_orientation=signs.get((i, j)), role=label))
        return dict(schema='smartskin.atlas-adjacency.v1', checked=bool(compatible),
                    source_digest=_digest(self.roles), geometry_digest=_digest(self.surfaces),
                    shared_edges=pairs, interval_units='normalized local chart-edge fraction',
                    additional_point_contacts='only endpoint equivalence induced by these checked shared edges')

    def run(self):
        self.ledger()
        self.regularity_and_points()
        self.compare_shared()
        self.compare_native()
        orientation = self.orientation()
        guides = self.guides()
        # Nothing in a descriptor can grant its own nonoverlap approval. A
        # separate, source-bound bounded separation construction is required.
        self.pending.append('bounded_native_parent_separation')
        source_codes = {'SOURCE_LOCUS', 'SOURCE_COVERAGE', 'SOURCE_TRACE_BACKTRACK', 'NATIVE_OUTWARD_SIDE', 'UNAPPROVED_COLLAPSED_POINT', 'COLLAPSED_BINDING', 'COLLAPSED_LOCUS'}
        source_pass = all(self.metrics[k]['count'] > 0 for k in ('side', 'upper', 'lower')) and not any(f['code'] in source_codes or f['code'] in ('SIDE_G2', 'UPPER_G2', 'LOWER_G2') for f in self.failures)
        shared_pass = self.metrics['shared']['count'] > 0 and not any(f['code'] in ('SHARED_G2', 'UNCOVERED_CHART_EDGE', 'ONE_SIDED_COLLAPSE', 'SHARED_ORIENTATION') for f in self.failures)
        all_metrics = self.metrics
        reasons = [f['code'] for f in self.failures] + ['PENDING_' + x.upper() for x in self.pending]
        curvature_encoding_failures = [f for f in self.failures
            if f['code'] in ('SIDE_G2','UPPER_G2','LOWER_G2','SHARED_G2') and
            len(f.get('residuals',[])) == 3 and f['residuals'][0] <= self.tol and
            f['residuals'][1] <= self.angle and f['residuals'][2] > self.curv]
        output_diagnostic = ('Internal output construction or numerical conditioning failed the stored-control curvature check. '
                             'The original selected geometry was left unchanged.' if curvature_encoding_failures else '')
        report = dict(checked=True, fatal=bool(self.failures or self.pending), full_boundary_pass=False,
                      source_full_finite_boundary_pass=False, shared_full_finite_boundary_pass=False,
                      numeric_source_finite_samples_pass=source_pass, numeric_shared_finite_samples_pass=shared_pass,
                      numeric_geometry_samples_pass=not self.failures, geometry_valid=not (self.failures or self.pending), reason=(output_diagnostic+' ' if output_diagnostic else '')+('; '.join(dict.fromkeys(reasons)) or 'Finite numeric checks passed.'),
                      output_conditioning_diagnostic=output_diagnostic,
                      failures=self.failures, pending_gates=list(dict.fromkeys(self.pending)),
                      position_tolerance=self.tol, angle_tolerance_radians=self.angle,
                      angle_tolerance_degrees=math.degrees(self.angle), curvature_tolerance=self.curv,
                      source_position_error=all_metrics['side']['position'], source_angle_degrees=math.degrees(all_metrics['side']['angle']), source_curvature_error=all_metrics['side']['curvature'],
                      upper_position_error=all_metrics['upper']['position'], upper_angle_degrees=math.degrees(all_metrics['upper']['angle']), upper_curvature_error=all_metrics['upper']['curvature'],
                      lower_position_error=all_metrics['lower']['position'], lower_angle_degrees=math.degrees(all_metrics['lower']['angle']), lower_curvature_error=all_metrics['lower']['curvature'],
                      seam_position_error=all_metrics['shared']['position'], seam_angle_degrees=math.degrees(all_metrics['shared']['angle']), seam_curvature_error=all_metrics['shared']['curvature'],
                      sample_count=self.samples, precise_evaluation_count=self.precise_samples,
                      minimum_sampled_sine=self.minimum_sine, minimum_sampled_jacobian=self.minimum_jacobian,
                      sampled_max_curvature=max(self.ordinary_curvature, self.upper_grid_curvature),
                      ordinary_chart_sampled_max_curvature=self.ordinary_curvature,
                      upper_interior_grid_sampled_max_curvature=self.upper_grid_curvature,
                      all_finite_sampled_max_curvature=self.maximum_curvature, minimum_native_outward_cosine=None if not math.isfinite(self.minimum_outward) else self.minimum_outward,
                      orientation=orientation, guide_coverage=guides, upper_radial_certificates=self.certificates,
                      source_modifications=0, excluded_intervals=[],
                      hard_corner_curvature=dict(unbounded_growth_allowed=True, physical_points=sorted(self.approved),
                                                 raw_jacobian_decay_is_not_failure=True, positive_radius_excluded=0.,
                                                 logarithmic_sampled_max_curvature=self.upper_log_curvature,
                                                 display_scope='ordinary charts and upper r>=0.25 grid; all smaller positive radii remain validated'),
                      source_coverage={k: v for k, v in self.source_coverage.items()}, native_contact_ledger=self.contact_ledger(),
                      atlas_adjacency=self.adjacency_ledger(shared_pass and orientation['compatible']),
                      atlas_edge_count=4 * len(self.surfaces), shared_pair_count=len(self.pairs), native_trace_count=len(self.native_edges),
                      certificate='finite stations across every declared span and repeated-knot limit; no global collision or all-parameter G2 certificate',
                      source_digest=_digest(self.roles), geometry_digest=_digest(self.surfaces), native_provenance_verified=False)
        return report


def validate_repaired_numeric(model, result, source_roles, approved_corners=None, cancelled=None):
    """Return geometry metrics using explicit original records, never provenance.

    ``approved_corners`` is caller-owned geometry context, not a candidate-owned
    allowlist. The production entry point replaces it with capture-derived data.
    Missing owner-side capture and bounded separation remain named pending gates.
    """
    sk = _module('skin_kernel')
    before = _digest(source_roles)
    try:
        report = _Validator(model, result, source_roles, approved_corners, cancelled).run()
    except sk.Cancelled:
        raise
    except (ValueError, KeyError, TypeError, IndexError, ArithmeticError, np.linalg.LinAlgError) as error:
        report = dict(checked=False, fatal=True, full_boundary_pass=False,
                      source_full_finite_boundary_pass=False, shared_full_finite_boundary_pass=False,
                      reason='REPAIRED_VALIDATION_INPUT: ' + str(error), failures=[dict(code='REPAIRED_VALIDATION_INPUT', detail=str(error))],
                      native_provenance_verified=False, excluded_intervals=[], source_modifications=0)
    if _digest(source_roles) != before:
        raise ValueError('Original source records changed during read-only validation.')
    return report


def validate_repaired(model, result, cancelled=None):
    """Production gate: re-read genuine source provenance before all geometry.

    Returns a fresh result wrapper accepted by the selected-U/V callback. No
    result-declared approvals or stale attachment proof are read or propagated.
    """
    sk, nf = _module('skin_kernel'), _module('native_family')
    nf.require_native_provenance(model.spec, cancelled)
    approved = sk._approved_upper_corner_bindings(model.spec)
    report = validate_repaired_numeric(model, result, model.spec['source_boundaries']['roles'], approved, cancelled)
    report['native_provenance_verified'] = True
    # Recheck immutable evidence after the potentially long numerical pass.
    nf.require_native_provenance(model.spec, cancelled)
    oriented = copy.deepcopy(result.get('surfaces', []))
    if report.get('orientation', {}).get('compatible'):
        for surface, reversed_flag in zip(oriented, report['orientation']['orientation_reversed']):
            surface['orientation_reversed'] = bool(reversed_flag)
        # Face orientation changes no UV jet, but it is part of the native
        # descriptor identity. Bind every downstream receipt to final flags.
        report['geometry_digest'] = _digest(oriented)
        for ledger in ('native_contact_ledger','atlas_adjacency'):
            if isinstance(report.get(ledger),dict):
                report[ledger]['geometry_digest'] = report['geometry_digest']
    out = dict(report=report, metrics=report, surfaces=oriented, patches=oriented, valid=False, geometry_valid=report.get('geometry_valid', False),
               fatal=True, full_boundary_pass=False, continuity_pass=False, experimental_commit_allowed=False,
               reason=report['reason'])
    out['native_contact_ledger'] = copy.deepcopy(report.get('native_contact_ledger', {}))
    out['atlas_adjacency'] = copy.deepcopy(report.get('atlas_adjacency', {}))
    # Attachment and native separation have deliberately distinct receipts. The
    # first says only that finite source/shared G0/G1/G2 and local regularity
    # passed for this exact source-bound atlas. It does not permit native commit.
    upper = [s for s in result.get('surfaces', []) if s.get('kind') == 'upper_hard_corner']
    corner_counts = {key: sum(s.get('approved_physical_corner_id') == key and
                              s.get('source_corner_binding') == value['binding'] for s in upper)
                     for key, value in approved.items()}
    finite_pass = (report.get('checked') is True and not report.get('failures') and
                   report.get('numeric_source_finite_samples_pass') is True and
                   report.get('numeric_shared_finite_samples_pass') is True and
                   report.get('numeric_geometry_samples_pass') is True and
                   report.get('orientation', {}).get('compatible') is True and
                   report.get('guide_coverage', {}).get('compatible') is True and
                   report.get('native_contact_ledger', {}).get('checked') is True and
                   report.get('pending_gates') == ['bounded_native_parent_separation'] and
                   set(corner_counts) == {'upper:side0', 'upper:side1'} and
                   len(upper) == 4 and all(x == 2 for x in corner_counts.values()) and
                   len(report.get('upper_radial_certificates', [])) == 4 and
                   all(x.get('passed') is True for x in report['upper_radial_certificates']))
    if finite_pass:
        report.update(fatal=False, geometry_valid=True, full_boundary_pass=True,
                      source_full_finite_boundary_pass=True, shared_full_finite_boundary_pass=True,
                      disposition='native_screen_pending',
                      reason='Finite native attachment, shared G2, orientation, guide and local regularity checks passed; bounded native separation screen remains pending.')
        out.update(valid=True, geometry_valid=True, fatal=False, full_boundary_pass=True,
                   continuity_pass=True, disposition='native_screen_pending', reason=report['reason'])
        out['attachment_proof'] = dict(schema='smartskin.attachments.v2', checked=True,
                                       source_full_finite_boundary_pass=True, shared_full_finite_boundary_pass=True,
                                       corner_policy='hard_upper_source_corners', excluded_intervals=[],
                                       excluded_points=[copy.deepcopy(approved[key]['binding']) for key in sorted(approved)])
    # No separation receipt is accepted from result metadata or fabricated here.
    # The native preview stage binds its own check to current geometry/request.
    out['experimental_commit_allowed'] = False
    return out
