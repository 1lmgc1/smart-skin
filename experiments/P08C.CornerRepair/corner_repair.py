"""P08C.4: explicit, bounded candidate-edge relief and corner-jet reconstruction.

Developer CPython module. Sources are never edited. A relief proposal is NOT an
exact-contour result: the caller must explicitly enable it and carry its bound
into the native seam check. Zero/out-of-budget evidence never enables CAD commit.
"""
from dataclasses import dataclass
import time
import numpy as np
from scipy.linalg import null_space
from scipy.interpolate import PPoly
from scipy.optimize import minimize
from scipy.special import logsumexp
from uv_basis_fairing import Tensor, free_modes, section_curvatures
from geometric_fairing import (GeometricProblem, Limits, Plane, sites,
    principal_curvature_stats, silhouette_stats, lock_evidence)
from local_regularity import inspect


def hermite_weights(t):
    t2=t*t;t3=t2*t;t4=t3*t;t5=t4*t
    return np.array([1-10*t3+15*t4-6*t5,t-6*t3+8*t4-3*t5,
        .5*(t2-3*t3+3*t4-t5),10*t3-15*t4+6*t5,-4*t3+7*t4-3*t5,
        .5*(t3-2*t4+t5)])


def local_jet_basis(t,axis,cut,order):
    K,p,B,n=(t.ku,t.p,t.bu,t.nu) if axis==0 else (t.kv,t.q,t.bv,t.nv)
    if p!=5 or order not in (0,1,2) or not 0<cut<1 or np.count_nonzero(K==cut)<3:
        raise ValueError('SUPPORTED_QUINTIC_C2_ZONE_REQUIRED')
    g=np.array([K[i+1:i+p+1].mean() for i in range(n)])
    f=np.array([hermite_weights(x/cut)[order]*cut**order if x<cut else 0. for x in g])
    out=np.linalg.solve(B(g),f)
    # Verify endpoint jets and the compact support, rather than trusting a solve.
    xs=np.unique(np.r_[g,np.linspace(cut,1,31)])
    expected=np.array([hermite_weights(x/cut)[order]*cut**order if x<cut else 0. for x in xs])
    if np.max(np.abs(B(xs)@out-expected))>1e-9:raise ValueError('ZONE_BASIS_RESIDUAL')
    return out


def minimum_twist(jet):
    """Minimize Frobenius norm of the corner shape operator over N dot Suv only.
    First derivatives and pure second derivatives are supplied/fixed. This is NOT
    a complete surface solve or a claim of an attainable global curvature bound.
    """
    x=np.asarray(jet,float)
    if x.shape!=(6,3) or not np.isfinite(x).all():raise ValueError('FINITE_SECOND_JET_REQUIRED')
    _,A,B,C,D,F=x;cn=np.cross(A,B);area=np.linalg.norm(cn)
    if area<=1e-12*np.linalg.norm(A)*np.linalg.norm(B) or area<=1e-14:
        raise ValueError('DEGENERATE_CORNER_FRAME')
    N=cn/area;E=A@A;l=np.sqrt(E);s=(A@B)/l;r=area/l;e=N@C;g=N@F
    H0=np.array([[e/E,-e*s/E/r],[-e*s/E/r,(g+s*s*e/E)/r**2]])
    H1=np.array([[0,1/l/r],[1/l/r,-2*s/l/r**2]])
    wanted=-np.sum(H0*H1)/np.sum(H1*H1)
    return N,float(wanted)


def curve_axis_minimum(t,side,axis,end):
    """Double-precision polynomial critical-point check, including all knot spans.
    Not interval arithmetic. Checks actual derivative extrema, not only a mesh.
    """
    from scipy.interpolate import BSpline
    scalar=t.net[0 if side==0 else -1]@axis
    pp=PPoly.from_spline(BSpline(t.kv,scalar,t.q))
    roots=pp.derivative(2).roots(extrapolate=False)
    xs=np.unique(np.r_[0.,end,t.kv,roots[np.isfinite(roots)]])
    xs=xs[(xs>=0)&(xs<=end)]
    return float(np.min(pp.derivative()(xs)))


