"""Bounded, source-bound projected cap/cap nonoverlap SCREEN.

This is a finite numerical screen, not a global injectivity certificate. A
common projection is selected from oriented actual chart normals. Knot-span
boundary polylines use a station union across the checked affine seam ledger;
only those seam segments and their induced endpoint equivalences may coincide.
Every other boundary intersection, self-intersection and interior containment
fails. An upper point pole is allowed only with the separately checked exact
radial certificate. No positive-radius interval is excluded.

Invariants: read-only source/surface records, bounded work and cancellation,
no native provenance fabrication, and no receipt valid for a different edit.
Rhino UI/native execution is NOT VERIFIED by this pure numeric module.
"""
import importlib
import copy
import math
import time
from collections import defaultdict
from fractions import Fraction

import numpy as np
from scipy.optimize import linprog


def _module(name):
    try:
        return importlib.import_module('_smartskin_p08e1_' + name)
    except ModuleNotFoundError as error:
        if error.name != '_smartskin_p08e1_' + name:
            raise
        return importlib.import_module(name)


MAX_SECONDS = 30.
MAX_SURFACES = 64
MAX_CONTROL_POINTS = 16384
MAX_AGGREGATE_CONTROL_POINTS = 262144
MAX_NORMAL_SAMPLES = 65536
MAX_BOUNDARY_SEGMENTS = 16384
MAX_PAIR_WORK = 140000000
MAX_INTERSECTION_TESTS = 262144
MAX_EVALUATION_WORK = 120000000
_STEPS = 16
_EDGES = ('bottom', 'right', 'top', 'left')
_METHOD = ('finite knot-span normal-cone projection; synchronized affine-seam '
           'boundary polylines; all segment intersections and chart containment')
_SCHEMA = 'smartskin.atlas-separation.v1'


class AtlasSeparationError(ValueError):
    pass


def _fail(message):
    raise AtlasSeparationError(message)


def _digest(value):
    return _module('repaired_validation')._digest(value)


def _spec(model):
    return model if isinstance(model, dict) else model.spec


def _bounded_geometry(result):
    surfaces = result.get('surfaces')
    if not isinstance(surfaces, (list, tuple)) or not 1 <= len(surfaces) <= MAX_SURFACES:
        _fail('Atlas surface-count budget exceeded.')
    aggregate = 0
    for surface in surfaces:
        cp = surface.get('homogeneous_cp')
        if not isinstance(cp, (list, tuple, np.ndarray)) or not len(cp):
            _fail('Invalid homogeneous control net.')
        width = len(cp[0])
        count = len(cp) * width
        aggregate += count
        if count > MAX_CONTROL_POINTS or aggregate > MAX_AGGREGATE_CONTROL_POINTS:
            _fail('Atlas control-net budget exceeded.')
        if (not width or any(len(row) != width for row in cp) or
                any(len(point) != 4 for row in cp for point in row)):
            _fail('Invalid homogeneous control net.')
        for key in ('degree_u', 'degree_v'):
            degree = surface.get(key)
            if isinstance(degree, bool) or not isinstance(degree, (int, np.integer)) or not 1 <= degree <= 40:
                _fail('Invalid atlas degree.')


def _binding(result, source_model, request):
    _bounded_geometry(result)
    spec = _spec(source_model)
    roles = spec.get('source_boundaries', {}).get('roles')
    if not isinstance(roles, dict) or not roles:
        _fail('Explicit original source_boundaries.roles are required.')
    if request is None:
        if 'edit_request' in result:
            _fail('Baseline receipt cannot bind an edited result.')
    elif 'edit_request' not in result or _digest(request) != _digest(result['edit_request']):
        _fail('Current request differs from the exact result edit_request.')
    return dict(source_digest=_digest(roles), geometry_digest=_digest(result.get('surfaces')),
                request_digest=_digest(request))


