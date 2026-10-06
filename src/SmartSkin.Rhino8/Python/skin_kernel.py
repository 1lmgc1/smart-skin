"""Bounded native-network skin construction, independent of Rhino.

Five prescribed geometric-Hermite sections, nine fixed longitudinal rows,
quintic native-jet collars, and four central bands. The only live parameter is
``h``: native first/second cross handles scale by h/h**2. Correspondence,
profiles, native source knots, and artificial joins never depend on h.

This is an experimental bounded-family constructor, not a global G2 solver.
Validation is finite sampled evidence; source boundary corner failures remain
visible. Homogeneous upper curves are retained algebraically, including weights
arbitrarily close to one. All public knots are FULL standard B-spline knots;
Rhino's compact knot collections omit the first and last entries.

Compatible dependencies: numpy 1.26.4, scipy 1.13.1, mpmath 1.3.0.
"""
from __future__ import annotations

import math
import time
from functools import lru_cache

import mpmath as mp
import numpy as np
from scipy.integrate import quad
from scipy.interpolate import BSpline, CubicSpline
from scipy.optimize import brentq


class UnsupportedFamily(ValueError):
    """The input cannot be represented safely by this bounded construction."""


class Cancelled(RuntimeError):
    """Cooperative cancellation; no source or external state was changed."""


def _check(cancelled):
    if cancelled is not None and cancelled():
        raise Cancelled("Skin construction cancelled.")


def _obj(a):
    a = np.asarray(a)
    return np.vectorize(lambda x: mp.mpf(float(x)), otypes=[object])(a)


def _zeros(shape):
    a = np.empty(shape, dtype=object)
    a.fill(mp.mpf(0))
    return a


def _add(a, b):
    a, b = np.asarray(a, dtype=object), np.asarray(b, dtype=object)
    shape = tuple(max(x, y) for x, y in zip(a.shape, b.shape))
    out = _zeros(shape)
    out[tuple(slice(0, n) for n in a.shape)] += a
    out[tuple(slice(0, n) for n in b.shape)] += b
    return out


def _mul(a, b):
    """Univariate scalar polynomial times scalar/vector polynomial."""
    a, b = np.asarray(a, dtype=object), np.asarray(b, dtype=object)
    out = _zeros((len(a) + len(b) - 1,) + b.shape[1:])
    for i, x in enumerate(a):
        out[i:i + len(b)] += x * b
    return out


def _der(a, n=1):
    a = np.asarray(a, dtype=object)
    for _ in range(n):
        if len(a) == 1:
            return _zeros((1,) + a.shape[1:])
        a = np.asarray([a[i] * i for i in range(1, len(a))], dtype=object)
    return a


def _val(a, t):
    out = np.zeros(np.asarray(a).shape[1:], dtype=object)
    for c in a[::-1]:
        out = out * t + c
    return out


def _compose(a, q):
    a = np.asarray(a, dtype=object)
    out = a[-1:][:].copy()
    for c in a[-2::-1]:
        out = _mul(q, out)
        out[0] += c
    return out


@lru_cache(maxsize=80)
def _b2p_matrix(n):
    with mp.workdps(80):
        t = _zeros((n + 1, n + 1))
        for k in range(n + 1):
            for i in range(k + 1):
                t[k, i] = mp.mpf(math.comb(n, k) * math.comb(k, i) * (-1) ** (k-i))
        return t


@lru_cache(maxsize=120)
def _p2b_matrix(n, degree):
    with mp.workdps(80):
        t = _zeros((degree + 1, n + 1))
        for i in range(degree + 1):
            for k in range(min(i, n) + 1):
                t[i, k] = mp.mpf(math.comb(i, k)) / math.comb(degree, k)
        return t


def _axis_matrix(a, matrix, axis):
    return np.moveaxis(np.tensordot(matrix, np.moveaxis(a, axis, 0), axes=(1, 0)), 0, axis)


def bernstein_to_power(cp, axis=0):
    """High-precision Bernstein conversion on a normalized [0,1] span."""
    return _axis_matrix(_obj(cp) if np.asarray(cp).dtype != object else cp,
                        _b2p_matrix(np.asarray(cp).shape[axis] - 1), axis)


def power_to_bernstein(coefficients, degree=None, axis=0):
    """High-precision conversion/elevation; no point sampling or fitting."""
    a = np.asarray(coefficients, dtype=object)
    n = a.shape[axis] - 1
    degree = n if degree is None else degree
    if degree < n:
        raise ValueError("Cannot lower a polynomial degree without a proof.")
    return _axis_matrix(a, _p2b_matrix(n, degree), axis)


def _outer(a, b):
    return np.asarray(a, dtype=object)[:, None, None] * np.asarray(b, dtype=object)[None, :, :]


def _mul_u(w, tensor):
    out = _zeros((len(w) + tensor.shape[0] - 1, tensor.shape[1], tensor.shape[2]))
    for i, x in enumerate(w):
        out[i:i + tensor.shape[0]] += x * tensor
    return out


def _unit(v):
    v = np.asarray(v, dtype=float)
    length = float(np.linalg.norm(v))
    if not np.isfinite(length) or length <= 1e-14:
        raise UnsupportedFamily("A required native section tangent or plane normal is degenerate.")
    return v / length


def hermite_control_points(p0, p1, d0, d1, dd0, dd1):
    p0, p1, d0, d1, dd0, dd1 = [np.asarray(x) for x in (p0,p1,d0,d1,dd0,dd1)]
    return np.asarray([p0, p0+d0/5, p0+2*d0/5+dd0/20,
                       p1-2*d1/5+dd1/20, p1-d1/5, p1])


# Cardinal polynomials use normalized span coordinates; physical derivative
# cardinals multiply by span length and its square.
_C0 = _obj([1, 0, 0, -10, 15, -6])
_C1 = _obj([0, 1, 0, -6, 8, -3])
_C2 = _obj([0, 0, .5, -1.5, 1.5, -.5])
_C3 = _obj([0, 0, 0, 10, -15, 6])
_C4 = _obj([0, 0, 0, -4, 7, -3])
_C5 = _obj([0, 0, 0, .5, -1, .5])
_H3 = _obj([0, 0, 0, 1, 0, -6, 8, -3])
_H4 = _obj([0, 0, 0, 0, 1, -3, 3, -1])


def _curve_record(record):
    p = int(record['degree'])
    h = np.asarray(record.get('homogeneous_cp', record.get('homogeneousCP')), dtype=float)
    knots = np.asarray(record['knots'], dtype=float)
    if p < 1 or p > 8 or h.ndim != 2 or h.shape[1] != 4 or len(h) > 256:
        raise UnsupportedFamily("Unsupported native curve degree or control-point count.")
    if len(knots) != len(h) + p + 1 or np.any(np.diff(knots) < 0):
        raise UnsupportedFamily("Curve knots must be a full nondecreasing B-spline vector.")
    if not np.all(np.isfinite(h)) or np.min(h[:, 3]) <= 0:
        raise UnsupportedFamily("Native curve homogeneous weights must be finite and positive.")
    domain = tuple(record.get('domain', (knots[p], knots[-p-1])))
    if not (knots[p] <= domain[0] < domain[1] <= knots[-p-1]):
        raise UnsupportedFamily("Curve interval lies outside its native domain.")
    return p, h, knots, domain


