"""P08D.1B: exact active two-jet reparameterization for a three-strip graph.

Developer CPython, NOT Rhino RunPythonScript. Parents/boundaries do not move.
The inherited active geometric two-jet is retained; its PARAMETER speeds/shear
may change. This bounded version uses constant chart coefficients on one active
longitudinal polynomial span. End zones are determined by compatible splines,
not assumed to realize a redesigned corner-normal law. No native Join is run.
"""
from dataclasses import dataclass
import time
import numpy as np
from scipy.linalg import lstsq
from scipy.optimize import minimize
from structured_transition import finite_scalar, seam_evidence, sample_sites
from structured_flow import JointProblem, SolveLimits


def transform_jet(A, T, B, M, F, chart):
    """Surface chart r=a*t+c*t^2/2, s=v+b*t+d*t^2/2 at t=0.
    A=P_r,T=P_s,B=P_rr,M=P_rs,F=P_ss. a>0 preserves orientation.
    Constant chart coefficients on the active interval; no omitted a'(v) terms.
    Return new (S_t,S_v,S_tt,S_tv,S_vv). Does not change positions.
    """
    vals=[np.asarray(x,float) for x in (A,T,B,M,F)]
    if vals[0].ndim<1 or any(x.shape!=vals[0].shape for x in vals) or vals[0].shape[-1]!=3 or not all(np.isfinite(x).all() for x in vals):
        raise ValueError('FINITE_EQUAL_JET_ARRAYS_REQUIRED')
    z=np.asarray(chart,float)
    if z.shape!=(4,) or not np.isfinite(z).all() or z[0]<=0:raise ValueError('POSITIVE_ORIENTED_CHART_REQUIRED')
    a,b,c,d=z;A,T,B,M,F=vals
    return a*A+b*T,T,a*a*B+2*a*b*M+b*b*F+c*A+d*T,a*M+b*F,F


def world_shape(A,T,B,M,F):
    """Oriented normal and ambient shape operator; compares geometry, not UV entries."""
    A,T,B,M,F=[np.asarray(x,float).reshape(-1,3) for x in (A,T,B,M,F)]
    if not all(np.isfinite(x).all() for x in (A,T,B,M,F)):raise ValueError('NONFINITE_GEOMETRIC_JET')
    cross=np.cross(A,T);area=np.linalg.norm(cross,axis=1)
    scale=np.linalg.norm(A,axis=1)*np.linalg.norm(T,axis=1)
    if np.any(area<=1e-12) or np.any(area/np.maximum(scale,1e-300)<1e-10):raise ValueError('SINGULAR_GEOMETRIC_JET')
    N=cross/area[:,None];J=np.stack((A,T),axis=2);Q,R=np.linalg.qr(J,mode='reduced')
    inv=np.linalg.inv(R)
    II=np.empty((len(A),2,2));II[:,0,0]=np.einsum('ni,ni->n',N,B);II[:,0,1]=II[:,1,0]=np.einsum('ni,ni->n',N,M);II[:,1,1]=np.einsum('ni,ni->n',N,F)
    K=np.swapaxes(inv,1,2)@II@inv
    return N,Q@K@np.swapaxes(Q,1,2)


