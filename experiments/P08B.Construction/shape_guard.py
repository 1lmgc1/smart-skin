# -*- coding: utf-8 -*-
"""P08B.3: bounded cubic-patch geometry checks, independent of Rhino.

Every positive knot cell is converted to a tensor Bezier net. Bernstein bounds
on its projected Jacobian are subdivided when inconclusive. This is a numerical
single-chart guard, NOT a formal interval-arithmetic or global intersection
certificate. Inconclusive/budget-limited checks fail closed. Positive projection
is intentionally more restrictive than mere nonzero 3D Jacobian.
"""
from __future__ import division
import math
from mixed_kernel import Patch, SIDES, basis, dot, add, sub, mul, norm, cross, unit, finite, side_uv


def _check(callback):
    if callback is not None: callback()


def spans(K):
    return [(a,b) for a,b in zip(K,K[1:]) if b>a]


class FastEvaluator(object):
    """Sparse tensor evaluation with per-axis basis caching (no NumPy in Rhino)."""
    def __init__(self, patch):
        self.patch=patch; self.cache={}
    def weights(self,t):
        if t not in self.cache:
            rows=basis(self.patch.n,self.patch.p,t,self.patch.K)
            self.cache[t]=[[(i,x) for i,x in enumerate(row) if x] for row in rows]
        return self.cache[t]
    def eval(self,u,v):
        bu,bv=self.weights(u),self.weights(v); out=[]; net=self.patch.net
        for du,dv in ((0,0),(1,0),(0,1),(2,0),(1,1),(0,2)):
            data=[0.,0.,0.]
            for i,x in bu[du]:
                for j,y in bv[dv]:
                    c=x*y; pt=net[i][j]
                    for k in range(3): data[k]+=c*pt[k]
            out.append(tuple(data))
        return tuple(out)


def cell_extractors(patch):
    if patch.p!=3: raise ValueError('SHAPE_GUARD_REQUIRES_CUBIC_NONRATIONAL_PATCH')
    K=patch.K
    if K[:4]!=[0.]*4 or K[-4:]!=[1.]*4 or len(K)!=patch.n+4:
        raise ValueError('SHAPE_GUARD_INVALID_CLAMPED_KNOTS')
    if any(not finite(x) for x in K) or any(a>b for a,b in zip(K,K[1:])):
        raise ValueError('SHAPE_GUARD_INVALID_KNOTS')
    interior=K[4:-4]
    if len(set(interior))!=len(interior):
        raise ValueError('SHAPE_GUARD_SIMPLE_INTERIOR_KNOTS_REQUIRED')
    out=[]
    for a,b in spans(K):
        left=basis(patch.n,3,a,K); right=basis(patch.n,3,b,K); h=(b-a)/3.
        vectors=[left[0], [x+h*y for x,y in zip(left[0],left[1])],
                 [x-h*y for x,y in zip(right[0],right[1])], right[0]]
        out.append((a,b,[[(i,x) for i,x in enumerate(row) if abs(x)>1e-16] for row in vectors]))
    return out


def bezier_cell(patch,eu,ev):
    net=[]
    for row in eu:
        nr=[]
        for col in ev:
            value=[0.,0.,0.]
            for i,a in row:
                for j,b in col:
                    for k in range(3): value[k]+=a*b*patch.net[i][j][k]
            nr.append(tuple(value))
        net.append(nr)
    return net


def _choose(n,k):
    return math.factorial(n)//(math.factorial(k)*math.factorial(n-k))


# Products of Bernstein polynomials use positive binomial-ratio coefficients.
_PRODUCT_WEIGHTS=[(i,j,r,s,_choose(2,i)*_choose(3,r)/_choose(5,i+r)
                  *_choose(3,j)*_choose(2,s)/_choose(5,j+s))
                  for i in range(3) for j in range(4) for r in range(4) for s in range(3)]


def jacobian_coefficients(net,normal):
    a=[[mul(sub(net[i+1][j],net[i][j]),3.) for j in range(4)] for i in range(3)]
    b=[[mul(sub(net[i][j+1],net[i][j]),3.) for j in range(3)] for i in range(4)]
    scale=max(norm(x) for row in a for x in row)*max(norm(x) for row in b for x in row)
    if not finite(scale) or scale<=1e-24: raise ValueError('DEGENERATE_BEZIER_CELL')
    C=[[0.]*6 for _ in range(6)]
    for i,j,r,s,w in _PRODUCT_WEIGHTS:
        C[i+r][j+s]+=w*dot(cross(a[i][j],b[r][s]),normal)/scale
    return C