def _bezier_segments(degree, cp, knots, breaks):
    """Exact knot insertion, retaining every requested and original source knot."""
    spline = BSpline(knots, cp, degree, extrapolate=False)
    for t in breaks:
        multiplicity = int(np.count_nonzero(spline.t == t))
        if multiplicity < degree:
            spline = spline.insert_knot(float(t), degree-multiplicity)
    result = []
    for a, b in zip(breaks[:-1], breaks[1:]):
        k = int(np.searchsorted(spline.t, (a+b)/2, side='right') - 1)
        result.append(np.asarray(spline.c[k-degree:k+1], dtype=float))
    return result


def _upper_pieces(path):
    pieces = []
    for segment in path:
        p, h, knots, domain = _curve_record(segment['curve'])
        ua, ub = map(float, segment['u_interval'])
        if not 0 <= ua < ub <= 1:
            raise UnsupportedFamily("Upper path intervals must partition [0,1].")
        breaks = sorted(set([domain[0], domain[1]] + [float(k) for k in knots if domain[0] < k < domain[1]]))
        controls = _bezier_segments(p, h, knots, breaks)
        reverse = bool(segment.get('reverse', False))
        for a,b,cp in zip(breaks[:-1], breaks[1:], controls):
            x,y = (a-domain[0])/(domain[1]-domain[0]), (b-domain[0])/(domain[1]-domain[0])
            if reverse:
                x,y,cp = 1-y,1-x,cp[::-1]
            pieces.append({'ua':ua+(ub-ua)*x, 'ub':ua+(ub-ua)*y,
                           'top':bernstein_to_power(cp), 'source_degree':p})
    pieces.sort(key=lambda x:x['ua'])
    if not pieces or len(pieces)>16 or abs(pieces[0]['ua'])>1e-12 or abs(pieces[-1]['ub']-1)>1e-12:
        raise UnsupportedFamily("Each upper path must cover [0,1] with at most sixteen native spans.")
    for left,right in zip(pieces[:-1],pieces[1:]):
        if abs(left['ub']-right['ua'])>1e-11:
            raise UnsupportedFamily("Upper path contains a gap or overlap in its parameter intervals.")
    return pieces


class _Side:
    def __init__(self, record):
        self.pu, self.pv = int(record['degree_u']), int(record['degree_v'])
        self.ku, self.kv = np.asarray(record['knots_u'],float),np.asarray(record['knots_v'],float)
        h=np.asarray(record.get('homogeneous_cp',record.get('homogeneousCP')),float)
        if h.ndim != 3 or h.shape[2]!=4 or max(self.pu,self.pv)>5 or min(self.pu,self.pv)<1:
            raise UnsupportedFamily("Side charts must be bounded natural nonrational tensor NURBS, degrees at most five.")
        if h.shape[0]>512 or h.shape[1]>128 or len(self.ku)!=h.shape[0]+self.pu+1 or len(self.kv)!=h.shape[1]+self.pv+1:
            raise UnsupportedFamily("Unsupported side-chart knot/control-point dimensions.")
        if not np.all(np.isfinite(h)) or h[0,0,3]<=0 or not np.all(h[:,:,3]==h[0,0,3]):
            raise UnsupportedFamily("This bounded family requires genuinely nonrational side charts.")
        if np.any(np.diff(self.ku)<0) or np.any(np.diff(self.kv)<0):
            raise UnsupportedFamily("Side-chart knot vectors must be nondecreasing.")
        self.cp=h[:,:,:3]/h[0,0,3]
        self.u0,self.u1=self.ku[self.pu],self.ku[-self.pu-1]
        self.v0,self.v1=self.kv[self.pv],self.kv[-self.pv-1]
        self.sign=float(record.get('source_cross_sign',-1.0))
        if self.sign not in (-1,1):
            raise UnsupportedFamily("Source cross direction must be +1 or -1.")
        self.bu=BSpline(self.ku,np.eye(h.shape[0]),self.pu,extrapolate=False)
        self.edge=[]
        for d in range(3):
            c=np.zeros((h.shape[1],3)) if d>self.pu else np.einsum('i,ijc->jc',self.bu(self.u0,nu=d),self.cp)
            self.edge.append(BSpline(self.kv,c,self.pv,extrapolate=False))
    def jet(self,v,du=0,dv=0):
        if dv>self.pv:
            return np.zeros(3)
        return self.edge[du](v,nu=dv)
    def span_jets(self,breaks):
        return [[bernstein_to_power(cp) for cp in _bezier_segments(self.pv,e.c,self.kv,breaks)] for e in self.edge]


def _spline_poly(spline,a,b):
    k=max(0,min(len(spline.x)-2,np.searchsorted(spline.x,(a+b)/2,side='right')-1))
    c=_obj(spline.c[:,k][::-1])
    return _compose(c,_obj([a-spline.x[k],b-a]))


def _tensor_u_restrict(tensor,a,b):
    return _compose(tensor,_obj([a,b-a]))


def _rational_u_jet(tensor,w,t,du=0):
    """Returns a vector polynomial in V, differentiated in normalized U."""
    num=[_val(_der(tensor,i),mp.mpf(t)) for i in range(du+1)]
    den=[_val(_der(w,i),mp.mpf(t)) for i in range(du+1)]
    out=[]
    for n in range(du+1):
        x=num[n].copy()
        for k in range(1,n+1):
            x-=math.comb(n,k)*den[k]*out[n-k]
        out.append(x/den[0])
    return out[-1]


def _jet_patch(patch,u,v,du=0,dv=0):
    a,b,c,d=patch['ua'],patch['ub'],patch['va'],patch['vb']
    p=_rational_u_jet(patch['p'],patch['w'],(u-a)/(b-a),du)
    return np.asarray(_val(_der(p,dv),mp.mpf((v-c)/(d-c))),float)/(b-a)**du/(d-c)**dv


def _point_curve(record,t,derivative=0):
    degree,h,knots,domain=_curve_record(record)
    sp=BSpline(knots,h,degree,extrapolate=False)
    jets=[sp(t,nu=d) if d<=degree else np.zeros(4) for d in range(derivative+1)]
    out=[]
    for n in range(derivative+1):
        x=jets[n][:3].copy()
        for k in range(1,n+1):
            x-=math.comb(n,k)*jets[k][3]*out[n-k]
        out.append(x/jets[0][3])
    return out[-1]


def evaluate_curve(record,t,derivative=0):
    """Evaluate a public rational curve descriptor in its physical domain."""
    return _point_curve(record,float(t),derivative)


