"""P08D.1A: three-strip joint coefficient construction and shared seam fields.

Developer CPython. No Rhino/doc/network/file writes. Fixed station layout is a
first bounded route: C/D/E on the seams and the surrounding center can change,
while a central PROFILE and the supplied outer boundary/active jets stay fixed.
No native Join or product acceptance is inferred. Exact splitting is a negative
control, not a form repair. All comparisons refer to one immutable input graph.
"""
from dataclasses import dataclass
import hashlib
import numpy as np
from scipy.interpolate import BSpline
from scipy.linalg import null_space
from uv_basis_fairing import Tensor

JET_ORDERS=((0,0),(1,0),(0,1),(2,0),(1,1),(0,2))


def finite_scalar(x):
    return isinstance(x,(int,float,np.integer,np.floating)) and not isinstance(x,(bool,np.bool_)) and np.isfinite(x)


def sample_sites(knots,density,per_span):
    """Knot-aware finite samples with ROUND-OFF duplicate sites coalesced.
    Actual knot spans below this bounded route's resolution cause a named stop,
    not removal of a geometric span. Knot positions take precedence over samples.
    """
    K=np.unique(np.asarray(knots,float))
    if not np.isfinite(K).all() or K[0]!=0 or K[-1]!=1 or np.min(np.diff(K))<1e-10:
        raise ValueError('UNRESOLVED_OR_INVALID_KNOT_SPAN')
    if type(density) is not int or type(per_span) is not int or min(density,per_span)<3 or max(density,per_span)>1001:
        raise ValueError('BOUNDED_SAMPLE_GRID_REQUIRED')
    vals=np.r_[np.linspace(0,1,density),K,np.concatenate([a+(b-a)*(1-np.cos(np.linspace(0,np.pi,per_span)))/2 for a,b in zip(K[:-1],K[1:])])]
    eps=64*np.finfo(float).eps
    for k in K:vals[np.abs(vals-k)<=eps]=k
    vals=np.sort(vals);out=[vals[0]]
    for x in vals[1:]:
        if x-out[-1]>eps:out.append(x)
    return np.array(out)


@dataclass(frozen=True)
class SourceInterval:
    key: str
    side: str
    start: float
    end: float
    source_start: float=0.
    source_end: float=1.
    reverse: bool=False
    def validate(self):
        if not self.key or self.side not in ('bottom','top','left','right'):
            raise ValueError('NAMED_SOURCE_SIDE_REQUIRED')
        if not all(finite_scalar(x) for x in (self.start,self.end,self.source_start,self.source_end)):
            raise ValueError('FINITE_SOURCE_INTERVAL_REQUIRED')
        if not 0<=self.start<self.end<=1 or self.source_start>=self.source_end:
            raise ValueError('ORDERED_SOURCE_INTERVAL_REQUIRED')
        if type(self.reverse) is not bool:raise ValueError('EXPLICIT_REVERSAL_REQUIRED')

    def source_parameter(self,value):
        self.validate()
        if not finite_scalar(value) or not self.start<=value<=self.end:
            raise ValueError('POINT_OUTSIDE_SOURCE_INTERVAL')
        t=(value-self.start)/(self.end-self.start)
        if self.reverse:t=1-t
        return self.source_start+t*(self.source_end-self.source_start)


def check_cover(expected,pieces,eps=1e-11):
    """Coverage in source-interval space, not a count of returned Brep edges.
    pieces=(key,lo,hi). Missing/duplicate/extra intervals fail independently.
    """
    if not finite_scalar(eps) or eps<=0:raise ValueError('POSITIVE_INTERVAL_EPS_REQUIRED')
    specs={r.key:r for r in expected}
    if len(specs)!=len(expected):raise ValueError('DUPLICATE_SOURCE_KEY')
    for rec in expected:rec.validate()
    groups={key:[] for key in specs}
    for key,lo,hi in pieces:
        if key not in groups:raise ValueError('UNKNOWN_SOURCE_INTERVAL')
        if not all(finite_scalar(x) for x in (lo,hi)) or not lo<hi:
            raise ValueError('INVALID_COVERAGE_PIECE')
        groups[key].append((float(lo),float(hi)))
    report=[]
    for key,rec in specs.items():
        here=sorted(groups[key]);cursor=rec.start
        if not here:raise ValueError('MISSING_SOURCE_INTERVAL:'+key)
        for lo,hi in here:
            if lo<cursor-eps:raise ValueError('DUPLICATE_SOURCE_COVERAGE:'+key)
            if lo>cursor+eps:raise ValueError('SOURCE_COVERAGE_GAP:'+key)
            if hi>rec.end+eps:raise ValueError('SOURCE_COVERAGE_OVERRUN:'+key)
            cursor=hi
        if abs(cursor-rec.end)>eps:raise ValueError('INCOMPLETE_SOURCE_COVERAGE:'+key)
        report.append(dict(source=key,pieces=len(here),complete=True))
    return report