def corner_strip(t,core,active,axis,boundary_budget,allow_cap_edge_relief=False,max_control_step=.3):
    if t.p!=5 or t.q!=5:raise ValueError('PINNED_QUINTIC_CONSTRUCTOR_REQUIRED')
    lo,hi=map(float,core);a,b=map(float,active);axis=np.asarray(axis,float)
    if not 0<lo<hi<1 or not 0<a<b<1:raise ValueError('VALID_FIXED_INTERVALS_REQUIRED')
    if axis.shape!=(3,) or not np.isfinite(axis).all() or np.linalg.norm(axis)<1e-14:
        raise ValueError('EXPLICIT_AXIS_REQUIRED')
    axis=axis/np.linalg.norm(axis)
    if not np.isfinite([boundary_budget,max_control_step]).all() or min(boundary_budget,max_control_step)<=0:
        raise ValueError('FINITE_POSITIVE_LIMITS_REQUIRED')
    psi=local_jet_basis(t,1,a,1);accbasis=local_jet_basis(t,1,a,2)
    g=np.array([t.ku[i+1:i+6].mean() for i in range(t.nu)])
    ends=[];evidence=[]
    for edge,c in ((0,lo),(1,hi)):
        u=float(edge);sgn=1 if edge==0 else -1;w=abs(c-u)
        J=list(t.jet(u,0));start=J[2].copy();acc=J[5].copy();speed=float(start@axis)
        if speed<0:
            if not allow_cap_edge_relief:raise ValueError('CAP_EDGE_RELIEF_REQUIRES_EXPLICIT_POLICY')
            start-=2*speed*axis;acc-=(acc@axis)*axis
        changed=list(J);changed[2]=start;changed[5]=acc
        N,f=minimum_twist(changed);T=J[1]/np.linalg.norm(J[1])
        core1=t.grid([c],[0],0,1)[0,0];core1u=t.grid([c],[0],1,1)[0,0];core1uu=t.grid([c],[0],2,1)[0,0]
        mixed=T*(core1u@T)+N*f
        d1=np.array([start,sgn*w*mixed,np.zeros(3),core1,sgn*w*core1u,w*w*core1uu])
        core2=t.grid([c],[0],0,2)[0,0];core2u=t.grid([c],[0],1,2)[0,0];core2uu=t.grid([c],[0],2,2)[0,0]
        d2=np.array([acc,np.zeros(3),np.zeros(3),core2,sgn*w*core2u,w*w*core2uu])
        ends.append((u,w,d1,d2));evidence.append({'side':edge,'axis_speed_before':speed,
            'axis_speed_after':float(start@axis),'new_normal_mixed':f})
    first=[];second=[]
    for u in g:
        if lo<=u<=hi:first.append(np.zeros(3));second.append(np.zeros(3));continue
        end,w,d1,d2=ends[0 if u<lo else 1];r=abs(u-end)/w
        first.append(hermite_weights(r)@d1-t.grid([u],[0],0,1)[0,0])
        second.append(hermite_weights(r)@d2-t.grid([u],[0],0,2)[0,0])
    C1=np.linalg.solve(t.bu(g),first);C2=np.linalg.solve(t.bu(g),second)
    delta=C1[:,None,:]*psi[None,:,None]+C2[:,None,:]*accbasis[None,:,None]
    candidate=Tensor(t.net+delta,t.ku,t.kv,t.p,t.q)
    bounds=[float(np.linalg.norm(x,axis=-1).max()) for x in (delta[0],delta[-1],delta[:,0],delta[:,-1])]
    if max(bounds)>boundary_budget:raise ValueError('CANDIDATE_EDGE_RELIEF_EXCEEDS_BUDGET')
    step=float(np.linalg.norm(delta,axis=-1).max())
    if step>max_control_step:raise ValueError('CORNER_RECONSTRUCTION_STEP_EXCEEDS_BUDGET')
    locks=lock_evidence(t,candidate,core,active)
    if max(locks['core_coefficient_delta'],locks['active_jet_coefficient_delta'])>1e-7:
        raise ValueError('LOCKED_CORE_OR_ACTIVE_JETS_CHANGED')
    if max(bounds[2:])>1e-9:raise ValueError('COMPOUND_FEATURE_BOUNDARY_CHANGED')
    minima=[curve_axis_minimum(candidate,i,axis,a) for i in (0,1)]
    if min(minima)<-1e-10:raise ValueError('AXIAL_BACKTRACK_REMAINS')
    return candidate,{'mode':'CAP_EDGE_RELIEF' if max(bounds)>1e-10 else 'EXACT_CONTOUR',
        'boundary_coefficient_position_bounds':bounds,'boundary_budget':boundary_budget,
        'control_step':step,'corners':evidence,'axis_derivative_minima':minima,
        'core_active_locks':locks,'sources_edited':False,'geometry_commit':False,
        'status':'PROPOSAL_ONLY_REQUIRES_NATIVE_VALIDATION'}