def evaluate_surface(record,u,v,du=0,dv=0):
    """Rational tensor evaluation, including arbitrary mixed quotient jets."""
    cp=np.asarray(record.get('homogeneous_cp',record.get('homogeneousCP')),float)
    pu,pv=int(record['degree_u']),int(record['degree_v'])
    bu=BSpline(record['knots_u'],np.eye(cp.shape[0]),pu,extrapolate=False)
    bv=BSpline(record['knots_v'],np.eye(cp.shape[1]),pv,extrapolate=False)
    homogeneous={}
    out={}
    for i in range(du+1):
        for j in range(dv+1):
            homogeneous[i,j]=(np.einsum('a,b,abc->c',bu(u,nu=i),bv(v,nu=j),cp)
                              if i<=pu and j<=pv else np.zeros(4))
            x=homogeneous[i,j][:3].copy()
            for a in range(i+1):
                for b in range(j+1):
                    if a or b:
                        x-=math.comb(i,a)*math.comb(j,b)*homogeneous[a,b][3]*out[i-a,j-b]
            out[i,j]=x/homogeneous[0,0][3]
    return out[du,dv]



class _Evaluator:
    """Reuse tensor bases and quotient jets during bounded validation."""
    def __init__(self,record):
        self.cp=np.asarray(record['homogeneous_cp'],float)
        self.pu,self.pv=record['degree_u'],record['degree_v']
        self.bu=BSpline(record['knots_u'],np.eye(self.cp.shape[0]),self.pu,extrapolate=False)
        self.bv=BSpline(record['knots_v'],np.eye(self.cp.shape[1]),self.pv,extrapolate=False)
        self.ucache={};self.vcache={};self.cache={}
    def jets(self,u,v):
        key=(float(u),float(v))
        if key in self.cache:return self.cache[key]
        if u not in self.ucache:
            self.ucache[u]=np.asarray([self.bu(u,nu=i) if i<=self.pu else np.zeros(self.cp.shape[0]) for i in range(3)])
        if v not in self.vcache:
            self.vcache[v]=np.asarray([self.bv(v,nu=i) if i<=self.pv else np.zeros(self.cp.shape[1]) for i in range(3)])
        left=(self.ucache[u]@self.cp.reshape(self.cp.shape[0],-1)).reshape(3,self.cp.shape[1],4)
        hd=np.einsum('ijc,kj->ikc',left,self.vcache[v])
        out={}
        for i in range(3):
            for j in range(3):
                x=hd[i,j,:3].copy()
                for a in range(i+1):
                    for b in range(j+1):
                        if a or b:x-=math.comb(i,a)*math.comb(j,b)*hd[a,b,3]*out[i-a,j-b]
                out[i,j]=x/hd[0,0,3]
        result=[out[d] for d in ((0,0),(1,0),(0,1),(2,0),(1,1),(0,2))]
        self.cache[key]=result
        return result


def _geometry(jets):
    if not np.all(np.isfinite(np.asarray(jets,float))):
        return None,0.0
    _,du,dv,duu,duv,dvv=jets
    lu,lv=np.linalg.norm(du),np.linalg.norm(dv)
    cross=np.cross(du,dv);area=np.linalg.norm(cross)
    sine=area/max(lu*lv,np.finfo(float).tiny)
    if sine<1e-10 or min(lu,lv)<=1e-14:
        return None,float(sine)
    normal=cross/area
    jac=np.column_stack([du,dv]);metric=jac.T@jac
    try: inv=np.linalg.inv(metric)
    except np.linalg.LinAlgError: return None,float(sine)
    second=np.array([[normal@duu,normal@duv],[normal@duv,normal@dvv]])
    shape=jac@inv@second@inv@jac.T
    return (normal,shape),float(sine)


def _compare_geometry(a,b):
    if a is None or b is None:return math.inf,math.inf
    na,ka=a;nb,kb=b
    if na@nb<0:nb,kb=-nb,-kb
    angle=math.degrees(math.atan2(np.linalg.norm(np.cross(na,nb)),np.clip(na@nb,-1,1)))
    return float(angle),float(np.linalg.norm(ka-kb,ord=2))


