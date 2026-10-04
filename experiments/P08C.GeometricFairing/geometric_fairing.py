"""P08C.3: bounded offline *geometric* curvature and silhouette proposals.

Developer CPython/NumPy/SciPy code, NOT a Rhino command. No file, network,
document or commit calls. A numerical improvement is not a CAD acceptance.
Boundary/core/active jets are locked by the inherited coefficient null space.
Both section families AND surface principal curvature are independently screened.
"""
from dataclasses import dataclass
import time
import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp
from uv_basis_fairing import Tensor, free_modes, section_curvatures
from local_regularity import inspect


@dataclass(frozen=True)
class Limits:
    max_control_step: float = 0.3
    max_iterations: int = 240
    max_evaluations: int = 1500
    max_seconds: float = 45.0
    training_density: int = 31
    validation_density: int = 201
    backtracks: int = 6

    def validate(self):
        if not np.isfinite([self.max_control_step,self.max_seconds]).all() or self.max_control_step<=0 or self.max_seconds<=0:
            raise ValueError('FINITE_POSITIVE_BUDGETS_REQUIRED')
        for x,lo,hi in ((self.max_iterations,1,500),(self.max_evaluations,1,5000),
                        (self.training_density,11,81),(self.validation_density,101,301),(self.backtracks,0,10)):
            if type(x) is not int or not lo<=x<=hi:raise ValueError('BOUNDED_INTEGER_POLICY_REQUIRED')


@dataclass(frozen=True)
class Plane:
    """Explicit design halfspace n.point <= offset; not an inferred parent collision.
    scale is a positive length for the optimization penalty, never a CAD tolerance.
    """
    normal: tuple
    offset: float
    scale: float

    def data(self):
        n=np.asarray(self.normal,float)
        if n.shape!=(3,) or not np.isfinite(n).all() or not np.isfinite([self.offset,self.scale]).all() or self.scale<=0:
            raise ValueError('FINITE_EXPLICIT_PLANE_REQUIRED')
        length=np.linalg.norm(n)
        if length<=1e-14:raise ValueError('NONZERO_PLANE_NORMAL_REQUIRED')
        return n/length,float(self.offset)/length,float(self.scale)


class BudgetStop(RuntimeError):
    pass


def sites(knots,density,per_span=15):
    """One fixed set contains endpoints, uniform sites and every positive knot span.
    Includes short boundary spans. Still a finite sample, NOT a global extremum.
    """
    K=np.unique(knots)
    return np.unique(np.r_[np.linspace(0,1,density),
        np.concatenate([a+(b-a)*(1-np.cos(np.linspace(0,np.pi,per_span)))/2 for a,b in zip(K[:-1],K[1:])])])


def squared_curvature_gradient(first,second):
    """Squared geometric curve curvature and derivatives with respect to D and DD.
    No silent dropping of degenerate/nonfinite samples or epsilon flattening.
    """
    D=np.asarray(first,float);A=np.asarray(second,float)
    if D.shape!=A.shape or D.ndim!=2 or D.shape[1]!=3 or not np.isfinite(D).all() or not np.isfinite(A).all():
        raise ValueError('FINITE_PAIRED_DERIVATIVES_REQUIRED')
    s=np.sum(D*D,axis=1)
    if np.min(s)<=1e-24:raise ValueError('DEGENERATE_CURVE_DERIVATIVE')
    C=np.cross(D,A);k2=np.sum(C*C,axis=1)/s**3
    gd=2*np.cross(A,C)/s[:,None]**3-6*k2[:,None]*D/s[:,None]
    ga=2*np.cross(C,D)/s[:,None]**3
    if not all(np.isfinite(x).all() for x in (k2,gd,ga)):raise ValueError('NONFINITE_GEOMETRIC_CURVATURE')
    return k2,gd,ga


