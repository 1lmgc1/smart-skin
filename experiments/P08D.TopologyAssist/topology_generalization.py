"""P08D.2A: topology-generalized strip routing + semantic Assist controls.

Developer CPython research layer. No Rhino/document/file writes.
"""
from dataclasses import dataclass, field
import hashlib, math
import numpy as np

ROLES=("FEATURE","G1","G2")

def _finite(x):
    return isinstance(x,(int,float,np.integer,np.floating)) and not isinstance(x,(bool,np.bool_)) and math.isfinite(float(x))

def _unit3(v):
    a=np.asarray(v,float)
    if a.shape!=(3,) or not np.isfinite(a).all(): raise ValueError("FINITE_AXIS_REQUIRED")
    n=float(np.linalg.norm(a))
    if n<=1e-12: raise ValueError("NONZERO_AXIS_REQUIRED")
    return tuple((a/n).tolist())

@dataclass(frozen=True)
class BoundarySegment:
    key:str
    start:str
    end:str
    parent:str
    role:str="FEATURE"
    continuity_cap:str="AUTO"
    def validate(self):
        if not all(isinstance(x,str) and x for x in (self.key,self.start,self.end,self.parent)):
            raise ValueError("NAMED_BOUNDARY_SEGMENT_REQUIRED")
        if self.role not in ROLES: raise ValueError("SUPPORTED_SEGMENT_ROLE_REQUIRED")
        if self.continuity_cap not in ("AUTO","G0","G1","G2"): raise ValueError("SUPPORTED_CONTINUITY_CAP_REQUIRED")
        if self.start==self.end: raise ValueError("NONDEGENERATE_SEGMENT_REQUIRED")

@dataclass(frozen=True)
class LogicalChain:
    role:str
    segments:tuple
    start_vertex:str
    end_vertex:str
    def validate(self):
        if self.role not in ROLES or not self.segments: raise ValueError("NONEMPTY_LOGICAL_CHAIN_REQUIRED")
        if not self.start_vertex or not self.end_vertex: raise ValueError("CHAIN_ENDPOINTS_REQUIRED")

class BoundaryCycle:
    def __init__(self,segments):
        self.segments=tuple(segments)
        if len(self.segments)<4 or len(self.segments)>64: raise ValueError("BOUNDED_BOUNDARY_SEGMENT_COUNT_REQUIRED")
        keys=set()
        for s in self.segments:
            s.validate()
            if s.key in keys: raise ValueError("DUPLICATE_SEGMENT_KEY")
            keys.add(s.key)
        for a,b in zip(self.segments,self.segments[1:]+self.segments[:1]):
            if a.end!=b.start: raise ValueError("ORDERED_SINGLE_CYCLE_REQUIRED")
        counts={}
        for s in self.segments:
            counts[s.start]=counts.get(s.start,0)+1
            counts[s.end]=counts.get(s.end,0)+1
        if any(v!=2 for v in counts.values()) or len(counts)!=len(self.segments):
            raise ValueError("SIMPLE_CYCLE_REQUIRED")
    def reversed(self):
        return BoundaryCycle([BoundarySegment(s.key,s.end,s.start,s.parent,s.role,s.continuity_cap) for s in reversed(self.segments)])
    def rotated(self,k):
        n=len(self.segments);k%=n
        return BoundaryCycle(self.segments[k:]+self.segments[:k])
    def digest(self):
        h=hashlib.sha256()
        for s in self.segments:h.update(repr(s).encode("utf8"))
        return h.hexdigest()
    def source_keys(self): return tuple(s.key for s in self.segments)

def _runs(cycle):
    s=list(cycle.segments);n=len(s)
    cut=next((i for i in range(n) if s[i-1].role!=s[i].role),0)
    s=s[cut:]+s[:cut]
    out=[];cur=[s[0]]
    for x in s[1:]:
        if x.role==cur[-1].role:cur.append(x)
        else:
            out.append(LogicalChain(cur[0].role,tuple(y.key for y in cur),cur[0].start,cur[-1].end));cur=[x]
    out.append(LogicalChain(cur[0].role,tuple(y.key for y in cur),cur[0].start,cur[-1].end))
    for x in out:x.validate()
    return tuple(out)