class SkinModel:
    """Fixed network and exact quadratic-in-h coefficient cache."""
    def __init__(self,spec,cancelled=None):
        self.spec=spec
        self.cancelled=cancelled or spec.get('cancelled')
        seconds=float(spec.get('build_timeout_seconds',90))
        if not np.isfinite(seconds) or not 1<=seconds<=300:
            raise UnsupportedFamily('Build timeout must be between one and 300 seconds.')
        self._deadline=time.monotonic()+seconds
        self._checkpoint()
        self.normal=_unit(spec['upper_plane_normal'])
        self.transverse=_unit(spec['transverse_direction'])
        if abs(self.normal@self.transverse)>1e-7:
            raise UnsupportedFamily("The transverse direction must lie in the native upper plane.")
        if len(spec['side_surfaces'])!=2 or len(spec['profiles'])!=5 or len(spec['upper_paths'])!=2:
            raise UnsupportedFamily("The native family requires two side charts and five section profiles.")
        self.sides=[_Side(x) for x in spec['side_surfaces']]
        if abs(self.sides[0].v0-self.sides[1].v0)>1e-12 or abs(self.sides[0].v1-self.sides[1].v1)>1e-12:
            raise UnsupportedFamily("Opposing native charts must have the same oriented V domain.")
        self.v0,self.v1=self.sides[0].v0,self.sides[0].v1
        self.profiles=[]
        for section in spec['profiles']:
            p0,p1=np.asarray(section['p0'],float),np.asarray(section['p1'],float)
            t0,t1=_unit(section['t0']),_unit(section['t1'])
            k0,k1=np.asarray(section['k0'],float),np.asarray(section['k1'],float)
            s0,s1=float(section['speed0']),float(section['speed1'])
            if min(s0,s1)<=0 or max(abs(t0@k0),abs(t1@k1))>1e-7*max(1,np.linalg.norm(k0),np.linalg.norm(k1)):
                raise UnsupportedFamily("Section speeds must be positive and curvature vectors normal to tangents.")
            cp=hermite_control_points(p0,p1,s0*t0,s1*t1,s0*s0*k0+float(section.get('accel0',0))*t0,
                                      s1*s1*k1+float(section.get('accel1',0))*t1)
            self.profiles.append(bernstein_to_power(cp))
        allpoints=np.concatenate([np.asarray(x['p0'],float)[None] for x in spec['profiles']]+[np.asarray(x['p1'],float)[None] for x in spec['profiles']])
        self.scale=max(float(np.linalg.norm(np.ptp(allpoints,axis=0))),1e-9)
        self.tolerance=float(spec.get('absolute_tolerance',spec.get('tolerance',max(self.scale*1e-7,1e-9))))
        if not np.isfinite(self.tolerance) or self.tolerance<=0:
            raise UnsupportedFamily('A finite positive model tolerance is required.')
        self.upper=[_upper_pieces(x) for x in spec['upper_paths']]
        active=spec.get('active_v_fraction',[.2,.9])
        fractions=np.asarray(spec.get('row_fractions',np.r_[.12,np.linspace(active[0],active[1],7),.95]),float)
        if len(fractions)!=9 or np.any(np.diff(fractions)<=0) or not 0<fractions[0]<fractions[-1]<1:
            raise UnsupportedFamily("Nine distinct increasing interior native-V rows are required.")
        self.rows=self.v0+(self.v1-self.v0)*fractions
        self.vs=np.r_[self.v0,self.rows,self.v1]
        row_t=spec.get('row_t')
        if row_t is None:
            length=quad(lambda v:float(np.linalg.norm(self.sides[0].jet(v,0,1))),self.v0,self.v1,epsabs=self.tolerance*.001,limit=100)[0]
            center=self.profiles[2]
            speed=lambda t:float(np.linalg.norm(np.asarray(_val(_der(center),mp.mpf(t)),float)))
            total=quad(speed,0,1,epsabs=self.tolerance*.001,limit=100)[0]
            if min(length,total)<self.tolerance:
                raise UnsupportedFamily("Native side or center-profile arc length is degenerate.")
            row_t=[]
            for v in self.rows:
                self._checkpoint()
                fraction=quad(lambda x:float(np.linalg.norm(self.sides[0].jet(x,0,1))),self.v0,v,epsabs=self.tolerance*.001,limit=100)[0]/length
                row_t.append(brentq(lambda t:quad(speed,0,t,epsabs=self.tolerance*.001,limit=100)[0]/total-fraction,0,1,xtol=2e-13))
        row_t=np.asarray(row_t,float)
        if len(row_t)!=9 or np.any(np.diff(row_t)<=0) or not 0<row_t[0]<row_t[-1]<1:
            raise UnsupportedFamily("The fixed native/profile row correspondence must be monotone.")
        self.tmap=CubicSpline(self.vs,np.r_[0,row_t,1],bc_type='natural')
        # A cubic derivative is quadratic: endpoints and its vertex suffice.
        for k,(a,b) in enumerate(zip(self.vs[:-1],self.vs[1:])):
            xs=[a,b]
            c=self.tmap.c[:,k]
            if abs(c[0])>1e-30:
                vertex=a-c[1]/(3*c[0])
                if a<vertex<b:xs.append(vertex)
            if min(self.tmap(x,1) for x in xs)<=0:
                raise UnsupportedFamily("The native/profile cubic correspondence reverses within a span.")
        self.breaks=sorted(set(self.vs.tolist()+[float(x) for side in self.sides for x in side.kv if self.v0<x<self.v1]))
        if len(self.breaks)>65:
            raise UnsupportedFamily("Native source knot count exceeds the bounded 64-span budget.")
        self.parent_polys=[side.span_jets(self.breaks) for side in self.sides]
        self.qpolys=[]
        for a,b in zip(self.breaks[:-1],self.breaks[1:]):
            tm=_spline_poly(self.tmap,a,b)
            self.qpolys.append([_compose(profile,tm) for profile in self.profiles])
        self.fields=[]
        for si,side in enumerate(self.sides):
            idx=0 if si==0 else 4
            aa,bb,hh=[],[],[]
            for v in self.rows:
                p,su,suu=side.jet(v),side.jet(v,1),side.jet(v,2)
                target=np.asarray(_val(self.profiles[idx],mp.mpf(float(self.tmap(v)))),float)
                chord=np.linalg.norm(target-p);length=np.linalg.norm(su)
                if min(chord,length)<=self.tolerance:
                    raise UnsupportedFamily("A native collar chord or cross tangent is degenerate.")
                alpha=.75*chord/length
                # Cancel tangential acceleration, retaining exact native normal curvature.
                beta=-alpha*alpha*float(suu@su)/float(su@su)
                aa.append(alpha);bb.append(beta);hh.append(chord)
            ends=[np.linalg.norm(side.jet(v)-np.asarray(_val(self.profiles[idx],mp.mpf(t)),float)) for v,t in [(self.v0,0),(self.v1,1)]]
            self.fields.append((CubicSpline(self.vs,np.r_[aa[0],aa,aa[-1]],bc_type='natural'),
                                CubicSpline(self.vs,np.r_[bb[0],bb,bb[-1]],bc_type='natural'),
                                CubicSpline(self.vs,np.r_[ends[0],hh,ends[1]],bc_type='natural')))
        self._maps=None
        # All operators below are linear in the position/jet fields and maps
        # depend only on fixed top boundary jets. Thus this cache is algebraic,
        # not a sampled geometric surrogate.
        with mp.workdps(60):
            zero=self._construct(0.0)
            plus=self._construct(1.0)
            minus=self._construct(-1.0)
            self.cache=[]
            for z,p,m in zip(zero,plus,minus):
                if (z['shape']!=p['shape'] or z['shape']!=m['shape']):
                    raise UnsupportedFamily("Quadratic cache changed its fixed tensor topology.")
                self.cache.append((z,(p['cp']-m['cp'])/2,(p['cp']+m['cp'])/2-z['cp']))
            self.cache_error=self._check_cache()
        self.network={'profile_count':5,'row_count':9,'profile_parameters':row_t.tolist(),
                      'native_v':self.rows.tolist(),'native_v_breaks':list(self.breaks),
                      'native_u_breaks':[[x['ua'] for x in p]+[1.0] for p in self.upper],
                      'density_policy':'five sections; seven active rows and two context rows; fixed while h changes',
                      'source_handle_policy':'d(h)=h*d(1), dd(h)=h^2*dd(1)'}

    def _checkpoint(self):
        _check(self.cancelled)
        if time.monotonic()>self._deadline:
            raise TimeoutError('Bounded native-network preparation exceeded its time budget.')

    def _base(self,side,span,h):
        a,b=self.breaks[span:span+2]
        p,su,suu=[x[span] for x in self.parent_polys[side]]
        A,B,H=[_spline_poly(x,a,b) for x in self.fields[side]]
        d=_mul(A,su)*(mp.mpf(h)*self.sides[side].sign)
        dd=_add(_mul(_mul(A,A),suu),_mul(B,su))*mp.mpf(h*h)
        q=self.qpolys[span][0 if side==0 else 4]
        inner=_mul(H,_obj(self.transverse if side==0 else -self.transverse)[None])
        size=max(len(p),len(q),len(d),len(dd),len(inner))
        def pad(x):return _add(x,_zeros((size,3)))
        zero=_zeros((size,3))
        cp=hermite_control_points(pad(p),pad(q),pad(d),pad(inner),pad(dd),zero)
        return bernstein_to_power(cp)

    def _target_v(self,side,end,derivative):
        idx=0 if side==0 else 4
        v=self.v0 if end==0 else self.v1
        q=self.profiles[idx]
        t=0 if end==0 else 1
        if derivative==1:
            qv=_val(_der(q),mp.mpf(t))*mp.mpf(float(self.tmap(v,1)))
        else:
            qv=(_val(_der(q,2),mp.mpf(t))*mp.mpf(float(self.tmap(v,1)))**2+
                _val(_der(q),mp.mpf(t))*mp.mpf(float(self.tmap(v,2))))
        parent=_obj(self.sides[side].jet(v,0,derivative))
        inner=_obj(self.transverse if side==0 else -self.transverse)*mp.mpf(float(self.fields[side][2](v,derivative)))
        cp=hermite_control_points(parent,qv,_zeros((3,)),inner,_zeros((3,)),_zeros((3,)))
        target=bernstein_to_power(cp)
        if end==0:
            # Native upper plane normal, never a hard-coded world coordinate.
            projection=np.asarray([sum(c[k]*mp.mpf(float(self.normal[k])) for k in range(3)) for c in target],dtype=object)
            target-=_outer(projection,_obj(self.normal)[None])[:,0]
            first=self.upper[side][0]['ub']
            # Added piecewise compact term is handled in _end_corrections.
            return target,float(parent@_obj(self.normal)),first
        if derivative==2:
            first=self._target_v(side,end,1)
            section=self.spec['profiles'][idx]
            tangent=_unit(section['t1']);curvature=np.asarray(section['k1'],float)
            normal=np.cross(self.transverse,tangent)
            normal=_unit(normal)
            k=float(curvature@normal)
            scalar=np.asarray([sum(c[j]*mp.mpf(float(tangent[j])) for j in range(3)) for c in first],dtype=object)
            existing=np.asarray([sum(c[j]*mp.mpf(float(normal[j])) for j in range(3)) for c in target],dtype=object)
            correction=_add(_mul(scalar,scalar)*mp.mpf(k),-existing)
            target=_add(target,correction[:,None]*_obj(normal)[None])
        return target

    def _end_corrections(self,side,piece,span,base):
        ua,ub=piece['ua'],piece['ub'];va,vb=self.breaks[span:span+2]
        w=piece['top'][:,3]
        numerator=_mul_u(w,_tensor_u_restrict(base,ua,ub))
        start,end=self.vs[1],self.vs[-2]
        if va<start-1e-12:
            # Apply on every native knot span inside the compact first-row support.
            length=start-self.v0
            cards=[_compose(c,_obj([(va-self.v0)/length,(vb-va)/length]))*mp.mpf(length**d)
                   for d,c in enumerate((_C0,_C1,_C2))]
            edgebase=self._base(side,0,self._h)
            for d in range(3):
                vjet=_der(np.moveaxis(edgebase,1,0),d)[0]/mp.mpf(self.breaks[1]-self.breaks[0])**d
                restricted=_tensor_u_restrict(vjet[:,None,:],ua,ub)[:,0,:]
                if d==0:
                    delta=_add(piece['top'][:,:3],-_mul(w,restricted))
                else:
                    target,normaljet,first=self._target_v(side,0,d)
                    target=_tensor_u_restrict(target[:,None,:],ua,ub)[:,0,:]
                    if ub<=first+1e-12:
                        normalcard=_compose(_C0,_obj([ua/first,(ub-ua)/first]))
                        target=_add(target,normalcard[:,None]*_obj(self.normal)[None]*mp.mpf(normaljet))
                    delta=_mul(w,_add(target,-restricted))
                numerator=_add(numerator,delta[:,None,:]*cards[d][None,:,None])
        if vb>end+1e-12:
            length=self.v1-end
            cards=[_compose(c,_obj([(va-end)/length,(vb-va)/length]))*mp.mpf(length**d)
                   for d,c in enumerate((_C3,_C4,_C5))]
            edgebase=self._base(side,len(self.breaks)-2,self._h)
            for d in range(3):
                vjet=_val(_der(np.moveaxis(edgebase,1,0),d),mp.mpf(1))/mp.mpf(self.breaks[-1]-self.breaks[-2])**d
                restricted=_tensor_u_restrict(vjet[:,None,:],ua,ub)[:,0,:]
                if d==0:
                    p=_obj(self.sides[side].jet(self.v1));q=_val(self.profiles[0 if side==0 else 4],mp.mpf(1))
                    target=np.asarray([p,q-p],dtype=object)
                else:target=self._target_v(side,1,d)
                target=_tensor_u_restrict(target[:,None,:],ua,ub)[:,0,:]
                delta=_mul(w,_add(target,-restricted))
                numerator=_add(numerator,delta[:,None,:]*cards[d][None,:,None])
        return {'p':numerator,'w':w,'ua':ua,'ub':ub,'va':va,'vb':vb}

    def _normal_compatibility(self,side,piece_index,patch):
        # V3/V4 coefficients are constrained at the top, not fitted samples.
        if patch['va']>=self.vs[1]-1e-12:return patch
        # Reexpress the first-row polynomial in one global local coordinate
        # before extracting its top coefficients, including native internal knots.
        length=self.vs[1]-self.v0
        pv=np.moveaxis(patch['p'],1,0)
        globalp=_compose(pv,_obj([(self.v0-patch['va'])/(patch['vb']-patch['va']),length/(patch['vb']-patch['va'])]))
        z=_C3 if piece_index==0 else (_C0 if piece_index==len(self.upper[side])-1 else _obj([1]))
        if len(self.upper[side])==1:
            # There is no artificial upper seam; no higher compatibility constraint.
            return patch
        correction=_zeros((1,1,3))
        for order,card in ((3,_H3),(4,_H4)):
            if len(globalp)<=order:continue
            c=globalp[order]
            normalco=np.asarray([sum(x[j]*mp.mpf(float(self.normal[j])) for j in range(3)) for x in c],dtype=object)
            along=_mul(z,normalco)
            localcard=_compose(card,_obj([(patch['va']-self.v0)/length,(patch['vb']-patch['va'])/length]))
            correction=_add(correction,along[:,None,None]*localcard[None,:,None]*_obj(self.normal)[None,None,:])
        patch=dict(patch);patch['p']=_add(patch['p'],-correction)
        return patch

    def _seam_map(self,left,right):
        u,v=right['ua'],self.v0
        lu=_jet_patch(left,u,v,1,0);cv=_jet_patch(left,u,v,0,1);ru=_jet_patch(right,u,v,1,0)
        matrix=np.column_stack([lu,cv])
        alpha,beta=np.linalg.lstsq(matrix,ru,rcond=None)[0]
        desired=alpha*alpha*_jet_patch(left,u,v,2,0)+2*alpha*beta*_jet_patch(left,u,v,1,1)+beta*beta*_jet_patch(left,u,v,0,2)
        gamma,delta=np.linalg.lstsq(matrix,_jet_patch(right,u,v,2,0)-desired,rcond=None)[0]
        first=np.linalg.norm(matrix@np.array([alpha,beta])-ru)
        second=np.linalg.norm(matrix@np.array([gamma,delta])+desired-_jet_patch(right,u,v,2,0))
        if alpha<=0 or first>max(self.tolerance*.1,self.scale*1e-8) or second>max(self.tolerance,self.scale*1e-6):
            raise UnsupportedFamily("An upper native boundary join has incompatible geometric two-jets.")
        return tuple(map(float,(alpha,beta,gamma,delta)))

    def _repair(self,left,right,mapping):
        if right['va']>=self.vs[1]-1e-12:return right
        alpha,beta,gamma,delta=map(mp.mpf,mapping)
        length=self.vs[1]-self.v0
        h=_compose(_C0,_obj([(right['va']-self.v0)/length,(right['vb']-right['va'])/length]))
        A=_add(_obj([1]),h*(alpha-1));B=h*beta;G=h*gamma;D=h*delta
        ul,ur=mp.mpf(left['ub']-left['ua']),mp.mpf(right['ub']-right['ua'])
        vl=mp.mpf(left['vb']-left['va'])
        lu=_rational_u_jet(left['p'],left['w'],1,1)/ul
        luu=_rational_u_jet(left['p'],left['w'],1,2)/(ul*ul)
        c=_rational_u_jet(left['p'],left['w'],1,0)
        cv=_der(c)/vl;cvv=_der(c,2)/(vl*vl);luv=_der(lu)/vl
        ru=_rational_u_jet(right['p'],right['w'],0,1)/ur
        ruu=_rational_u_jet(right['p'],right['w'],0,2)/(ur*ur)
        d1=_add(_add(_mul(A,lu),_mul(B,cv)),-ru)
        d2=_add(_add(_add(_mul(_mul(A,A),luu),_mul(_mul(A,B),luv)*2),_mul(_mul(B,B),cvv)),
                _add(_add(_mul(G,lu),_mul(D,cv)),-ruu))
        correction=_add(_outer(_C1*ur,d1),_outer(_C2*ur*ur,d2))
        result=dict(right);result['p']=_add(right['p'],_mul_u(right['w'],correction))
        return result

    def _encode_strip(self,patches,kind,side,piece):
        du=max(max(x['p'].shape[0]-1,len(x['w'])-1) for x in patches)
        dv=max(x['p'].shape[1]-1 for x in patches)
        if du>40 or dv>40:
            raise UnsupportedFamily("Exact construction exceeded its bounded degree budget.")
        predicted=(du+1)*(len(patches)*dv+1)
        if predicted>16384:
            raise UnsupportedFamily('A skin strip exceeded its 16,384 control-point budget before encoding.')
        if self._encoded_control_points+predicted>65536:
            raise UnsupportedFamily('The skin exceeded its aggregate 65,536 control-point budget before encoding.')
        self._encoded_control_points+=predicted
        spans=[]
        for x in patches:
            cp=power_to_bernstein(power_to_bernstein(x['p'],du,0),dv,1)
            weight=power_to_bernstein(x['w'],du)
            homogeneous=_zeros((du+1,dv+1,4));homogeneous[:,:,:3]=cp
            homogeneous[:,:,3]=weight[:,None]
            spans.append(np.asarray(homogeneous,float))
        # Adjacent spans have a common coefficient by construction. Keep the
        # left endpoint, never independently average source boundary geometry.
        maxjump=max([float(np.max(np.abs(a[:,-1]-b[:,0]))) for a,b in zip(spans[:-1],spans[1:])]+[0.0])
        if maxjump>max(self.tolerance*.02,self.scale*2e-10):
            raise UnsupportedFamily("Native span assembly is not position-compatible.")
        cp=np.concatenate([spans[0]]+[x[:,1:] for x in spans[1:]],axis=1)
        if not np.all(np.isfinite(cp)) or np.any(cp[:,:,3]<=0):
            raise UnsupportedFamily('The homogeneous skin coefficients or weights are not finite and positive.')
        if cp.shape[0]*cp.shape[1]>16384:
            raise UnsupportedFamily('A skin strip exceeded its 16,384 control-point budget.')
        ku=[patches[0]['ua']]*(du+1)+[patches[0]['ub']]*(du+1)
        kv=[self.v0]*(dv+1)+sum(([v]*dv for v in self.breaks[1:-1]),[])+[self.v1]*(dv+1)
        return {'cp':cp,'shape':cp.shape,'degree_u':du,'degree_v':dv,'knots_u':ku,'knots_v':kv,
                'domain':[[patches[0]['ua'],patches[0]['ub']],[self.v0,self.v1]],
                'kind':kind,'side':side,'piece':piece,'assembly_roundoff':maxjump}

    def _construct(self,h):
        self._h=h;self._encoded_control_points=0;output=[];allmaps=[]
        for side in range(2):
            self._checkpoint()
            strips=[]
            for k,piece in enumerate(self.upper[side]):
                patches=[]
                for span in range(len(self.breaks)-1):
                    self._checkpoint()
                    base=self._base(side,span,h)
                    patches.append(self._normal_compatibility(side,k,self._end_corrections(side,piece,span,base)))
                strips.append(patches)
            maps=[]
            for k in range(1,len(strips)):
                # Fixed top jets have no source-handle dependence.
                mapping=self._seam_map(strips[k-1][0],strips[k][0]) if self._maps is None else self._maps[side][k-1]
                maps.append(mapping)
                strips[k]=[self._repair(l,r,mapping) for l,r in zip(strips[k-1],strips[k])]
            allmaps.append(maps)
            for k,patches in enumerate(strips):output.append(self._encode_strip(patches,'collar',side,k))
        if self._maps is None:self._maps=allmaps
        for j in range(4):
            self._checkpoint()
            patches=[]
            # Fixed section spacing supplies the declared near-linear quintic.
            p0=np.asarray(self.spec['profiles'][j]['p0'],float)
            p1=np.asarray(self.spec['profiles'][j+1]['p0'],float)
            width=float((p1-p0)@self.transverse)
            if width<=self.tolerance:
                raise UnsupportedFamily("Five native sections must be uniquely ordered across the upper straight run.")
            for i,(a,b) in enumerate(zip(self.breaks[:-1],self.breaks[1:])):
                left,right=self.qpolys[i][j:j+2];size=max(len(left),len(right))
                left=_add(left,_zeros((size,3)));right=_add(right,_zeros((size,3)))
                d=_zeros((size,3));d[0]=_obj(self.transverse)*mp.mpf(width)
                zero=_zeros((size,3))
                p=bernstein_to_power(hermite_control_points(left,right,d,d,zero,zero))
                patches.append({'p':p,'w':_obj([1]),'ua':0.0,'ub':1.0,'va':a,'vb':b})
            output.append(self._encode_strip(patches,'middle',None,j))
        return output

    def _check_cache(self):
        # Fourth algebraic construction tests the degree-two assumption rather
        # than accepting a three-point quadratic interpolation on faith.
        h=.731
        direct=self._construct(h)
        error=0.0
        for fresh,(zero,first,second) in zip(direct,self.cache):
            approximation=zero['cp']+h*first+h*h*second
            error=max(error,float(np.max(np.abs(approximation-fresh['cp']))))
        if error>max(self.tolerance*.005,self.scale*2e-10):
            raise UnsupportedFamily("The fixed-topology handle cache failed independent evaluation.")
        return error

    def _guides(self,h):
        out=[]
        for j,profile in enumerate(self.profiles):
            cp=np.asarray(power_to_bernstein(profile),float)
            out.append({'degree':5,'knots':[0.0]*6+[1.0]*6,'homogeneous_cp':np.c_[cp,np.ones(6)].tolist(),
                        'domain':[0.0,1.0],'kind':'profile','piece':j})
        # The original six-span longitudinal network, independent of top-end
        # correction strips; all nine rows lie at cardinal-zero boundaries.
        for row,v in enumerate(self.rows):
            span=max(0,min(len(self.breaks)-2,np.searchsorted(self.breaks,v,side='right')-1))
            for side in range(2):
                base=self._base(side,span,h)
                cp=np.asarray(power_to_bernstein(_val(np.moveaxis(base,1,0),mp.mpf((v-self.breaks[span])/(self.breaks[span+1]-self.breaks[span])))),float)
                out.append({'degree':5,'knots':[0.0]*6+[1.0]*6,'homogeneous_cp':np.c_[cp,np.ones(6)].tolist(),
                            'domain':[0.0,1.0],'kind':'row_collar','row':row,'side':side})
            qs=[np.asarray(_val(p,mp.mpf(float(self.tmap(v)))),float) for p in self.profiles]
            for j in range(4):
                width=float((np.asarray(self.spec['profiles'][j+1]['p0'])-np.asarray(self.spec['profiles'][j]['p0']))@self.transverse)
                d=width*self.transverse;zero=np.zeros(3)
                cp=hermite_control_points(qs[j],qs[j+1],d,d,zero,zero)
                out.append({'degree':5,'knots':[0.0]*6+[1.0]*6,'homogeneous_cp':np.c_[cp,np.ones(6)].tolist(),
                            'domain':[0.0,1.0],'kind':'row_middle','row':row,'piece':j})
        return out

    def evaluate(self,h=1.0,validate=True,cancelled=None):
        h=float(h);callback=cancelled or self.cancelled
        _check(callback)
        if not .5<=h<=1.5 or not np.isfinite(h):
            raise ValueError("Curvature handle factor must be finite and in [0.5,1.5].")
        surfaces=[]
        for zero,first,second in self.cache:
            _check(callback)
            cp=zero['cp']+h*first+h*h*second
            record={k:v for k,v in zero.items() if k not in ('cp','shape')}
            record['homogeneous_cp']=cp.tolist();record['homogeneousCP']=record['homogeneous_cp']
            record['weights']=cp[:,:,3].tolist();record['control_points']=(cp[:,:,:3]/cp[:,:,3,None]).tolist()
            surfaces.append(record)
        report=self._validate(surfaces,callback) if validate else {'checked':False,'fatal':False,'full_boundary_pass':False,'reason':'Finite validation was not requested.'}
        report.update({'h':h,'cache_independent_error':self.cache_error,
                       'certificate':'finite sampled evidence only; no global G2, collision, or self-intersection certificate',
                       'source_modifications':0,'native_rational_upper_preserved':True})
        with mp.workdps(60):
            guides=self._guides(h)
        # Validate the evaluated value, never reuse a pass from another h.
        fatal=bool(report.get('fatal',False))
        valid=bool(report.get('checked',False)) and not fatal
        return {'surfaces':surfaces,'patches':surfaces,'report':report,'metrics':report,'network':self.network,
                'guides':guides,'valid':valid,'geometry_valid':valid,'continuity_pass':bool(report.get('full_boundary_pass',False)),
                'experimental_commit_allowed':valid,'fatal':fatal,'reason':report.get('reason',''),
                'experimental':not bool(report.get('full_boundary_pass',False)),'full_boundary_pass':bool(report.get('full_boundary_pass',False)),'h':h}

    def _validate(self,surfaces,cancelled):
        maxpos=0.0;maxangle=0.0;maxcurvature=0.0;minsin=1.0;maxseam=0.0
        sourcepos=0.0;sourceangle=0.0;sourcecurv=0.0;upperangle=0.0;uppercurv=0.0;lowerangle=0.0;lowercurv=0.0
        samples=0;fatal=[];minimum_jacobian=math.inf;maximum_curvature=0.0;minimum_orientation_dot=1.0
        angle_limit=float(self.spec.get('angle_tolerance_degrees',math.degrees(self.spec.get('angle_tolerance',math.radians(.1)))))
        curvature_limit=float(self.spec.get('curvature_tolerance',max(1e-5/self.scale,1e-8)))
        if not np.isfinite(angle_limit) or not 0<angle_limit<90 or not np.isfinite(curvature_limit) or curvature_limit<=0:
            raise UnsupportedFamily('Finite positive angle and curvature tolerances are required.')
        upper_failures=[];source_failures=[];active_angle=0.0;active_curvature=0.0
        required_upper_angle=0.0;required_upper_curvature=0.0
        evaluators={id(s):_Evaluator(s) for s in surfaces}
        references={}
        for record,(zero,first,second) in zip(surfaces,self.cache):
            base=dict(zero);base['homogeneous_cp']=zero['cp']+first+second
            references[id(record)]=_Evaluator(base)
        def jets(s,u,v):
            return evaluators[id(s)].jets(float(u),float(v))
        def geom(s,u,v):
            nonlocal minsin,samples,minimum_jacobian,maximum_curvature,minimum_orientation_dot
            values=jets(s,u,v)
            result,sine=_geometry(values);minsin=min(minsin,sine);samples+=1
            if samples%64==0:_check(cancelled)
            minimum_jacobian=min(minimum_jacobian,float(np.linalg.norm(np.cross(values[1],values[2]))))
            if result is not None:
                maximum_curvature=max(maximum_curvature,float(np.linalg.norm(result[1],ord=2)))
                refvalues=references[id(s)].jets(float(u),float(v))
                refnormal=np.cross(refvalues[1],refvalues[2]);length=float(np.linalg.norm(refnormal))
                if length>np.finfo(float).tiny:
                    minimum_orientation_dot=min(minimum_orientation_dot,float(result[0]@(refnormal/length)))
            if result is None:fatal.append('A sampled surface point has a singular tangent frame.')
            return result
        for s in surfaces:
            _check(cancelled)
            ua,ub=s['domain'][0]
            # Every native span participates; no hidden corner exclusion.
            us=np.linspace(ua,ub,7)
            vs=sorted(set([self.v0,self.v1]+[a+(b-a)*q for a,b in zip(self.breaks[:-1],self.breaks[1:]) for q in (0,.25,.5,.75,1)]))
            for u in us:
                for v in vs:geom(s,float(u),float(v))
            if s['kind']=='collar':
                side=s['side'];piece=self.upper[side][s['piece']]
                upper_samples=[]
                for u in np.linspace(ua,ub,13):
                    t=(u-ua)/(ub-ua);top=_val(piece['top'],mp.mpf(t));expected=np.asarray(top[:3]/top[3],float)
                    maxpos=max(maxpos,float(np.linalg.norm(jets(s,u,self.v0)[0]-expected)))
                    g=geom(s,u,self.v0)
                    if g is not None:
                        n,k=g
                        local_angle=math.degrees(math.acos(np.clip(abs(n@self.normal),0,1)))
                        local_curv=float(np.linalg.norm(k,ord=2))
                        upperangle=max(upperangle,local_angle);uppercurv=max(uppercurv,local_curv)
                        if s['piece']>0:
                            required_upper_angle=max(required_upper_angle,local_angle)
                            required_upper_curvature=max(required_upper_curvature,local_curv)
                        upper_samples.append((float(u),local_angle,local_curv))
                for a,b in zip(upper_samples[:-1],upper_samples[1:]):
                    if max(a[1],b[1])>angle_limit or max(a[2],b[2])>curvature_limit:
                        upper_failures.append({'side':side,'piece':s['piece'],'u_interval':[a[0],b[0]],'sample_bracket':True,'angle_degrees':max(a[1],b[1]),'curvature_error':max(a[2],b[2])})
                if s['piece']==0:
                    parent=self.sides[side]
                    source_samples=[]
                    for v in vs:
                        sj=jets(s,ua,v);pj=[parent.jet(v),parent.jet(v,1),parent.jet(v,0,1),parent.jet(v,2),parent.jet(v,1,1),parent.jet(v,0,2)]
                        ga,_=_geometry(sj);gb,_=_geometry(pj)
                        a,k=_compare_geometry(ga,gb)
                        sourcepos=max(sourcepos,float(np.linalg.norm(sj[0]-pj[0])))
                        sourceangle=max(sourceangle,a);sourcecurv=max(sourcecurv,k)
                        source_samples.append((float(v),a,k))
                        if self.rows[0]-1e-12<=v<=self.rows[-1]+1e-12:
                            active_angle=max(active_angle,a);active_curvature=max(active_curvature,k)
                    for a,b in zip(source_samples[:-1],source_samples[1:]):
                        if max(a[1],b[1])>angle_limit or max(a[2],b[2])>curvature_limit:
                            source_failures.append({'side':side,'v_interval':[a[0],b[0]],'sample_bracket':True,'angle_degrees':max(a[1],b[1]),'curvature_error':max(a[2],b[2])})
            if s['kind']=='middle':
                for u in np.linspace(ua,ub,9):
                    g=geom(s,u,self.v0)
                    if g is not None:
                        n,k=g
                        local_angle=math.degrees(math.acos(np.clip(abs(n@self.normal),0,1)));local_curv=float(np.linalg.norm(k,ord=2))
                        upperangle=max(upperangle,local_angle);uppercurv=max(uppercurv,local_curv)
                        required_upper_angle=max(required_upper_angle,local_angle)
                        required_upper_curvature=max(required_upper_curvature,local_curv)
            # Lower ruled parent jets are provided by the fixed native sections.
            for u in np.linspace(ua,ub,9):
                if s['kind']=='collar':section=self.spec['profiles'][0 if s['side']==0 else 4]
                else:section=self.spec['profiles'][s['piece']]
                t=_unit(section['t1']);n=_unit(np.cross(self.transverse,t));k=float(np.asarray(section['k1'])@n)
                target=(n,k*np.outer(t,t))
                a,c=_compare_geometry(geom(s,u,self.v1),target)
                lowerangle=max(lowerangle,a);lowercurv=max(lowercurv,c)
        # Repeated V knots are explicit patch joins too. Evaluate both limits;
        # evaluating the knot itself alone would silently inspect only one side.
        for s in surfaces:
            _check(cancelled)
            for v in self.breaks[1:-1]:
                before=float(np.nextafter(v,-np.inf));after=float(np.nextafter(v,np.inf))
                for u in np.linspace(*s['domain'][0],7):
                    left=jets(s,float(u),before);right=jets(s,float(u),after)
                    maxseam=max(maxseam,float(np.linalg.norm(left[0]-right[0])))
                    a,k=_compare_geometry(geom(s,float(u),before),geom(s,float(u),after))
                    maxangle=max(maxangle,a);maxcurvature=max(maxcurvature,k)

        # Every collar artificial U seam and the four-band internal joints.
        groups=[[x for x in surfaces if x['kind']=='collar' and x['side']==side] for side in range(2)]
        pairs=[]
        for group in groups:
            group.sort(key=lambda x:x['piece'])
            pairs += [(a,a['domain'][0][1],b,b['domain'][0][0]) for a,b in zip(group[:-1],group[1:])]
        mids=sorted([x for x in surfaces if x['kind']=='middle'],key=lambda x:x['piece'])
        pairs += [(a,1.0,b,0.0) for a,b in zip(mids[:-1],mids[1:])]
        pairs += [(groups[0][-1],1.0,mids[0],0.0),(groups[1][-1],1.0,mids[-1],1.0)]
        for left,ul,right,ur in pairs:
            _check(cancelled)
            for v in sorted(set(np.r_[self.vs,np.linspace(self.v0,self.v1,31)].tolist())):
                maxseam=max(maxseam,float(np.linalg.norm(jets(left,ul,v)[0]-jets(right,ur,v)[0])))
                a,k=_compare_geometry(geom(left,ul,v),geom(right,ur,v))
                maxangle=max(maxangle,a);maxcurvature=max(maxcurvature,k)
        if minimum_orientation_dot<=0:
            fatal.append('A sampled surface frame inverted relative to the fixed h=1 reference.')
        if minsin<float(self.spec.get('minimum_sine',1e-6)):
            fatal.append('The sampled minimum tangent crossing angle is below the regularity threshold.')
        if max(maxpos,sourcepos,maxseam)>self.tolerance:
            fatal.append('A sampled source-boundary or internal-seam position residual exceeds tolerance.')
        if maxangle>angle_limit or maxcurvature>curvature_limit:
            fatal.append('Required internal seam continuity failed finite checks.')
        if active_angle>angle_limit or active_curvature>curvature_limit:
            fatal.append('Required source-side continuity between the first and last network rows failed finite checks.')
        if required_upper_angle>angle_limit or required_upper_curvature>curvature_limit:
            fatal.append('Upper-plane continuity failed outside the explicit first native corner span.')
        if lowerangle>angle_limit or lowercurv>curvature_limit:
            fatal.append('Required lower ruled-parent continuity failed finite checks.')
        full=(not fatal and max(sourceangle,upperangle,lowerangle,maxangle)<=angle_limit and
              max(sourcecurv,uppercurv,lowercurv,maxcurvature)<=curvature_limit)
        reason='Finite sampled boundary and seam checks passed.' if full else (' '.join(dict.fromkeys(fatal)) if fatal else 'Finite G1/G2 failures remain in the reported upper and source-end strips.')
        return {'checked':True,'fatal':bool(fatal),'g0_pass':max(maxpos,sourcepos,maxseam)<=self.tolerance,'full_boundary_pass':full,'reason':reason,'sample_count':samples,
                'minimum_sampled_sine':minsin,'minimum_sampled_jacobian':minimum_jacobian,'sampled_max_curvature':maximum_curvature,'minimum_orientation_dot_h1':minimum_orientation_dot,
                'upper_failure_intervals':upper_failures,'source_failure_intervals':source_failures,
                'active_source_angle_degrees':active_angle,'active_source_curvature_error':active_curvature,'source_position_error':sourcepos,'upper_position_error':maxpos,
                'source_angle_degrees':sourceangle,'source_curvature_error':sourcecurv,
                'upper_angle_degrees':upperangle,'upper_curvature_error':uppercurv,
                'required_upper_angle_degrees':required_upper_angle,'required_upper_curvature_error':required_upper_curvature,
                'lower_angle_degrees':lowerangle,'lower_curvature_error':lowercurv,
                'seam_position_error':maxseam,'seam_angle_degrees':maxangle,'seam_curvature_error':maxcurvature,
                'position_tolerance':self.tolerance,'angle_tolerance_degrees':angle_limit,'curvature_tolerance':curvature_limit,
                'corner_policy':'All finite boundary intervals sampled; no finite corner interval is silently excluded.'}


def build_model(spec,cancelled=None):
    """Build a source-independent bounded skin model from native numeric records."""
    return SkinModel(spec,cancelled)


def prepare(spec,cancelled=None):
    return build_model(spec,cancelled)
