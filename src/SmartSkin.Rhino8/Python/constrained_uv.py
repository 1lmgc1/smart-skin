"""Bounded coupled U/V edits on an independently validated native-network base.

No source extraction, Rhino calls, native attachment repair, or commit permission
lives here. Source records are immutable. The constructor is supplied its base
result and per-value validator by the owning kernel. An unproved base stays
unproved. This module never promotes an old PARTIAL result to full attachment.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import time

import mpmath as mp
import numpy as np
from scipy.interpolate import BSpline

HANDLE_SCHEMA = 'smartskin.uv-handles.v1'
PROOF_SCHEMA = 'smartskin.edit-proof.v2'
_MAX_CP = 65536


def _zeros(shape):
    out = np.empty(shape, dtype=object)
    out.fill(mp.mpf(0))
    return out


def _poly(values):
    return np.vectorize(lambda x: mp.mpf(float(x)), otypes=[object])(np.asarray(values))


def _add(a, b):
    a, b = np.asarray(a, dtype=object), np.asarray(b, dtype=object)
    out = _zeros(tuple(max(x, y) for x, y in zip(a.shape, b.shape)))
    out[tuple(slice(0, x) for x in a.shape)] += a
    out[tuple(slice(0, x) for x in b.shape)] += b
    return out


def _mul(a, b):
    a, b = np.asarray(a, dtype=object), np.asarray(b, dtype=object)
    out = _zeros((len(a) + len(b) - 1,) + b.shape[1:])
    for i, x in enumerate(a):
        out[i:i + len(b)] += x * b
    return out


def _der(a, order=1):
    a = np.asarray(a, dtype=object)
    for _ in range(order):
        a = np.asarray([i*a[i] for i in range(1, len(a))], dtype=object) if len(a) > 1 else _zeros((1,) + a.shape[1:])
    return a


def _value(a, t):
    out = _zeros(np.asarray(a).shape[1:])
    for x in a[::-1]:
        out = out*t+x
    return out


def _compose(a, offset, scale):
    out = np.asarray(a[-1:], dtype=object).copy()
    for x in a[-2::-1]:
        out = _mul([offset, scale], out)
        out[0] += x
    return out


def _b2p(cp):
    cp = np.asarray(cp, dtype=object)
    n = len(cp)-1
    out = _zeros(cp.shape)
    for k in range(n+1):
        for i in range(k+1):
            out[k] += math.comb(n, k)*math.comb(k, i)*(-1)**(k-i)*cp[i]
    return out


def _p2b(poly, degree=None):
    degree = len(poly)-1 if degree is None else degree
    if degree < len(poly)-1:
        raise ValueError('Cannot lower a polynomial degree.')
    out = _zeros((degree+1,) + np.asarray(poly).shape[1:])
    for i in range(degree+1):
        for k in range(min(i, len(poly)-1)+1):
            out[i] += mp.mpf(math.comb(i,k))/math.comb(degree,k)*poly[k]
    return out


def _elevate(cp, degree, axis):
    """Stable nonnegative Bernstein elevation, never a fitted surrogate."""
    cp = np.moveaxis(np.asarray(cp, float), axis, 0)
    old = len(cp)-1
    if degree < old:
        raise ValueError('Cannot lower Bernstein degree.')
    if degree == old:
        return np.moveaxis(cp.copy(), 0, axis)
    matrix = np.zeros((degree+1, old+1))
    for i in range(degree+1):
        for j in range(max(0, i-(degree-old)), min(old, i)+1):
            matrix[i,j] = math.comb(old,j)*math.comb(degree-old,i-j)/math.comb(degree,i)
    return np.moveaxis(np.tensordot(matrix, cp, axes=(1,0)), 0, axis)


# Degree-9 step and degree-10 bump have endpoint derivatives 1..4 = 0;
# the bump also has zero endpoint values. The maximum bump value is one.
_STEP = _b2p(_poly([0]*5 + [1]*5))
_BUMP = _poly([0]*5 + [1024, -5120, 10240, -10240, 5120, -1024])
_HERMITE = tuple(_poly(x) for x in (
    [1,0,0,-10,15,-6], [0,1,0,-6,8,-3], [0,0,.5,-1.5,1.5,-.5],
    [0,0,0,10,-15,6], [0,0,0,-4,7,-3], [0,0,0,.5,-1,.5]))


def transported_jets(common, alpha, beta, gamma=(0,), delta=(0,)):
    """Transport displacement (C, D, A) through a fixed geometric 2-jet.

    R_u = alpha D + beta C_v
    R_uu = alpha^2 A + 2 alpha beta D_v + beta^2 C_vv
           + gamma D + delta C_v
    Coefficients use the same physical seam parameter on both sides.
    """
    C, D, A = map(lambda x: np.asarray(x, dtype=object), common)
    alpha, beta, gamma, delta = map(lambda x: np.asarray(x, dtype=object), (alpha,beta,gamma,delta))
    right_d = _add(_mul(alpha,D), _mul(beta,_der(C)))
    right_a = _add(_add(_mul(_mul(alpha,alpha),A), 2*_mul(_mul(alpha,beta),_der(D))),
                   _add(_mul(_mul(beta,beta),_der(C,2)), _add(_mul(gamma,D),_mul(delta,_der(C)))))
    return C.copy(), right_d, right_a


def endpoint_lift(jets, endpoint, span=1.):
    """Polynomial tensor with specified cross 2-jet and zero opposite 2-jet."""
    out = _zeros((6, max(map(len,jets)), 3))
    for order, field in enumerate(jets):
        card = _HERMITE[3*endpoint+order] * mp.mpf(span)**order
        out[:, :len(field)] += card[:,None,None]*field[None,:,:]
    return out


def coupled_seam_displacements(common, transport, left_span=1., right_span=1.):
    """Lift a changed shared trace to BOTH incident patches, with full G2 jets."""
    return (endpoint_lift(common, 1, left_span),
            endpoint_lift(transported_jets(common, *transport), 0, right_span))


def tensor_value(poly, u, v, du=0, dv=0):
    along = _value(_der(poly,du),mp.mpf(u))
    return np.asarray(_value(_der(along,dv),mp.mpf(v)), float)


def _span_coefficients(record):
    cp = np.asarray(record['homogeneous_cp'],float)
    pu, pv = record['degree_u'],record['degree_v']
    ua,ub = record['domain'][0]
    if len(set(record['knots_u'])) != 2 or cp.shape[0] != pu+1:
        raise ValueError('Selected-U/V edits require one Bernstein span per transverse strip.')
    va,vb = record['domain'][1]
    breaks = sorted(set([va,vb]+[float(x) for x in record['knots_v'] if va<x<vb]))
    spline = BSpline(record['knots_v'],np.moveaxis(cp,1,0),pv,extrapolate=False)
    for v in breaks:
        multiplicity = int(np.count_nonzero(spline.t==v))
        if multiplicity < pv:
            spline = spline.insert_knot(v,pv-multiplicity)
    spans = []
    for a,b in zip(breaks[:-1],breaks[1:]):
        k = int(np.searchsorted(spline.t,(a+b)/2,side='right')-1)
        spans.append(np.moveaxis(np.asarray(spline.c[k-pv:k+1],float),0,1))
    return breaks, spans


def _scalar_span(kind, span, source):
    a,b = span
    if kind == 'profile':
        lo,hi = source
        if b<=lo or a>=hi:
            return _poly([0])
        if a < lo-1e-12 or b > hi+1e-12:
            raise ValueError('Compact edit support must follow the fixed native knot layout.')
        return _compose(_BUMP,mp.mpf((a-lo)/(hi-lo)),mp.mpf((b-a)/(hi-lo)))
    lo,center,hi = source
    if b<=lo or a>=hi:
        return _poly([0])
    if b<=center:
        return _compose(_STEP,mp.mpf((a-lo)/(center-lo)),mp.mpf((b-a)/(center-lo)))
    if a>=center:
        return _compose(_STEP,mp.mpf((hi-a)/(hi-center)),mp.mpf(-(b-a)/(hi-center)))
    raise ValueError('A row handle center must be an existing native V knot.')


def _record_with_cp(template, cp):
    result = dict(template)
    result['homogeneous_cp'] = np.asarray(cp,float).tolist()
    result['homogeneousCP'] = result['homogeneous_cp']
    result['weights'] = cp[:,:,3].tolist()
    result['control_points'] = (cp[:,:,:3]/cp[:,:,3,None]).tolist()
    return result


def surface_isocurve(surface, varying_axis, constant_parameter):
    """Exact full-domain rational trace used to bind repaired inspection guides."""
    if varying_axis not in ('u','v') or not math.isfinite(float(constant_parameter)):
        raise ValueError('A bound guide requires a finite U/V isocurve parameter.')
    axis=0 if varying_axis=='u' else 1;fixed=1-axis
    a,b=surface['domain'][fixed]
    if not a<=constant_parameter<=b:raise ValueError('A bound guide lies outside its surface domain.')
    cp=np.asarray(surface['homogeneous_cp'],float)
    fixed_name='v' if fixed else 'u'
    basis=BSpline(surface['knots_'+fixed_name],np.eye(cp.shape[fixed]),surface['degree_'+fixed_name],extrapolate=False)(constant_parameter)
    h=np.einsum('j,ijc->ic',basis,cp) if axis==0 else np.einsum('i,ijc->jc',basis,cp)
    return dict(degree=surface['degree_'+varying_axis],knots=list(surface['knots_'+varying_axis]),
                homogeneous_cp=h.tolist(),domain=list(surface['domain'][axis]))


def _rational_control_bound(first, second):
    """Positional convex-hull bound for two positive rational control arrays."""
    first,second=np.asarray(first,float),np.asarray(second,float)
    if first.shape!=second.shape or not np.isfinite(first).all() or not np.isfinite(second).all():
        return math.inf
    lw,rw=first[...,-1],second[...,-1]
    if np.min(lw)<=0 or np.min(rw)<=0:return math.inf
    lp=first[...,:3]/lw[...,None];rp=second[...,:3]/rw[...,None]
    point_bound=float(np.max(np.linalg.norm(lp-rp,axis=-1)))
    logs=np.log(lw)-np.log(rw)
    centered=logs-(float(np.min(logs))+float(np.max(logs)))/2
    eta=math.inf if np.max(np.abs(centered))>math.log(2.) else float(np.max(np.abs(np.expm1(centered))))
    if eta>=1 or not math.isfinite(point_bound):return math.inf
    radius=float(np.max(np.linalg.norm(rp-rp.reshape(-1,3)[0],axis=-1)))
    return point_bound+2*eta*radius/(1-eta)


def _coincident_curve_bound(first,second,tolerance,cancelled=None):
    """Bound same-direction rational curves after exact knot-union refinement.

    Cross-multiplied Bernstein residuals allow unequal degrees and denominator
    gauges. Bounded subdivision sharpens the positive-denominator bound. This
    never accepts a nearest-point fit or a point-sampling substitute.
    """
    deadline=time.monotonic()+8.;curves=[];breaks={0.,1.}
    for curve in (first,second):
        degree=int(curve['degree']);cp=np.asarray(curve['homogeneous_cp'],float)
        a,b=map(float,curve['domain']);knots=(np.asarray(curve['knots'],float)-a)/(b-a)
        if not 1<=degree<=40 or len(cp)>4096 or np.min(cp[:,3])<=0:
            raise ValueError('Coincident guide exceeds bounded rational-curve limits.')
        breaks.update(float(x) for x in knots if 0<x<1)
        curves.append((degree,cp,knots))
    breaks=sorted(breaks)
    if len(breaks)>129:raise ValueError('Coincident guide knot union exceeds the bounded span budget.')
    spans=[]
    for degree,cp,knots in curves:
        spline=BSpline(knots,cp,degree,extrapolate=False)
        for x in breaks:
            m=int(np.count_nonzero(spline.t==x))
            if m<degree:spline=spline.insert_knot(x,degree-m)
        parts=[]
        for a,b in zip(breaks[:-1],breaks[1:]):
            k=int(np.searchsorted(spline.t,(a+b)/2,side='right')-1)
            parts.append(_poly(spline.c[k-degree:k+1]))
        spans.append(parts)
    def split(coeff):
        rows=[coeff];left=[coeff[0]];right=[coeff[-1]]
        while len(rows[-1])>1:
            q=(rows[-1][:-1]+rows[-1][1:])/2;rows.append(q);left.append(q[0]);right.append(q[-1])
        return np.asarray(left,object),np.asarray(right[::-1],object)
    worst=0.;visited=0
    with mp.workdps(65):
        stack=[]
        for a,b in zip(*spans):
            a=a/max(a[:,3]);b=b/max(b[:,3]);p,q=len(a)-1,len(b)-1
            residual=_zeros((p+q+1,3));denominator=_zeros((p+q+1,))
            for i in range(p+1):
                for j in range(q+1):
                    weight=mp.mpf(math.comb(p,i)*math.comb(q,j))/math.comb(p+q,i+j)
                    residual[i+j]+=weight*(a[i,:3]*b[j,3]-b[j,:3]*a[i,3])
                    denominator[i+j]+=weight*a[i,3]*b[j,3]
            stack.append((residual,denominator,0))
        while stack:
            visited+=1
            if visited>4096 or time.monotonic()>deadline:
                raise ValueError('Coincident guide proof exceeded its bounded subdivision/time budget.')
            if cancelled and cancelled():raise ValueError('Coincident guide proof cancelled.')
            residual,denominator,depth=stack.pop()
            bound=float(max(mp.sqrt(sum(x*x for x in row)) for row in residual)/min(denominator))
            if bound<=tolerance:worst=max(worst,bound);continue
            if depth>=14:return bound
            l,r=split(residual);dl,dr=split(denominator)
            stack.extend(((l,dl,depth+1),(r,dr,depth+1)))
    return worst


class PreparedUVEdits:
    """Affine coefficient response cache on caller-owned, source-derived topology.

    The supplied validator must check this edited value, including regularity,
    outward orientation, source attachment, and every new/shared seam. Its result
    replaces baseline proof. A missing validator fails closed. This class may be
    used with a PARTIAL base for differential tests only; it creates no full
    attachment certificate of its own.
    """
    def __init__(self, model, baseline_result, validator, kernel, cancelled=None, differential_only=False,
                 validator_receives_result=False):
        if not callable(validator):
            raise ValueError('A per-value native attachment and regularity validator is required.')
        proof=baseline_result.get('attachment_proof',{})
        if not differential_only and (not isinstance(proof,dict) or
                proof.get('schema')!='smartskin.attachments.v2' or
                proof.get('corner_policy')!='hard_upper_source_corners' or
                proof.get('excluded_intervals')!=[] or
                any(proof.get(key) is not True for key in ('checked','source_full_finite_boundary_pass','shared_full_finite_boundary_pass')) or
                baseline_result.get('report',{}).get('checked') is not True or
                baseline_result.get('report',{}).get('fatal') is not False):
            raise ValueError('Selected-U/V editing requires a separately validated repaired base; unproved bases are differential-test only.')
        self.differential_only=bool(differential_only)
        if type(validator_receives_result) is not bool:raise ValueError('The full-result validator contract must be explicit.')
        self.validator_receives_result=validator_receives_result
        self.model,self.kernel,self.validator = model,kernel,validator
        self.cancelled = cancelled
        self._baseline = copy.deepcopy(baseline_result)
        self._source_digest = self._digest(model.spec)
        self.direction = np.asarray(model.normal,float)
        self.v0,self.v1 = float(model.v0),float(model.v1)
        network=baseline_result.get('network',{})
        self.rows=np.asarray(network.get('native_v',[]),float)
        if (network.get('profile_count')!=5 or self.rows.ndim!=1 or not 2<=len(self.rows)<=32 or
                type(network.get('row_count')) is not int or network['row_count']!=len(self.rows) or
                not np.isfinite(self.rows).all() or np.any(np.diff(self.rows)<=0) or
                not self.v0<self.rows[0]<self.rows[-1]<self.v1):
            raise ValueError('The displayed baseline must declare its actual finite ordered row layout.')
        self.row_count=len(self.rows)
        self.bound = max(4*float(model.tolerance), .015*float(model.scale))
        self._responses = {}
        self._records = []
        self._baseline_cp = []
        self._handle_specs = []
        self._profile_support = (float(self.rows[0]),float(self.rows[-1]))
        self._profile_supports={'lift':self._profile_support,
                                'upper':(self.v0,float(self.rows[0])),
                                'lower':(float(self.rows[-1]),self.v1)}
        report = baseline_result.get('report',{})
        self.shared_tolerances = dict(
            position=float(report.get('position_tolerance',model.tolerance)),
            normal_angle_degrees=float(report.get('angle_tolerance_degrees',
                model.spec.get('angle_tolerance_degrees',math.degrees(model.spec.get('angle_tolerance',math.radians(.1)))))),
            shape_operator=float(report.get('curvature_tolerance',
                model.spec.get('curvature_tolerance',max(1e-5/model.scale,1e-8)))))
        if not all(math.isfinite(x) and x>0 for x in self.shared_tolerances.values()):
            raise ValueError('Prepared shared-seam tolerances must be finite and positive.')
        self.symmetry_tolerance=min(float(model.tolerance),self.shared_tolerances['position'])
        self._mirror_normal=np.asarray(model.transverse,float)
        self._mirror_origin=(np.asarray(model.spec['profiles'][0]['p0'],float)+
                             np.asarray(model.spec['profiles'][4]['p0'],float))/2
        self._widths = np.asarray([float((np.asarray(model.spec['profiles'][i+1]['p0'])-
                                         np.asarray(model.spec['profiles'][i]['p0']))@model.transverse) for i in range(4)])
        if min(self._widths)<=model.tolerance:
            raise ValueError('The native section order is not suitable for bounded coupled edits.')
        self._cross_breaks = np.r_[0.,np.cumsum(self._widths)/sum(self._widths)]
        self._profile_groups = {0:(0,4),1:(1,3),2:(2,)}
        self._keys = (['row:%d:lift'%i for i in range(self.row_count)]+['profile:%d:lift'%i for i in range(3)]+
                      ['profile:0:upper','profile:0:lower'])
        self._verify_layout_support()
        self._prepare_coefficients()
        self._verify_source_responses()
        self._derive_shoulder_ranges()
        self._bind_repaired_guides()
        self._make_handles()
        signature = {'version':'bounded-uv-coupled-v1','source':self._source_digest,
                     'surfaces':self._records,'coupling':'mirror','native_rows':self.rows.tolist(),
                     'retained_guide_bindings':[x[0]['binding'] for x in self._retained_guides]}
        self.basis_id = 'uv-'+self._digest(signature)[:24]
        for array in self._baseline_cp+[a for group in self._responses.values() for a in group if a is not None]:
            array.setflags(write=False)

    @staticmethod
    def _digest(value):
        def default(x):
            if isinstance(x,np.ndarray):return x.tolist()
            if isinstance(x,np.generic):return x.item()
            if callable(x):return '<callback>'
            raise TypeError(type(x).__name__)
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False,default=default).encode()).hexdigest()

    def _check(self, cancelled=None):
        callback = cancelled or self.cancelled
        if callback and callback():
            raise self.kernel.Cancelled('Selected-U/V edit cancelled.')

    def _u_fields(self, record):
        """Scalar U response for each independent handle (mirror counted once)."""
        kind,piece,side = record.get('kind'),record.get('piece'),record.get('side')
        fields = {}
        if kind == 'middle' and piece in range(4):
            q0,q1 = self._cross_breaks[piece:piece+2]
            row_u = _compose(_BUMP,mp.mpf(float(q0)),mp.mpf(float(q1-q0)))
            for row in range(self.row_count):fields['row:%d:lift'%row] = row_u
            for canonical,profiles in self._profile_groups.items():
                u = _poly([0])
                if piece in profiles:u = _add(u,_HERMITE[0])
                if piece+1 in profiles:u = _add(u,_HERMITE[3])
                if np.any(u):fields['profile:%d:lift'%canonical] = u
            if 'profile:0:lift' in fields:
                fields['profile:0:upper']=fields['profile:0:lift']
                fields['profile:0:lower']=fields['profile:0:lift']
        elif kind in ('collar','lower_bridge') and side in (0,1) and piece == len(self.model.upper[side])-1:
            # Zero two-jets at the left artificial seam; move the new profile
            # trace at the right edge together with its neighboring middle band.
            fields['profile:0:lift'] = _HERMITE[3]
            fields['profile:0:upper'] = _HERMITE[3]
            fields['profile:0:lower'] = _HERMITE[3]
        return fields

    def _verify_layout_support(self):
        surfaces=self._baseline.get('surfaces',[])
        for piece in range(4):
            matches=[s for s in surfaces if s.get('kind')=='middle' and s.get('piece')==piece]
            if len(matches)!=1 or matches[0].get('domain')!=[[0.,1.],[self.v0,self.v1]]:
                raise ValueError('Bounded U/V edits require four retained full-domain central bands.')
        lo,hi=self.v0,self.v1
        # A named full U row must traverse both complete collars. In
        # particular, retaining a historical row inside a replaced fan must
        # not silently leave only the middle four guide segments visible.
        for v in self.rows:
            for side in (0,1):
                intervals=sorted(tuple(map(float,s['domain'][0])) for s in surfaces
                                 if s.get('kind')=='collar' and s.get('side')==side and
                                 s['domain'][1][0]<=v<=s['domain'][1][1])
                end=0.
                for a,b in intervals:
                    if b<=end:continue
                    if a>end+1e-12:break
                    end=max(end,b)
                if end<1.-1e-12:
                    raise ValueError('A displayed U row has incomplete collar coverage inside a replaced chart.')
        for side in (0,1):
            piece=len(self.model.upper[side])-1
            matches=[s for s in surfaces if s.get('kind') in ('collar','lower_bridge') and s.get('side')==side and s.get('piece')==piece]
            intervals=sorted(tuple(map(float,s['domain'][1])) for s in matches)
            end=lo
            for a,b in intervals:
                if b<=end:continue
                if a>end+1e-12:break
                end=max(end,b)
            if end<hi-1e-12:
                raise ValueError('Outer-profile shoulder support requires a retained last collar/bridge reaching both original source endpoints; rebuilding an incident corner is unsupported.')

    def _prepare_coefficients(self):
        total = 0
        with mp.workdps(70):
            for original in self._baseline['surfaces']:
                self._check()
                fields = self._u_fields(original)
                if not fields:
                    self._records.append({k:copy.deepcopy(v) for k,v in original.items() if k not in ('homogeneous_cp','homogeneousCP','weights','control_points')})
                    self._baseline_cp.append(np.asarray(original['homogeneous_cp'],float).copy())
                    for key in self._keys:self._responses.setdefault(key,[]).append(None)
                    total += self._baseline_cp[-1].shape[0]*self._baseline_cp[-1].shape[1]
                    continue
                breaks,spans = _span_coefficients(original)
                pu,pv = original['degree_u'],original['degree_v']
                # Denominators must be U-only; required by the exact affine lift.
                original_cp=np.asarray(original['homogeneous_cp'],float)
                weights=original_cp[:,0,3]
                if not np.all(original_cp[:,:,3]==weights[:,None]):
                    raise ValueError('Bounded U/V strip editing requires a fixed U-only rational denominator.')
                w = _b2p(_poly(weights))
                while len(w)>1 and abs(w[-1])<mp.mpf('1e-60'):w=w[:-1]
                degree_u = max(pu,max(len(u)+len(w)-2 for u in fields.values()))
                degree_v = max(pv,10)
                count = (degree_u+1)*(len(spans)*degree_v+1)
                if max(degree_u,degree_v)>40 or count>16384 or total+count>_MAX_CP:
                    raise ValueError('Bounded U/V degree or control-point budget exceeded before allocation.')
                total += count
                elevated = [_elevate(_elevate(span,degree_u,0),degree_v,1) for span in spans]
                # Preserve the proven V-constant weight identity through
                # floating degree elevation rather than inventing tiny V terms.
                elevated_weights=np.asarray(_p2b(w,degree_u),float)
                for span in elevated:span[:,:,3]=elevated_weights[:,None]
                base = np.concatenate([elevated[0]]+[x[:,1:] for x in elevated[1:]],axis=1)
                record = {k:copy.deepcopy(v) for k,v in original.items() if k not in ('homogeneous_cp','homogeneousCP','weights','control_points')}
                ua,ub = record['domain'][0]
                record.update(degree_u=degree_u,degree_v=degree_v,
                              knots_u=[ua]*(degree_u+1)+[ub]*(degree_u+1),
                              knots_v=[breaks[0]]*(degree_v+1)+sum(([v]*degree_v for v in breaks[1:-1]),[])+[breaks[-1]]*(degree_v+1))
                self._records.append(record);self._baseline_cp.append(base)
                for key in self._keys:
                    if key not in fields:
                        self._responses.setdefault(key,[]).append(None);continue
                    u = _p2b(_mul(w,fields[key]),degree_u)
                    response_spans = []
                    for a,b in zip(breaks[:-1],breaks[1:]):
                        if key.startswith('row:'):
                            row = int(key.split(':')[1])
                            bounds = (self.v0 if row==0 else float(self.rows[row-1]),float(self.rows[row]),
                                      self.v1 if row==self.row_count-1 else float(self.rows[row+1]))
                            v = _scalar_span('row',(a,b),bounds)
                        else:v = _scalar_span('profile',(a,b),self._profile_supports[key.split(':')[2]])
                        bv = _p2b(v,degree_v)
                        cp = np.zeros((degree_u+1,degree_v+1,4))
                        cp[:,:,:3] = np.asarray(u[:,None,None]*bv[None,:,None]*_poly(self.direction)[None,None,:],float)
                        response_spans.append(cp)
                    response = np.concatenate([response_spans[0]]+[x[:,1:] for x in response_spans[1:]],axis=1)
                    self._responses.setdefault(key,[]).append(response)
        if total>_MAX_CP:raise ValueError('Bounded U/V aggregate control-point budget exceeded.')
        self.coefficient_count = total

    def _anchor(self, identifier, surfaces):
        family,index,mode = identifier.split(':');index = int(index)
        if family == 'profile':
            matches = [s for s in surfaces if s.get('kind')=='middle' and s.get('piece')==min(index,3)]
            u = 1. if index==4 else 0.
            v = sum(self._profile_supports[mode])/2
        else:
            # The source-derived transverse midpoint need not coincide with a
            # named profile. Use the native cumulative section widths.
            piece = min(3,max(0,int(np.searchsorted(self._cross_breaks,.5,side='right')-1)))
            u = (.5-self._cross_breaks[piece])/(self._cross_breaks[piece+1]-self._cross_breaks[piece])
            v = float(self.rows[index])
            matches = [s for s in surfaces if s.get('kind')=='middle' and s.get('piece')==piece]
        if len(matches)!=1:raise ValueError('Expected exactly one central tensor band for a handle anchor.')
        return self.kernel.evaluate_surface(matches[0],u,v).tolist()

    def _derive_shoulder_ranges(self):
        """Bound every slider range from its actual affine Jacobian response.

        All displacement derivatives are parallel to the captured plane normal,
        so their mutual cross product vanishes: J(value)=J0+value*J1 exactly.
        The sampled J0-dot-J1 ratio supplies a conservative initial range with
        a 50% projection margin at those points. This is not a global immersion
        certificate; fresh whole-model gates still decide every requested value.
        """
        self._handle_ranges={};self._handle_range_evidence={}
        for key in self._keys:
            family,index,mode=key.split(':');index=int(index)
            support=((self.v0 if index==0 else float(self.rows[index-1]),
                      self.v1 if index==self.row_count-1 else float(self.rows[index+1]))
                     if family=='row' else self._profile_supports[mode])
            maximum=0.;samples=0
            for record,base,delta in zip(self._records,self._baseline_cp,self._responses[key]):
                self._check()
                if delta is None or not np.any(delta):continue
                lo=max(support[0],record['domain'][1][0]);hi=min(support[1],record['domain'][1][1])
                if not lo<hi:continue
                us=np.linspace(*record['domain'][0],17)
                breaks=sorted(set([lo,hi]+[float(v) for v in record['knots_v'] if lo<v<hi]))
                vs=sorted(set(a+(b-a)*q for a,b in zip(breaks[:-1],breaks[1:]) for q in np.linspace(0.,1.,17)))
                pu,pv=record['degree_u'],record['degree_v']
                bu=BSpline(record['knots_u'],np.eye(base.shape[0]),pu,extrapolate=False)
                bv=BSpline(record['knots_v'],np.eye(base.shape[1]),pv,extrapolate=False)
                U,Ud,V,Vd=bu(us),bu(us,nu=1),bv(vs),bv(vs,nu=1)
                def first_jets(cp):
                    h=np.einsum('ia,jb,abc->ijc',U,V,cp,optimize=True)
                    hu=np.einsum('ia,jb,abc->ijc',Ud,V,cp,optimize=True)
                    hv=np.einsum('ia,jb,abc->ijc',U,Vd,cp,optimize=True)
                    return h,hu,hv
                h,hu,hv=first_jets(base);d,du,dv=first_jets(delta)
                w=h[:,:,3,None]
                position=h[:,:,:3]/w
                su=(hu[:,:,:3]-position*hu[:,:,3,None])/w
                sv=(hv[:,:,:3]-position*hv[:,:,3,None])/w
                dp=d[:,:,:3]/w
                dsu=(du[:,:,:3]-dp*hu[:,:,3,None])/w
                dsv=(dv[:,:,:3]-dp*hv[:,:,3,None])/w
                j0=np.cross(su,sv);j1=np.cross(dsu,sv)+np.cross(su,dsv)
                area2=np.einsum('ijc,ijc->ij',j0,j0)
                if not np.isfinite(area2).all() or np.min(area2)<=0:
                    maximum=math.inf;break
                ratio=np.abs(np.einsum('ijc,ijc->ij',j0,j1))/area2
                maximum=max(maximum,float(np.max(ratio)));samples+=ratio.size
            bound=self.bound if maximum==0 else min(self.bound,.5/maximum)
            if not math.isfinite(bound) or bound<=0:bound=0.
            self._handle_ranges[key]=bound
            self._handle_range_evidence[key]=dict(sample_count=samples,maximum_affine_orientation_ratio=maximum,
                                                 bounded_value=bound,minimum_sampled_projection_fraction=.5,
                                                 global_regularity_certificate=False)
        self._shoulder_ranges={mode:self._handle_ranges['profile:0:'+mode] for mode in ('upper','lower')}
        self._shoulder_range_evidence={mode:self._handle_range_evidence['profile:0:'+mode] for mode in ('upper','lower')}

    @classmethod
    def _surface_signature(cls,surface):
        return cls._digest({k:surface[k] for k in
                           ('degree_u','degree_v','knots_u','knots_v','domain','homogeneous_cp')})

    def _bind_repaired_guides(self):
        self._retained_guides=[];coverage=self._covered_boundary_roles()
        surfaces=[_record_with_cp(r,cp) for r,cp in zip(self._records,self._baseline_cp)]
        collapsed=self._collapsed_guide_boundaries(surfaces)
        for index in collapsed:coverage.setdefault(index,set()).add(('u',0))
        for guide in self._baseline.get('guides',[]):
            kind=guide.get('kind')
            if kind in ('row_collar','row_middle'):
                row=guide.get('row')
                if type(row) is not int or not 0<=row<self.row_count:
                    raise ValueError('A historical row guide is not in the displayed row layout.')
                if 'native_v' in guide and guide['native_v']!=float(self.rows[row]):
                    raise ValueError('A row guide is bound to a stale native parameter.')
                continue
            if kind=='profile':continue
            binding=guide.get('binding',{})
            if (not isinstance(binding,dict) or set(binding)!={'schema','surface_index','varying_axis','constant_parameter'} or
                    binding.get('schema')!='smartskin.guide-isocurve.v1' or
                    type(binding.get('surface_index')) is not int or
                    not 0<=binding['surface_index']<len(surfaces) or
                    binding.get('varying_axis') not in ('u','v') or
                    type(binding.get('constant_parameter')) not in (int,float) or
                    not math.isfinite(binding['constant_parameter']) or
                    not isinstance(guide.get('guide_id'),str) or not guide['guide_id'] or
                    guide.get('varying_axis')!=binding['varying_axis']):
                raise ValueError('A repaired guide lacks an exact source-derived surface-isocurve binding.')
            index=binding['surface_index'];surface=surfaces[index]
            if index in collapsed and binding['varying_axis']=='u' and binding['constant_parameter']==surface['domain'][1][0]:
                raise ValueError('An approved collapsed point cannot be emitted as a degenerate curve guide.')
            changes=any(response[index] is not None and np.any(response[index]) for response in self._responses.values())
            original=self._baseline['surfaces'][index]
            expected=surface_isocurve(original,binding['varying_axis'],binding['constant_parameter'])
            if any(guide.get(k)!=expected[k] for k in ('degree','knots','domain')):
                raise ValueError('A repaired guide does not cover the complete bound chart trace.')
            error=_rational_control_bound(guide.get('homogeneous_cp',[]),expected['homogeneous_cp'])
            if not math.isfinite(error) or error>self.model.tolerance*.01:
                raise ValueError('A repaired guide is not on its bound unchanged surface.')
            fixed=1 if binding['varying_axis']=='u' else 0
            for end,parameter in enumerate(surface['domain'][fixed]):
                if binding['constant_parameter']==parameter:
                    coverage.setdefault(index,set()).add((binding['varying_axis'],end))
            signature=self._surface_signature(surface)
            regenerate=changes or signature!=self._surface_signature(original)
            extras=guide.get('coincident_bindings',[])
            if not isinstance(extras,list) or len(extras)>8:
                raise ValueError('Coincident guide bindings exceed their bounded list contract.')
            seen={self._digest(binding)};coincident=[]
            for extra in extras:
                if (not isinstance(extra,dict) or set(extra)!={'schema','surface_index','varying_axis','constant_parameter'} or
                        extra.get('schema')!='smartskin.guide-isocurve.v1' or type(extra.get('surface_index')) is not int or
                        not 0<=extra['surface_index']<len(surfaces) or extra.get('varying_axis') not in ('u','v') or
                        type(extra.get('constant_parameter')) not in (int,float) or not math.isfinite(extra['constant_parameter']) or
                        self._digest(extra) in seen):
                    raise ValueError('A coincident guide binding is malformed or duplicated.')
                seen.add(self._digest(extra));other_index=extra['surface_index']
                other=surface_isocurve(self._baseline['surfaces'][other_index],extra['varying_axis'],extra['constant_parameter'])
                bound=_coincident_curve_bound(expected,other,self.model.tolerance,self.cancelled)
                if not math.isfinite(bound) or bound>self.model.tolerance:
                    raise ValueError('A coincident binding is not the same whole geometric guide.')
                fixed=1 if extra['varying_axis']=='u' else 0
                for end,parameter in enumerate(surfaces[other_index]['domain'][fixed]):
                    if extra['constant_parameter']==parameter:coverage.setdefault(other_index,set()).add((extra['varying_axis'],end))
                coincident.append((copy.deepcopy(extra),self._digest(expected),self._digest(other)))
            self._retained_guides.append((copy.deepcopy(guide),index,signature,regenerate,coincident))
        complete={('u',0),('u',1),('v',0),('v',1)}
        for index,surface in enumerate(surfaces):
            if surface.get('kind') not in ('collar','middle') and coverage.get(index,set())!=complete:
                raise ValueError('A repaired chart is missing complete bound boundary-guide coverage.')
        self.guide_coverage=dict(schema='smartskin.guide-coverage.v1',checked=not self._role_coverage_pending,
                                 full_row_coverage=True,repaired_chart_boundary_coverage=not self._role_coverage_pending,
                                 row_count=self.row_count,retained_guide_count=len(self._retained_guides),
                                 regenerated_bound_guide_count=sum(int(x[3]) for x in self._retained_guides),
                                 role_coverage_pending_native_attachment=self._role_coverage_pending,
                                 approved_collapsed_point_count=len(collapsed))

    def _covered_boundary_roles(self):
        records=self._baseline.get('network',{}).get('repaired_boundary_roles',[])
        if not isinstance(records,list) or len(records)>256:raise ValueError('Repaired boundary-role coverage is malformed or unbounded.')
        allowed={'native_source_side','native_upper','native_lower','retained_body_2jet'}
        edges={'left':('v',0),'right':('v',1),'bottom':('u',0),'top':('u',1)}
        coverage={};self._role_coverage_pending=False
        proof=self._baseline.get('attachment_proof',{})
        proven=(proof.get('schema')=='smartskin.attachments.v2' and all(proof.get(k) is True for k in
                ('checked','source_full_finite_boundary_pass','shared_full_finite_boundary_pass')) and proof.get('excluded_intervals')==[])
        for record in records:
            if (not isinstance(record,dict) or set(record)!={'surface_index','edge','role'} or
                    type(record.get('surface_index')) is not int or not 0<=record['surface_index']<len(self._baseline['surfaces']) or
                    record.get('edge') not in edges or record.get('role') not in allowed):
                raise ValueError('Only named native-source/retained-body roles may replace duplicate exported boundary guides.')
            index=record['surface_index'];edge=record['edge'];role=record['role']
            declared=self._baseline['surfaces'][index].get('boundary_roles',{}).get(edge,{})
            if not isinstance(declared,dict) or declared.get('role')!=role:
                raise ValueError('Repaired boundary-role coverage does not match its actual chart ledger.')
            if edges[edge] in coverage.get(index,set()):raise ValueError('A repaired boundary-role coverage entry is duplicated.')
            if not proven:
                if not self.differential_only:raise ValueError('Boundary-role guide coverage requires a current full attachment proof.')
                self._role_coverage_pending=True
            coverage.setdefault(index,set()).add(edges[edge])
        return coverage

    def _collapsed_guide_boundaries(self,surfaces):
        """Only source-bound approved upper vertices may replace a curve edge."""
        records=self._baseline.get('network',{}).get('collapsed_boundary_bindings',[])
        if not isinstance(records,list):raise ValueError('Collapsed guide bindings must be explicit records.')
        output=set()
        for record in records:
            if (not isinstance(record,dict) or set(record)!={'surface_index','edge','corner_id'} or
                    type(record.get('surface_index')) is not int or not 0<=record['surface_index']<len(surfaces) or
                    record.get('edge')!='bottom' or record['surface_index'] in output):
                raise ValueError('A collapsed guide boundary is malformed or duplicated.')
            index=record['surface_index'];surface=surfaces[index];side=surface.get('side');corner=record['corner_id']
            if (surface.get('kind')!='upper_hard_corner' or side not in (0,1) or corner!='upper:side%d'%side or
                    surface.get('collapsed_parameter_edge')!='v=0' or surface['domain'][1][0]!=0. or
                    surface.get('approved_physical_corner_id')!=corner):
                raise ValueError('Only an approved upper hard-corner point may replace a guide curve.')
            evidence=self.model.spec.get('source_boundaries',{})
            if (evidence.get('schema')!='native-boundaries-v1' or evidence.get('complete') is not True or
                    evidence.get('status')!='validated'):
                if self.differential_only:
                    # Explicit research mode may inspect a numerical atlas
                    # before native owner replay exists. Verify both original
                    # numerical source endpoints, but keep guide coverage and
                    # editing disabled; do not manufacture a v2 owner proof.
                    try:
                        segment=self.model.spec['upper_paths'][side][0]
                        if segment['u_interval'][0]!=0.:raise ValueError('Not the original upper endpoint.')
                        _,_,_,domain=self.kernel._curve_record(segment['curve'])
                        parameter=domain[1] if segment.get('reverse',False) else domain[0]
                        up=self.kernel.evaluate_curve(segment['curve'],parameter)
                        parent=self.kernel._Side(self.model.spec['side_surfaces'][side]);sp=parent.jet(parent.v0)
                        curve=surface_isocurve(surface,'u',0.);cp=np.asarray(curve['homogeneous_cp'],float)
                        xyz=cp[:,:3]/cp[:,3,None]
                    except (KeyError,IndexError,TypeError) as error:
                        raise ValueError('The differential corner lacks its original numerical source endpoints.') from error
                    if (not np.isfinite(cp).all() or np.min(cp[:,3])<=0 or np.linalg.norm(up-sp)>self.model.tolerance or
                            float(np.max(np.linalg.norm(xyz-xyz[0],axis=1)))>self.model.tolerance*.01 or
                            float(np.max(np.linalg.norm(xyz-up,axis=1)))>self.model.tolerance):
                        raise ValueError('The differential collapsed edge is not the original numerical source corner.')
                    self._role_coverage_pending=True;output.add(index)
                    continue
                raise ValueError('A collapsed guide point needs independently captured source evidence.')
            roles=evidence.get('roles',{});side_role='side%d'%side
            if set(roles)!={'side0','side1','upper','lower'} or len(roles[side_role])!=1 or not roles['upper'] or not roles['lower']:
                raise ValueError('A collapsed guide point has incomplete or ambiguous source roles.')
            try:
                upper=roles['upper'][0 if side==0 else -1];parent=roles[side_role][0]
                def endpoint(source,traversal_end):
                    domain=source['original_curve_domain'];traversal=source['traversal_domain']
                    if len(domain)!=2 or len(traversal)!=2 or set(domain)!=set(traversal):
                        raise ValueError('A collapsed point lacks its original native endpoint domain.')
                    parameter=traversal[traversal_end];native_end=0 if parameter==domain[0] else 1
                    points=[x['point'] for x in source['reference_corners'] if x.get('edge_end')==native_end and x.get('edge_parameter')==parameter]
                    if len(points)!=1:raise ValueError('A collapsed guide point lacks a unique source endpoint witness.')
                    point=np.asarray(points[0],float)
                    if point.shape!=(3,) or not np.isfinite(point).all():raise ValueError('Invalid collapsed source point.')
                    return source['source_key'],parameter,point
                uk,ut,up=endpoint(upper,side);sk,st,sp=endpoint(parent,0)
            except (KeyError,IndexError,TypeError) as error:
                raise ValueError('A collapsed guide point lacks complete captured upper/side endpoint roles.') from error
            expected=dict(corner_id=corner,role='upper_source_corner',side_role=side_role,
                          upper_source_key=uk,upper_native_parameter=ut,side_source_key=sk,side_native_parameter=st)
            proof=self._baseline.get('attachment_proof',{})
            if (proof.get('schema')!='smartskin.attachments.v2' or proof.get('checked') is not True or
                    proof.get('source_full_finite_boundary_pass') is not True or proof.get('shared_full_finite_boundary_pass') is not True or
                    proof.get('corner_policy')!='hard_upper_source_corners' or proof.get('excluded_intervals')!=[] or
                    expected not in proof.get('excluded_points',[]) or uk==sk or np.linalg.norm(up-sp)>self.model.tolerance):
                raise ValueError('A collapsed guide point is not bound by the current approved source-vertex proof.')
            curve=surface_isocurve(surface,'u',0.)
            cp=np.asarray(curve['homogeneous_cp'],float)
            if not np.isfinite(cp).all() or np.min(cp[:,3])<=0:
                raise ValueError('A collapsed guide point has invalid rational coefficients.')
            xyz=cp[:,:3]/cp[:,3,None]
            if (float(np.max(np.linalg.norm(xyz-xyz[0],axis=1)))>self.model.tolerance*.01 or
                    float(np.max(np.linalg.norm(xyz-up,axis=1)))>self.model.tolerance):
                raise ValueError('The omitted curve edge is not the captured constant upper source point.')
            output.add(index)
        return output

    def _verify_source_responses(self):
        """Check whole-edge homogeneous coefficients, not sampled points.

        Three zero outer control rows fix every partial of total order <=2.
        Denominators never change. Unknown corner/fan charts have no response.
        Tiny conversion roundoff is projected to exact zero only after checking
        the analytic endpoint-zero identity against a scale-aware bound.
        """
        maximum = 0.
        for response in self._responses.values():
            for record,cp in zip(self._records,response):
                if cp is None:continue
                if np.any(cp[:,:,3]):raise ValueError('An edit response changes rational weights.')
                slices=[]
                va,vb=record['domain'][1]
                if va==self.v0:slices.append((slice(None),slice(0,3),slice(None)))
                if vb==self.v1:slices.append((slice(None),slice(-3,None),slice(None)))
                if record.get('kind')=='collar' and record.get('piece')==0:
                    slices.append((slice(0,3),slice(None),slice(None)))
                for index in slices:
                    error=float(np.max(np.abs(cp[index])))
                    maximum=max(maximum,error)
                    if error>1e-11:
                        raise ValueError('A selected-U/V basis changes an immutable source two-jet.')
                    cp[index]=0.
        self.source_response_error=maximum

    def _make_handles(self):
        surfaces = [_record_with_cp(r,c) for r,c in zip(self._records,self._baseline_cp)]
        for family,count,axis in (('row',self.row_count,'u'),('profile',5,'v')):
            for i in range(count):
                identifier = '%s:%d:lift'%(family,i)
                anchor = self._anchor(identifier,surfaces)
                canonical=identifier if family=='row' else 'profile:%d:lift'%min(i,4-i)
                supported=self._handle_ranges[canonical];bound=max(supported,self.model.tolerance)
                record = dict(id=identifier,guide_id='%s:%d'%(family,i),varying_axis=axis,
                              label='%s %d normal lift'%(axis.upper(),i+1),minimum=-bound,maximum=bound,
                              neutral=0.,units='model units',anchor=anchor,position=anchor,direction=self.direction.tolist())
                if supported<=self.model.tolerance:
                    record['locked_reason']='No meaningful regular range exceeds the model tolerance at the sampled Jacobian margin.'
                record['mirror_handle_id']=('profile:%d:lift'%(4-i) if family=='profile' else identifier)
                if family=='row':record['native_v']=float(self.rows[i])
                self._handle_specs.append(record)
        for mode in ('upper','lower'):
            for index in (0,4):
                identifier='profile:%d:%s'%(index,mode)
                anchor=self._anchor(identifier,surfaces)
                supported=self._shoulder_ranges[mode];bound=max(supported,self.model.tolerance)
                handle=dict(id=identifier,guide_id='profile:%d'%index,varying_axis='v',
                    label='%s shoulder lift'%mode.capitalize(),minimum=-bound,maximum=bound,
                    neutral=0.,units='model units',anchor=anchor,position=anchor,direction=self.direction.tolist(),
                    mirror_handle_id='profile:%d:%s'%(4-index,mode),native_v_support=list(self._profile_supports[mode]))
                if supported<=self.model.tolerance:
                    handle['locked_reason']='No meaningful regular shoulder range is supported by the sampled Jacobian response; native attachment is not the reason for this limit.'
                self._handle_specs.append(handle)

    def handle_edit_catalog(self):
        return dict(schema=HANDLE_SCHEMA,enabled=not self.differential_only,basis_id=self.basis_id,preserves_attachment_order=2,
                    handles=copy.deepcopy(self._handle_specs),mirror_coupling=True,
                    shared_tolerances=dict(self.shared_tolerances),
                    symmetry_tolerance=self.symmetry_tolerance,
                    row_count=self.row_count,native_v=self.rows.tolist(),
                    shoulder_range_evidence=copy.deepcopy(self._shoulder_range_evidence),
                    range_evidence=copy.deepcopy(self._handle_range_evidence),
                    reason=('The supplied base is differential-test only; native full attachment is unproved.' if self.differential_only else ''),
                    support_policy='body lifts between first/last full rows; mirrored outer-profile shoulder lifts reach original source endpoints')

    def _request(self, request):
        if (not isinstance(request,dict) or set(request)!={'schema','basis_id','revision','values'} or
                request.get('schema')!=HANDLE_SCHEMA or request.get('basis_id')!=self.basis_id or
                type(request.get('revision')) is not int or request['revision']<0):
            raise ValueError('Malformed or foreign selected-U/V edit request.')
        values = request.get('values')
        if not isinstance(values,dict) or set(values)!={h['id'] for h in self._handle_specs}:
            raise ValueError('The request must include every generated handle exactly once.')
        for h in self._handle_specs:
            v = values[h['id']]
            if type(v) not in (int,float) or not math.isfinite(v) or not h['minimum']<=v<=h['maximum']:
                raise ValueError('Selected-U/V handle value is nonfinite or outside its bounded range.')
            mirror = h.get('mirror_handle_id')
            if mirror and values[mirror]!=v:raise ValueError('Mirror-coupled profile values must agree.')
            if h.get('locked_reason') and v!=h['neutral']:raise ValueError(h['locked_reason'])
        return copy.deepcopy(request)

    def neutral_request(self, revision=0):
        return dict(schema=HANDLE_SCHEMA,basis_id=self.basis_id,revision=revision,
                    values={h['id']:0. for h in self._handle_specs})

    def _guides(self, surfaces, cancelled=None):
        out = []
        for j in range(5):
            surface = next(s for s in surfaces if s.get('kind')=='middle' and s.get('piece')==min(j,3))
            cp = np.asarray(surface['homogeneous_cp'],float)
            h = cp[-1 if j==4 else 0]
            out.append(dict(degree=surface['degree_v'],knots=list(surface['knots_v']),homogeneous_cp=h.tolist(),
                            domain=list(surface['domain'][1]),kind='profile',piece=j))
        for row,v in enumerate(self.rows):
            for s in surfaces:
                if s.get('kind') not in ('collar','middle') or not s['domain'][1][0]<=v<=s['domain'][1][1]:continue
                cp = np.asarray(s['homogeneous_cp'],float)
                basis = BSpline(s['knots_v'],np.eye(cp.shape[1]),s['degree_v'],extrapolate=False)(v)
                h = np.einsum('j,ijc->ic',basis,cp)
                out.append(dict(degree=s['degree_u'],knots=list(s['knots_u']),homogeneous_cp=h.tolist(),
                                domain=list(s['domain'][0]),kind='row_'+s['kind'],row=row,native_v=float(v),
                                side=s.get('side'),piece=s.get('piece')))
        for guide,index,signature,regenerate,coincident in self._retained_guides:
            self._check(cancelled)
            current=copy.deepcopy(guide)
            if regenerate:
                binding=guide['binding']
                for alias in ('homogeneousCP','control_points','weights','control_points_h'):current.pop(alias,None)
                current.update(surface_isocurve(surfaces[index],binding['varying_axis'],binding['constant_parameter']))
            elif self._surface_signature(surfaces[index])!=signature:
                raise ValueError('A retained repaired guide is no longer bound to unchanged geometry.')
            curve={k:current[k] for k in ('degree','knots','domain','homogeneous_cp')}
            for other_binding,primary_signature,other_signature in coincident:
                other=surface_isocurve(surfaces[other_binding['surface_index']],other_binding['varying_axis'],other_binding['constant_parameter'])
                if self._digest(curve)==primary_signature and self._digest(other)==other_signature:continue
                bound=_coincident_curve_bound(curve,other,self.model.tolerance,cancelled or self.cancelled)
                if not math.isfinite(bound) or bound>self.model.tolerance:
                    raise ValueError('An edited coincident guide no longer matches its other incident chart.')
            out.append(current)
        return out

    def _geometric_symmetry(self, surfaces, cancelled=None):
        """Fresh all-parameter positional bound on every reflected chart pair.

        Matching positive rational basis weights make a surface a convex
        combination of its Euclidean control points. Slightly nonproportional
        weights add a conservative total-variation bound. This is a geometric
        coefficient check, not a test of equal requested scalar values. An
        unknown or unmatched chart/parameter basis cannot earn a symmetry pass.
        """
        def key(s):
            kind=s.get('kind')
            if kind not in ('middle','collar','upper_hard_corner','fan_prototype','lower_chart','lower_bridge'):
                raise ValueError('An output chart has no verified mirror correspondence.')
            side=s.get('side')
            if kind!='middle' and side not in (0,1):
                raise ValueError('A mirrored output chart has no source-side identity.')
            return kind,side,s.get('piece'),tuple(s['domain'][1])

        def basis(s,axis,reverse=False):
            a,b=map(float,s['domain'][axis]);knots=np.asarray(s['knots_'+('u' if axis==0 else 'v')],float)
            normalized=(knots-a)/(b-a)
            return 1-normalized[::-1] if reverse else normalized

        try:
            records={}
            for s in surfaces:
                identity=key(s)
                if identity in records:raise ValueError('A mirror chart identity is ambiguous.')
                records[identity]=s
            residual=0.;visited=set();pairs=0
            for identity,left in records.items():
                self._check(cancelled)
                if identity in visited:continue
                kind,side,piece,domain_v=identity
                mirror=(kind,None,3-piece,domain_v) if kind=='middle' else (kind,1-side,piece,domain_v)
                right=records.get(mirror)
                if right is None:raise ValueError('An output chart is missing its mirrored partner.')
                reverse=kind=='middle'
                if (left['degree_u']!=right['degree_u'] or left['degree_v']!=right['degree_v'] or
                        not np.array_equal(basis(left,0),basis(right,0,reverse)) or
                        not np.array_equal(basis(left,1),basis(right,1))):
                    raise ValueError('Mirrored charts use different parameter bases; a geometric symmetry bound is unavailable.')
                lc=np.asarray(left['homogeneous_cp'],float)
                rc=np.asarray(right['homogeneous_cp'],float)
                if reverse:rc=rc[::-1]
                if lc.shape!=rc.shape or not np.isfinite(lc).all() or not np.isfinite(rc).all():
                    raise ValueError('Mirrored rational chart coefficients are incompatible or nonfinite.')
                lw,rw=lc[:,:,3],rc[:,:,3]
                if np.min(lw)<=0 or np.min(rw)<=0:
                    raise ValueError('Geometric symmetry requires positive rational weights.')
                lp=lc[:,:,:3]/lw[:,:,None];rp=rc[:,:,:3]/rw[:,:,None]
                rp=rp-2*np.einsum('ijc,c->ij',rp-self._mirror_origin,self._mirror_normal)[:,:,None]*self._mirror_normal
                point_bound=float(np.max(np.linalg.norm(lp-rp,axis=2)))
                # Let r_i = w_left_i/(k*w_right_i), so |r_i-1|<=eta.
                # The induced normalized basis weights differ in L1 by at
                # most 2*eta/(1-eta); subtracting a reference point gives a
                # translation-invariant positional bound for that term.
                logs=np.log(lw)-np.log(rw)
                centered=logs-(float(np.min(logs))+float(np.max(logs)))/2
                eta=math.inf if np.max(np.abs(centered))>math.log(2.) else float(np.max(np.abs(np.expm1(centered))))
                if eta>=1 or not math.isfinite(point_bound):
                    bound=math.inf
                else:
                    radius=float(np.max(np.linalg.norm(rp-rp[0,0],axis=2)))
                    bound=point_bound+2*eta*radius/(1-eta)
                residual=max(residual,bound)
                visited.update((identity,mirror));pairs+=1
            if len(visited)!=len(records) or not pairs:
                raise ValueError('Not every output chart participated in the symmetry check.')
            return dict(checked=True,compatible=math.isfinite(residual) and residual<=self.symmetry_tolerance,
                        residual=float(residual),tolerance=self.symmetry_tolerance,chart_pairs=pairs,
                        method='whole-surface rational control-hull reflection bound',reason='')
        except (ValueError,KeyError,TypeError,OverflowError) as error:
            return dict(checked=False,compatible=False,residual=math.inf,tolerance=self.symmetry_tolerance,
                        chart_pairs=0,method='whole-surface rational control-hull reflection bound',reason=str(error))

    def exact_initial_neutral(self,baseline,request,cancelled=None):
        """Bind a zero operation to the original checked descriptors verbatim.

        The prepared-model caller also verifies its sealed validator/source and
        basis state. Differential test mode remains non-committable here.
        """
        request=self._request(request);self._check(cancelled)
        if self._digest(self.model.spec)!=self._source_digest:
            raise ValueError('Captured source records changed after edit preparation.')
        if any(h['neutral']!=0. or request['values'][h['id']]!=0. for h in self._handle_specs):
            raise ValueError('Initial neutral handoff requires exact zero handle values.')
        fields=('surfaces','patches','guides','network','report','metrics','attachment_proof',
                'atlas_separation','atlas_adjacency','native_contact_ledger')
        if any(self._digest(baseline.get(key))!=self._digest(self._baseline.get(key)) for key in fields):
            raise ValueError('Initial neutral descriptors or validator evidence changed.')
        candidate=dict(surfaces=copy.deepcopy(baseline['surfaces']),patches=copy.deepcopy(baseline['surfaces']),
                       guides=copy.deepcopy(baseline['guides']),network=copy.deepcopy(baseline['network']),
                       edit_request=request,guide_coverage=copy.deepcopy(self.guide_coverage),
                       handle_positions_request=copy.deepcopy(request),
                       handle_positions={h['id']:self._anchor(h['id'],baseline['surfaces']) for h in self._handle_specs})
        result=self._finish_edit_candidate(candidate,copy.deepcopy(baseline),cancelled)
        result['edit_proof']['method']='exact zero operation on the verbatim validated baseline; fresh request positions and symmetry'
        result['initial_neutral_reuse']=dict(schema='smartskin.exact-neutral.v1',
            ordered_geometry_unchanged=True,ordered_guides_unchanged=True,network_unchanged=True,
            native_owner_receipt_reused=False)
        # Native host receipts belong to the preview session, never this cache.
        for key in ('native_receipt','native_owner_receipt','native_separation_proof'):
            result.pop(key,None)
        return result

    def evaluate_edit(self, request, cancelled=None):
        request = self._request(request);self._check(cancelled)
        if self._digest(self.model.spec)!=self._source_digest:
            raise ValueError('Captured source records changed after edit preparation.')
        surfaces = []
        for index,(template,base) in enumerate(zip(self._records,self._baseline_cp)):
            self._check(cancelled);cp=base.copy()
            for key,response in self._responses.items():
                delta=response[index]
                if delta is not None:cp += float(request['values'][key])*delta
            if not np.isfinite(cp).all() or np.min(cp[:,:,3])<=0:
                raise ValueError('Edited homogeneous coefficients are nonfinite or have invalid weights.')
            surfaces.append(_record_with_cp(template,cp))
        candidate=dict(surfaces=surfaces,patches=surfaces,guides=self._guides(surfaces,cancelled),
                       network=copy.deepcopy(self._baseline.get('network',{})),edit_request=request,
                       guide_coverage=copy.deepcopy(self.guide_coverage),handle_positions_request=copy.deepcopy(request),
                       handle_positions={h['id']:self._anchor(h['id'],surfaces) for h in self._handle_specs})
        # The validator may return a complete result or just a fresh report.
        checked = self.validator(candidate if self.validator_receives_result else surfaces,cancelled or self.cancelled)
        return self._finish_edit_candidate(candidate,checked,cancelled)

    def _finish_edit_candidate(self,candidate,checked,cancelled=None):
        request=candidate['edit_request'];surfaces=candidate['surfaces']
        self._check(cancelled)
        if self._digest(self.model.spec)!=self._source_digest:
            raise ValueError('Captured source records changed during edit validation.')
        if not isinstance(checked,dict):raise ValueError('The per-value validator returned no proof.')
        if 'report' in checked:
            result = copy.deepcopy(checked)
        else:
            report=copy.deepcopy(checked)
            result = dict(report=report,metrics=report)
            if 'attachment_proof' in checked:result['attachment_proof']=copy.deepcopy(checked['attachment_proof'])
            for name in ('disposition','commit_disposition','native_screen_pending'):
                if name in checked:result[name]=copy.deepcopy(checked[name])
        report = result['report']
        result.update(candidate)
        residuals = dict(position=float(report.get('seam_position_error',math.inf)),
                         normal_angle_degrees=float(report.get('seam_angle_degrees',math.inf)),
                         shape_operator=float(report.get('seam_curvature_error',math.inf)))
        tolerances = dict(position=float(report.get('position_tolerance',self.shared_tolerances['position'])),
                          normal_angle_degrees=float(report.get('angle_tolerance_degrees',self.shared_tolerances['normal_angle_degrees'])),
                          shape_operator=float(report.get('curvature_tolerance',self.shared_tolerances['shape_operator'])))
        if tolerances!=self.shared_tolerances:
            raise ValueError('A per-value validator changed the prepared shared-seam tolerances.')
        symmetry=self._geometric_symmetry(surfaces,cancelled)
        report.update(symmetry_checked=symmetry['checked'],symmetry_compatible=symmetry['compatible'],
                      symmetry_residual=symmetry['residual'],symmetry_tolerance=self.symmetry_tolerance,
                      symmetry_method=symmetry['method'],symmetry_chart_pairs=symmetry['chart_pairs'])
        shared = bool(report.get('checked') is True and all(math.isfinite(float(x)) and 0<=x<=tolerances[k]
                                                           for k,x in residuals.items()))
        result['edit_proof'] = dict(schema=PROOF_SCHEMA,checked=report.get('checked') is True,
                                   source_2jets_unchanged=True,shared_2jets_compatible=shared,
                                   shared_residuals=residuals,shared_tolerances=tolerances,
                                   source_response_coefficient_error=self.source_response_error,
                                   symmetry_checked=symmetry['checked'],symmetry_compatible=symmetry['compatible'],
                                   symmetry_residual=symmetry['residual'],symmetry_tolerance=self.symmetry_tolerance,
                                   method='fixed-layout homogeneous affine lifts; per-value geometric seam checks')
        valid = report.get('checked') is True and not report.get('fatal',True) and shared and symmetry['compatible']
        attachment=result.get('attachment_proof',{})
        full_attachment=(isinstance(attachment,dict) and
                         attachment.get('schema')=='smartskin.attachments.v2' and
                         attachment.get('corner_policy')=='hard_upper_source_corners' and
                         attachment.get('excluded_intervals')==[] and
                         all(attachment.get(k) is True for k in
                             ('checked','source_full_finite_boundary_pass','shared_full_finite_boundary_pass')))
        numeric_ready=bool(valid and not self.differential_only and full_attachment and report.get('full_boundary_pass') is True)
        reason=report.get('reason','')
        if not shared:reason='Post-edit shared two-jet compatibility was not verified. '+reason
        if not symmetry['compatible']:reason='Post-edit geometric symmetry failed. '+symmetry['reason']+' '+reason
        elif valid and not self.differential_only and not full_attachment:
            reason='The edited value has no fresh full native attachment proof. '+reason
        if numeric_ready:reason='Numerical attachment checks passed; the native owner-separation screen is pending. '+reason
        result.update(valid=valid,geometry_valid=valid,fatal=not valid,reason=report.get('reason',''),
                      full_boundary_pass=bool(report.get('full_boundary_pass',False)),
                      continuity_pass=bool(report.get('full_boundary_pass',False)),experimental_commit_allowed=False,
                      disposition=('native_screen_pending' if numeric_ready else 'differential_only' if self.differential_only else 'blocked'),
                      commit_disposition=('native_screen_pending' if numeric_ready else 'blocked'),native_screen_pending=numeric_ready,
                      experimental=not bool(report.get('full_boundary_pass',False)))
        result['reason']=reason
        # Ordinary edits receive only the fresh validator's attachment proof.
        # The separately sealed exact-neutral path may reuse that same proof
        # solely with verbatim source-bound geometry, guides and coverage.
        return result