def split_scalar(C,axis):
    n=len(C); m=len(C[0]); low=[[0.]*m for _ in range(n)]; high=[[0.]*m for _ in range(n)]
    for index in range(m if axis==0 else n):
        values=[C[i][index] for i in range(n)] if axis==0 else list(C[index])
        left=[values[0]]; right=[values[-1]]
        while len(values)>1:
            values=[(a+b)*.5 for a,b in zip(values,values[1:])]
            left.append(values[0]); right.append(values[-1])
        right.reverse()
        for k in range(len(left)):
            if axis==0: low[k][index]=left[k]; high[k][index]=right[k]
            else: low[index][k]=left[k]; high[index][k]=right[k]
    return low,high


def positive_bernstein(C,checkpoint=None,max_depth=5,max_nodes=2048,epsilon=1e-9):
    """Return a positive lower bound or a named unresolved/negative outcome.
    A negative coefficient alone is NOT claimed to be a negative function value.
    """
    stack=[(C,0,(0.,1.,0.,1.))]; visited=0; lower=1.; depth_used=0
    while stack:
        _check(checkpoint); co,depth,box=stack.pop(); visited+=1; depth_used=max(depth_used,depth)
        values=[x for row in co for x in row]
        if not all(finite(x) for x in values):
            return dict(ok=False,reason='NONFINITE_JACOBIAN',nodes=visited,box=box)
        lo,hi=min(values),max(values)
        if lo>epsilon:
            lower=min(lower,lo); continue
        # Corner control values are actual endpoint values; the others only bound.
        if min(co[0][0],co[-1][0],co[0][-1],co[-1][-1])<=epsilon:
            return dict(ok=False,reason='NONPOSITIVE_PROJECTED_JACOBIAN_SAMPLE',nodes=visited,box=box,lower=lo)
        if hi<=epsilon:
            return dict(ok=False,reason='NONPOSITIVE_PROJECTED_JACOBIAN_CELL',nodes=visited,box=box,lower=lo)
        if depth>=max_depth or visited>=max_nodes:
            return dict(ok=False,reason='PROJECTED_JACOBIAN_UNRESOLVED',nodes=visited,box=box,lower=lo)
        a,b=split_scalar(co,0); a0,a1=split_scalar(a,1); b0,b1=split_scalar(b,1)
        u0,u1,v0,v1=box; um=(u0+u1)*.5; vm=(v0+v1)*.5
        stack.extend([(a0,depth+1,(u0,um,v0,vm)),(a1,depth+1,(u0,um,vm,v1)),
                      (b0,depth+1,(um,u1,v0,vm)),(b1,depth+1,(um,u1,vm,v1))])
    return dict(ok=True,reason='POSITIVE_BERNSTEIN_NUMERICAL_BOUND',lower=lower,nodes=visited,depth=depth_used)


def geometry_scale(boundaries):
    distances=[]
    for a,b in (('bottom','top'),('left','right')):
        distances.append(sum(norm(sub(boundaries[a](i/8.).point,boundaries[b](i/8.).point)) for i in range(9))/9.)
    scale=min(distances)
    if not finite(scale) or scale<=1e-10: raise ValueError('DEGENERATE_OPENING_SCALE')
    return scale


