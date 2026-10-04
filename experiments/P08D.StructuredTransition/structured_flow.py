"""P08D.1A: bounded joint normal-flow experiment on a fixed three-strip graph.
Developer CPython. A solver proposal is NOT a field/Join/product acceptance.
Physical chord-length normal-rate variation is a sampled design metric, not G3.
"""
from dataclasses import dataclass
import time
import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp
from structured_transition import joint_modes,lock_evidence,seam_evidence,sample_sites
from geometric_fairing import squared_curvature_gradient
from corner_repair import squared_shape_gradient
from local_regularity import inspect


def normal_flow_energy(points,normals):
    """Mean per-curve integral of changes in dN/ds, normalized by curve length.
    points/normals shape (paths,sites,3). Chord lengths are differentiated too.
    This is a discrete finite-site screen; deliberate S-shaped paths are allowed.
    Returns energy, derivative wrt positions, derivative wrt oriented unit normals.
    """
    P=np.asarray(points,float);N=np.asarray(normals,float)
    if P.shape!=N.shape or P.ndim!=3 or P.shape[-1]!=3 or P.shape[1]<3 or not np.isfinite([P,N]).all():
        raise ValueError('FINITE_NORMAL_PATHS_REQUIRED')
    if np.max(np.abs(np.linalg.norm(N,axis=-1)-1))>1e-6:raise ValueError('UNIT_NORMALS_REQUIRED')
    d=np.diff(P,axis=1);l=np.linalg.norm(d,axis=-1)
    if l.min()<=1e-12:raise ValueError('ZERO_LENGTH_NORMAL_PATH_STEP')
    q=np.diff(N,axis=1);r=q/l[:,:,None];jump=np.diff(r,axis=1)
    h=(l[:,1:]+l[:,:-1])/2;L=l.sum(axis=1)
    sq=np.sum(jump*jump,axis=-1);each=(sq/h).sum(axis=1)/L
    nj=P.shape[0];E=float(each.mean())
    gj=2*jump/(h*L[:,None]*nj)[:,:,None]
    gh=-sq/(h*h*L[:,None]*nj)
    gr=np.zeros_like(r);gr[:,1:]+=gj;gr[:,:-1]-=gj
    gl=np.broadcast_to((-each/(L*nj))[:,None],l.shape).copy()
    gl[:,1:]+=.5*gh;gl[:,:-1]+=.5*gh
    gl-=np.sum(gr*q,axis=-1)/(l*l)
    gq=gr/l[:,:,None];gd=gl[:,:,None]*d/l[:,:,None]
    gp=np.zeros_like(P);gn=np.zeros_like(N)
    gp[:,1:]+=gd;gp[:,:-1]-=gd;gn[:,1:]+=gq;gn[:,:-1]-=gq
    return E,gp,gn


@dataclass(frozen=True)
class SolveLimits:
    iterations:int=180
    evaluations:int=900
    seconds:float=40.
    max_control_step:float=.2
    training_density:int=25
    flow_weight:float=1.
    def validate(self):
        for val,lo,hi in ((self.iterations,1,700),(self.evaluations,1,3000),(self.training_density,7,51)):
            if type(val) is not int or not lo<=val<=hi:raise ValueError('BOUNDED_INTEGER_LIMIT_REQUIRED')
        if not np.isfinite([self.seconds,self.max_control_step,self.flow_weight]).all() or not 0<self.seconds<=120 or not 0<self.max_control_step<=1 or not 0<=self.flow_weight<=10:
            raise ValueError('FINITE_SOLVE_BUDGET_REQUIRED')


