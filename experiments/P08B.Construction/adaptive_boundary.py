# -*- coding: utf-8 -*-
"""P08B.2F2: bounded residual-directed boundary fitting before frozen-row jets.
Standard Python 2.7/3. No Rhino, document, network or file access.
All distances here use sampled known correspondence, never a certified global bound.
The released numerical kernel and its derivative refinement are unchanged.
"""
from __future__ import division
from mixed_kernel import SIDES, Patch, basis, knots, qr_fit, finite, norm, sub, add, mul


class BoundaryFitResult(object):
    def __init__(self, patch, evidence, history, reason, validation_sites):
        self.patch = patch
        self.evidence = evidence
        self.history = history
        self.reason = reason
        self.validation_sites = validation_sites
        self.commit_allowed = False


def check(checkpoint):
    if checkpoint is not None:
        checkpoint()


def knot_spans(K):
    return [(a, b) for a, b in zip(K, K[1:]) if b > a]


def fit_sites(func, K, count=97):
    points = set(i / (count - 1) for i in range(count))
    points.update(getattr(func, 'parameters', ()))
    # Every positive knot span has multiple interior data sites, including after
    # highly local refinement. Do not build rank-deficient fits with empty spans.
    for a, b in knot_spans(K):
        points.update(a + (b - a) * f for f in (.2, .5, .8))
    return sorted(t for t in points if finite(t) and 0 <= t <= 1)


def validation_sites(func, K, count=257):
    # Deliberately different from the fit lattice. Shared original junctions are
    # checked too; this is not a holdout probability bound or a native deviation.
    points = {0.0, 1.0}
    points.update((i + .38196601125) / count for i in range(count))
    points.update(getattr(func, 'parameters', ()))
    for a, b in knot_spans(K):
        points.update(a + (b - a) * f for f in (.031, .113, .307, .619, .887, .969))
    return sorted(t for t in points if finite(t) and 0 <= t <= 1)


def curve_point(control, p, K, t, basis_cache=None):
    b = basis_cache.get(t) if basis_cache is not None else None
    if b is None:
        b = basis(len(control), p, t, K)[0]
        if basis_cache is not None:
            basis_cache[t] = b
    return tuple(sum(c * pt[k] for c, pt in zip(b, control) if c) for k in range(3))


def fit_curve(func, K, p, first, last, checkpoint=None, basis_cache=None):
    n = len(K) - p - 1
    A, Y = [], []
    for t in fit_sites(func, K):
        check(checkpoint)
        b = basis_cache.get(t) if basis_cache is not None else None
        if b is None:
            b = basis(n, p, t, K)[0]
            if basis_cache is not None:
                basis_cache[t] = b
        pt = func(t).point
        A.append(b[1:-1])
        Y.append(sub(sub(pt, mul(first, b[0])), mul(last, b[-1])))
    # Same endpoint-constrained Householder LS as the original kernel, now on
    # an explicitly nonuniform, residual-refined knot vector.
    result = [first] + qr_fit(A, Y) + [last]
    check(checkpoint)
    return result


def inspect_curves(boundaries, controls, K, p, target, tolerance, checkpoint=None):
    reports, sites = {}, {}
    cache = {}
    for side in SIDES:
        func = boundaries[side]
        sites[side] = validation_sites(func, K)
        maximum, witness = -1.0, None
        by_source = {}
        for t in sites[side]:
            check(checkpoint)
            support = func(t)
            point = curve_point(controls[side], p, K, t, cache)
            gap = norm(sub(point, support.point))
            if not finite(gap):
                raise ValueError('BOUNDARY_FIT_NONFINITE_RESIDUAL')
            if support.key not in by_source:
                by_source[support.key] = {'gap': 0.0, 'count': 0, 'preferred': support.preferred}
            record = by_source[support.key]
            record['gap'] = max(record['gap'], gap)
            record['count'] += 1
            if gap > maximum:
                maximum = gap
                witness = {'parameter': float(t), 'source_key': support.key,
                           'target_point': tuple(support.point), 'fitted_point': point}
        reports[side] = {'gap': maximum, 'witness': witness, 'sources': by_source,
                         'samples': len(sites[side])}
    maximum = max(r['gap'] for r in reports.values())
    return {'gap': maximum, 'target': target, 'document_tolerance': tolerance,
            'target_sampled_met': maximum <= target,
            'document_sampled_met': maximum <= tolerance,
            'sides': reports, 'scope': 'SAMPLED_CORRESPONDENCE;NOT_NATIVE_JOIN;NO_GLOBAL_BOUND',
            'commit_allowed': False}, sites


def coons_from_curves(controls, corners, p, K):
    n = len(K) - p - 1
    p00, p10, p01, p11 = corners
    g = [sum(K[i+1:i+p+1]) / p for i in range(n)]
    net = []
    for i, u in enumerate(g):
        row = []
        for j, v in enumerate(g):
            a = add(mul(controls['bottom'][i], 1-v), mul(controls['top'][i], v))
            a = add(a, add(mul(controls['left'][j], 1-u), mul(controls['right'][j], u)))
            bilinear = add(add(mul(p00, (1-u)*(1-v)), mul(p10, u*(1-v))),
                           add(mul(p01, (1-u)*v), mul(p11, u*v)))
            row.append(sub(a, bilinear))
        net.append(row)
    for i in range(n):
        net[i][0], net[i][-1] = controls['bottom'][i], controls['top'][i]
    for j in range(n):
        net[0][j], net[-1][j] = controls['left'][j], controls['right'][j]
    return Patch(net, p, K)