def verify_atlas_separation(result, source_model, request=None):
    """Pure commit-time check against actual current sources, surfaces and edit."""
    binding = _binding(result, source_model, request)
    receipt = result.get('atlas_separation', {})
    if (receipt.get('schema') != _SCHEMA or receipt.get('checked') is not True or
            receipt.get('passed') is not True or
            receipt.get('global_injectivity_certified') is not False or
            receipt.get('method') != _METHOD):
        _fail('A completed bounded atlas separation screen is required.')
    for key, value in binding.items():
        if receipt.get(key) != value:
            _fail('Stale atlas separation ' + key + '.')
    ledger = _checked_ledger(result, binding)
    if receipt.get('adjacency_digest') != _digest(ledger):
        _fail('Stale atlas separation adjacency digest.')
    return True


def rebind_identical_neutral_request(baseline,result,source_model,request):
    """Rebind a completed screen only for identical geometry and exact zero.

    This does not repeat the numerical screen and never supplies a native-owner
    receipt. The caller must separately seal the trusted baseline/basis state.
    """
    values=request.get('values') if isinstance(request,dict) else None
    if (not isinstance(values,dict) or not values or
            any(type(x) not in (int,float) or not math.isfinite(x) or x!=0. for x in values.values())):
        _fail('Atlas neutral rebinding requires exact zero handle values.')
    verify_atlas_separation(baseline,source_model,None)
    for key in ('surfaces','patches','guides','network','atlas_adjacency','native_contact_ledger','attachment_proof'):
        if _digest(baseline.get(key))!=_digest(result.get(key)):
            _fail('Atlas neutral rebinding changed '+key+'.')
    binding=_binding(result,source_model,request)
    _checked_ledger(result,binding)
    receipt=copy.deepcopy(baseline['atlas_separation'])
    receipt['request_digest']=binding['request_digest']
    result['atlas_separation']=receipt
    verify_atlas_separation(result,source_model,request)
    return receipt


def _checked_ledger(result, binding):
    report = result.get('report', {})
    if not isinstance(report, dict):
        _fail('Fresh checked atlas validation report is required.')
    ledger = result.get('atlas_adjacency', report.get('atlas_adjacency', {}))
    if not isinstance(ledger, dict):
        _fail('Fresh checked atlas adjacency is required.')
    if (report.get('checked') is not True or report.get('failures') or
            report.get('excluded_intervals', []) != [] or
            ledger.get('checked') is not True or
            ledger.get('schema') != 'smartskin.atlas-adjacency.v1' or
            ledger.get('interval_units') != 'normalized local chart-edge fraction' or
            ledger.get('additional_point_contacts') !=
            'only endpoint equivalence induced by these checked shared edges'):
        _fail('Fresh checked source-bound atlas adjacency is required.')
    for key in ('source_digest', 'geometry_digest'):
        if report.get(key) != binding[key] or ledger.get(key) != binding[key]:
            _fail('Stale source-bound atlas adjacency ' + key + '.')
    # Reject contradictory duplicate copies instead of silently choosing one.
    if 'atlas_adjacency' in result and 'atlas_adjacency' in report:
        if _digest(result['atlas_adjacency']) != _digest(report['atlas_adjacency']):
            _fail('Conflicting adjacency ledger copies.')
    return ledger


def _orient(a, b, c):
    x, y = b - a, c - a
    left, right = float(x[0] * y[1]), float(x[1] * y[0])
    determinant = left - right
    if abs(determinant) > 16 * np.finfo(float).eps * (abs(left) + abs(right)):
        return 1 if determinant > 0 else -1
    # Rare near-collinear cases use exact binary64 predicates. No tolerance
    # can convert an unapproved near miss/crossing into an allowed seam.
    ax, ay, bx, by, cx, cy = map(Fraction, map(float, (*a, *b, *c)))
    exact = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    return (exact > 0) - (exact < 0)


def _between(p, a, b):
    return bool(np.all(p >= np.minimum(a, b)) and np.all(p <= np.maximum(a, b)))