def squared_shape_gradient(A,B,C,D,F):
    """k1^2+k2^2 and gradients wrt Su,Sv,Suu,Suv,Svv. Mixed curvature included.
    Values use a QR tangent frame; gradients use the equivalent fundamental forms.
    No epsilon flattens a degenerate sample and no sample is removed.
    """
    args=[np.asarray(x,float) for x in (A,B,C,D,F)]
    if any(x.ndim!=2 or x.shape!=args[0].shape or x.shape[1]!=3 or not np.isfinite(x).all() for x in args):
        raise ValueError('FINITE_PAIRED_SURFACE_DERIVATIVES_REQUIRED')
    A,B,C,D,F=args;cross=np.cross(A,B);area=np.linalg.norm(cross,axis=1)
    E=np.sum(A*A,1);G=np.sum(B*B,1);ff=np.sum(A*B,1)
    if area.min()<=1e-14 or E.min()<=1e-24:raise ValueError('DEGENERATE_SURFACE_FRAME')
    N=cross/area[:,None];Q=np.stack([G,-ff,-ff,E],1).reshape(-1,2,2)/area[:,None,None]**2
    e=np.sum(N*C,1);f=np.sum(N*D,1);g=np.sum(N*F,1)
    l=np.sqrt(E);s=ff/l;r=area/l
    h11=e/E;h12=(f/l-e*s/E)/r;h22=(g-2*s*f/l+s*s*e/E)/r**2
    value=h11*h11+2*h12*h12+h22*h22
    II=np.stack([e,f,f,g],1).reshape(-1,2,2);dII=2*Q@II@Q;dI=-2*Q@II@Q@II@Q
    gn=dII[:,0,0,None]*C+2*dII[:,0,1,None]*D+dII[:,1,1,None]*F
    gc=(gn-N*np.sum(gn*N,1)[:,None])/area[:,None]
    ga=2*dI[:,0,0,None]*A+2*dI[:,0,1,None]*B+np.cross(B,gc)
    gb=2*dI[:,1,1,None]*B+2*dI[:,0,1,None]*A+np.cross(gc,A)
    gradients=[ga,gb,dII[:,0,0,None]*N,2*dII[:,0,1,None]*N,dII[:,1,1,None]*N]
    if not np.isfinite(value).all() or not all(np.isfinite(x).all() for x in gradients):
        raise ValueError('NONFINITE_SHAPE_OPERATOR')
    return value,gradients


@dataclass(frozen=True)
class CornerLimits:
    max_control_step:float=.3
    iterations:int=650
    evaluations:int=2200
    seconds:float=90.
    def validate(self):
        if not np.isfinite([self.max_control_step,self.seconds]).all() or min(self.max_control_step,self.seconds)<=0:
            raise ValueError('FINITE_POSITIVE_LIMITS_REQUIRED')
        if type(self.iterations) is not int or not 1<=self.iterations<=700 or type(self.evaluations) is not int or not 1<=self.evaluations<=3000:
            raise ValueError('BOUNDED_INTEGER_LIMITS_REQUIRED')