def insertions_for_residuals(K, evidence, target, maximum_count):
    """Insert only SIMPLE interior knots. No automatic crease/multiplicity change.
    Refitting, not knot insertion alone, is what changes the approximating curves.
    """
    choices = []
    for side in SIDES:
        report = evidence['sides'][side]
        if report['gap'] <= target:
            continue
        t = report['witness']['parameter']
        spans = [(a, b) for a, b in knot_spans(K) if a <= t <= b and b-a > 1e-8]
        if not spans:
            continue
        # A knot/endpoint witness is associated with a neighboring nonzero span.
        # Clamp the insertion into that span, rather than create duplicates.
        a, b = max(spans, key=lambda ab: ab[1]-ab[0])
        value = max(a + .2*(b-a), min(b - .2*(b-a), t))
        choices.append((report['gap'], side, value))
    chosen = []
    for gap, side, value in sorted(choices, reverse=True):
        if len(chosen) >= maximum_count:
            break
        if min(abs(value - old) for old in K) <= 1e-10:
            continue
        if any(abs(value - old['parameter']) <= 1e-10 for old in chosen):
            continue
        chosen.append({'parameter': value, 'trigger_side': side, 'sampled_gap': gap})
    return chosen


def adaptive_coons(boundaries, n=10, p=3, tolerance=.01, target_fraction=.25,
                   max_controls=32, max_rounds=10, checkpoint=None, on_step=None):
    """Fit/inspect/refit with a bounded *tighter* internal position objective.
    Returns the best fitted baseline even after a later bad refit. This is NOT a
    retained native/Join-verified preview, and no returned state permits commit.
    Public document tolerance and each original preferred grade remain untouched.
    """
    if p != 3 or not 4 <= n <= max_controls <= 32 or not 0 <= max_rounds <= 12:
        raise ValueError('BOUNDARY_FIT_COMPLEXITY_LIMIT')
    if not finite(tolerance) or tolerance <= 0 or not finite(target_fraction) or not 0 < target_fraction < 1:
        raise ValueError('BOUNDARY_FIT_INVALID_TOLERANCE')
    if set(boundaries) != set(SIDES):
        raise ValueError('FOUR_BOUNDARY_CALLBACKS_REQUIRED')
    if any(len(getattr(f, 'parameters', ())) > 128 for f in boundaries.values()):
        raise ValueError('BOUNDARY_PARAMETER_BUDGET')
    check(checkpoint)
    b, r, t, l = [boundaries[s] for s in SIDES]
    pairs = ((b(0).point, l(0).point), (b(1).point, r(0).point),
             (t(0).point, l(1).point), (t(1).point, r(1).point))
    if any(norm(sub(a, z)) > tolerance for a, z in pairs):
        raise ValueError('OPEN_BOUNDARY_CORNER')
    corners = [mul(add(a, z), .5) for a, z in pairs]
    p00, p10, p01, p11 = corners
    ends = {'bottom': (p00, p10), 'right': (p10, p11),
            'top': (p01, p11), 'left': (p00, p01)}
    K, target = knots(n, p), tolerance * target_fraction
    best, history = None, []
    reason = 'BOUNDARY_FIT_BUDGET_REACHED'
    for iteration in range(max_rounds + 1):
        check(checkpoint)
        count = len(K) - p - 1
        cache = {}
        try:
            controls = {s: fit_curve(boundaries[s], K, p, ends[s][0], ends[s][1], checkpoint, cache)
                        for s in SIDES}
            evidence, sites = inspect_curves(boundaries, controls, K, p, target, tolerance, checkpoint)
        except ValueError as error:
            if best is None:
                raise
            reason = 'BOUNDARY_REFIT_FAILED;previous_fitted_baseline_retained'
            record = {'round': iteration, 'controls': count, 'error': str(error), 'kept': False}
            history.append(record)
            if on_step is not None:
                on_step(record)
            break
        kept = best is None or evidence['gap'] < best[0]['gap']
        if kept:
            best = (evidence, controls, list(K), sites)
        record = {'round': iteration, 'controls': count, 'evidence': evidence,
                  'knots': tuple(K), 'kept': kept, 'best_gap': best[0]['gap']}
        history.append(record)
        if on_step is not None:
            on_step(record)
        if evidence['target_sampled_met']:
            reason = 'BOUNDARY_TARGET_SAMPLED_MET'
            break
        if iteration == max_rounds or count >= max_controls:
            break
        added = insertions_for_residuals(K, evidence, target, min(4, max_controls-count))
        if not added:
            reason = 'BOUNDARY_FIT_NO_ADMISSIBLE_INSERTION'
            break
        record['inserted'] = added
        K = sorted(K + [row['parameter'] for row in added])
    if best is None:
        raise ValueError('BOUNDARY_FIT_NO_FINITE_BASELINE')
    evidence, controls, K, sites = best
    patch = coons_from_curves(controls, corners, p, K)
    return BoundaryFitResult(patch, evidence, history, reason, sites)