def _constraint_rows(graph,active):
    """Same hard invariants as D1A, but active rows have a nonzero chart RHS.
    Returns normalized rows, row norms, and active-row indices. No solver weights
    can trade an exact boundary or internal shared seam against attachment quality.
    """
    a,b=map(float,active)
    if not 0<a<b<1:raise ValueError('ORDERED_ACTIVE_INTERVAL_REQUIRED')
    n=len(graph.control);rows=[];active_rows=[];corner_rows=[]
    def add(A):
        ids=[]
        for row in np.atleast_2d(A):
            if np.linalg.norm(row)>1e-12:ids.append(len(rows));rows.append(row)
        return ids
    def block(k,row):
        r=np.zeros(n);r[graph.offsets[k]:graph.offsets[k+1]]=np.asarray(row).ravel();return r
    for k,t in enumerate(graph.patches):
        for j in (0,t.nv-1):
            rr=np.zeros((t.nu,t.nu,t.nv));rr[np.arange(t.nu),np.arange(t.nu),j]=1
            add(np.array([block(k,x) for x in rr]))
        for x in np.unique(t.ku)[1:-1]:
            if np.count_nonzero(t.ku==x)<=t.p-2:continue
            for d in (1,2):
                dif=t.bu(np.nextafter(x,0),nu=d)-t.bu(np.nextafter(x,1),nu=d)
                add(np.array([block(k,np.outer(dif,np.eye(t.nv)[j])) for j in range(t.nv)]))
        for x in np.unique(t.kv)[1:-1]:
            if np.count_nonzero(t.kv==x)<=t.q-2:continue
            for d in (1,2):
                dif=t.bv(np.nextafter(x,0),nu=d)-t.bv(np.nextafter(x,1),nu=d)
                add(np.array([block(k,np.outer(np.eye(t.nu)[i],dif)) for i in range(t.nu)]))
    for k,x in ((0,0.),(2,1.)):
        t=graph.patches[k];add(graph.trace(k,x))
        jj=np.array([j for j in range(t.nv) if t.kv[j]<b-1e-13 and t.kv[j+t.q+1]>a+1e-13])
        inside=np.unique(t.kv[(t.kv>a+1e-13)&(t.kv<b-1e-13)])
        if len(inside) or len(jj)!=t.q+1 or not np.any(np.abs(t.kv-a)<1e-13) or not np.any(np.abs(t.kv-b)<1e-13):
            raise ValueError('ACTIVE_SINGLE_POLYNOMIAL_SPAN_REQUIRED')
        for d in (1,2):active_rows.append((k,x,d,jj,add(graph.trace(k,x,d)[jj])))
        corner_rows.append((k,x,add(t.bv(0.,nu=1)@graph.trace(k,x,1))))
    mid=(.5-graph.intervals[1][0])/graph.width(1);add(graph.trace(1,mid))
    for seam in graph.seams:
        for d in (0,1,2):add(graph.trace(seam.left,1,d)-graph.trace(seam.right,0,d))
    C=np.array(rows);norm=np.linalg.norm(C,axis=1)
    return C/norm[:,None],norm,active_rows,corner_rows


def _features(eta):
    """da,b,c,d -> exact polynomial chart monomials and analytic Jacobian."""
    z=np.asarray(eta,float)
    if z.shape!=(4,) or not np.isfinite(z).all() or 1+z[0]<=0:raise ValueError('INVALID_ATTACHMENT_PARAMETERS')
    a,b,c,d=z
    f=np.array([a,b,a*a,a*b,b*b,c,d])
    J=np.array([[1,0,0,0],[0,1,0,0],[2*a,0,0,0],[b,a,0,0],[0,2*b,0,0],[0,0,1,0],[0,0,0,1]],float)
    return f,J