@dataclass(frozen=True)
class StripRoute:
    chains:tuple
    support_indices:tuple
    feature_indices:tuple
    segment_count:int
    def validate(self):
        if len(self.support_indices)!=2 or len(self.feature_indices)!=2: raise ValueError("TWO_SUPPORT_TWO_FEATURE_ARCS_REQUIRED")
        if sum(len(c.segments) for c in self.chains)!=self.segment_count: raise ValueError("SOURCE_SEGMENT_LOSS")
        if any(self.chains[i].role not in ("G1","G2") for i in self.support_indices): raise ValueError("SMOOTH_SUPPORT_REQUIRED")
        if any(self.chains[i].role!="FEATURE" for i in self.feature_indices): raise ValueError("FEATURE_ARC_REQUIRED")
    @property
    def side_edge_counts(self):return tuple(len(c.segments) for c in self.chains)

def infer_two_support_strip_route(cycle):
    """Two smooth supports + two feature arcs; source-segment counts are unrestricted."""
    chains=_runs(cycle)
    smooth=[i for i,c in enumerate(chains) if c.role in ("G1","G2")]
    feature=[i for i,c in enumerate(chains) if c.role=="FEATURE"]
    if len(chains)!=4 or len(smooth)!=2 or len(feature)!=2:
        raise ValueError("NOT_TWO_SUPPORT_STRIP_TOPOLOGY")
    for i,c in enumerate(chains):
        if (c.role=="FEATURE")==(chains[(i+1)%4].role=="FEATURE"):
            raise ValueError("SUPPORT_FEATURE_CHAINS_MUST_ALTERNATE")
    route=StripRoute(chains,tuple(smooth),tuple(feature),len(cycle.segments));route.validate()
    flat=tuple(k for c in chains for k in c.segments)
    if set(flat)!=set(cycle.source_keys()) or len(flat)!=len(cycle.source_keys()):raise ValueError("SOURCE_SEGMENT_COVERAGE_FAILURE")
    return route

@dataclass(frozen=True)
class SemanticAssist:
    preferred_axis:tuple|None=None
    center_profile_strength:float=.8
    transition_length_start:float=.18
    transition_length_end:float=.18
    corner_freedom:float=.35
    contour_relief_budget_mm:float=.0
    symmetry_coupling:float=1.
    fairness_strength:float=.65
    seam_bias:float=.0
    continuity_default:str="AUTO"
    continuity_overrides:dict=field(default_factory=dict)
    def validate(self):
        if self.preferred_axis is not None:_unit3(self.preferred_axis)
        for name in ("center_profile_strength","transition_length_start","transition_length_end","corner_freedom","symmetry_coupling","fairness_strength"):
            x=getattr(self,name)
            if not _finite(x) or not 0<=float(x)<=1:raise ValueError("NORMALIZED_SEMANTIC_CONTROL_REQUIRED:"+name)
        if not _finite(self.seam_bias) or not -.45<=float(self.seam_bias)<=.45:raise ValueError("BOUNDED_SEAM_BIAS_REQUIRED")
        if not _finite(self.contour_relief_budget_mm) or not 0<=float(self.contour_relief_budget_mm)<=.05:raise ValueError("BOUNDED_RELIEF_BUDGET_REQUIRED")
        if self.continuity_default not in ("AUTO","G0","G1","G2"):raise ValueError("SUPPORTED_CONTINUITY_DEFAULT_REQUIRED")
        if not isinstance(self.continuity_overrides,dict):raise ValueError("CONTINUITY_OVERRIDE_MAP_REQUIRED")
        for k,v in self.continuity_overrides.items():
            if not isinstance(k,str) or not k or v not in ("AUTO","G0","G1","G2"):raise ValueError("SUPPORTED_CONTINUITY_OVERRIDE_REQUIRED")
        return self
    def normalized_axis(self):
        self.validate();return None if self.preferred_axis is None else _unit3(self.preferred_axis)
    def semantic_controls(self):
        self.validate()
        return {
            "preferred_axis":self.normalized_axis(),
            "center_profile_strength":float(self.center_profile_strength),
            "transition_length_start":float(self.transition_length_start),
            "transition_length_end":float(self.transition_length_end),
            "corner_freedom":float(self.corner_freedom),
            "contour_relief_budget_mm":float(self.contour_relief_budget_mm),
            "symmetry_coupling":float(self.symmetry_coupling),
            "fairness_strength":float(self.fairness_strength),
            "seam_bias":float(self.seam_bias),
            "continuity_default":self.continuity_default,
            "continuity_overrides":dict(self.continuity_overrides),
        }