def refine_shape(corner,core,active,planes=(),limits=None,mirror_axis=None,checkpoint=None):
    """Return a numerical proposal, not acceptance. Independent final host tests required.
    Preserve corner mixed normal values; bound the FINAL coupled XYZ movement.
    """
    limits=limits or CornerLimits();limits.validate();M,_=free_modes(corner,core,active)
    if M.shape[1]==0:raise ValueError('NO_FREE_MODES')
    problem=GeometricProblem(corner,M,Limits(max_seconds=limits.seconds,max_control_step=limits.max_control_step,training_density=31),planes,mirror_axis,checkpoint)
    op=np.einsum('ui,vj->uvij',corner.bu(problem.us,nu=1),corner.bv(problem.vs,nu=1)).reshape(problem.N,-1)
    problem.ops[1,1]=np.einsum('np,pmc->nmc',op,problem.control_modes,optimize=True)
    problem.base[1,1]=op@corner.net.reshape(-1,3)
    rows=[]
    for u in (0.,1.):
        N,_=minimum_twist(corner.jet(u,0))
        row=(corner.bu(u,nu=1)[:,None]*corner.bv(0,nu=1)[None,:]).ravel()
        rows.append((np.einsum('p,pmc->mc',row,problem.control_modes)*N).ravel())
    A=np.array(rows);scale=np.linalg.norm(A,axis=1);A=A[scale>1e-12]/scale[scale>1e-12,None]
    Z=null_space(A,rcond=1e-11);best=[np.inf,np.zeros(problem.m*3)];calls=0;started=time.monotonic()
    class Stop(RuntimeError):pass
    def objective(y):
        nonlocal calls
        if checkpoint is not None:checkpoint()
        if calls>=limits.evaluations or time.monotonic()-started>=limits.seconds:raise Stop('OPTIMIZATION_BUDGET')
        calls+=1;x=Z@y;coef=x.reshape(problem.m,3)
        values={k:problem.base[k]+np.einsum('nmc,mc->nc',v,coef) for k,v in problem.ops.items()}
        value,grad=problem.value_gradient(x,False);grad=grad.reshape(problem.m,3)
        s2,derivs=squared_shape_gradient(values[1,0],values[0,1],values[2,0],values[1,1],values[0,2])
        # Reference curvature scale guides optimization, never changes a CAD tolerance.
        shape_scale=25.;z=np.log1p(s2/shape_scale);beta=4.;lse=logsumexp(beta*z)
        weight=(np.exp(beta*z-lse)+.1/problem.N)/(shape_scale+s2)
        value+=3*(lse/beta+.1*np.mean(z))
        for k,g in zip(((1,0),(0,1),(2,0),(1,1),(0,2)),derivs):
            grad+=3*np.einsum('nmc,nc->mc',problem.ops[k],weight[:,None]*g,optimize=True)
        if not np.isfinite(value) or not np.isfinite(grad).all():raise ValueError('NONFINITE_OBJECTIVE')
        if value<best[0]:best[:]=[float(value),x.copy()]
        return float(value),Z.T@grad.ravel()
    try:
        result=minimize(objective,np.zeros(Z.shape[1]),jac=True,method='L-BFGS-B',
            options={'maxiter':limits.iterations,'maxfun':limits.evaluations,'maxls':30,'maxcor':30,'ftol':1e-10,'gtol':1e-6})
        solve={'converged':bool(result.success),'reason':str(result.message),'iterations':int(result.nit)}
    except Stop as error:solve={'converged':False,'reason':str(error),'iterations':None}
    if checkpoint is not None:checkpoint()
    if not np.isfinite(best[0]):raise ValueError('NO_FINITE_ITERATE')
    delta=problem.delta(best[1]).reshape(corner.net.shape);maximum=float(np.linalg.norm(delta,axis=-1).max())
    alpha=min(1.,limits.max_control_step/maximum) if maximum else 1.
    candidate=Tensor(corner.net+alpha*delta,corner.ku,corner.kv,corner.p,corner.q)
    locks=lock_evidence(corner,candidate,core,active)
    if not locks['ok']:raise ValueError('POST_CLIP_LOCK_FAILURE')
    return candidate,{'solve':solve,'evaluations':calls,'final_step':float(np.linalg.norm(alpha*delta,axis=-1).max()),
        'clip_alpha':alpha,'locks':locks,'geometry_commit':False,'native_join':'NOT_RUN',
        'status':'PROPOSAL_ONLY_NOT_GEOMETRIC_ACCEPTANCE'}