class AttachmentSpace:
    """Exact polynomial active attachments + shared null modes.
    chart_symmetry=True couples left (a,b,c,d), right (a,-b,-c,d).
    This policy requires a verified reflection, and is never silently inferred.
    Independent charts are otherwise available for both sides (8 variables).
    """
    def __init__(self,graph,active,chart_symmetry=False,mirror_axis=None,corner_tangent_freedom=True):
        self.graph=graph;self.active=tuple(map(float,active));self.symmetric=chart_symmetry;self.corner_tangent_freedom=corner_tangent_freedom
        if type(chart_symmetry) is not bool or type(corner_tangent_freedom) is not bool:raise ValueError('EXPLICIT_CHART_LINK_REQUIRED')
        if chart_symmetry and mirror_axis is None:raise ValueError('CHART_LINK_NEEDS_VERIFIED_SYMMETRY')
        if mirror_axis is not None and not chart_symmetry:raise ValueError('MIRROR_REQUIRES_LINKED_CHARTS')
        if mirror_axis is not None:
            if mirror_axis not in (0,1,2):raise ValueError('EXPLICIT_MIRROR_AXIS_REQUIRED')
            for k in range(3):
                p,r=graph.patches[k],graph.patches[2-k];sign=np.ones(3);sign[mirror_axis]=-1
                if p.net.shape!=r.net.shape or not np.allclose(p.ku,1-r.ku[::-1],atol=1e-12,rtol=0) or abs(graph.width(k)-graph.width(2-k))>1e-12 or np.max(np.abs(p.net-r.net[::-1]*sign))>1e-8:
                    raise ValueError('MIRROR_GEOMETRY_NOT_VERIFIED')
        self.C,self.norm,self.rows,self.corner_rows=_constraint_rows(graph,active)
        # Columns are coupled XYZ fields, unlike free scalar modes per coordinate.
        self.chart_features=7 if chart_symmetry else 14
        self.corner_count=(2 if chart_symmetry else 4) if corner_tangent_freedom else 0
        self.feature_count=self.chart_features+self.corner_count
        RHS=np.zeros((len(self.C),self.feature_count,3))
        for k,x,order,jj,ids in self.rows:
            p=graph.patches[k];a,b=active
            v=a+(b-a)*(1-np.cos((np.arange(p.q+1)+.5)*np.pi/(p.q+1)))/2
            mat=p.bv(v)[:,jj]
            if np.linalg.cond(mat)>1e10:raise ValueError('ILL_CONDITIONED_ACTIVE_RESTRICTION')
            C0=graph.trace(k,x,0)@graph.control
            A0=graph.trace(k,x,1)@graph.control;B0=graph.trace(k,x,2)@graph.control
            T=np.linalg.solve(mat,p.bv(v,nu=1)@C0)
            M=np.linalg.solve(mat,p.bv(v,nu=1)@A0)
            F=np.linalg.solve(mat,p.bv(v,nu=2)@C0)
            A=A0[jj];B=B0[jj];terms=np.zeros((len(jj),7,3))
            if order==1:terms[:,0]=A;terms[:,1]=T
            else:
                terms[:,0]=2*B;terms[:,1]=2*M;terms[:,2]=B;terms[:,3]=2*M
                terms[:,4]=F;terms[:,5]=A;terms[:,6]=T
            if chart_symmetry and k==2:terms*=np.array([1,-1,1,-1,1,-1,1])[None,:,None]
            off=0 if chart_symmetry or k==0 else 7
            RHS[np.array(ids),off:off+7]=terms/self.norm[np.array(ids),None,None]
        if corner_tangent_freedom:
            first_frame=None
            for k,x,ids in self.corner_rows:
                A=graph.evaluate(float(k==2),0.,1,0);T=graph.evaluate(float(k==2),0.,0,1)
                cross=np.cross(A,T);area=np.linalg.norm(cross)
                if area<=1e-12:raise ValueError('SINGULAR_CORNER_TANGENT_FRAME')
                N=cross/area;e1=A/np.linalg.norm(A);e2=np.cross(N,e1)
                frame=np.array([e1,e2])*max(np.linalg.norm(A),np.linalg.norm(T))/active[0]
                if k==0:first_frame=frame.copy()
                if chart_symmetry and k==2:
                    sign=np.ones(3);sign[mirror_axis]=-1
                    frame=-first_frame*sign
                    if np.max(np.abs(frame@N))>1e-8:raise ValueError('CORNER_FRAME_SYMMETRY_INCOMPATIBLE')
                off=self.chart_features+(0 if chart_symmetry or k==0 else 2)
                RHS[np.array(ids),off:off+2]=frame[None]/self.norm[np.array(ids),None,None]
        response,_,rank,_=lstsq(self.C,RHS.reshape(len(self.C),-1),cond=1e-11,lapack_driver='gelsd')
        self.response=response.reshape(len(graph.control),self.feature_count,3)
        self.rhs=RHS
        residual=float(np.max(np.abs(self.C@response-RHS.reshape(len(self.C),-1))))
        if residual>1e-8:raise ValueError('GEOMETRIC_ATTACHMENT_RHS_INCOMPATIBLE')
        self.evidence=dict(response_constraint_residual=residual,rank=int(rank),active_chart='CONSTANT_PER_SIDE',station_sliding=False,
                           corner_mixed='TANGENTIAL_FREEDOM_WITH_NORMAL_COMPONENT_FIXED' if corner_tangent_freedom else 'FULLY_FROZEN',inherited_geometric_reference='SUPPLIED_BASELINE_ACTIVE_TWO_JET',native_parent_measurement='NOT_RUN')

    @property
    def count(self):return (4 if self.symmetric else 8)+self.corner_count
    def features(self,eta):
        eta=np.asarray(eta,float)
        if eta.shape!=(self.count,):raise ValueError('ATTACHMENT_PARAMETER_COUNT')
        nc=4 if self.symmetric else 8
        if self.symmetric:f,J0=_features(eta[:4])
        else:
            f0,j0=_features(eta[:4]);f1,j1=_features(eta[4:8]);J0=np.zeros((14,8));J0[:7,:4]=j0;J0[7:,4:]=j1;f=np.r_[f0,f1]
        J=np.zeros((self.feature_count,self.count));J[:self.chart_features,:nc]=J0
        if self.corner_count:J[self.chart_features:,nc:]=np.eye(self.corner_count)
        return np.r_[f,eta[nc:]],J
    def charts(self,eta):
        e=np.asarray(eta,float);self.features(e)
        left=np.r_[1+e[0],e[1:4]]
        right=left*np.array([1,-1,-1,1]) if self.symmetric else np.r_[1+e[4],e[5:8]]
        return left,right
    def displacement(self,eta):
        f,_=self.features(eta);return np.einsum('pfk,f->pk',self.response,f)
    def evidence_on(self,trial,eta,sites=1001):
        if type(sites) is not int or not 7<=sites<=4001:raise ValueError('BOUNDED_ACTIVE_CHECK_SITES_REQUIRED')
        if trial.intervals!=self.graph.intervals or trial.boundary_policy!=self.graph.boundary_policy or trial.relief_bound!=self.graph.relief_bound or trial.relief_budget!=self.graph.relief_budget:
            raise ValueError('IMMUTABLE_ATTACHMENT_REFERENCE_REQUIRED')
        for x,y in zip(trial.patches,self.graph.patches):
            if (x.p,x.q)!=(y.p,y.q) or not np.array_equal(x.ku,y.ku) or not np.array_equal(x.kv,y.kv):raise ValueError('ATTACHMENT_SAME_BASIS_REQUIRED')
        f,_=self.features(eta);rhs=np.einsum('rfk,f->rk',self.rhs,f)
        residual=float(np.max(np.abs(self.C@(trial.control-self.graph.control)-rhs)))
        a,b=self.active;v=np.linspace(a,b,sites);records=[]
        for u,chart in zip((0.,1.),self.charts(eta)):
            old=[self.graph.evaluate(np.full(sites,u),v,*key) for key in ((1,0),(0,1),(2,0),(1,1),(0,2))]
            now=[trial.evaluate(np.full(sites,u),v,*key) for key in ((1,0),(0,1),(2,0),(1,1),(0,2))]
            expected=transform_jet(*old,chart)
            N,H=world_shape(*old);n,h=world_shape(*now)
            angle=np.degrees(np.arctan2(np.linalg.norm(np.cross(N,n),axis=1),np.sum(N*n,axis=1)))
            err=np.linalg.norm(H-h,axis=(1,2));scale=np.maximum(np.linalg.norm(H,axis=(1,2)),1e-6)
            records.append(dict(u=u,chart=chart.tolist(),jet_residual=max(float(np.max(np.abs(x-y))) for x,y in zip(now,expected)),
                                normal_deg=float(angle.max()),shape_absolute=float(err.max()),shape_relative=float((err/scale).max())))
        corners=[]
        for u in (0.,1.):
            old=[self.graph.evaluate(u,0.,*key)[None] for key in ((1,0),(0,1),(2,0),(1,1),(0,2))]
            now=[trial.evaluate(u,0.,*key)[None] for key in ((1,0),(0,1),(2,0),(1,1),(0,2))]
            N,H=world_shape(*old);n,h=world_shape(*now)
            corners.append(dict(u=u,mixed_vector_change=float(np.linalg.norm(now[3]-old[3])),
                                mixed_normal_change=float(abs(np.sum(N*(now[3]-old[3])))),
                                shape_absolute=float(np.linalg.norm(H-h))))
        seams=seam_evidence(trial)
        ok=residual<=1e-8 and all(r['normal_deg']<1e-6 and r['shape_relative']<1e-5 for r in records)
        ok=ok and all(r['shape_absolute']<1e-6 for r in corners)
        ok=ok and all(x['position_coefficient_gap']<1e-8 and x['common_d1_coefficient_gap']<1e-6 and x['common_d2_coefficient_gap']<1e-5 for x in seams)
        return dict(ok=ok,coefficient_constraint_residual=residual,active_geometric=records,lower_corner_geometry=corners,seams=seams,
                    step=float(np.linalg.norm(trial.control-self.graph.control,axis=1).max()),
                    boundary_policy=trial.boundary_policy,inherited_source_bound=trial.relief_bound,native_Join='NOT_RUN',geometry_commit=False)