def principal_curvature_stats(tensor,us,vs):
    """Shape operator in an orthonormal tangent frame, not parameter second derivatives.
    An a.e. sample does not certify curvature extrema or smoothness at knot jumps.
    """
    a=tensor.grid(us,vs,1,0);b=tensor.grid(us,vs,0,1)
    cross=np.cross(a,b);area=np.linalg.norm(cross,axis=2)
    if not np.isfinite(area).all() or area.min()<=1e-14:raise ValueError('SURFACE_FRAME_DEGENERATE')
    E=np.sum(a*a,axis=2);F=np.sum(a*b,axis=2);normal=cross/area[:,:,None]
    if E.min()<=1e-24:raise ValueError('SURFACE_FRAME_DEGENERATE')
    e=np.sum(tensor.grid(us,vs,2,0)*normal,axis=2)
    f=np.sum(tensor.grid(us,vs,1,1)*normal,axis=2)
    g=np.sum(tensor.grid(us,vs,0,2)*normal,axis=2)
    l=np.sqrt(E);s=F/l;r=area/l
    h11=e/E;h12=(f/l-e*s/E)/r;h22=(g-2*s*f/l+s*s*e/E)/(r*r)
    h=(h11+h22)/2;disc=np.sqrt(((h11-h22)/2)**2+h12*h12)
    k=np.maximum(np.abs(h+disc),np.abs(h-disc))
    if not np.isfinite(k).all():raise ValueError('SURFACE_CURVATURE_UNAVAILABLE')
    loc=np.unravel_index(np.argmax(k),k.shape)
    return {'maximum':float(k.max()),'p99':float(np.quantile(k,.99)),
            'witness_uv':[float(us[loc[0]]),float(vs[loc[1]])],
            'minimum_cross_norm':float(area.min()),'sites':int(k.size)}


def lock_evidence(baseline,candidate,core,active):
    """Coefficient checks over complete functions; do not validate only selected points."""
    if (baseline.p,baseline.q)!=(candidate.p,candidate.q) or not np.array_equal(baseline.ku,candidate.ku) or not np.array_equal(baseline.kv,candidate.kv):
        raise ValueError('IDENTICAL_BASES_REQUIRED')
    delta=candidate.net-baseline.net;a,b=active;lo,hi=core
    boundary=max(np.linalg.norm(x,axis=-1).max() for x in (delta[0],delta[-1],delta[:,0],delta[:,-1]))
    js=[j for j in range(candidate.nv) if candidate.kv[j]<b-1e-13 and candidate.kv[j+candidate.q+1]>a+1e-13]
    jet=0.
    for u in (0.,1.):
        for order in (1,2):
            values=np.einsum('i,ijc->jc',candidate.bu(u,nu=order),delta)
            jet=max(jet,float(np.linalg.norm(values[js],axis=1).max()))
    ix=[i for i in range(candidate.nu) if candidate.ku[i]<hi-1e-13 and candidate.ku[i+candidate.p+1]>lo+1e-13]
    band=float(np.linalg.norm(delta[ix],axis=2).max())
    jump=0.
    for x in np.unique(candidate.ku)[1:-1]:
        for order in (1,2):
            v=candidate.bu(np.nextafter(x,0.),nu=order)-candidate.bu(np.nextafter(x,1.),nu=order)
            jump=max(jump,float(np.linalg.norm(np.einsum('i,ijc->jc',v,delta),axis=1).max()))
    return {'ok':bool(boundary<1e-9 and band<1e-9 and jet<1e-7 and jump<1e-6),
            'boundary_coefficient_delta':float(boundary),'core_coefficient_delta':band,
            'active_jet_coefficient_delta':jet,'increment_one_sided_jump':jump}


def silhouette_stats(tensor,us,vs,planes):
    p=tensor.grid(us,vs);out=[]
    for plane in planes:
        n,d,_=plane.data();e=np.maximum(p@n-d,0.)
        ij=np.unravel_index(np.argmax(e),e.shape)
        out.append({'max_excess':float(e.max()),'rms_excess':float(np.sqrt(np.mean(e*e))),
                    'witness_uv':[float(us[ij[0]]),float(vs[ij[1]])]})
    return out


