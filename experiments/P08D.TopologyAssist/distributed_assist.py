"""P08D.2B.1: solver-facing distributed Assist field adapter.

Pure CPython research code. It turns semantic controls into bounded longitudinal
chart fields and provides nonlinear parameter retraction. It deliberately does
not know whether a boundary is the user's Case A or Case B.
"""
from dataclasses import dataclass
import numpy as np
from topology_generalization import SemanticAssist, DistributedChart, transform_distributed_jet, world_shape

IDENTITY=np.array([1.,0.,0.,0.])

@dataclass(frozen=True)
class FieldPlan:
    stations:tuple
    left:tuple
    right:tuple
    linked:bool
    def validate(self):
        x=np.asarray(self.stations,float)
        L=np.asarray(self.left,float);R=np.asarray(self.right,float)
        if x.ndim!=1 or len(x)<5 or x[0]!=0 or x[-1]!=1 or np.any(np.diff(x)<=0):
            raise ValueError('ORDERED_FIELD_STATIONS_REQUIRED')
        if L.shape!=(len(x),4) or R.shape!=L.shape or not np.isfinite(L).all() or not np.isfinite(R).all():
            raise ValueError('FINITE_FIELD_ANCHORS_REQUIRED')
        if np.min(L[:,0])<=0 or np.min(R[:,0])<=0:
            raise ValueError('POSITIVE_FIELD_SPEED_REQUIRED')
        return self

def _ease_stations(start,end):
    if not 0<start<.49 or not 0<end<.49 or start+end>=.9:
        raise ValueError('NONOVERLAPPING_TRANSITION_ZONES_REQUIRED')
    mid=(start+(1-end))*.5
    vals=np.array([0.,start,mid,1-end,1.])
    if np.min(np.diff(vals))<=1e-8:raise ValueError('DEGENERATE_TRANSITION_STATIONS')
    return tuple(float(x) for x in vals)

def semantic_field_plan(assist,side_bias=.0,independent_right_bias=None):
    """Map user intent to a bounded field. No NURBS degree/CV decisions are exposed.
    side_bias is a solver-produced signed shear seed, not a UI setting.
    """
    assist.validate()
    if not np.isfinite(side_bias) or abs(side_bias)>.45:raise ValueError('BOUNDED_SIDE_BIAS_REQUIRED')
    if independent_right_bias is not None and (not np.isfinite(independent_right_bias) or abs(independent_right_bias)>.45):
        raise ValueError('BOUNDED_RIGHT_BIAS_REQUIRED')
    st=_ease_stations(float(assist.transition_length_start),float(assist.transition_length_end))
    cf=float(assist.corner_freedom);fair=float(assist.fairness_strength);seam=float(assist.seam_bias)
    # The semantic controls tune amplitudes only. End anchors return to identity,
    # so exact end vertices are not displaced by this parameter chart.
    speed=1.-.28*cf*(1.-.35*fair)
    shear=side_bias*(.35+.65*cf)+.30*seam
    accel=.06*cf*(1.-fair)
    drift=.08*seam*(.25+.75*cf)
    center=np.array([speed,shear,accel,drift])
    shoulder=IDENTITY+.55*(center-IDENTITY)
    L=np.stack((IDENTITY,shoulder,center,shoulder,IDENTITY))
    if independent_right_bias is None:
        R=L*np.array([1.,-1.,-1.,1.])
        linked=True
    else:
        rb=float(independent_right_bias)
        rs=rb*(.35+.65*cf)-.30*seam
        rc=np.array([speed,rs,-accel,drift])
        rsh=IDENTITY+.55*(rc-IDENTITY)
        R=np.stack((IDENTITY,rsh,rc,rsh,IDENTITY));linked=False
    return FieldPlan(st,tuple(map(tuple,L)),tuple(map(tuple,R)),linked).validate()

def charts_from_plan(plan):
    plan.validate()
    return DistributedChart.from_anchors(plan.stations,plan.left),DistributedChart.from_anchors(plan.stations,plan.right)

def retract_plan(plan,alpha):
    """Nonlinear rollback in chart-parameter space; never blend final control nets."""
    plan.validate()
    if not np.isfinite(alpha) or not 0<=alpha<=1:raise ValueError('BOUNDED_RETRACTION_REQUIRED')
    L=IDENTITY+alpha*(np.asarray(plan.left)-IDENTITY)
    R=IDENTITY+alpha*(np.asarray(plan.right)-IDENTITY)
    return FieldPlan(plan.stations,tuple(map(tuple,L)),tuple(map(tuple,R)),plan.linked).validate()

def attachment_evidence(jets,v,chart):
    now=transform_distributed_jet(*jets,chart,v)
    N0,K0=world_shape(*jets);N1,K1=world_shape(*now)
    angle=np.degrees(np.arctan2(np.linalg.norm(np.cross(N0,N1),axis=1),np.sum(N0*N1,axis=1)))
    err=np.linalg.norm(K0-K1,axis=(1,2));scale=np.maximum(np.linalg.norm(K0,axis=(1,2)),1e-9)
    return dict(normal_deg=float(np.max(angle)),shape_absolute=float(np.max(err)),
                shape_relative=float(np.max(err/scale)),finite=bool(np.isfinite(err).all()))

def common_case_contract(route,assist):
    """Shared solver contract for every topology case; no side-specific branch."""
    route.validate();assist.validate()
    return {
        'source_segments':route.segment_count,
        'logical_chain_count':len(route.chains),
        'logical_side_edge_counts':route.side_edge_counts,
        'semantic_controls':assist.semantic_controls(),
        'solver_family':'THREE_STRIP_DISTRIBUTED_ATTACHMENT',
        'case_specific_solver_branch':False,
    }