def split_u(t,cut):
    if not finite_scalar(cut) or not 0<cut<1:raise ValueError('INTERIOR_CUT_REQUIRED')
    m=int(np.count_nonzero(t.ku==cut));bs=BSpline(t.ku,t.net,t.p,axis=0)
    if m<t.p:bs=bs.insert_knot(float(cut),t.p-m)
    first=int(np.flatnonzero(bs.t==cut)[0])
    lk=np.r_[bs.t[:first+t.p],cut]/cut
    rk=(np.r_[cut,bs.t[first:]]-cut)/(1-cut)
    return Tensor(bs.c[:first],lk,t.kv,t.p,t.q),Tensor(bs.c[first-1:],rk,t.kv,t.p,t.q)


@dataclass(frozen=True)
class SharedSeam:
    name: str
    left: int
    right: int
    station: float


class PatchGraph:
    """Three patches in an affine common transverse chart, shared longitudinal basis.
    Input geometry/coefficients are copied. A new graph is made for each proposal.
    """
    def __init__(self,patches,intervals,source=(),boundary_policy='EXACT_SOURCE',inherited_relief_bound=0.,relief_budget=0.):
        if len(patches)!=3 or len(intervals)!=3:raise ValueError('THREE_STRIPS_REQUIRED')
        self.patches=tuple(Tensor(t.net,t.ku,t.kv,t.p,t.q) for t in patches)
        self.intervals=tuple(tuple(map(float,x)) for x in intervals)
        ends=[self.intervals[0][0]]+[x[1] for x in self.intervals]
        if not np.isfinite(ends).all() or ends[0]!=0 or ends[-1]!=1:raise ValueError('UNIT_LAYOUT_REQUIRED')
        for i,(a,b) in enumerate(self.intervals):
            if not 0<=a<b<=1 or b-a<.01:raise ValueError('NONCOLLAPSING_STRIP_REQUIRED')
            if i and a!=self.intervals[i-1][1]:raise ValueError('LAYOUT_GAP_OR_OVERLAP')
        if not self.intervals[1][0]<.5<self.intervals[1][1]:raise ValueError('PROFILE_MUST_BE_IN_CENTER_PATCH')
        t0=self.patches[0]
        if any(t.q!=t0.q or not np.array_equal(t.kv,t0.kv) for t in self.patches):
            raise ValueError('COMMON_LONGITUDINAL_BASIS_REQUIRED')
        if min(min(t.p,t.q) for t in self.patches)<2:raise ValueError('SECOND_JET_BASIS_REQUIRED')
        if sum(t.nu*t.nv for t in self.patches)>800:raise ValueError('GRAPH_CONTROL_BUDGET')
        if boundary_policy not in ('EXACT_SOURCE','CAP_EDGE_RELIEF'):raise ValueError('EXPLICIT_SUPPORTED_BOUNDARY_POLICY_REQUIRED')
        if not all(finite_scalar(x) for x in (inherited_relief_bound,relief_budget)) or min(inherited_relief_bound,relief_budget)<0:
            raise ValueError('FINITE_RELIEF_BUDGET_REQUIRED')
        if inherited_relief_bound>relief_budget or (boundary_policy=='EXACT_SOURCE' and inherited_relief_bound!=0):
            raise ValueError('CUMULATIVE_BOUNDARY_POLICY_VIOLATION')
        self.boundary_policy=boundary_policy;self.relief_bound=float(inherited_relief_bound);self.relief_budget=float(relief_budget)
        self.source=tuple(source);self._validate_source()
        self.seams=(SharedSeam('JL',0,1,self.intervals[0][1]),SharedSeam('JR',1,2,self.intervals[1][1]))
        self.offsets=np.r_[0,np.cumsum([t.nu*t.nv for t in self.patches])]
        self.control=np.concatenate([t.net.reshape(-1,3) for t in self.patches])

    def _validate_source(self):
        if not self.source:return
        if len({r.key for r in self.source})!=len(self.source):raise ValueError('DUPLICATE_SOURCE_KEY')
        for side in ('bottom','right','top','left'):
            rec=sorted([r for r in self.source if r.side==side],key=lambda x:x.start)
            for r in rec:r.validate()
            cursor=0.
            for r in rec:
                if abs(r.start-cursor)>1e-11:raise ValueError('SOURCE_SIDE_NOT_PARTITIONED')
                cursor=r.end
            if abs(cursor-1)>1e-11:raise ValueError('SOURCE_SIDE_INCOMPLETE')

    @classmethod
    def from_tensor(cls,t,stations,**kwargs):
        a,b=map(float,stations)
        if not 0<a<.5<b<1:raise ValueError('ORDERED_SEAM_STATIONS_REQUIRED')
        l,rest=split_u(t,a);c,r=split_u(rest,(b-a)/(1-a))
        return cls((l,c,r),((0,a),(a,b),(b,1)),**kwargs)

    def replace(self,control):
        c=np.asarray(control,float)
        if c.shape!=self.control.shape or not np.isfinite(c).all():raise ValueError('FINITE_GRAPH_CONTROL_REQUIRED')
        pts=[]
        for k,t in enumerate(self.patches):
            pts.append(Tensor(c[self.offsets[k]:self.offsets[k+1]].reshape(t.net.shape),t.ku,t.kv,t.p,t.q))
        return PatchGraph(pts,self.intervals,self.source,self.boundary_policy,self.relief_bound,self.relief_budget)

    def digest(self):
        h=hashlib.sha256()
        for t in self.patches:
            for x in (t.net,t.ku,t.kv):h.update(np.asarray(x,dtype='<f8').tobytes())
            h.update(str((t.p,t.q)).encode('ascii'))
        h.update(repr((self.intervals,self.boundary_policy,self.relief_bound,self.relief_budget,self.source)).encode())
        return h.hexdigest()

    def width(self,k):return self.intervals[k][1]-self.intervals[k][0]

    def trace(self,k,tvalue,du=0):
        """Map all graph CVs to common-chart transverse-jet coefficients along s."""
        p=self.patches[k];w=p.bu(tvalue,nu=du)/self.width(k)**du
        out=np.zeros((p.nv,len(self.control)))
        out[:,self.offsets[k]:self.offsets[k+1]]=np.einsum('i,jk->jik',w,np.eye(p.nv)).reshape(p.nv,-1)
        return out

    def shared_fields(self,seam):
        # One field record; BOTH adjacent traces are independently checked against it.
        return tuple(self.trace(seam.left,1,d)@self.control for d in range(3))

    def operators(self,us,vs,du=0,dv=0):
        us,vs=np.broadcast_arrays(np.asarray(us,float),np.asarray(vs,float));shape=us.shape
        u=us.ravel();v=vs.ravel()
        if not np.isfinite([u,v]).all() or np.any((u<0)|(u>1)|(v<0)|(v>1)):raise ValueError('FINITE_UNIT_PARAMETERS_REQUIRED')
        if len(u)*len(self.control)>12000000:raise ValueError('EVALUATION_MATRIX_BUDGET')
        O=np.zeros((len(u),len(self.control)));which=np.searchsorted([self.intervals[0][1],self.intervals[1][1]],u,side='right')
        for k,t in enumerate(self.patches):
            ix=np.flatnonzero(which==k)
            if not len(ix):continue
            a,b=self.intervals[k];uv=(u[ix]-a)/(b-a)
            O[ix,self.offsets[k]:self.offsets[k+1]]=np.einsum('ni,nj->nij',t.bu(uv,nu=du)/(b-a)**du,t.bv(v[ix],nu=dv)).reshape(len(ix),-1)
        return O

    def evaluate(self,u,v,du=0,dv=0):
        u,v=np.broadcast_arrays(u,v);return (self.operators(u,v,du,dv)@self.control).reshape(u.shape+(3,))

    def allocated_sources(self):
        out=[]
        for rec in self.source:
            strips=range(3) if rec.side in ('bottom','top') else (0 if rec.side=='left' else 2,)
            for k in strips:
                a,b=self.intervals[k] if rec.side in ('bottom','top') else (0.,1.)
                lo=max(a,rec.start);hi=min(b,rec.end)
                if hi>lo:out.append((rec.key,lo,hi,k))
        return out

    def coverage(self):return check_cover(self.source,[(key,a,b) for key,a,b,k in self.allocated_sources()])