class GeometricProblem:
    """Actual nonlinear sampled objective and analytical gradient.
    A normalized soft maximum plus mean squared curvature of BOTH families;
    explicit silhouette and orientation/step penalties. Penalties do not authorize
    acceptance: all hard locks, displacement and independent screens run afterwards.
    """
    def __init__(self,baseline,modes,limits,planes=(),mirror_axis=None,checkpoint=None):
        limits.validate();self.t=baseline;self.M=np.array(modes,float,copy=True)
        if self.M.ndim!=2 or self.M.shape[0]!=baseline.nu*baseline.nv or not np.isfinite(self.M).all():
            raise ValueError('FINITE_COEFFICIENT_MODES_REQUIRED')
        self.limits=limits;self.planes=tuple(planes);self.checkpoint=checkpoint
        for plane in self.planes:plane.data()
        self.started=time.monotonic();self.calls=0;self.last_good=None;self.m=self.M.shape[1]
        self.us=sites(baseline.ku,limits.training_density,11);self.vs=sites(baseline.kv,limits.training_density,11)
        self.N=len(self.us)*len(self.vs)
        if self.m==0 or self.N*self.m>2000000:raise ValueError('MODE_OR_SAMPLE_BUDGET')
        # Optional explicit bilateral design symmetry in the supplied local frame.
        # Not an automatic inference; original geometry and knot symmetry are checked.
        self.control_modes=np.repeat(self.M[:,:,None],3,axis=2)
        self.mirror_axis=mirror_axis
        if mirror_axis is not None:
            if mirror_axis not in (0,1,2) or not np.allclose(baseline.ku,1-baseline.ku[::-1],atol=1e-12,rtol=0):
                raise ValueError('VALIDATED_BILATERAL_BASIS_REQUIRED')
            signs=np.ones(3);signs[mirror_axis]=-1
            if np.max(np.abs(baseline.net-baseline.net[::-1]*signs))>1e-8:
                raise ValueError('SOURCE_NOT_SYMMETRIC_IN_SUPPLIED_FRAME')
            reverse=self.M.reshape(baseline.nu,baseline.nv,self.m)[::-1].reshape(-1,self.m)
            self.control_modes=(self.control_modes+reverse[:,:,None]*signs)/2
        self.ops={};self.base={};self.scales={}
        for a,b in ((0,0),(1,0),(0,1),(2,0),(0,2)):
            op=np.einsum('ui,vj->uvij',baseline.bu(self.us,nu=a),baseline.bv(self.vs,nu=b)).reshape(self.N,-1)
            self.ops[a,b]=np.einsum('np,pmc->nmc',op,self.control_modes,optimize=True)
            self.base[a,b]=op@baseline.net.reshape(-1,3)
        scale=float(np.linalg.norm(np.ptp(baseline.net.reshape(-1,3),axis=0)))
        if scale<=1e-12:raise ValueError('DEGENERATE_BASELINE')
        for a,b in ((1,0),(0,1)):
            k2=squared_curvature_gradient(self.base[a,b],self.base[2*a,2*b])[0]
            self.scales[a,b]=max(float(k2.max()),1e-12/scale**2)
        cross=np.cross(self.base[1,0],self.base[0,1]);self.cn=np.linalg.norm(cross,axis=1)
        if self.cn.min()<=1e-14:raise ValueError('BASELINE_SURFACE_FRAME_DEGENERATE')
        self.normals=cross/self.cn[:,None]

    def delta(self,x):
        return np.einsum('pmc,mc->pc',self.control_modes,np.asarray(x).reshape(self.m,3))

    def value_gradient(self,x,check_budget=True):
        if check_budget:
            if self.checkpoint is not None:self.checkpoint()
            if time.monotonic()-self.started>self.limits.max_seconds:raise BudgetStop('TIME_BUDGET')
            if self.calls>=self.limits.max_evaluations:raise BudgetStop('EVALUATION_BUDGET')
            self.calls+=1
        coeff=np.asarray(x).reshape(self.m,3)
        values={key:self.base[key]+np.einsum('nmc,mc->nc',op,coeff) for key,op in self.ops.items()}
        loss=0.;grad=np.zeros_like(coeff)
        def adj(key,g):return np.einsum('nmc,nc->mc',self.ops[key],g,optimize=True)
        for a,b in ((1,0),(0,1)):
            k2,gd,ga=squared_curvature_gradient(values[a,b],values[2*a,2*b])
            scale=self.scales[a,b];z=k2/scale;beta=30.
            lse=logsumexp(beta*z);w=np.exp(beta*z-lse)/scale+.2*z/(scale*self.N)
            loss+=lse/beta+.1*np.mean(z*z)
            grad+=adj((a,b),w[:,None]*gd)+adj((2*a,2*b),w[:,None]*ga)
        A,B=values[1,0],values[0,1]
        ratio=np.sum(np.cross(A,B)*self.normals,axis=1)/self.cn
        bad=np.minimum(ratio-.25,0.);loss+=100*np.mean(bad**2)
        g=200*bad/(self.cn*self.N)
        grad+=adj((1,0),g[:,None]*np.cross(B,self.normals))+adj((0,1),g[:,None]*np.cross(self.normals,A))
        for plane in self.planes:
            n,d,scale=plane.data();pos=np.maximum(values[0,0]@n-d,0.)
            loss+=np.mean((pos/scale)**2)
            grad+=adj((0,0),(2*pos/(scale*scale*self.N))[:,None]*n)
        delta=self.delta(x);sq=np.sum(delta*delta,axis=1);step=self.limits.max_control_step
        excess=np.maximum(sq/step**2-1,0.);loss+=100*np.sum(excess**2)
        grad+=np.einsum('pmc,pc->mc',self.control_modes,400*excess[:,None]*delta/step**2,optimize=True)
        loss+=1e-4*np.sum(coeff*coeff);grad+=2e-4*coeff
        if not np.isfinite(loss) or not np.isfinite(grad).all():raise ValueError('NONFINITE_PROPOSAL_OBJECTIVE')
        if check_budget and (self.last_good is None or loss<self.last_good[0]):self.last_good=(float(loss),np.asarray(x).copy())
        return float(loss),grad.ravel()


