"""Bounded native-source family recognition; no model IDs or cached geometry.

All coordinates come from selected native edges and their uniquely owning faces.
Source records are immutable. Unsupported topology is an explicit error.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import numpy as np
from scipy.interpolate import BSpline, BPoly, PPoly
from scipy.integrate import quad
from scipy.optimize import brentq, least_squares, minimize


try:
    from _smartskin_p08e1_native_boundary_evidence import build_source_boundaries, require_complete_evidence, BoundaryEvidenceError
except ModuleNotFoundError as error:
    if error.name != '_smartskin_p08e1_native_boundary_evidence':
        raise
    from native_boundary_evidence import build_source_boundaries, require_complete_evidence, BoundaryEvidenceError


class UnsupportedFamily(ValueError):
    def __init__(self, code, detail):
        self.code = code
        super().__init__(code + ': ' + detail)


def fail(code, detail):
    raise UnsupportedFamily(code, detail)


def finite(a, name):
    a = np.asarray(a, dtype=float)
    if not np.all(np.isfinite(a)):
        fail('NONFINITE_INPUT', name)
    return a


def unit(a):
    a = finite(a, 'vector')
    n = np.linalg.norm(a)
    if n <= 1e-14:
        fail('DEGENERATE_FRAME', 'Zero direction.')
    return a / n


def check_cancel(cancelled):
    if cancelled and cancelled():
        fail('CANCELLED', 'Cancelled between bounded operations.')


class Curve:
    def __init__(self, record):
        self.record = record
        self.degree = int(record['degree'])
        self.cp = finite(record['homogeneous_cp'], 'curve control net')
        self.knots = finite(record['knots'], 'curve knots')
        if self.cp.ndim != 2 or self.cp.shape[1] != 4 or len(self.cp) > 512:
            fail('CURVE_COMPLEXITY', 'Expected at most512 homogeneous control points.')
        if not 1 <= self.degree <= 7 or len(self.knots) != len(self.cp) + self.degree + 1:
            fail('CURVE_BASIS', 'Unsupported degree or knot count.')
        if np.any(self.cp[:, 3] <= 0) or np.any(np.diff(self.knots) < 0):
            fail('CURVE_BASIS', 'Positive rational weights and ordered knots are required.')
        self.domain = tuple(record.get('domain', (self.knots[self.degree], self.knots[-self.degree-1])))
        if self.domain[1] <= self.domain[0]:
            fail('CURVE_DOMAIN', 'Empty source interval.')
        self.b = BSpline(self.knots, self.cp, self.degree, extrapolate=False)

    def __call__(self, t, d=0):
        h = self.b(t)
        p = h[..., :3] / h[..., 3, None]
        if d == 0:
            return p
        h1 = self.b(t, nu=1)
        p1 = (h1[..., :3] - h1[..., 3, None] * p) / h[..., 3, None]
        if d == 1:
            return p1
        h2 = self.b(t, nu=2) if self.degree >= 2 else np.zeros_like(h)
        return (h2[..., :3] - h2[..., 3, None]*p - 2*h1[..., 3, None]*p1) / h[..., 3, None]

    def samples(self, count=33):
        return self(np.linspace(*self.domain, count))

    def bezier_spans(self):
        """Exact homogeneous knot insertion on the active source interval.

        The source record, full control net, and original knots remain immutable.
        Returned control nets are analytical restrictions, never sampled fits.
        """
        lo,hi=self.domain
        if lo<self.knots[self.degree] or hi>self.knots[-self.degree-1]:
            fail('CURVE_DOMAIN','Source interval lies outside its native curve domain.')
        breaks=np.unique(np.r_[lo,self.knots[(self.knots>lo)&(self.knots<hi)],hi])
        spline=self.b
        for t in breaks:
            multiplicity=int(np.count_nonzero(spline.t==t))
            if multiplicity<self.degree:
                spline=spline.insert_knot(float(t),self.degree-multiplicity)
        spans=[]
        for a,b in zip(breaks[:-1],breaks[1:]):
            k=int(np.searchsorted(spline.t,(a+b)/2,side='right')-1)
            spans.append((float(a),float(b),np.array(spline.c[k-self.degree:k+1],copy=True)))
        return spans

    def linear(self, tolerance):
        direction = self(self.domain[1])-self(self.domain[0])
        if np.linalg.norm(direction) <= tolerance:
            return False
        # In particular, a line subinterval of a compound curve is tested on
        # its own exact restricted control net, not unrelated parent handles.
        p=np.concatenate([h[:,:3]/h[:,3,None] for _,_,h in self.bezier_spans()])
        return np.max(np.linalg.norm(np.cross(p-self(self.domain[0]),unit(direction)),axis=1))<=tolerance


class Surface:
    def __init__(self, record):
        self.record = record
        self.cp = finite(record['homogeneous_cp'], 'surface control net')
        self.ku = finite(record['knots_u'], 'surface U knots')
        self.kv = finite(record['knots_v'], 'surface V knots')
        self.du, self.dv = int(record['degree_u']), int(record['degree_v'])
        if self.cp.ndim != 3 or self.cp.shape[2] != 4 or self.cp.shape[0] > 512 or self.cp.shape[1] > 128:
            fail('SURFACE_COMPLEXITY', 'Native surface exceeds the bounded control-net budget.')
        if not 1 <= self.du <= 5 or not 1 <= self.dv <= 7:
            fail('SURFACE_DEGREE', 'Supported native degree: U<=5,V<=7 before orientation.')
        if len(self.ku) != self.cp.shape[0]+self.du+1 or len(self.kv) != self.cp.shape[1]+self.dv+1:
            fail('SURFACE_BASIS', 'Native knot/control count mismatch.')
        if np.any(self.cp[..., 3] <= 0):
            fail('SURFACE_WEIGHT', 'Positive native weights are required.')
        self.ud = (self.ku[self.du], self.ku[-self.du-1])
        self.vd = (self.kv[self.dv], self.kv[-self.dv-1])
        self.bu = BSpline(self.ku, np.eye(self.cp.shape[0]), self.du, extrapolate=False)
        self.bv = BSpline(self.kv, np.eye(self.cp.shape[1]), self.dv, extrapolate=False)

    def homogeneous(self, u, v, du=0, dv=0):
        if du > self.du or dv > self.dv:
            return np.zeros(4)
        return np.einsum('i,j,ijc->c', self.bu(u, nu=du), self.bv(v, nu=dv), self.cp)

    def jet(self, u, v):
        h, hu, hv, huu, huv, hvv = [self.homogeneous(u,v,i,j) for i,j in ((0,0),(1,0),(0,1),(2,0),(1,1),(0,2))]
        p = h[:3]/h[3]
        su, sv = (hu[:3]-hu[3]*p)/h[3], (hv[:3]-hv[3]*p)/h[3]
        suu = (huu[:3]-huu[3]*p-2*hu[3]*su)/h[3]
        suv = (huv[:3]-huv[3]*p-hu[3]*sv-hv[3]*su)/h[3]
        svv = (hvv[:3]-hvv[3]*p-2*hv[3]*sv)/h[3]
        return p,su,sv,suu,suv,svv


def _key(edge):
    # Stable under input reordering; only an internal deterministic tie breaker.
    return edge.get('key') or hashlib.sha256(json.dumps(edge['curve'],sort_keys=True).encode()).hexdigest()


def ordered_cycle(edges, tolerance):
    if not 4 <= len(edges) <= 16:
        fail('EDGE_COUNT', 'Select one loop of4–16 native naked Brep edges.')
    if len({_key(e) for e in edges}) != len(edges):
        fail('DUPLICATE_EDGE', 'A native edge was selected twice.')
    ends = [(Curve(e['curve'])(Curve(e['curve']).domain[0]),Curve(e['curve'])(Curve(e['curve']).domain[1])) for e in edges]
    links = {}
    for i in range(len(edges)):
        for end in (0,1):
            matches = [(j,k) for j in range(len(edges)) if j != i for k in (0,1)
                       if np.linalg.norm(ends[i][end]-ends[j][k]) <= tolerance]
            if len(matches) != 1:
                fail('AMBIGUOUS_BOUNDARY', 'Every source endpoint must meet exactly one other endpoint within document tolerance.')
            links[i,end] = matches[0]
    start = min(range(len(edges)),key=lambda i:_key(edges[i]))
    order, seen, i, reverse = [],set(),start,False
    while i not in seen:
        seen.add(i);order.append((edges[i],reverse))
        j,end = links[i, 0 if reverse else 1]
        i,reverse = j,bool(end)
    if i != start or len(seen) != len(edges):
        fail('MULTIPLE_BOUNDARIES', 'Selection is not one simple cycle.')
    return order


def _point(item, end):
    curve,rev = Curve(item[0]['curve']),item[1]
    return curve(curve.domain[(1-end) if rev else end])


def _chain_plane(chain,tol):
    if not chain or any(e.get('plane') is None for e,_ in chain):
        return None
    origin=np.array(chain[0][0]['plane']['origin'],float);normal=unit(chain[0][0]['plane']['normal'])
    for e,_ in chain:
        n=unit(e['plane']['normal'])
        if abs(n@normal)<1-1e-8 or abs((np.array(e['plane']['origin'])-origin)@normal)>tol:
            return None
        c=Curve(e['curve']);p=c.cp[:,:3]/c.cp[:,3,None]
        if np.max(abs((p-origin)@normal))>tol:
            return None
    return origin,normal


def _natural(edge,tol):
    if edge.get('plane') is not None:return None
    s=Surface(edge['surface']);c=Curve(edge['curve'])
    if c.linear(tol):return None
    hits=[]
    for axis,domain in ((0,s.ud),(1,s.vd)):
        constant_knots=s.ku if axis==0 else s.kv
        constant_degree=s.du if axis==0 else s.dv
        # Endpoint control rows are exact isocurves only for clamped charts.
        if not (np.all(constant_knots[:constant_degree+1]==domain[0]) and np.all(constant_knots[-constant_degree-1:]==domain[1])):continue
        degree=s.dv if axis==0 else s.du
        knots=s.kv if axis==0 else s.ku
        natural_domain=s.vd if axis==0 else s.ud
        if c.degree!=degree:continue
        native_knots=(knots-natural_domain[0])/(natural_domain[1]-natural_domain[0])
        curve_knots=(c.knots-c.domain[0])/(c.domain[1]-c.domain[0])
        for end in (0,1):
            cp=s.cp[0 if end==0 else -1] if axis==0 else s.cp[:,0 if end==0 else -1]
            if cp.shape!=c.cp.shape:continue
            for reverse in (False,True):
                cc=c.cp[::-1] if reverse else c.cp
                ck=1-curve_knots[::-1] if reverse else curve_knots
                if not np.allclose(native_knots,ck,rtol=0,atol=1e-12):continue
                xyz=cp[:,:3]/cp[:,3,None];other=cc[:,:3]/cc[:,3,None]
                w=cp[:,3]/np.max(cp[:,3]);ow=cc[:,3]/np.max(cc[:,3])
                diameter=max(1.,float(np.max(np.linalg.norm(xyz-xyz[0],axis=1))))
                bound=float(np.max(np.linalg.norm(xyz-other,axis=1)))+2*diameter*float(np.max(abs(w-ow)))/min(float(min(w)),float(min(ow)))
                if bound<=max(tol*.05,1e-10):hits.append((axis,end));break
    return hits[0] if len(hits)==1 else None


def _orient_side(edge,natural,top,tol):
    r=edge['surface'];cp=np.array(r['homogeneous_cp'],float);ku=np.array(r['knots_u'],float);kv=np.array(r['knots_v'],float);du,dv=r['degree_u'],r['degree_v']
    if natural[0]==1: cp=cp.transpose(1,0,2);ku,kv=kv,ku;du,dv=dv,du
    if natural[1]==1: cp=cp[::-1];ku=ku[0]+ku[-1]-ku[::-1]
    if np.linalg.norm(cp[0,0,:3]/cp[0,0,3]-top)>tol:
        cp=cp[:,::-1];kv=kv[0]+kv[-1]-kv[::-1]
    if np.linalg.norm(cp[0,0,:3]/cp[0,0,3]-top)>tol:
        fail('SIDE_ORIENTATION','Could not align a side native chart to the planar end.')
    # Exact affine parameter change, never changes the locus or weights.
    kv=(kv-kv[dv])/(kv[-dv-1]-kv[dv])
    weights=cp[...,3]
    if np.max(weights)!=np.min(weights):
        fail('RATIONAL_SIDE_UNSUPPORTED','This field prototype requires nonrational side charts; rational upper curves are retained exactly.')
    cp=cp/weights[0,0]
    if dv>5 or du>3:
        fail('SIDE_DEGREE_UNSUPPORTED','Side chart requires native cross degree<=3 and boundary degree<=5.')
    return dict(degree_u=int(du),degree_v=int(dv),knots_u=ku.tolist(),knots_v=kv.tolist(),homogeneous_cp=cp.tolist(),source_cross_sign=-1)


def _mirror_check(left,right,origin,width,tol):
    a,b=Surface(left),Surface(right)
    if a.cp.shape!=b.cp.shape or (a.du,a.dv)!=(b.du,b.dv):
        fail('ASYMMETRIC_SIDE_BASIS','Opposing side surfaces need matching mirrored native bases.')
    au=(a.ku-a.ud[0])/(a.ud[1]-a.ud[0]);bu=(b.ku-b.ud[0])/(b.ud[1]-b.ud[0])
    if not np.allclose(au,bu,rtol=0,atol=1e-11) or not np.allclose(a.kv,b.kv,rtol=0,atol=1e-11):
        fail('ASYMMETRIC_SIDE_BASIS','Side knot correspondence is not an affine mirrored map.')
    p=a.cp[...,:3];mirror=p-2*np.einsum('...c,c->...',p-origin,width)[...,None]*width
    error=float(np.max(np.linalg.norm(mirror-b.cp[...,:3],axis=2)))
    if error>tol:
        fail('ASYMMETRIC_SIDE_GEOMETRY','Full native control nets fail the mirrored-family test; maximum control-point residual='+format(error,'.6g'))
    return error


def _curve_mirror_check(chain,origin,width,tol):
    maximum=0.
    for (edge,reverse),(other,other_reverse) in zip(chain,reversed(chain)):
        a,b=Curve(edge['curve']),Curve(other['curve'])
        ac,bc=a.cp.copy(),b.cp.copy();ak=a.knots.copy();bk=b.knots.copy()
        if reverse:ac=ac[::-1];ak=ak[0]+ak[-1]-ak[::-1]
        # Traversal on the mirrored opposite source chain is reversed.
        if not other_reverse:bc=bc[::-1];bk=bk[0]+bk[-1]-bk[::-1]
        if a.degree!=b.degree or ac.shape!=bc.shape:
            fail('ASYMMETRIC_UPPER_BASIS','Mirrored upper source spans need matching rational bases and segmentation.')
        ak=(ak-ak[a.degree])/(ak[-a.degree-1]-ak[a.degree]);bk=(bk-bk[b.degree])/(bk[-b.degree-1]-bk[b.degree])
        if not np.allclose(ak,bk,atol=1e-11,rtol=0):
            fail('ASYMMETRIC_UPPER_BASIS','Upper source knot correspondence is not mirrored.')
        pa,pb=ac[:,:3]/ac[:,3,None],bc[:,:3]/bc[:,3,None]
        mirror=pa-2*((pa-origin)@width)[:,None]*width
        wa,wb=ac[:,3]/np.max(ac[:,3]),bc[:,3]/np.max(bc[:,3])
        diameter=max(1.,float(np.max(np.linalg.norm(pb-origin,axis=1))))
        # Positive rational basis: both geometric and weight perturbations are
        # bounded. This is a recognition tolerance, never weight replacement.
        residual=float(np.max(np.linalg.norm(mirror-pb,axis=1)))+2*diameter*float(np.max(abs(wa-wb)))/min(float(np.min(wa)),float(np.min(wb)))
        maximum=max(maximum,residual)
        if residual>tol:fail('ASYMMETRIC_UPPER_GEOMETRY','Complete native rational upper control nets are not mirrored within document tolerance.')
    return maximum


def _ruled_lower_check(chain,origin,width,tol):
    surfaces=[]
    for edge,_ in chain:
        surface=Surface(edge['surface']);cp=surface.cp
        if np.max(cp[...,3])!=np.min(cp[...,3]):
            fail('RATIONAL_LOWER_UNSUPPORTED','The bounded lower-parent family requires polynomial ruled native surfaces.')
        p=cp[...,:3]/cp[...,3,None]
        matched=False
        for axis in (0,1):
            q=p if axis==1 else p.transpose(1,0,2)
            shifts=q-q[:,0:1]
            off=shifts-np.einsum('ijc,c->ij',shifts,width)[...,None]*width
            # Parallel ruled generators: C(u)+Y(u,v)W. Their parameter speed
            # may vary with U; physical constant-width section2jets are
            # independently checked at every declared profile below.
            if np.max(np.linalg.norm(off,axis=2))<=tol:
                matched=True;break
        if not matched:fail('LOWER_PARENT_NOT_RULED','Straight lower edges alone are insufficient: owning control nets must be parallel cross-width ruled surfaces within document tolerance.')
        surfaces.append(surface)
    # Verify every selected lower owner is part of the same mirrored section
    # family using coefficient-derived section jets at all knot spans below.
    return len(surfaces)


def _all_roots(chain,origin,width,level,tol,cancelled):
    """Solve the exact homogeneous plane numerator on EVERY native knot span.

    No sampled sign-change search: even-multiplicity/tangent roots are retained.
    Ill-conditioned near-real roots and overlap spans are rejected conservatively.
    """
    hits=[]
    for edge,rev in chain:
        check_cancel(cancelled);c=Curve(edge['curve']);lo,hi=c.domain
        numerator=c.cp[:,:3]@width-(origin@width+level)*c.cp[:,3]
        pp=PPoly.from_spline((c.knots,numerator,c.degree))
        for i,(aa,bb) in enumerate(zip(pp.x[:-1],pp.x[1:])):
            a,b=max(float(aa),lo),min(float(bb),hi)
            if b-a<=1e-14*max(1.,abs(hi-lo)):continue
            # Shift to a dimensionless span coordinate before root isolation.
            polynomial=np.polynomial.Polynomial(pp.c[:,i][::-1])
            local=polynomial(np.polynomial.Polynomial([a-aa,b-a]))
            coefficients=np.asarray(local.coef)
            scale=max(1.,float(np.max(abs(c.cp[:,3]))))
            threshold=max(1e-13,tol*1e-7)*scale
            if np.max(abs(coefficients))<=threshold:
                fail('SECTION_OVERLAP','A native boundary span lies in a section plane; no unique root.')
            roots=local.roots()
            candidates=[]
            for root in roots:
                real=float(root.real);imag=abs(float(root.imag))
                if -1e-9<=real<=1+1e-9 and imag<=1e-6:
                    if imag>1e-9:
                        fail('ILL_CONDITIONED_SECTION_ROOT','Near-tangent section root cannot be isolated reliably.')
                    candidates.append(max(0.,min(1.,real)))
            if abs(local(0.))<=threshold:candidates.append(0.)
            if abs(local(1.))<=threshold:candidates.append(1.)
            for z in candidates:
                t=a+(b-a)*z
                if abs(float((c(t)-origin)@width-level))>max(tol*1e-4,1e-9):
                    fail('SECTION_ROOT_RESIDUAL','Homogeneous section root failed native rational readback.')
                if not any(_key(x[0])==_key(edge) and abs(x[1]-t)<=1e-8*max(1.,hi-lo) for x in hits):
                    hits.append((edge,t,c(t)))
    unique=[]
    for hit in hits:
        duplicate=False
        for old in unique:
            if np.linalg.norm(hit[2]-old[2])>tol:continue
            ca,cb=Curve(hit[0]['curve']),Curve(old[0]['curve'])
            endpoints=(min(abs(hit[1]-x) for x in ca.domain)<=1e-8*max(1.,ca.domain[1]-ca.domain[0]) and
                       min(abs(old[1]-x) for x in cb.domain)<=1e-8*max(1.,cb.domain[1]-cb.domain[0]))
            if endpoints:duplicate=True;break
            fail('AMBIGUOUS_SECTION','Coincident section points belong to multiple interior branches.')
        if not duplicate:unique.append(hit)
    if len(unique)!=1:
        fail('AMBIGUOUS_SECTION','A declared width station must intersect each source chain uniquely.')
    return unique[0]


def _surface_uv(edge,point,tol):
    s=Surface(edge['surface']);ud,vd=s.ud,s.vd
    samples=edge.get('uv_samples',[])
    guesses=[]
    if samples:
        samples=sorted(samples,key=lambda z:np.linalg.norm(np.array(z['point'])-point))
        guesses=[[(x['uv'][0]-ud[0])/(ud[1]-ud[0]),(x['uv'][1]-vd[0])/(vd[1]-vd[0])] for x in samples[:2]]
    else: guesses=[[0,.25],[0,.5],[0,.75]]
    def jet(x): return s.jet(ud[0]+x[0]*(ud[1]-ud[0]),vd[0]+x[1]*(vd[1]-vd[0]))
    solutions=[]
    for g in guesses:
        fit=least_squares(lambda x:jet(x)[0]-point,np.clip(g,1e-12,1-1e-12),bounds=(np.zeros(2),np.ones(2)),max_nfev=80,xtol=1e-12,ftol=1e-12,gtol=1e-12)
        if np.linalg.norm(jet(fit.x)[0]-point)<=max(tol*.05,1e-9): solutions.append(fit.x)
    if not solutions: fail('SOURCE_TRIM_MAPPING','Owning native face could not reproduce the selected edge point.')
    if max(np.linalg.norm(x-solutions[0]) for x in solutions)>1e-5:
        fail('AMBIGUOUS_SOURCE_UV','Owning native face has multiple source-point branches.')
    uv=np.array([ud[0]+solutions[0][0]*(ud[1]-ud[0]),vd[0]+solutions[0][1]*(vd[1]-vd[0])])
    return s.jet(*uv),uv


def _physical_shape_operator(jets):
    _,su,sv,suu,suv,svv=jets
    normal=unit(np.cross(su,sv));J=np.column_stack([su,sv]);I=J.T@J
    if np.linalg.det(I)<=1e-24*max(1.,float(np.trace(I))**2):
        fail('SOURCE_FRAME_SINGULAR','Native lower parent has a degenerate tangent frame.')
    II=np.array([[normal@suu,normal@suv],[normal@suv,normal@svv]])
    inverse=np.linalg.inv(I)
    return normal,J@inverse@II@inverse@J.T


def _section_jet(edge,point,width,arrival,tol):
    jets,uv=_surface_uv(edge,point,tol)
    p,su,sv,suu,suv,svv=jets
    # Implicit native plane section W.S=constant. Choose stable solved parameter.
    if abs(sv@width)>=abs(su@width):
        if abs(sv@width)<1e-12: fail('SECTION_SINGULAR','No unique native section direction.')
        vp=-(su@width)/(sv@width);vpp=-(suu@width+2*vp*(suv@width)+vp*vp*(svv@width))/(sv@width)
        d=su+vp*sv;dd=suu+2*vp*suv+vp*vp*svv+vpp*sv
    else:
        up=-(sv@width)/(su@width);upp=-(svv@width+2*up*(suv@width)+up*up*(suu@width))/(su@width)
        d=sv+up*su;dd=svv+2*up*suv+up*up*suu+upp*su
    if d@arrival<0: d=-d
    t=unit(d);k=(dd-t*(dd@t))/(d@d)
    return t,k,uv


def _quintic(p0,p1,t0,t1,k0,k1,s0,s1,q0,q1):
    d0,d1=s0*t0,s1*t1;dd0,dd1=s0*s0*k0+q0*t0,s1*s1*k1+q1*t1
    return np.array([p0,p0+d0/5,p0+2*d0/5+dd0/20,p1-2*d1/5+dd1/20,p1-d1/5,p1])


def _fair_handles(p0,p1,t0,t1,k0,k1,normal,depth,cancelled):
    length=np.linalg.norm(p1-p0)
    gn,gw=np.polynomial.legendre.leggauss(3);gt=(gn+1)/2;gw=gw/2
    def cp(x): return _quintic(p0,p1,t0,t1,k0,k1,*(x*length))
    def objective(x):
        check_cancel(cancelled);j=BPoly(cp(x)[:,None,:],[0.,1.]).derivative(3)(gt)
        return float(np.einsum('i,ij,ij->',gw,j,j)/(length*length))
    def constraints(x):
        d=np.diff(cp(x),axis=0)/length
        return np.r_[d@normal,d@depth]
    results=[]
    for start in ([1,1,0,0],[.7,1.3,0,0],[1.3,.7,0,0]):
        fit=minimize(objective,start,method='SLSQP',bounds=[(.05,3),(.05,3),(-10,10),(-10,10)],constraints=[{'type':'ineq','fun':constraints}],options={'maxiter':200,'ftol':1e-10})
        if fit.success and min(constraints(fit.x))>=-1e-8: results.append((objective(fit.x),fit.x*length))
    if not results: fail('CENTER_GUIDE_FAIRING','No regular monotone quintic endpoint-jet profile passed the bounded fairness solve.')
    return min(results,key=lambda x:x[0])[1]


def _path_to(chain,target_edge,target_t,from_start=True):
    path=[]
    items=chain if from_start else [(e,not rev) for e,rev in reversed(chain)]
    for edge,rev in items:
        c=Curve(edge['curve']);a,b=c.domain
        is_target=_key(edge)==_key(target_edge)
        if is_target:
            if rev:a=target_t
            else:b=target_t
        if b-a>1e-12:
            record=dict(edge['curve']);record['domain']=[float(a),float(b)]
            path.append(dict(curve=record,reverse=rev,source_key=_key(edge),source_domain=list(c.domain),
                             source_active_domain=[float(a),float(b)],source_boundary_role='upper'))
        if is_target:break
    if not path or _key(edge)!=_key(target_edge):fail('UPPER_PATH','Section is outside the native upper chain.')
    return path


def _upper_span_paths(path,cancelled=None):
    """Virtual spans retaining original curve records and parameter provenance."""
    out=[]
    for item in path:
        check_cancel(cancelled)
        c=Curve(item['curve']);spans=c.bezier_spans()
        if item.get('reverse',False):spans=list(reversed(spans))
        for a,b,h in spans:
            record=dict(item['curve']);record['domain']=[a,b]
            out.append((dict(item,curve=record,source_active_domain=[float(a),float(b)]),h))
    return out


def _straight_span(h,direction,threshold):
    p=h[:,:3]/h[:,3,None]
    chord=p[-1]-p[0]
    if abs(chord@direction)<=threshold:return False
    return np.max(np.linalg.norm(np.cross(p-p[0],direction),axis=1))<=threshold


def _central_upper_run(upper,origin,direction,tol,cancelled=None):
    """Find one centered transverse straight run in exact native knot spans.

    Straight recognition is a coefficient test with a tight, dimensionally
    scaled numerical threshold: max(document tolerance*1e-6, extent*1e-10,
    128*machine epsilon*coordinate magnitude). It is deliberately separate
    from document-tolerance endpoint matching and generic topology checks.
    """
    spans=_upper_span_paths([dict(curve=e['curve'],reverse=rev) for e,rev in upper],cancelled)
    points=np.concatenate([h[:,:3]/h[:,3,None] for _,h in spans])
    extent=max(float(np.linalg.norm(np.ptp(points,axis=0))),tol)
    magnitude=float(np.max(np.abs(points)))
    threshold=max(tol*1e-6,extent*1e-10,128*np.finfo(float).eps*magnitude)
    if threshold>tol*.01:
        fail('UPPER_LINEARITY_PRECISION','Coordinates are too poorly resolved for exact straight-span recognition.')
    indices=[i for i,(_,h) in enumerate(spans) if _straight_span(h,direction,threshold)]
    if not indices:
        fail('UPPER_CENTRAL_LINE','No coefficient-verified central straight native span.')
    if indices!=list(range(indices[0],indices[-1]+1)):
        fail('UPPER_CENTRAL_LINE','Straight upper spans do not form one contiguous central run.')
    if indices[0]==0 or indices[-1]==len(spans)-1:
        fail('UPPER_CENTRAL_LINE','The central straight run must lie between the two native shoulders.')
    selected=[spans[i] for i in indices]
    c0=Curve(selected[0][0]['curve']);line_origin=c0(c0.domain[1 if selected[0][0].get('reverse',False) else 0])
    levels=[]
    for item,h in selected:
        p=h[:,:3]/h[:,3,None]
        if item.get('reverse',False):p=p[::-1]
        if np.max(np.linalg.norm(np.cross(p-line_origin,direction),axis=1))>threshold:
            fail('UPPER_CENTRAL_LINE','Central straight spans do not share one transverse line.')
        projected=(p-origin)@direction
        if np.min(np.diff(projected)) < -threshold:
            fail('UPPER_CENTRAL_LINE','The central straight run has nonmonotone native controls.')
        levels.extend([float(projected[0]),float(projected[-1])])
    lo,hi=min(levels),max(levels)
    if not lo < -tol*10 or not hi > tol*10 or abs(lo+hi)>tol:
        fail('UPPER_CENTRAL_LINE','The straight run is not centered on the derived symmetry section.')
    return min(-lo,hi),line_origin,threshold


def _parameterize_upper(path,tol,direction,line_origin,straight_threshold,cancelled=None):
    # Canonical native spans make joined and separate source-edge descriptions
    # use the same allocation. Arc length is integrated from exact rational
    # derivatives; no 129-point chord-length approximation is used.
    spans=_upper_span_paths(path,cancelled)
    if len(spans)>16:
        fail('UPPER_SPAN_BUDGET','Each upper shoulder is limited to16 exact native spans before integration.')
    curved=[]
    for item,h in spans:
        p=h[:,:3]/h[:,3,None]
        on_line=np.max(np.linalg.norm(np.cross(p-line_origin,direction),axis=1))<=straight_threshold
        curved.append(not (_straight_span(h,direction,straight_threshold) and on_line))
    first_linear=next((i for i,v in enumerate(curved) if not v),len(spans))
    if first_linear==len(spans) or any(curved[first_linear:]):
        fail('UPPER_CHAIN_LAYOUT','Each shoulder needs rounded native spans followed by the central straight run.')
    lengths=[]
    for item,_ in spans:
        check_cancel(cancelled)
        c=Curve(item['curve'])
        length=quad(lambda t:float(np.linalg.norm(c(t,1))),*c.domain,
                    epsabs=max(straight_threshold*.01,np.finfo(float).tiny),epsrel=1e-12,limit=100)[0]
        if not math.isfinite(length) or length<=straight_threshold:
            fail('UPPER_CHAIN_LAYOUT','A native upper span has degenerate length.')
        lengths.append(length)
    breaks=[0.]
    if first_linear:
        for i in range(first_linear):breaks.append(breaks[-1]+.2*lengths[i]/sum(lengths[:first_linear]))
    for i in range(first_linear,len(spans)):
        breaks.append(breaks[-1]+(1-(.2 if first_linear else 0))*lengths[i]/sum(lengths[first_linear:]))
    breaks[-1]=1.
    return [dict(item,u_interval=[float(breaks[i]),float(breaks[i+1])]) for i,(item,_) in enumerate(spans)]


def _source_side_map(edge,natural,top,tol):
    surface=Surface(edge['surface']);curve=Curve(edge['curve'])
    domains=[surface.ud,surface.vd];cross_axis=natural[0];along_axis=1-cross_axis
    cross_domain,along_domain=domains[cross_axis],domains[along_axis]
    uv=[0.,0.];uv[cross_axis]=cross_domain[natural[1]];uv[along_axis]=along_domain[0]
    reverse_along=np.linalg.norm(surface.jet(*uv)[0]-top)>tol
    a=np.zeros((2,2));b=np.zeros(2)
    a[cross_axis,0]=-1. if natural[1] else 1.
    b[cross_axis]=sum(cross_domain) if natural[1] else 0.
    a[along_axis,1]=(along_domain[1]-along_domain[0])*(-1. if reverse_along else 1.)
    b[along_axis]=along_domain[1] if reverse_along else along_domain[0]
    reverse_edge=np.linalg.norm(curve(curve.domain[0])-top)>tol
    slope=(curve.domain[1]-curve.domain[0])*(-1. if reverse_edge else 1.)
    offset=curve.domain[1] if reverse_edge else curve.domain[0]
    return dict(native_uv_from_chart_uv=dict(matrix=a.tolist(),offset=b.tolist()),
                chart_domain=[list(cross_domain),[0.,1.]],native_surface_domain=[list(x) for x in domains],
                boundary_chart_u=float(cross_domain[0]),edge_parameter_from_chart_v=[float(slope),float(offset)])


def require_native_provenance(model,cancelled=None):
    """Production preview/fan gate, independent of numerical fixture extraction."""
    try:
        evidence=model.get('source_boundaries')
        require_complete_evidence(evidence,float(model['absolute_tolerance']),Curve,Surface,cancelled)
        if evidence['source_edge_count']!=model['extraction_report']['source_edge_count']:
            fail('NATIVE_BOUNDARY_EVIDENCE','Validated owner coverage differs from the selected native edges.')
    except BoundaryEvidenceError as error:
        fail('NATIVE_BOUNDARY_EVIDENCE',str(error))
    return True


def build_spec(edges,tolerance,angle_tolerance=1e-3,cancelled=None):
    """Recognize the stated mirrored family and extract a generic numerical spec."""
    tol=float(tolerance)
    if not math.isfinite(tol) or tol<=0:fail('INVALID_TOLERANCE','Document tolerance must be finite and positive.')
    check_cancel(cancelled)
    cycle=ordered_cycle(edges,tol)
    natural={i:_natural(e,tol) for i,(e,_) in enumerate(cycle)}
    candidates=[];n=len(cycle)
    for i in range(n):
        if natural[i] is None:continue
        for j in range(i+1,n):
            if natural[j] is None:continue
            a=cycle[i+1:j];b=cycle[j+1:]+cycle[:i]
            pa,pb=_chain_plane(a,tol),_chain_plane(b,tol)
            if (pa is None)==(pb is None):continue
            upper,lower=(a,b) if pa is not None else (b,a)
            if not lower or not all(Curve(e['curve']).linear(tol) for e,_ in lower):continue
            candidates.append((i,j,upper,lower,pa if pa is not None else pb))
    if len(candidates)!=1:fail('UNSUPPORTED_FOUR_CHAIN_TOPOLOGY','Need one unambiguous pair of curved natural sides, one coplanar end chain and one straight ruled-end chain.')
    i,j,upper,lower,plane=candidates[0]
    # Orient upper from side0→side1 and lower in the same width direction.
    top0,top1=_point(upper[0],0),_point(upper[-1],1)
    side0=next(k for k in (i,j) if min(np.linalg.norm(top0-_point(cycle[k],e)) for e in (0,1))<=tol)
    side1=j if side0==i else i
    left=_orient_side(cycle[side0][0],natural[side0],top0,tol);right=_orient_side(cycle[side1][0],natural[side1],top1,tol)
    L,R=Surface(left),Surface(right);bottom0=L.jet(L.ud[0],1.)[0];bottom1=R.jet(R.ud[0],1.)[0]
    if np.linalg.norm(_point(lower[0],0)-bottom0)>tol:lower=[(e,not rev) for e,rev in reversed(lower)]
    if np.linalg.norm(_point(lower[0],0)-bottom0)>tol or np.linalg.norm(_point(lower[-1],1)-bottom1)>tol:
        fail('LOWER_CHAIN_ORDER','Lower native chain does not connect the opposite side endpoints.')
    # Pure numerical callers may explicitly lack native trim evidence. Native
    # capture and fan preview independently require complete validated evidence.
    # Partial or contradictory capture is never silently treated as missing.
    if any('owner_side' in edge for edge in edges):
        side_edges=[cycle[side0][0],cycle[side1][0]]
        maps={role:_source_side_map(edge,natural[index],top,tol)
              for role,edge,index,top in zip(('side0','side1'),side_edges,(side0,side1),(top0,top1))}
        roles=dict(upper=upper,lower=lower)
        roles.update({role:[(edge,bool(maps[role]['edge_parameter_from_chart_v'][0]<0.))]
                      for role,edge in zip(('side0','side1'),side_edges)})
        try:source_boundaries=build_source_boundaries(roles,tol,Curve,Surface,maps,cancelled)
        except BoundaryEvidenceError as error:fail('NATIVE_BOUNDARY_EVIDENCE',str(error))
    else:
        source_boundaries=dict(schema='native-boundaries-v1',complete=False,status='missing',
                               source_edge_count=len(edges),roles={},missing_source_keys=sorted(_key(e) for e in edges))
    origin=(top0+top1)/2;direction=unit(top1-top0);normal=unit(plane[1]);bottom_mid=(bottom0+bottom1)/2
    if normal@(bottom_mid-origin)<0:normal=-normal
    if abs(normal@direction)>1e-7:fail('FRAME_NOT_ORTHOGONAL','Upper plane and cross-width direction disagree.')
    depth=unit(bottom_mid-origin-normal*(normal@(bottom_mid-origin)))
    if abs(depth@direction)>1e-6:fail('ASYMMETRIC_ENDS','End-chain centers do not share the derived symmetry section.')
    mirror_error=_mirror_check(left,right,origin,direction,tol)
    upper_mirror_error=_curve_mirror_check(upper,origin,direction,tol)
    _ruled_lower_check(lower,origin,direction,tol)
    # Exact straight-line locus test on native control points, not sampled recognition.
    for e,_ in lower:
        c=Curve(e['curve']);p=c.cp[:,:3]/c.cp[:,3,None]
        if np.max(np.linalg.norm(np.cross(p-bottom_mid,direction),axis=1))>tol:
            fail('LOWER_NOT_CROSS_WIDTH','The ruled-end native chain must be straight across width.')
    half=min(abs((bottom0-origin)@direction),abs((bottom1-origin)@direction))
    upper_half,line_origin,straight_threshold=_central_upper_run(upper,origin,direction,tol,cancelled)
    half=min(half,upper_half)
    if half<=tol*10:fail('TOO_SMALL_OPENING','No bounded interior width remains.')
    # Declared dimensionless design density and shoulder allocation, never source dimensions.
    levels=np.linspace(-.85*half,.85*half,5)
    profiles=[];anchors=[]
    for level in levels:
        check_cancel(cancelled)
        et,tt,p0=_all_roots(upper,origin,direction,level,tol,cancelled)
        eb,tb,p1=_all_roots(lower,origin,direction,level,tol,cancelled)
        t0=unit(p1-p0-normal*(normal@(p1-p0)));k0=np.zeros(3)
        t1,k1,uv=_section_jet(eb,p1,direction,p1-p0,tol)
        if abs(t1@direction)>1e-7:fail('LOWER_SECTION_BRANCH','Native lower section is not transverse to width.')
        anchors.append((et,tt,eb,tb,uv))
        profiles.append(dict(p0=p0.tolist(),p1=p1.tolist(),t0=t0.tolist(),t1=t1.tolist(),k0=k0.tolist(),k1=k1.tolist()))
    center=profiles[2]
    for p in profiles:
        for field in ('t0','t1','k0','k1'):
            if np.linalg.norm(np.array(p[field])-np.array(center[field]))>max(1e-8,tol*.01):
                fail('INCOMPATIBLE_LOWER_SECTION_JETS','The selected lower owners do not share one cross-width native section2jet.')
        shift=np.array(p['p1'])-np.array(center['p1'])
        if np.linalg.norm(shift-(shift@direction)*direction)>tol:
            fail('INCOMPATIBLE_LOWER_CHAIN','Lower section anchors are not collinear across the derived width.')
    # Every selected lower source edge is checked, including short spans
    # between the five design stations. No owner is silently substituted.
    lower_jet_error=0.;lower_tangent_error=0.;lower_operator_error=0.
    target_normal=unit(np.cross(direction,np.array(center["t1"])))
    target_operator=(np.array(center["k1"])@target_normal)*np.outer(center["t1"],center["t1"])
    for edge,_ in lower:
        c=Curve(edge['curve']);lo,hi=c.domain
        spans=np.unique(np.r_[lo,c.knots[(c.knots>lo)&(c.knots<hi)],hi])
        parameters=set(float(x) for x in spans)
        parameters.update(float(a+(b-a)*f) for a,b in zip(spans[:-1],spans[1:]) for f in (.001,.25,.5,.75,.999))
        for t in sorted(parameters):
            check_cancel(cancelled)
            tangent,curvature,uv=_section_jet(edge,c(t),direction,np.array(center['t1']),tol)
            lower_tangent_error=max(lower_tangent_error,float(np.linalg.norm(tangent-np.array(center['t1']))))
            lower_jet_error=max(lower_jet_error,float(np.linalg.norm(curvature-np.array(center['k1']))))
            native_jets,_=_surface_uv(edge,c(t),tol)
            native_normal,native_operator=_physical_shape_operator(native_jets)
            if native_normal@target_normal<0:native_normal=-native_normal;native_operator=-native_operator
            lower_tangent_error=max(lower_tangent_error,float(np.linalg.norm(native_normal-target_normal)))
            lower_operator_error=max(lower_operator_error,float(np.linalg.norm(native_operator-target_operator,ord=2)))
    if lower_tangent_error>max(1e-8,float(angle_tolerance)*.01) or max(lower_jet_error,lower_operator_error)>max(1e-9,tol*.001/max(half*half,1e-12)):
        fail('INCOMPATIBLE_LOWER_OWNER_JETS','A selected lower edge owner has incompatible native section2jets between the design stations.')
    handles=_fair_handles(*(np.array(center[x]) for x in ('p0','p1','t0','t1','k0','k1')),normal,depth,cancelled)
    for p in profiles:
        p.update(speed0=float(handles[0]),speed1=float(handles[1]),accel0=float(handles[2]),accel1=float(handles[3]))
    upper_paths=[_parameterize_upper(_path_to(upper,*anchors[0][:2],True),tol,direction,line_origin,straight_threshold,cancelled),_parameterize_upper(_path_to(upper,*anchors[-1][:2],False),tol,direction,line_origin,straight_threshold,cancelled)]
    scale=float(np.linalg.norm(bottom_mid-origin))
    return dict(side_surfaces=[left,right],profiles=profiles,upper_paths=upper_paths,source_boundaries=source_boundaries,
                upper_plane_normal=normal.tolist(),transverse_direction=direction.tolist(),
                active_v_fraction=[.2,.9],absolute_tolerance=tol,tolerance=tol,angle_tolerance=float(angle_tolerance),angle_tolerance_degrees=float(np.degrees(angle_tolerance)),
                source_cross_sign=[-1.,-1.],length_scale=scale,
                extraction_report=dict(family='mirrored_polynomial_side_charts_planar_upper_ruled_lower',source_edge_count=len(edges),
                    lower_all_edge_shape_operator_residual=lower_operator_error,lower_all_edge_tangent_residual=lower_tangent_error,lower_all_edge_curvature_residual=lower_jet_error,mirror_control_residual=mirror_error,upper_mirror_control_bound=upper_mirror_error,original_edge_coverage=len(edges),source_modified=False,
                    profile_count=5,station_count=9,profile_half_width_fraction=.85,shoulder_round_parameter_fraction=.2,
                    upper_straight_coefficient_tolerance=straight_threshold,upper_span_policy='exact_homogeneous_native_spans_contiguous_centered_run',
                    partial_parent_continuity=True,exact_rational_upper=True))