class AttachmentProblem:
    """Exact nonlinear parameter manifold, evaluated by the D1A geometric objective.
    No linear interpolation of control nets is allowed during a nonlinear rollback.
    """
    def __init__(self,graph,active,limits=None,planes=(),mirror_axis=None,chart_symmetry=False,corner_tangent_freedom=True):
        self.limits=limits or SolveLimits();self.limits.validate()
        self.space=AttachmentSpace(graph,active,chart_symmetry,mirror_axis,corner_tangent_freedom)
        self.engine=JointProblem(graph,active,self.limits,planes,mirror_axis)
        self.base_modes=self.engine.m
        self.engine.modes=np.concatenate((self.engine.modes,self.space.response),axis=1)
        self.engine.m+=self.space.feature_count
        if self.engine.N*self.engine.m>2400000:raise ValueError('ATTACHMENT_TRAINING_BUDGET')
        self.engine.ops={}
        U,V=np.meshgrid(self.engine.us,self.engine.vs,indexing='ij')
        for key in self.engine.base:
            self.engine.ops[key]=np.einsum('np,pmc->nmc',graph.operators(U,V,*key),self.engine.modes,optimize=True)
        self.nfree=self.base_modes*3;self.size=self.nfree+self.space.count
    def expand(self,x):
        x=np.asarray(x,float)
        if x.shape!=(self.size,) or not np.isfinite(x).all():raise ValueError('FINITE_SOLVE_VECTOR_REQUIRED')
        f,J=self.space.features(x[self.nfree:])
        return np.r_[x[:self.nfree],np.repeat(f,3)],J
    def value_gradient(self,x):
        full,J=self.expand(x);value,gradient=self.engine.value_gradient(full)
        df=gradient[self.nfree:].reshape(-1,3).sum(axis=1)
        return value,np.r_[gradient[:self.nfree],J.T@df]
    def candidate(self,x,alpha=1.):
        if not finite_scalar(alpha) or not 0<=alpha<=1:raise ValueError('BOUNDED_PARAMETER_BACKTRACK_REQUIRED')
        scaled=alpha*np.asarray(x);full,_=self.expand(scaled)
        return self.space.graph.replace(self.space.graph.control+self.engine.delta(full))