class QuinticSchedule:
    """Bounded scalar field through ordered anchors using C2 smootherstep pieces."""
    def __init__(self,stations,values):
        x=np.asarray(stations,float);y=np.asarray(values,float)
        if x.ndim!=1 or y.ndim!=1 or len(x)!=len(y) or len(x)<2 or len(x)>16:raise ValueError("BOUNDED_SCHEDULE_ANCHORS_REQUIRED")
        if not np.isfinite(x).all() or not np.isfinite(y).all() or x[0]!=0 or x[-1]!=1 or np.any(np.diff(x)<=1e-8):raise ValueError("ORDERED_UNIT_SCHEDULE_REQUIRED")
        self.x=x;self.y=y
    def eval(self,v):
        q=np.asarray(v,float);shape=q.shape;z=q.ravel()
        if not np.isfinite(z).all() or np.any((z<0)|(z>1)):raise ValueError("UNIT_SCHEDULE_PARAMETER_REQUIRED")
        ids=np.searchsorted(self.x,z,side="right")-1;ids=np.clip(ids,0,len(self.x)-2)
        a=self.x[ids];b=self.x[ids+1];t=(z-a)/(b-a)
        h=t**3*(10+t*(-15+6*t));dh=(30*t*t*(t-1)*(t-1))/(b-a)
        val=self.y[ids]+(self.y[ids+1]-self.y[ids])*h
        der=(self.y[ids+1]-self.y[ids])*dh
        return val.reshape(shape),der.reshape(shape)

class DistributedChart:
    def __init__(self,a,b,c,d):self.a=a;self.b=b;self.c=c;self.d=d
    @classmethod
    def from_anchors(cls,stations,charts):
        q=np.asarray(charts,float)
        if q.ndim!=2 or q.shape[1]!=4 or q.shape[0]!=len(stations) or not np.isfinite(q).all():raise ValueError("FINITE_CHART_ANCHORS_REQUIRED")
        if np.min(q[:,0])<=0:raise ValueError("POSITIVE_ORIENTED_CHART_REQUIRED")
        return cls(*[QuinticSchedule(stations,q[:,i]) for i in range(4)])
    def eval(self,v):
        a,ap=self.a.eval(v);b,bp=self.b.eval(v);c,_=self.c.eval(v);d,_=self.d.eval(v)
        if np.min(a)<=0:raise ValueError("ORIENTATION_REVERSAL_IN_DISTRIBUTED_CHART")
        return a,b,c,d,ap,bp

def transform_distributed_jet(A,T,B,M,F,chart,v):
    """Exact variable-chart boundary 2-jet; a'/b' are mandatory in S_tv."""
    A,T,B,M,F=[np.asarray(x,float) for x in (A,T,B,M,F)]
    shape=A.shape
    if len(shape)<1 or shape[-1]!=3 or any(x.shape!=shape for x in (T,B,M,F)) or not all(np.isfinite(x).all() for x in (A,T,B,M,F)):
        raise ValueError("FINITE_EQUAL_JET_ARRAYS_REQUIRED")
    vv=np.asarray(v,float)
    if vv.shape!=shape[:-1]:vv=np.broadcast_to(vv,shape[:-1])
    a,b,c,d,ap,bp=chart.eval(vv);ex=(...,None)
    return (a[ex]*A+b[ex]*T,T,
            a[ex]*a[ex]*B+2*a[ex]*b[ex]*M+b[ex]*b[ex]*F+c[ex]*A+d[ex]*T,
            a[ex]*M+b[ex]*F+ap[ex]*A+bp[ex]*T,F)

def world_shape(A,T,B,M,F):
    A,T,B,M,F=[np.asarray(x,float).reshape(-1,3) for x in (A,T,B,M,F)]
    cross=np.cross(A,T);area=np.linalg.norm(cross,axis=1);scale=np.linalg.norm(A,axis=1)*np.linalg.norm(T,axis=1)
    if np.any(area<=1e-12) or np.any(area/np.maximum(scale,1e-300)<1e-10):raise ValueError("SINGULAR_GEOMETRIC_JET")
    N=cross/area[:,None];J=np.stack((A,T),axis=2);Q,R=np.linalg.qr(J,mode="reduced");inv=np.linalg.inv(R)
    II=np.empty((len(A),2,2));II[:,0,0]=np.einsum("ni,ni->n",N,B);II[:,0,1]=II[:,1,0]=np.einsum("ni,ni->n",N,M);II[:,1,1]=np.einsum("ni,ni->n",N,F)
    K=np.swapaxes(inv,1,2)@II@inv
    return N,Q@K@np.swapaxes(Q,1,2)

def route_summary(route):
    route.validate()
    return {"source_segments":route.segment_count,"logical_chains":len(route.chains),
            "side_edge_counts":route.side_edge_counts,"roles":tuple(c.role for c in route.chains),
            "support_chain_count":len(route.support_indices),
            "source_coverage":tuple(k for c in route.chains for k in c.segments),
            "hardcoded_source_side_count":False}