class JointProblem:
    def __init__(self,graph,active,limits,planes=(),mirror_axis=None,fixed_coordinate=None):
        limits.validate();self.graph=graph;self.active=tuple(active);self.limits=limits
        for e in seam_evidence(graph):
            if e['position_coefficient_gap']>1e-8 or e['common_d1_coefficient_gap']>1e-6 or e['common_d2_coefficient_gap']>1e-5:
                raise ValueError('BASELINE_SHARED_FIELDS_NOT_COMPATIBLE')
        M,self.mode_evidence,self.A=joint_modes(graph,active);self.m=M.shape[1]
        if not self.m:raise ValueError('NO_JOINT_FREEDOM')
        # Homogeneous per-coordinate symmetry projection, never inferred from axis.
        self.modes=np.repeat(M[:,:,None],3,axis=2)
        if mirror_axis is not None:
            if mirror_axis not in (0,1,2):raise ValueError('EXPLICIT_MIRROR_AXIS_REQUIRED')
            reverse=[]
            for k in range(3):
                rk=2-k;t=graph.patches[k];r=graph.patches[rk]
                if t.net.shape!=r.net.shape or not np.allclose(t.ku,1-r.ku[::-1],atol=1e-12,rtol=0) or abs(graph.width(k)-graph.width(rk))>1e-12:
                    raise ValueError('MIRROR_LAYOUT_NOT_VERIFIED')
                reverse.extend(np.arange(graph.offsets[rk],graph.offsets[rk+1]).reshape(r.nu,r.nv)[::-1].ravel())
            reverse=np.array(reverse);sign=np.ones(3);sign[mirror_axis]=-1
            if np.max(np.abs(graph.control-graph.control[reverse]*sign))>1e-8:raise ValueError('MIRROR_GEOMETRY_NOT_VERIFIED')
            self.modes=(self.modes+self.modes[reverse]*sign)/2
        if fixed_coordinate is not None:
            if fixed_coordinate not in (0,1,2):raise ValueError('EXPLICIT_FIXED_COORDINATE_REQUIRED')
            self.modes[:,:,fixed_coordinate]=0.
        ks=np.unique(np.concatenate([a+(b-a)*t.ku for t,(a,b) in zip(graph.patches,graph.intervals)]))
        self.us=sample_sites(ks,limits.training_density,9);self.vs=sample_sites(graph.patches[0].kv,limits.training_density,9)
        self.shape=(len(self.us),len(self.vs));self.N=np.prod(self.shape)
        if self.N*self.m>2000000:raise ValueError('JOINT_TRAINING_BUDGET')
        U,V=np.meshgrid(self.us,self.vs,indexing='ij');self.ops={};self.base={}
        for key in ((0,0),(1,0),(0,1),(2,0),(1,1),(0,2)):
            O=graph.operators(U,V,*key)
            self.base[key]=O@graph.control
            self.ops[key]=np.einsum('np,pmc->nmc',O,self.modes,optimize=True)
        cross=np.cross(self.base[1,0],self.base[0,1]);self.area=np.linalg.norm(cross,axis=1)
        if self.area.min()<=1e-12:raise ValueError('DEGENERATE_BASELINE')
        self.normal=cross/self.area[:,None];self.curve_scales=[]
        for d in ((1,0),(0,1)):
            k2=squared_curvature_gradient(self.base[d],self.base[tuple(2*x for x in d)])[0]
            self.curve_scales.append(max(float(k2.max()),1e-6))
        self.shape_scale=max(float(squared_shape_gradient(*[self.base[k] for k in ((1,0),(0,1),(2,0),(1,1),(0,2))])[0].max()),1e-6)
        P=self.base[0,0].reshape(self.shape+(3,));N=self.normal.reshape(self.shape+(3,))
        self.flow_scales=[max(normal_flow_energy(P,N)[0],1e-6),max(normal_flow_energy(P.swapaxes(0,1),N.swapaxes(0,1))[0],1e-6)]
        self.planes=tuple(planes)
        for plane in planes:plane.data()

    def delta(self,x):return np.einsum('pmc,mc->pc',self.modes,np.asarray(x).reshape(self.m,3),optimize=True)

    def value_gradient(self,x):
        coef=np.asarray(x,float).reshape(self.m,3)
        values={k:self.base[k]+np.einsum('nmc,mc->nc',O,coef,optimize=True) for k,O in self.ops.items()}
        g={k:np.zeros_like(v) for k,v in values.items()};loss=0.
        for scale,d in zip(self.curve_scales,((1,0),(0,1))):
            dd=tuple(2*x for x in d);v,ga,gb=squared_curvature_gradient(values[d],values[dd])
            z=v/scale;beta=20.;lse=logsumexp(beta*z)
            w=(np.exp(beta*z-lse)+.2/self.N)/scale
            loss+=lse/beta+.2*z.mean();g[d]+=w[:,None]*ga;g[dd]+=w[:,None]*gb
        v,grad=squared_shape_gradient(*[values[k] for k in ((1,0),(0,1),(2,0),(1,1),(0,2))])
        z=v/self.shape_scale;beta=20.;lse=logsumexp(beta*z);w=(np.exp(beta*z-lse)+.1/self.N)/self.shape_scale
        loss+=2*(lse/beta+.1*z.mean())
        for k,gk in zip(((1,0),(0,1),(2,0),(1,1),(0,2)),grad):g[k]+=2*w[:,None]*gk
        A,B=values[1,0],values[0,1];cross=np.cross(A,B);area=np.linalg.norm(cross,axis=1)
        if area.min()<=1e-14:raise ValueError('DEGENERATE_ITERATE')
        N=cross/area[:,None];P=values[0,0].reshape(self.shape+(3,));NN=N.reshape(self.shape+(3,))
        gn=np.zeros_like(N)
        for i in (0,1):
            pp=P if i==0 else P.swapaxes(0,1);nn=NN if i==0 else NN.swapaxes(0,1)
            f,gp,gg=normal_flow_energy(pp,nn);weight=self.limits.flow_weight/self.flow_scales[i]
            if i:gp=gp.swapaxes(0,1);gg=gg.swapaxes(0,1)
            loss+=weight*f;g[0,0]+=weight*gp.reshape(-1,3);gn+=weight*gg.reshape(-1,3)
        gc=(gn-N*np.sum(N*gn,axis=1)[:,None])/area[:,None]
        g[1,0]+=np.cross(B,gc);g[0,1]+=np.cross(gc,A)
        ratio=np.sum(cross*self.normal,axis=1)/self.area;bad=np.minimum(ratio-.2,0.)
        loss+=100*np.mean(bad*bad);gc=(200*bad/(self.area*self.N))[:,None]*self.normal
        g[1,0]+=np.cross(B,gc);g[0,1]+=np.cross(gc,A)
        for plane in self.planes:
            normal,d,scale=plane.data();ex=np.maximum(values[0,0]@normal-d,0)
            loss+=np.mean((ex/scale)**2);g[0,0]+=(2*ex/(scale*scale*self.N))[:,None]*normal
            # A mean alone can trade a large narrow silhouette bump for smoother normals.
            # A peak penalty guides the proposal; independent hard screening is still required.
            z=(ex/scale)**2;beta_plane=8.;lse_plane=logsumexp(beta_plane*z)
            loss+=5*(lse_plane-np.log(self.N))/beta_plane
            g[0,0]+=(10*np.exp(beta_plane*z-lse_plane)*ex/(scale*scale))[:,None]*normal
        result=sum(np.einsum('nmc,nc->mc',self.ops[k],gg,optimize=True) for k,gg in g.items())
        delta=self.delta(x);step=self.limits.max_control_step
        excess=np.maximum(np.sum(delta*delta,axis=1)/step**2-1,0.)
        loss+=100*np.sum(excess*excess)+1e-5*np.sum(coef*coef)
        result+=np.einsum('pmc,pc->mc',self.modes,400*excess[:,None]*delta/step**2,optimize=True)+2e-5*coef
        if not np.isfinite(loss) or not np.isfinite(result).all():raise ValueError('NONFINITE_JOINT_OBJECTIVE')
        return float(loss),result.ravel()