def joint_modes(graph,active,keep_corner_twist=True):
    """Build ONE null space across the three patches, not three independent solves.
    Boundary functions/profile/active 2jets and inherited knot jumps are retained.
    Shared C/D/E are free but equal in the common affine chart on both sides.
    """
    a,b=map(float,active)
    if not 0<a<b<1:raise ValueError('ORDERED_ACTIVE_INTERVAL_REQUIRED')
    n=len(graph.control);rows=[];labels=[]
    def add(A,label):
        for row in np.atleast_2d(A):
            if np.linalg.norm(row)>1e-12:rows.append(row);labels.append(label)
    def block(k,row):
        r=np.zeros(n);r[graph.offsets[k]:graph.offsets[k+1]]=np.asarray(row).ravel();return r
    for k,t in enumerate(graph.patches):
        for j in (0,t.nv-1):
            R=np.zeros((t.nu,t.nu,t.nv));R[np.arange(t.nu),np.arange(t.nu),j]=1
            add(np.array([block(k,r) for r in R]),'outer_feature')
        for x in np.unique(t.ku)[1:-1]:
            if np.count_nonzero(t.ku==x)<=t.p-2:continue
            for d in (1,2):
                dif=t.bu(np.nextafter(x,0),nu=d)-t.bu(np.nextafter(x,1),nu=d)
                add(np.array([block(k,np.outer(dif,np.eye(t.nv)[j])) for j in range(t.nv)]),'source_u_knot')
        for x in np.unique(t.kv)[1:-1]:
            if np.count_nonzero(t.kv==x)<=t.q-2:continue
            for d in (1,2):
                dif=t.bv(np.nextafter(x,0),nu=d)-t.bv(np.nextafter(x,1),nu=d)
                add(np.array([block(k,np.outer(np.eye(t.nu)[i],dif)) for i in range(t.nu)]),'source_v_knot')
    for k,x in ((0,0.),(2,1.)):
        t=graph.patches[k];add(graph.trace(k,x),'outer_side')
        jj=[j for j in range(t.nv) if t.kv[j]<b-1e-13 and t.kv[j+t.q+1]>a+1e-13]
        for d in (1,2):add(graph.trace(k,x,d)[jj],'active_jet')
        if keep_corner_twist:
            # Retain the already repaired mixed derivative at the lower endpoint.
            add(t.bv(0.,nu=1)@graph.trace(k,x,1),'lower_corner_twist')
    mid=(.5-graph.intervals[1][0])/graph.width(1)
    add(graph.trace(1,mid),'profile')
    for seam in graph.seams:
        for d in (0,1,2):add(graph.trace(seam.left,1,d)-graph.trace(seam.right,0,d),'shared_'+str(d))
    A=np.array(rows);norm=np.linalg.norm(A,axis=1);A=A/norm[:,None]
    M=null_space(A,rcond=1e-11)
    residual=float(np.max(np.abs(A@M))) if M.size else 0.
    if residual>1e-8:raise ValueError('JOINT_NULLSPACE_RESIDUAL')
    return M,dict(controls=n,scalar_modes=M.shape[1],constraints=len(A),rank=n-M.shape[1],residual=residual,profile_only=True,active_parameter_jets='FROZEN_IN_THIS_STAGE',station_sliding='NOT_IMPLEMENTED'),A


