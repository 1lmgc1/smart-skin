"""Analytic synthetic localized boundary detail; no private model data.
Parameters are arbitrary and do not reproduce a user's curves or face jets.
"""
from __future__ import division
import math
from mixed_kernel import Support, SIDES, side_uv, frame


def bump(u):
    # Smooth narrow endpoint neighborhoods deliberately underresolved by a
    # globally uniform small spline. Endpoints are precisely zero.
    return .64*u*(1-u)*(math.exp(-((u-.081)/.024)**2)+math.exp(-((u-.919)/.024)**2))


def base_surface(u, v):
    a = .35
    return ((u, v, a*u*(1-u)*v*(1-v)),
            (1, 0, a*(1-2*u)*v*(1-v)),
            (0, 1, a*u*(1-u)*(1-2*v)),
            (0, 0, -2*a*v*(1-v)),
            (0, 0, a*(1-2*u)*(1-2*v)),
            (0, 0, -2*a*u*(1-u)))


def localized_boundaries():
    result = {}
    for side in SIDES:
        def func(t, side=side):
            u, v = side_uv(side, t)
            values = base_surface(u, v)
            point = values[0]
            if side == 'top':
                point = (point[0], point[1], point[2]+bump(t))
            n, H = frame(values)
            if side in ('bottom', 'top'):
                key = side + ('_first' if t <= .5 else '_second')
                return Support(point, n, H, key, 0, .5)
            return Support(point, n, H, side, 2, 1.0)
        func.parameters = (0, .25, .5-1e-5, .5, .5+1e-5, .75, 1)
        result[side] = func
    return result