def optimize_joint(graph,active,limits=None,planes=(),mirror_axis=None,checkpoint=None,fixed_coordinate=None):
    """Returns proposal + exact coefficient lock evidence, NEVER geometry acceptance."""
    limits=limits or SolveLimits();limits.validate()
    if checkpoint:checkpoint()
    problem=JointProblem(graph,active,limits,planes,mirror_axis,fixed_coordinate);zero=np.zeros(problem.m*3)
    first=problem.value_gradient(zero)[0];best=[first,zero.copy()];calls=0;start=time.monotonic()
    class LimitStop(RuntimeError):pass
    def fun(x):
        nonlocal calls
        if checkpoint:checkpoint()
        if calls>=limits.evaluations or time.monotonic()-start>=limits.seconds:raise LimitStop('JOINT_SEARCH_BUDGET')
        calls+=1;value,grad=problem.value_gradient(x)
        if value<best[0]:best[:]=[value,x.copy()]
        return value,grad
    try:
        r=minimize(fun,zero,jac=True,method='L-BFGS-B',options={'maxiter':limits.iterations,'maxfun':limits.evaluations,'maxcor':20,'maxls':25,'ftol':1e-11,'gtol':1e-6})
        solve=dict(converged=bool(r.success),message=str(r.message),iterations=int(r.nit))
    except LimitStop as e:solve=dict(converged=False,message=str(e),iterations=None)
    if checkpoint:checkpoint()
    delta=problem.delta(best[1]);maxstep=float(np.linalg.norm(delta,axis=1).max());alpha=min(1.,limits.max_control_step/maxstep) if maxstep else 1.
    candidate=graph.replace(graph.control+alpha*delta);lock=lock_evidence(graph,candidate,active)
    if not lock['ok']:raise ValueError('JOINT_POSTCLIP_LOCK_FAILURE')
    report=dict(solve=solve,evaluations=calls,seconds=time.monotonic()-start,mode_evidence=problem.mode_evidence,training_sites=int(problem.N),
                before_objective=first,after_objective=problem.value_gradient(alpha*best[1])[0],clip_alpha=alpha,locks=lock,
                fixed_coordinate=fixed_coordinate,profile_mode='PROFILE_ONLY',station_sliding='NOT_IMPLEMENTED',external_active_speed_optimization='NOT_IMPLEMENTED',
                status='PROPOSAL_REQUIRES_INDEPENDENT_SCREENS',native_Join='NOT_RUN',geometry_commit=False)
    return candidate,report