def _inside(point, polygon):
    winding = 0
    for a, b in zip(polygon, np.roll(polygon, -1, axis=0)):
        sign = _orient(a, b, point)
        if sign == 0 and _between(point, a, b):
            return 0
        if a[1] <= point[1] < b[1] and sign > 0:
            winding += 1
        elif b[1] <= point[1] < a[1] and sign < 0:
            winding -= 1
    return 1 if winding else -1


def _merge(values):
    out = []
    for value in sorted(values):
        if not out or value - out[-1] > 2e-13:
            out.append(float(value))
    return out


class _Screen:
    def __init__(self, model, result, cancelled):
        self.model, self.result, self.cancelled = model, result, cancelled
        self.sk, self.rv = _module('skin_kernel'), _module('repaired_validation')
        self.started = time.monotonic()
        self.deadline = self.started + MAX_SECONDS
        self.metrics = dict(normal_samples=0, boundary_segments=0, intersection_tests=0,
                            pair_work=0, evaluation_work=0, containment_tests=0, positive_radius_excluded=0.,
                            shared_station_snap_maximum=0., global_injectivity_certified=False)
        self.check()
        self.binding = _binding(result, model, result.get('edit_request'))
        self.ledger = _checked_ledger(result, self.binding)
        self.adjacency_digest = _digest(self.ledger)
        self.surfaces = result.get('surfaces', [])
        if not 1 <= len(self.surfaces) <= MAX_SURFACES:
            _fail('Atlas surface-count budget exceeded.')
        self.tol = float(getattr(model, 'tolerance', _spec(model).get('absolute_tolerance', 1e-8)))
        if not math.isfinite(self.tol) or self.tol <= 0:
            _fail('A finite positive model tolerance is required.')
        self.evaluators, self.stations, self.collapsed = [], {}, set()
        self.count = 0
        for i, record in enumerate(self.surfaces):
            self.check()
            cp = np.asarray(record['homogeneous_cp'], float)
            pu, pv = int(record['degree_u']), int(record['degree_v'])
            if cp.ndim != 3 or cp.shape[-1] != 4:
                _fail('Invalid homogeneous control net.')
            count = cp.shape[0] * cp.shape[1]
            self.count += count
            if count > MAX_CONTROL_POINTS or self.count > MAX_AGGREGATE_CONTROL_POINTS:
                _fail('Atlas control-net budget exceeded.')
            if not 1 <= min(pu, pv) or max(pu, pv) > 40 or not np.isfinite(cp).all() or np.min(cp[:, :, 3]) <= 0:
                _fail('Invalid atlas degree, weights or coefficients.')
            d = self.rv._domain(record)
            for axis, degree, number in ((0, pu, cp.shape[0]), (1, pv, cp.shape[1])):
                knots = np.asarray(record['knots_u' if axis == 0 else 'knots_v'], float)
                if (len(knots) != number + degree + 1 or not np.isfinite(knots).all() or
                        np.any(np.diff(knots) < 0) or
                        not np.array_equal(d[axis], [knots[degree], knots[-degree-1]])):
                    _fail('Invalid atlas active knot domain.')
                breaks = sorted(set([0., 1.] + [(float(k)-d[axis, 0]) / np.ptp(d[axis])
                                               for k in knots if d[axis, 0] < k < d[axis, 1]]))
                if any(b-a <= 4e-13*_STEPS for a,b in zip(breaks[:-1],breaks[1:])):
                    _fail('A native knot span is unresolved at the bounded station precision.')
                stations = _merge(t for a, b in zip(breaks[:-1], breaks[1:])
                                  for t in np.linspace(a, b, _STEPS + 1))
                for edge in (('bottom', 'top') if axis == 0 else ('left', 'right')):
                    self.stations[i, edge] = stations[:]
            self.evaluators.append(self.sk._Evaluator(record))
            if record.get('kind') == 'upper_hard_corner':
                self.approved_pole(i, record)
        self.pairs = self.parse_pairs()
        self.signs = self.orientations()
        self.metrics['sampling'] = '16 subdivisions of every nonzero native knot span; shared affine station union'
        self.metrics['boundary_approximation'] = 'straight projected chords; no all-parameter curve enclosure'
        self.metrics['seam_snap_bound_relative'] = 1e-10
        self.metrics['surfaces'] = len(self.surfaces)
        self.metrics['control_points'] = self.count

    def check(self, work=0):
        self.sk._check(self.cancelled)
        self.metrics['pair_work'] += work
        if self.metrics['pair_work'] > MAX_PAIR_WORK or time.monotonic() > self.deadline:
            _fail('Atlas separation time/work budget exceeded.')

    def evaluation_check(self, work):
        self.metrics['evaluation_work'] += int(work)
        self.check()
        if self.metrics['evaluation_work'] > MAX_EVALUATION_WORK:
            _fail('Atlas evaluation-work budget exceeded.')

    def approved_pole(self, i, record):
        report = self.result['report']
        role = record.get('boundary_roles', {}).get('bottom', {})
        identity = record.get('approved_physical_corner_id')
        matches = [x for x in report.get('upper_radial_certificates', []) if x.get('surface_index') == i]
        if (identity not in ('upper:side0', 'upper:side1') or
                identity not in report.get('hard_corner_curvature', {}).get('physical_points', []) or
                role.get('role') != 'approved_source_vertex' or role.get('corner_id') != identity or
                role.get('physical_dimension') != 0 or len(matches) != 1 or
                record.get('collapsed_parameter_edge') != 'v=0' or
                record.get('side') != int(identity[-1]) or
                report.get('hard_corner_curvature', {}).get('positive_radius_excluded', 0.) != 0.):
            _fail('Unapproved collapsed chart point.')
        certificate = matches[0]
        proof = certificate.get('proof', {})
        if (certificate.get('passed') is not True or proof.get('local_immersion_certified') is not True or
                proof.get('excluded_positive_radius') != 0. or
                proof.get('constant_homogeneous_pole_row') is not True or
                proof.get('radial_factor', {}).get('quotient_strictly_positive_on_closed_square') is not True or
                proof.get('physical_corner_id') != identity or
                not np.array_equal(self.rv._domain(record), [[0., 1.], [0., 1.]])):
            _fail('Missing exact upper positive-radius certificate.')
        # The preceding source-bound validator owns physical approval; this
        # module only consumes that checked result and never asserts provenance.
        self.collapsed.add((i, 'bottom'))

    def parse_pairs(self):
        raw = self.ledger.get('shared_edges')
        if not isinstance(raw, list) or len(raw) > 8 * MAX_SURFACES:
            _fail('Atlas shared-edge budget or schema invalid.')
        pairs = []
        for item in raw:
            indices, edges = item['surface_indices'], item['edges']
            intervals = np.asarray(item['normalized_intervals'], float)
            if (len(indices) != 2 or len(edges) != 2 or
                    any(type(i) is not int or not 0 <= i < len(self.surfaces) for i in indices) or
                    indices[0] == indices[1] or any(e not in _EDGES for e in edges) or
                    intervals.shape != (2, 2) or not np.isfinite(intervals).all() or
                    np.any(intervals < 0) or np.any(intervals > 1) or
                    np.any(intervals[:, 0] == intervals[:, 1]) or
                    item.get('normal_orientation') not in (-1, 1)):
                _fail('Invalid checked affine seam record.')
            orientation = 1 if np.prod(intervals[:, 1] - intervals[:, 0]) > 0 else -1
            if item.get('parameter_orientation') != orientation:
                _fail('Affine seam parameter orientation disagrees.')
            pairs.append((tuple(indices), tuple(edges), intervals, item['normal_orientation']))
        return pairs

    def orientations(self):
        graph = defaultdict(list)
        for (i, j), _, _, sign in self.pairs:
            graph[i].append((j, sign)); graph[j].append((i, sign))
        signs = {}
        for start in range(len(self.surfaces)):
            if start in signs:
                continue
            signs[start] = -1 if self.surfaces[start].get('orientation_reversed', False) else 1
            stack = [start]
            while stack:
                i = stack.pop()
                for j, parity in graph[i]:
                    expected = signs[i] * parity
                    if j in signs and signs[j] != expected:
                        _fail('Nonorientable checked adjacency.')
                    if j not in signs:
                        signs[j] = expected; stack.append(j)
        return signs

    def projection(self):
        normals, first_tangent = [], None
        for i, record in enumerate(self.surfaces):
            self.check()
            d = self.rv._domain(record)
            us = self.stations[i, 'bottom']
            vs = self.stations[i, 'left']
            if (i, 'bottom') in self.collapsed:
                vs = [v for v in vs if v != 0.] + [1e-6, 1e-4, 1e-2]
            number = len(us) * len(vs)
            self.metrics['normal_samples'] += number
            if self.metrics['normal_samples'] > MAX_NORMAL_SAMPLES:
                _fail('Atlas normal-sample budget exceeded.')
            ev = self.evaluators[i]
            self.evaluation_check(3 * (len(us)*ev.cp.shape[0]*ev.cp.shape[1] +
                                      len(us)*len(vs)*ev.cp.shape[1]))
            u, v = d[0, 0] + np.asarray(us)*np.ptp(d[0]), d[1, 0] + np.asarray(vs)*np.ptp(d[1])
            h = np.einsum('ua,abk,vb->uvk', ev.bu(u), ev.local_cp, ev.bv(v), optimize=True)
            hu = np.einsum('ua,abk,vb->uvk', ev.bu(u, nu=1), ev.local_cp, ev.bv(v), optimize=True)
            hv = np.einsum('ua,abk,vb->uvk', ev.bu(u), ev.local_cp, ev.bv(v, nu=1), optimize=True)
            du = (hu[..., :3] - h[..., :3] * (hu[..., 3] / h[..., 3])[..., None]) / h[..., 3, None]
            dv = (hv[..., :3] - h[..., :3] * (hv[..., 3] / h[..., 3])[..., None]) / h[..., 3, None]
            n = np.cross(du, dv).reshape(-1, 3)
            lengths = np.linalg.norm(n, axis=1)
            if not np.isfinite(n).all() or np.any(lengths == 0):
                _fail('A finite chart sample has a singular tangent frame.')
            normals.extend(self.signs[i] * n / lengths[:, None])
            if first_tangent is None:
                first_tangent = du.reshape(-1, 3)[len(n)//2]
        normals = np.asarray(normals)
        # A data-derived basis makes the LP covariant under rigid transforms;
        # there is no fixed world projection or model-specific vector.
        nz = np.sum(normals, axis=0)
        if np.linalg.norm(nz) == 0:
            _fail('No common oriented sampled projection.')
        nz /= np.linalg.norm(nz)
        nx = first_tangent - nz * (first_tangent @ nz)
        if np.linalg.norm(nx) <= 1e-12 * np.linalg.norm(first_tangent):
            _fail('Cannot derive a stable source-bound projection frame.')
        nx /= np.linalg.norm(nx)
        frame = np.stack([nx, np.cross(nz, nx), nz], axis=1)
        self.check()
        remaining = max(.001, self.deadline - time.monotonic())
        fit = linprog([0., 0., 0., -1.], A_ub=np.c_[-normals @ frame, np.ones(len(normals))],
                      b_ub=np.zeros(len(normals)), bounds=[(-1., 1.)]*3 + [(None, None)],
                      method='highs', options={'time_limit': remaining})
        self.check()
        if not fit.success or not np.isfinite(fit.x).all():
            _fail('No bounded common sampled projection: ' + str(fit.message))
        normal = frame @ fit.x[:3]
        if np.linalg.norm(normal) == 0:
            _fail('Common sampled projection is zero.')
        normal /= np.linalg.norm(normal)
        margin = float(np.min(normals @ normal))
        if margin <= 1e-9:
            _fail('Common projected normal-cone margin is unresolved.')
        x = first_tangent - normal * (first_tangent @ normal)
        if np.linalg.norm(x) <= 1e-12 * np.linalg.norm(first_tangent):
            _fail('Projected source tangent is unresolved.')
        x /= np.linalg.norm(x)
        self.basis = np.stack([x, np.cross(normal, x)], axis=1)
        self.metrics['minimum_sampled_projected_normal'] = margin
        self.metrics['projection_normal'] = normal.tolist()

    def synchronize(self):
        for iteration in range(64):
            self.check()
            changed = False
            for indices, edges, intervals, _ in self.pairs:
                keys = list(zip(indices, edges))
                for side in (0, 1):
                    a, b = intervals[side], intervals[1-side]
                    station = self.stations[keys[side]]
                    q = [(t-a[0])/(a[1]-a[0]) for t in station
                         if min(a)-2e-13 <= t <= max(a)+2e-13]
                    target = self.stations[keys[1-side]]
                    union = _merge(target + list(b) + [float(b[0]+min(1.,max(0.,t))*(b[1]-b[0])) for t in q])
                    if len(union) != len(target):
                        changed = True
                    self.stations[keys[1-side]] = union
            if sum(map(len, self.stations.values())) > MAX_BOUNDARY_SEGMENTS + 4*MAX_SURFACES:
                _fail('Synchronized atlas boundary budget exceeded.')
            if not changed:
                self.metrics['station_union_iterations'] = iteration + 1
                return
        _fail('Shared-edge station union did not converge within its budget.')

    def boundaries(self):
        self.synchronize()
        node_ids, positions, parents = {}, [], []
        def find(i):
            while parents[i] != i:
                parents[i] = parents[parents[i]]; i = parents[i]
            return i
        def union(a, b):
            a, b = find(a), find(b)
            if a != b:
                parents[max(a, b)] = min(a, b)
        for key, stations in self.stations.items():
            self.check()
            i, edge = key
            ids = []
            for station_index, t in enumerate(stations):
                if station_index % 32 == 0:
                    self.check()
                self.evaluation_check(9 * self.evaluators[i].cp.shape[0] * self.evaluators[i].cp.shape[1])
                ids.append(len(positions)); parents.append(len(parents))
                positions.append(self.evaluators[i].jets(*self.rv._edge_uv(self.surfaces[i], edge, t))[0])
            node_ids[key] = ids
        for i in range(len(self.surfaces)):
            for a, ai, b, bi in (('bottom', 0, 'left', 0), ('bottom', -1, 'right', 0),
                                  ('top', 0, 'left', -1), ('top', -1, 'right', -1)):
                union(node_ids[i, a][ai], node_ids[i, b][bi])
        memberships = defaultdict(list)
        for seam, (indices, edges, intervals, _) in enumerate(self.pairs):
            keys = list(zip(indices, edges))
            for key, interval in zip(keys, intervals):
                memberships[key].append((seam, min(interval), max(interval)))
            a, b = intervals
            other = np.asarray(self.stations[keys[1]])
            for t, node in zip(self.stations[keys[0]], node_ids[keys[0]]):
                q = (t-a[0])/(a[1]-a[0])
                if -2e-12 <= q <= 1.+2e-12:
                    target = b[0]+min(1.,max(0.,q))*(b[1]-b[0])
                    k = int(np.argmin(np.abs(other-target)))
                    if abs(other[k]-target) > 2e-12:
                        _fail('Shared station matching is unresolved.')
                    union(node, node_ids[keys[1]][k])
        for key in self.collapsed:
            ids = node_ids[key]
            for node in ids[1:]:
                union(ids[0], node)
        positions = np.asarray(positions)
        origin = positions[0].copy()
        self.scale = float(np.max(np.linalg.norm(positions-origin, axis=1)))
        if not math.isfinite(self.scale) or self.scale <= 0:
            _fail('Atlas projected extent is zero or invalid.')
        groups = defaultdict(list)
        for node in range(len(positions)):
            groups[find(node)].append(node)
        normalized = (positions-origin)/self.scale
        canonical = {}
        for root, nodes in groups.items():
            delta = float(np.max(np.linalg.norm(normalized[nodes]-normalized[root], axis=1)))
            self.metrics['shared_station_snap_maximum'] = max(self.metrics['shared_station_snap_maximum'], delta*self.scale)
            if delta*self.scale > min(self.tol, 1e-10*self.scale):
                _fail('Checked seam stations no longer coincide within the numerical snap bound.')
            canonical[root] = np.mean(normalized[nodes], axis=0) @ self.basis
        self.segments, self.polygons = [], []
        for i in range(len(self.surfaces)):
            self.check()
            chart = []
            for edge in _EDGES:
                ids, ts = node_ids[i, edge], self.stations[i, edge]
                order = list(range(len(ids)))
                if edge in ('top', 'left'):
                    order.reverse()
                if (i, edge) in self.collapsed:
                    continue
                for a, b in zip(order[:-1], order[1:]):
                    roots = (find(ids[a]), find(ids[b]))
                    p, q = [canonical[x] for x in roots]
                    if roots[0] == roots[1] or np.array_equal(p, q):
                        _fail('Unapproved collapsed finite boundary segment.')
                    seam_ids = {s for s, lo, hi in memberships[i, edge]
                                if min(ts[a],ts[b]) >= lo-2e-12 and max(ts[a],ts[b]) <= hi+2e-12}
                    chart.append(dict(chart=i, edge=edge, roots=roots, p=p, q=q, seams=seam_ids))
            if len(chart) < 3:
                _fail('Projected chart boundary has fewer than three segments.')
            for k, segment in enumerate(chart):
                segment['position'], segment['length'] = k, len(chart)
                if segment['roots'][1] != chart[(k+1)%len(chart)]['roots'][0]:
                    _fail('Projected chart boundary is not closed.')
            polygon = np.asarray([s['p'] for s in chart])
            area = float(np.sum(polygon[:,0]*np.roll(polygon[:,1],-1)-polygon[:,1]*np.roll(polygon[:,0],-1)))
            if not math.isfinite(area) or area*self.signs[i] <= 0:
                _fail('Projected chart boundary orientation is inconsistent.')
            self.segments.extend(chart); self.polygons.append(polygon)
        self.metrics['boundary_segments'] = len(self.segments)
        if len(self.segments) > MAX_BOUNDARY_SEGMENTS:
            _fail('Atlas boundary segment budget exceeded.')
        self.origin = origin

    def intersections(self):
        segments = self.segments
        lower = np.asarray([np.minimum(s['p'],s['q']) for s in segments])
        upper = np.asarray([np.maximum(s['p'],s['q']) for s in segments])
        for i, a in enumerate(segments):
            self.check(len(segments)-i-1)
            hits = np.flatnonzero(np.all(lower[i+1:] <= upper[i],axis=1) &
                                  np.all(upper[i+1:] >= lower[i],axis=1)) + i+1
            for candidate_index, j in enumerate(hits):
                if candidate_index % 32 == 0:
                    self.check()
                b = segments[int(j)]
                self.metrics['intersection_tests'] += 1
                if self.metrics['intersection_tests'] > MAX_INTERSECTION_TESTS:
                    _fail('Atlas segment-intersection budget exceeded.')
                same = a['chart'] == b['chart']
                shared = a['seams'] & b['seams']
                if shared and set(a['roots']) == set(b['roots']):
                    # A seam may meet only opposite oriented chart interiors.
                    ar = a['roots'] if self.signs[a['chart']] > 0 else a['roots'][::-1]
                    br = b['roots'] if self.signs[b['chart']] > 0 else b['roots'][::-1]
                    if ar != br[::-1]:
                        _fail('Shared projected seam has overlapping chart interiors.')
                    continue
                p,q,r,s = a['p'],a['q'],b['p'],b['q']
                o1,o2,o3,o4 = _orient(p,q,r),_orient(p,q,s),_orient(r,s,p),_orient(r,s,q)
                if o1*o2 < 0 and o3*o4 < 0:
                    _fail('Projected boundary crossing between charts %d and %d.' % (a['chart'],b['chart']))
                contacts=[]
                for sign,point,left,right,node,ends in ((o1,r,p,q,b['roots'][0],a['roots']),
                    (o2,s,p,q,b['roots'][1],a['roots']), (o3,p,r,s,a['roots'][0],b['roots']),
                    (o4,q,r,s,a['roots'][1],b['roots'])):
                    if sign == 0 and _between(point,left,right):
                        contacts.append((node,ends))
                if not contacts:
                    continue
                adjacent = same and ((a['position']-b['position']) % a['length'] in (1,a['length']-1))
                if (same and not adjacent) or any(node not in ends for node,ends in contacts):
                    _fail('Unapproved projected boundary contact between charts %d and %d.' % (a['chart'],b['chart']))
                if o1 == o2 == o3 == o4 == 0 and len(set(a['roots']) & set(b['roots'])) != 1:
                    _fail('Unapproved projected coincident boundary segments.')

    def containment(self):
        for i, record in enumerate(self.surfaces):
            self.check()
            uv = np.mean(self.rv._domain(record),axis=1)
            point = ((self.evaluators[i].jets(*uv)[0]-self.origin)/self.scale) @ self.basis
            if _inside(point,self.polygons[i]) != 1:
                _fail('Projected chart interior sample is outside its simple boundary.')
            for j, polygon in enumerate(self.polygons):
                if i == j:
                    continue
                self.check()
                self.metrics['containment_tests'] += 1
                if _inside(point,polygon) >= 0:
                    _fail('Projected chart interior containment/contact between charts %d and %d.' % (i,j))

    def run(self):
        self.projection(); self.boundaries(); self.intersections(); self.containment()
        self.check()
        if _binding(self.result,self.model,self.result.get('edit_request')) != self.binding:
            _fail('Source, geometry or request changed during atlas separation.')
        if _digest(_checked_ledger(self.result, self.binding)) != self.adjacency_digest:
            _fail('Checked adjacency changed during atlas separation.')
        self.metrics['elapsed_seconds'] = time.monotonic()-self.started
        return self.metrics


def screen_atlas(model, result, cancelled=None):
    """Attach and return a fresh finite cap/cap screen, never a global proof."""
    result.pop('atlas_separation', None)
    receipt = dict(schema=_SCHEMA, checked=False, passed=False,
                   global_injectivity_certified=False, method=_METHOD,
                   source_digest=None, geometry_digest=None, request_digest=None, metrics={})
    screen = None
    try:
        screen = _Screen(model,result,cancelled)
        receipt.update(screen.binding)
        receipt['adjacency_digest'] = screen.adjacency_digest
        receipt['metrics'] = screen.run()
        receipt.update(checked=True,passed=True,
                       reason='Bounded projected atlas boundary and containment screen passed; finite sampling is not a global injectivity certificate.')
    except _module('skin_kernel').Cancelled:
        result.pop('atlas_separation',None)
        raise
    except (ValueError,KeyError,TypeError,IndexError,AttributeError,ArithmeticError,np.linalg.LinAlgError) as error:
        if screen is not None:
            receipt['metrics'] = screen.metrics
        receipt['reason'] = 'ATLAS_SEPARATION: '+str(error)
    result['atlas_separation'] = receipt
    return receipt