class ShapePolicy(object):
    """Read-only limits tied to the opening, not to an already distorted candidate.
    Bezier hull containment is conservative: an outside CV is a guard rejection,
    not a claim that the surface necessarily leaves the envelope.
    """
    def __init__(self,anchor,boundaries,tolerance,step_fraction=.06,total_fraction=.45):
        self.scale=geometry_scale(boundaries); self.tolerance=tolerance
        self.step_limit=step_fraction*self.scale; self.total_limit=total_fraction*self.scale
        sample=anchor.eval(.5,.5); self.origin=sample[0]
        x=unit(sample[1]); z=unit(cross(sample[1],sample[2])); y=unit(cross(z,x))
        self.axes=(x,y,z); self.normal=z
        pts=[boundaries[s](i/64.).point for s in SIDES for i in range(65)]
        coords=[[dot(sub(p,self.origin),axis) for p in pts] for axis in self.axes]
        margins=(.25*self.scale,.25*self.scale,.75*self.scale)
        self.limits=[(min(c)-m-2*tolerance,max(c)+m+2*tolerance) for c,m in zip(coords,margins)]
    def inspect(self,patch,anchor=None,checkpoint=None):
        _check(checkpoint)
        result=dict(ok=False,reason='NOT_CHECKED',scale=self.scale,cells=0,subdivision_nodes=0,
                    min_jacobian_bound=1.,scope='NUMERICAL_BERNSTEIN_SINGLE_CHART;NOT_GLOBAL_INTERSECTION_CERTIFICATE')
        if anchor is not None:
            if anchor.n!=patch.n or anchor.K!=patch.K: raise ValueError('ANCHOR_BASIS_MISMATCH')
            displacement=max(norm(sub(patch.net[i][j],anchor.net[i][j])) for i in range(patch.n) for j in range(patch.n))
            result['max_control_displacement']=displacement; result['total_limit']=self.total_limit
            if displacement>self.total_limit*(1+1e-12):
                result['reason']='ANCHOR_DISPLACEMENT_LIMIT'; return result
        extraction=cell_extractors(patch)
        if len(extraction)>29: raise ValueError('SHAPE_CELL_BUDGET')
        for ua,ub,eu in extraction:
            for va,vb,ev in extraction:
                _check(checkpoint); result['cells']+=1
                net=bezier_cell(patch,eu,ev)
                for row in net:
                    for point in row:
                        for axis,(lo,hi) in zip(self.axes,self.limits):
                            x=dot(sub(point,self.origin),axis)
                            if not finite(x) or x<lo or x>hi:
                                result.update(reason='BEZIER_ENVELOPE_UNRESOLVED',cell=(ua,ub,va,vb),value=x,allowed=(lo,hi))
                                return result
                try: coef=jacobian_coefficients(net,self.normal)
                except ValueError as error:
                    result.update(reason=str(error),cell=(ua,ub,va,vb)); return result
                test=positive_bernstein(coef,checkpoint)
                result['subdivision_nodes']+=test['nodes']
                if not test['ok']:
                    result.update(reason=test['reason'],cell=(ua,ub,va,vb),local_box=test.get('box'))
                    return result
                result['min_jacobian_bound']=min(result['min_jacobian_bound'],test['lower'])
        result.update(ok=True,reason='SHAPE_NUMERICAL_BOUNDS_MET'); return result


def harmonic_seed(patch,sweeps=160,checkpoint=None):
    """Positive-weight nonuniform discrete Laplace seed; original boundary frozen.
    Each update is a convex combination of four neighbours. Not a G1/G2 solver.
    """
    n=patch.n; g=[sum(patch.K[i+1:i+patch.p+1])/patch.p for i in range(n)]
    net=[[tuple(pt) for pt in row] for row in patch.net]
    center=mul(tuple(sum(pt[k] for pt in patch.boundary_snapshot()) for k in range(3)),1./len(patch.boundary_snapshot()))
    for i in range(1,n-1):
        for j in range(1,n-1): net[i][j]=center
    for sweep in range(sweeps):
        _check(checkpoint)
        for i in range(1,n-1):
            a,b=g[i]-g[i-1],g[i+1]-g[i]
            wu0,wu1=1./(a*(a+b)),1./(b*(a+b))
            for j in range(1,n-1):
                c,d=g[j]-g[j-1],g[j+1]-g[j]
                wv0,wv1=1./(c*(c+d)),1./(d*(c+d)); total=wu0+wu1+wv0+wv1
                net[i][j]=tuple((wu0*net[i-1][j][k]+wu1*net[i+1][j][k]+wv0*net[i][j-1][k]+wv1*net[i][j+1][k])/total for k in range(3))
    result=Patch(net,patch.p,patch.K)
    if result.boundary_snapshot()!=patch.boundary_snapshot(): raise AssertionError('HARMONIC_MOVED_BOUNDARY')
    return result