def optimize_attachment(graph,active,limits=None,planes=(),mirror_axis=None,chart_symmetry=False,checkpoint=None,corner_tangent_freedom=True):
    """Bounded proposal only. Geometric attachment is checked after parameter backtrack."""
    if checkpoint:checkpoint()
    problem=AttachmentProblem(graph,active,limits,planes,mirror_axis,chart_symmetry,corner_tangent_freedom)
    limits=problem.limits;zero=np.zeros(problem.size);first=problem.value_gradient(zero)[0]
    bounds=[(None,None)]*problem.nfree+([(-.35,.5),(-.5,.5),(-2.,2.),(-2.,2.)]*(1 if chart_symmetry else 2))+[(-1.,1.)]*problem.space.corner_count
    best=[first,zero.copy()];calls=0;start=time.monotonic()
    class BudgetStop(RuntimeError):pass
    def fun(x):
        nonlocal calls
        if checkpoint:checkpoint()
        if calls>=limits.evaluations or time.monotonic()-start>=limits.seconds:raise BudgetStop('ATTACHMENT_SEARCH_BUDGET')
        calls+=1;value,grad=problem.value_gradient(x)
        if value<best[0]:best[:]=[value,x.copy()]
        return value,grad
    try:
        out=minimize(fun,zero,jac=True,bounds=bounds,method='L-BFGS-B',options={'maxiter':limits.iterations,'maxfun':limits.evaluations,'maxcor':20,'maxls':25,'ftol':1e-11,'gtol':1e-6})
        solve=dict(converged=bool(out.success),message=str(out.message),iterations=int(out.nit))
    except BudgetStop as exc:solve=dict(converged=False,message=str(exc),iterations=None)
    if checkpoint:checkpoint()
    # Nonlinear active two-jets MUST be rebuilt for every shortened step.
    alpha=1.;candidate=graph
    for _ in range(24):
        candidate=problem.candidate(best[1],alpha)
        if np.linalg.norm(candidate.control-graph.control,axis=1).max()<=limits.max_control_step*(1+1e-12):break
        alpha*=.8
    else:raise ValueError('ATTACHMENT_STEP_BACKTRACK_BUDGET')
    selected_x=alpha*best[1];evidence=problem.space.evidence_on(candidate,selected_x[problem.nfree:])
    if not evidence['ok']:raise ValueError('POST_SOLVE_GEOMETRIC_ATTACHMENT_FAILED')
    report=dict(patch='P08D.1B',solve=solve,evaluations=calls,seconds=time.monotonic()-start,before_objective=first,
                after_objective=problem.value_gradient(selected_x)[0],training_sites=int(problem.engine.N),
                attachment_parameters=selected_x[problem.nfree:].tolist(),charts=[x.tolist() for x in problem.space.charts(selected_x[problem.nfree:])],
                homogeneous_scalar_modes=problem.base_modes,attachment_dimension=problem.space.count,
                parameter_backtrack_alpha=alpha,evidence=evidence,construction=problem.space.evidence,
                status='PROPOSAL_REQUIRES_INDEPENDENT_SCREENS',native_Join='NOT_RUN',geometry_commit=False)
    return candidate,report,problem,selected_x