def optimize_geometric(baseline,core_interval,active_interval,planes=(),limits=None,
                       mirror_axis=None,checkpoint=None):
    """Search then independently screen. Never alters baseline or grants CAD commit.
    Budget exhaustion/convergence status is reported separately from screening.
    The explicit baseline may have residual defects: retention is not acceptance.
    """
    limits=limits or Limits();limits.validate();planes=tuple(planes)
    M,scope=free_modes(baseline,core_interval,active_interval)
    if M.shape[1]==0:return baseline,{'selected':'BASELINE_RETAINED_NOT_CERTIFIED','reason':'NO_FREE_MODES','geometry_commit':False}
    problem=GeometricProblem(baseline,M,limits,planes,mirror_axis,checkpoint)
    zero=np.zeros(M.shape[1]*3);before=problem.value_gradient(zero)[0];stop=None
    try:
        result=minimize(problem.value_gradient,zero,jac=True,method='L-BFGS-B',
            bounds=[(-limits.max_control_step,limits.max_control_step)]*len(zero),
            options={'maxiter':limits.max_iterations,'maxfun':limits.max_evaluations,
                     'maxls':25,'maxcor':20,'ftol':1e-10,'gtol':1e-6})
        solve={'converged':bool(result.success),'message':str(result.message),'iterations':int(result.nit)}
    except (BudgetStop,ValueError) as exc:
        stop=str(exc);solve={'converged':False,'message':stop,'iterations':None}
    if checkpoint is not None:checkpoint()  # User cancellation propagates; never manufacture a result.
    coeff=problem.last_good[1];delta=problem.delta(coeff)
    maximum=float(np.linalg.norm(delta,axis=1).max())
    scale=min(1.,limits.max_control_step/maximum) if maximum>0 else 1.
    us=sites(baseline.ku,limits.validation_density);vs=sites(baseline.kv,limits.validation_density)
    oldsections=section_curvatures(baseline,us,vs);oldprincipal=principal_curvature_stats(baseline,us,vs)
    oldsil=silhouette_stats(baseline,us,vs,planes);events=[]
    report={'experiment':'P08C.3','solve':solve,'evaluations':problem.calls,'free_modes':scope,
            'training_sites':problem.N,'validation_sites':len(us)*len(vs),'mirror_axis':mirror_axis,
            'max_control_step':limits.max_control_step,'unclipped_proposal_step':maximum,'clip_scale':scale,
            'objective_before':before,'before_sections':oldsections,'before_principal':oldprincipal,
            'before_silhouette':oldsil,'events':events,'geometry_commit':False,
            'Rhino_Join':'NOT_RUN','parent_intersections':'NOT_CHECKED',
            'scope':'FINITE_SITE_GEOMETRIC_SCREEN_AND_LOCAL_NUMERICAL_REGULARITY;NOT_FINISHED_CAP'}
    for j in range(limits.backtracks+1):
        if checkpoint is not None:checkpoint()
        alpha=scale*0.5**j
        candidate=Tensor(baseline.net+alpha*delta.reshape(baseline.net.shape),baseline.ku,baseline.kv,baseline.p,baseline.q)
        event={'alpha':alpha,'failed':[]};fail=event['failed']
        try:
            lock=lock_evidence(baseline,candidate,core_interval,active_interval);event['locks']=lock
            if not lock['ok']:fail.append('BOUNDARY_CORE_OR_JET_LOCK')
            step=float(np.linalg.norm(candidate.net-baseline.net,axis=2).max());event['step']=step
            if step>limits.max_control_step*(1+1e-10):fail.append('CONTROL_STEP')
            if mirror_axis is not None:
                signs=np.ones(3);signs[mirror_axis]=-1
                sym=float(np.max(np.abs(candidate.net-candidate.net[::-1]*signs)));event['symmetry_residual']=sym
                if sym>1e-8:fail.append('EXPLICIT_SYMMETRY')
            value=problem.value_gradient(alpha*coeff,False)[0];event['objective']=value
            if value>=before-1e-10*max(1,abs(before)):fail.append('NO_GEOMETRIC_OBJECTIVE_IMPROVEMENT')
            sec=section_curvatures(candidate,us,vs);event['sections']=sec
            principal=principal_curvature_stats(candidate,us,vs);event['principal']=principal
            sil=silhouette_stats(candidate,us,vs,planes);event['silhouette']=sil
            for fam in ('u','v'):
                for metric in ('maximum','p99'):
                    if sec[fam][metric]>oldsections[fam][metric]+1e-8:fail.append(f'{fam}_{metric}_REGRESSION')
            for metric in ('maximum','p99'):
                if principal[metric]>oldprincipal[metric]*(1+1e-10)+1e-8:fail.append('PRINCIPAL_'+metric+'_REGRESSION')
            for n,(old,new) in enumerate(zip(oldsil,sil)):
                for metric in ('max_excess','rms_excess'):
                    if new[metric]>old[metric]+1e-9:fail.append(f'SILHOUETTE_{n}_{metric}_REGRESSION')
            local=inspect(candidate,checkpoint=checkpoint);event['local_regularity']=local
            if not local['ok']:fail.append('LOCAL_REGULARITY_NOT_PROVEN')
        except ValueError as exc:fail.append(str(exc))
        events.append(event)
        if not fail:
            report.update(selected='GEOMETRIC_RESEARCH_CANDIDATE_NOT_JOINED',selected_alpha=alpha)
            return candidate,report
    report.update(selected='BASELINE_RETAINED_NOT_CERTIFIED')
    return baseline,report