def seam_evidence(graph):
    out=[]
    for seam in graph.seams:
        ds=[]
        for d in range(3):
            ds.append(float(np.linalg.norm((graph.trace(seam.left,1,d)-graph.trace(seam.right,0,d))@graph.control,axis=1).max()))
        out.append(dict(name=seam.name,position_coefficient_gap=ds[0],common_d1_coefficient_gap=ds[1],common_d2_coefficient_gap=ds[2],native_Join='NOT_RUN'))
    return out


def lock_evidence(old,new,active):
    if old.intervals!=new.intervals or old.boundary_policy!=new.boundary_policy or old.relief_bound!=new.relief_bound or old.relief_budget!=new.relief_budget:
        raise ValueError('SAME_LAYOUT_AND_BOUNDARY_POLICY_REQUIRED')
    for x,y in zip(old.patches,new.patches):
        if x.p!=y.p or x.q!=y.q or not np.array_equal(x.ku,y.ku) or not np.array_equal(x.kv,y.kv):
            raise ValueError('SAME_BASIS_REQUIRED')
    delta=new.control-old.control
    _,scope,A=joint_modes(old,active)
    residual=float(np.max(np.abs(A@delta)))
    seams=seam_evidence(new)
    ok=residual<=1e-8 and all(e['position_coefficient_gap']<=1e-8 and e['common_d1_coefficient_gap']<=1e-6 and e['common_d2_coefficient_gap']<=1e-5 for e in seams)
    return dict(ok=ok,normalized_lock_residual=residual,step=float(np.linalg.norm(delta,axis=1).max()),seams=seams,
                boundary_delta_from_baseline='LOCKED',boundary_policy=old.boundary_policy,inherited_original_source_bound=old.relief_bound,
                native_Join='NOT_RUN',geometry_commit=False)
