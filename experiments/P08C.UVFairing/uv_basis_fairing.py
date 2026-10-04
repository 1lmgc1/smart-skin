"""P08C.2: bounded offline tensor-basis and section-fairing experiment.

CPython + NumPy/SciPy, NOT a Rhino RunPythonScript command. No document, filesystem
or network API is used here. Native seam/Join and global collision checks belong
to the host. A successful quadratic solve is never geometric acceptance.
"""
from dataclasses import dataclass
import numpy as np
from scipy.interpolate import BSpline
from scipy.linalg import null_space


@dataclass
class Tensor:
    net: np.ndarray
    ku: np.ndarray
    kv: np.ndarray
    p: int
    q: int

    def __post_init__(self):
        self.net = np.array(self.net, dtype=float, copy=True)
        self.ku = np.array(self.ku, dtype=float, copy=True)
        self.kv = np.array(self.kv, dtype=float, copy=True)
        if self.net.ndim != 3 or self.net.shape[2] != 3 or not np.isfinite(self.net).all():
            raise ValueError('FINITE_XYZ_CONTROL_NET_REQUIRED')
        for knots, degree, count in ((self.ku,self.p,self.net.shape[0]), (self.kv,self.q,self.net.shape[1])):
            if not isinstance(degree, (int,np.integer)) or not 1 <= degree <= 9:
                raise ValueError('BOUNDED_DEGREE_REQUIRED')
            if len(knots) != count + degree + 1 or not np.isfinite(knots).all() or np.any(np.diff(knots)<0):
                raise ValueError('INVALID_KNOT_VECTOR')
            if knots[degree] != 0. or knots[-degree-1] != 1.:
                raise ValueError('NORMALIZED_UNIT_DOMAIN_REQUIRED')
            if not np.all(knots[:degree+1] == 0) or not np.all(knots[-degree-1:] == 1):
                raise ValueError('CLAMPED_DOMAIN_REQUIRED')
            if any(np.count_nonzero(knots==x)>degree for x in np.unique(knots)[1:-1]):
                raise ValueError('DISCONNECTED_INTERNAL_BASIS_NOT_SUPPORTED')
        if max(self.net.shape[:2]) > 80 or np.prod(self.net.shape[:2]) > 1600:
            raise ValueError('CONTROL_BUDGET_EXCEEDED')
        self.nu,self.nv = self.net.shape[:2]
        self.bu = BSpline(self.ku,np.eye(self.nu),self.p, extrapolate=False)
        self.bv = BSpline(self.kv,np.eye(self.nv),self.q, extrapolate=False)

    def grid(self, us, vs, du=0, dv=0):
        return np.einsum('ui,vj,ijc->uvc',self.bu(np.atleast_1d(us),nu=du),
                         self.bv(np.atleast_1d(vs),nu=dv),self.net,optimize=True)

    def jet(self,u,v):
        return tuple(self.grid([u],[v],a,b)[0,0] for a,b in ((0,0),(1,0),(0,1),(2,0),(1,1),(0,2)))


def transform_second_jet(jet, jacobian, hessians):
    """Full chain rule. J[i,a]=d(old_i)/d(new_a), H[i,a,b].
    Reversals are allowed, singular maps are not. No curvature is inferred from
    parameter labels or copying untransformed mixed derivatives.
    """
    x=np.asarray(jet,float);A=np.asarray(jacobian,float);H=np.asarray(hessians,float)
    if x.shape!=(6,3) or A.shape!=(2,2) or H.shape!=(2,2,2):
        raise ValueError('SECOND_JET_SHAPES_INVALID')
    if not all(np.isfinite(v).all() for v in (x,A,H)) or abs(np.linalg.det(A))<1e-12:
        raise ValueError('FINITE_NONSINGULAR_MAP_REQUIRED')
    if not np.allclose(H,H.swapaxes(1,2),rtol=0,atol=1e-12):
        raise ValueError('MAP_HESSIAN_NOT_SYMMETRIC')
    first=x[1:3].T
    second=np.array([[x[3],x[4]],[x[4],x[5]]])
    D=first@A
    DD=np.einsum('ijc,ia,jb->abc',second,A,A)+np.einsum('ci,iab->abc',first,H)
    return (x[0],D[:,0],D[:,1],DD[0,0],DD[0,1],DD[1,1])


def remove_one_knot(tensor, axis, value, allowance=1e-10):
    """Invert a single Boehm insertion. Reconstruction CV residual bounds position
    error in the original nonrational basis (floating point, not interval arithmetic).
    No fit-to-mesh or dropping boundary samples is involved.
    """
    if axis not in (0,1) or not np.isfinite(allowance) or allowance<=0:
        raise ValueError('INVALID_REMOVAL_POLICY')
    K=(tensor.ku,tensor.kv)[axis];degree=(tensor.p,tensor.q)[axis]
    where=np.flatnonzero(K==value)
    if value<=0 or value>=1 or len(where)==0:
        raise ValueError('INTERNAL_EXISTING_KNOT_REQUIRED')
    newK=np.delete(K,where[0]);n=len(newK)-degree-1
    insertion=BSpline(newK,np.eye(n),degree).insert_knot(float(value))
    if len(insertion.t)!=len(K) or not np.allclose(insertion.t,K,rtol=0,atol=1e-14):
        raise ValueError('INSERTION_TO_SOURCE_BASIS_FAILED')
    old=np.moveaxis(tensor.net,axis,0)
    target=old.reshape(old.shape[0],-1)
    solved,_,rank,_=np.linalg.lstsq(insertion.c,target,rcond=None)
    error=(insertion.c@solved-target).reshape(old.shape)
    bound=float(np.linalg.norm(error,axis=2).max())
    evidence={'axis':axis,'value':float(value),'remaining_multiplicity':len(where)-1,
              'coefficient_position_bound':bound,'accepted':bool(rank==n and bound<=allowance)}
    if not evidence['accepted']:return tensor,evidence
    net=np.moveaxis(solved.reshape((n,)+old.shape[1:]),0,axis)
    return Tensor(net,newK if axis==0 else tensor.ku,newK if axis==1 else tensor.kv,tensor.p,tensor.q),evidence


def compact_basis(tensor, budget=1e-9, protected=()):
    """Greedy bounded representation reduction, NOT a global optimum or shape repair.
    Protected (axis,knot) pairs retain the complete original multiplicity.
    """
    if not np.isfinite(budget) or budget<=0:raise ValueError('INVALID_ERROR_BUDGET')
    current=tensor;spent=0.;events=[]
    for axis in (0,1):
        for x in np.unique((tensor.ku,tensor.kv)[axis])[1:-1]:
            if (axis,float(x)) in protected:continue
            while np.count_nonzero((current.ku,current.kv)[axis]==x):
                candidate,event=remove_one_knot(current,axis,x,max(budget-spent,1e-15))
                events.append(event)
                if not event['accepted']:break
                current=candidate;spent+=event['coefficient_position_bound']
                if spent>=budget:break
    return current,{'events':events,'accumulated_position_bound':spent,
                    'initial_shape':list(tensor.net.shape[:2]),'final_shape':list(current.net.shape[:2])}


def quadrature(knots, degree):
    nodes,weights=np.polynomial.legendre.leggauss(degree+1)
    ts=[];ws=[]
    for a,b in zip(np.unique(knots)[:-1],np.unique(knots)[1:]):
        ts.extend((a+b)/2+(b-a)*nodes/2);ws.extend((b-a)*weights/2)
    return np.asarray(ts),np.asarray(ws)


def gram_matrix(knots,degree,order):
    n=len(knots)-degree-1;xs,ws=quadrature(knots,degree)
    B=BSpline(knots,np.eye(n),degree)(xs,nu=order)
    return (B.T*ws)@B


def fairness_matrix(tensor, lengths, smoothness=2):
    """Parameter-section energy in explicit physical reference scales. It is not
    a reparameterization-invariant curvature integral. Compare final geometry too.
    """
    Lu,Lv=np.asarray(lengths,float)
    if min(Lu,Lv)<=0 or not np.isfinite([Lu,Lv]).all():raise ValueError('POSITIVE_REFERENCE_LENGTHS_REQUIRED')
    if smoothness not in (2,3) or min(tensor.p,tensor.q)<smoothness:
        raise ValueError('UNSUPPORTED_FAIRNESS_ORDER')
    gu=[gram_matrix(tensor.ku,tensor.p,i) for i in range(smoothness+1)]
    gv=[gram_matrix(tensor.kv,tensor.q,i) for i in range(smoothness+1)]
    if smoothness==2:
        Q=np.kron(gu[2],gv[0])/Lu**4+2*np.kron(gu[1],gv[1])/(Lu*Lv)**2+np.kron(gu[0],gv[2])/Lv**4
    else:
        Q=np.kron(gu[3],gv[0])/Lu**6+3*np.kron(gu[2],gv[1])/(Lu**4*Lv**2)+3*np.kron(gu[1],gv[2])/(Lu**2*Lv**4)+np.kron(gu[0],gv[3])/Lv**6
    return Lu*Lv*(Q+Q.T)/2


def free_modes(tensor, core_interval, active_interval, preserve_source_jumps=True, core_mode="band"):
    """Coefficient-space null modes. Full boundaries and whole core are fixed.
    Along both active sides all first/second transverse derivatives are fixed.
    Active restrictions are support-based, not a finite set of samples. Increment
    derivatives at inherited full-multiplicity U lines are continuous through C2.
    """
    lo,hi=core_interval;a,b=active_interval
    if not 0<lo<hi<1 or not 0<a<b<1 or min(tensor.p,tensor.q)<2:
        raise ValueError('INVALID_FIXED_INTERVALS')
    nu,nv=tensor.nu,tensor.nv
    # Only basis functions supported wholly outside the central band may change.
    if core_mode not in ('band','profile'):raise ValueError('EXPLICIT_CORE_MODE_REQUIRED')
    freeU=[i for i in range(1,nu-1) if core_mode=='profile' or tensor.ku[i+tensor.p+1]<=lo+1e-13 or tensor.ku[i]>=hi-1e-13]
    freeV=list(range(1,nv-1))
    pairs=[(i,j) for i in freeU for j in freeV]
    if not pairs:return np.zeros((nu*nv,0)),{'free_dimension':0,'raw_dofs':0}
    if len(pairs)>1024:raise ValueError('FREE_DOF_BUDGET')
    rows=[]
    if core_mode=='profile':
        guide=tensor.bu(.5)
        for j in freeV:rows.append([guide[i] if k==j else 0. for i,k in pairs])
    for u in (0.,1.):
        for d in (1,2):
            weights=tensor.bu(u,nu=d)
            for j in freeV:
                # A coefficient whose support enters the active interval stays fixed.
                if tensor.kv[j]<b-1e-13 and tensor.kv[j+tensor.q+1]>a+1e-13:
                    rows.append([weights[i] if k==j else 0. for i,k in pairs])
    if preserve_source_jumps:
        for x in np.unique(tensor.ku)[1:-1]:
            if np.count_nonzero(tensor.ku==x)<=tensor.p-2:continue
            # Exact one-sided polynomial limits of the basis; nextafter chooses span.
            for order in (1,2):
                difference=tensor.bu(np.nextafter(x,0.),nu=order)-tensor.bu(np.nextafter(x,1.),nu=order)
                for j in freeV:rows.append([difference[i] if k==j else 0. for i,k in pairs])
    A=np.asarray(rows,float).reshape(-1,len(pairs))
    norm=np.linalg.norm(A,axis=1);A=A[norm>1e-12]/norm[norm>1e-12,None]
    Z=null_space(A,rcond=1e-11) if len(A) else np.eye(len(pairs))
    M=np.zeros((nu*nv,Z.shape[1]))
    for k,(i,j) in enumerate(pairs):M[i*nv+j]=Z[k]
    residual=float(np.abs(A@Z).max()) if len(A) and Z.shape[1] else 0.
    return M,{'raw_dofs':len(pairs),'free_dimension':Z.shape[1],
             'normalized_constraint_residual':residual,'preserve_source_jumps':preserve_source_jumps,'core_mode':core_mode}


def fair_candidate(tensor, core_interval, active_interval, lengths, max_control_step,
                   order=2, point_weight=0.02,core_mode="band"):
    """Bounded quadratic optimization of interior section flow, in exact null modes.
    Returns a proposal only. Common alpha backtracking must follow shape/collision
    checks in the caller. Does not claim Join, G2, or self-intersection acceptance.
    """
    if not np.isfinite([max_control_step,point_weight]).all() or max_control_step<=0 or point_weight<0:
        raise ValueError('INVALID_STEP_POLICY')
    M,scope=free_modes(tensor,core_interval,active_interval,core_mode=core_mode)
    if not M.shape[1]:return tensor,dict(scope,proposed=False,reason='NO_FREE_INTERIOR_MODES')
    Q=fairness_matrix(tensor,lengths,order);P=tensor.net.reshape(-1,3)
    mass=np.kron(gram_matrix(tensor.ku,tensor.p,0),gram_matrix(tensor.kv,tensor.q,0))
    H=M.T@(Q+point_weight*mass)@M;H=(H+H.T)/2
    G=M.T@Q@P
    # Solve a regularized descent direction, then shorten it as one coupled XYZ
    # step. A single alpha preserves all null constraints and cannot overshoot
    # the quadratic minimizer along that direction. No unbounded retry loop.
    eigen,U=np.linalg.eigh(H)
    floor=max(float(eigen[-1])*1e-13,1e-20)
    coeff=-U@((U.T@G)/np.maximum(eigen,floor)[:,None])
    direction=M@coeff
    maximum=float(np.linalg.norm(direction,axis=1).max())
    if not np.isfinite(direction).all() or maximum<=1e-15:
        return tensor,dict(scope,proposed=False,reason='NO_FINITE_DESCENT_DIRECTION')
    alpha=min(1.,max_control_step/maximum)
    # Exact line minimizer for the UNregularized fairness+anchor objective.
    slope=float(np.sum(coeff*G))
    curvature=float(np.einsum('ic,ij,jc',coeff,H,coeff))
    if slope>=0 or curvature<=0:
        return tensor,dict(scope,proposed=False,reason='NON_DESCENT_DIRECTION;BASELINE_RETAINED')
    alpha=min(alpha,-slope/curvature)
    delta=alpha*direction
    departure=float(np.linalg.norm(delta,axis=1).max())
    statuses=[{'method':'EIGEN_DESCENT_AND_COUPLED_STEP_BOUND',
               'eigen_floor':floor,'alpha':alpha,'unbounded_step':maximum}]
    changed=Tensor((P+delta).reshape(tensor.net.shape),tensor.ku,tensor.kv,tensor.p,tensor.q)
    before=float(np.einsum('ic,ij,jc',P,Q,P));after=float(np.einsum('ic,ij,jc',P+delta,Q,P+delta))
    return changed,dict(scope,proposed=True,energy_before=before,energy_after=after,
                        max_control_displacement=departure,step_limit=max_control_step,solves=statuses,
                        acceptance='NONE;VALIDATE_SHAPE_SEAMS_AND_JOIN',order=order)


def bernstein_matrix(degree, parameters):
    from math import comb
    t=np.asarray(parameters,float)
    return np.column_stack([comb(degree,i)*t**i*(1-t)**(degree-i) for i in range(degree+1)])


def axis_conversion_bound(old, new, axis):
    """Piecewise Bernstein coefficient bound for changing one tensor axis.
    The other basis MUST be identical; positive B-spline/Bernstein weights then
    bound the reconstructed positional difference. Numeric, not interval proof.
    """
    if axis not in (0,1):raise ValueError('AXIS_REQUIRED')
    oldK,newK=(old.ku,new.ku) if axis==0 else (old.kv,new.kv)
    oK,nK=(old.kv,new.kv) if axis==0 else (old.ku,new.ku)
    od,nd=(old.p,new.p) if axis==0 else (old.q,new.q)
    if not np.array_equal(oK,nK) or (old.q if axis==0 else old.p)!=(new.q if axis==0 else new.p):
        raise ValueError('OTHER_AXIS_MUST_BE_IDENTICAL')
    p=max(od,nd);t=(1-np.cos(np.linspace(0,np.pi,p+1)))/2
    B=bernstein_matrix(p,t)
    op=np.moveaxis(old.net,axis,0);np_=np.moveaxis(new.net,axis,0)
    os=BSpline(oldK,op,od);ns=BSpline(newK,np_,nd)
    distinct=np.unique(np.r_[oldK,newK]);bound=0.
    for a,b in zip(distinct[:-1],distinct[1:]):
        D=os(a+(b-a)*t)-ns(a+(b-a)*t)
        coeff=np.linalg.solve(B,D.reshape(p+1,-1)).reshape(D.shape)
        bound=max(bound,float(np.linalg.norm(coeff,axis=2).max()))
    return bound


def change_degree(tensor,axis,degree,allowance=1e-9):
    """Try another degree without altering geometry beyond a strict representation
    budget. Lower degrees that cannot represent the locked boundary are rejected.
    Elevation alone is NOT fairing; new degrees must undergo a separate solve.
    """
    if axis not in (0,1) or not isinstance(degree,(int,np.integer)) or not 1<=degree<=9 or not np.isfinite(allowance) or allowance<=0:
        raise ValueError('BOUNDED_AXIS_AND_DEGREE_REQUIRED')
    K=(tensor.ku,tensor.kv)[axis];olddegree=(tensor.p,tensor.q)[axis]
    if degree==olddegree:return tensor,{'accepted':True,'axis':axis,'degree':degree,'bound':0.}
    delta=degree-olddegree
    newK=np.r_[np.zeros(degree+1),
               np.concatenate([np.repeat(x,max(1,int(np.sum(K==x))+delta)) for x in np.unique(K)[1:-1]])
                   if len(np.unique(K))>2 else np.array([]),np.ones(degree+1)]
    n=len(newK)-degree-1;greville=np.array([np.mean(newK[i+1:i+degree+1]) for i in range(n)])
    oldnet=np.moveaxis(tensor.net,axis,0);values=BSpline(K,oldnet,olddegree)(greville)
    B=BSpline(newK,np.eye(n),degree)(greville)
    net=np.linalg.solve(B,values.reshape(n,-1)).reshape((n,)+oldnet.shape[1:])
    candidate=Tensor(np.moveaxis(net,0,axis),newK if axis==0 else tensor.ku,
                     newK if axis==1 else tensor.kv,degree if axis==0 else tensor.p,
                     degree if axis==1 else tensor.q)
    bound=axis_conversion_bound(tensor,candidate,axis)
    accepted=bool(np.isfinite(bound) and bound<=allowance)
    return candidate if accepted else tensor,{'accepted':accepted,'axis':axis,'degree':degree,
                                             'bound':bound,'shape':list(candidate.net.shape[:2])}


def guarded_selection(baseline, proposal, validators, energy, maximum_backtracks=7):
    """Return only a proposal that passes EVERY supplied validator; retain baseline
    on rejection. This API does not supply or impersonate missing native checks.
    Evidence explicitly lists the validators run. Baseline is not certified here.
    """
    if not validators or not isinstance(maximum_backtracks,int) or not 0<=maximum_backtracks<=12:
        raise ValueError('BOUNDED_VALIDATION_POLICY_REQUIRED')
    if (baseline.p,baseline.q)!=(proposal.p,proposal.q) or not np.array_equal(baseline.ku,proposal.ku) or not np.array_equal(baseline.kv,proposal.kv):
        raise ValueError('IDENTICAL_BASES_REQUIRED')
    events=[];old_energy=float(energy(baseline))
    for backtrack in range(maximum_backtracks+1):
        alpha=0.5**backtrack
        t=Tensor(baseline.net+alpha*(proposal.net-baseline.net),baseline.ku,baseline.kv,baseline.p,baseline.q)
        reasons=[]
        for name,validator in validators:
            try:
                verdict=validator(t)
                if not isinstance(verdict,(bool,np.bool_)) or not verdict:reasons.append(name)
            except Exception as exc:reasons.append(name+':'+type(exc).__name__)
        value=float(energy(t))
        if not np.isfinite(value) or value>=old_energy:reasons.append('NO_FAIRNESS_IMPROVEMENT')
        events.append({'alpha':alpha,'failed':reasons,'energy':value})
        if not reasons:
            return t,{'selected':'NUMERICAL_CANDIDATE_ONLY','alpha':alpha,'events':events,
                      'validators_run':[name for name,_ in validators],
                      'Rhino_Join':'NOT_RUN_BY_THIS_API','geometry_commit':False}
    return baseline,{'selected':'BASELINE_RETAINED_NOT_CERTIFIED','events':events,
                      'validators_run':[name for name,_ in validators],
                      'Rhino_Join':'NOT_RUN_BY_THIS_API','geometry_commit':False}


def section_curvatures(tensor,us,vs):
    """Actual geometric curvature of both isocurve families on explicit sites.
    Fixed sampling is screening, not a certified global extremum. No valid sites
    are silently omitted at degenerate derivatives.
    """
    values={}
    for name,(a,b) in (('u',(1,0)),('v',(0,1))):
        D=tensor.grid(us,vs,a,b);DD=tensor.grid(us,vs,2*a,2*b)
        speed=np.linalg.norm(D,axis=2)
        if not np.isfinite(D).all() or not np.isfinite(DD).all() or speed.min()<=1e-12:
            raise ValueError('SECTION_REGULARITY_UNAVAILABLE')
        k=np.linalg.norm(np.cross(D,DD),axis=2)/speed**3
        values[name]={'maximum':float(k.max()),'p99':float(np.quantile(k,.99)),
                      'sites':int(k.size)}
    return values


def curvature_nonregression(baseline,proposal,relative_slack=0.,absolute_slack=1e-8,
                            density=101):
    """Do not trade a quiet family for a sharper spike in the other family.
    The same knot-aware sample sites are used for both surfaces. A passing result
    is only one screen; it is NOT topology/Join or a global curvature proof.
    """
    if not 11<=density<=301 or relative_slack<0 or absolute_slack<0 or not np.isfinite([relative_slack,absolute_slack]).all():
        raise ValueError('INVALID_CURVATURE_SCREEN_POLICY')
    def sites(A,B):
        K=np.unique(np.r_[A,B]);extra=np.concatenate([a+(b-a)*(1-np.cos(np.linspace(0,np.pi,9)))/2
                                                    for a,b in zip(K[:-1],K[1:])])
        return np.unique(np.r_[np.linspace(0,1,density),extra])
    us=sites(baseline.ku,proposal.ku);vs=sites(baseline.kv,proposal.kv)
    before=section_curvatures(baseline,us,vs);after=section_curvatures(proposal,us,vs)
    failures=[]
    for direction in ('u','v'):
        for metric in ('maximum','p99'):
            if after[direction][metric]>before[direction][metric]*(1+relative_slack)+absolute_slack:
                failures.append(direction+':'+metric)
    return {'ok':not failures,'before':before,'after':after,'failed':failures,
            'scope':'SAME_SITE_GEOMETRIC_SECTION_SCREEN;NOT_GLOBAL_EXTREMA'}


def screen_proposal(baseline,proposal,core_interval,active_interval,lengths,
                    maximum_backtracks=5):
    """Mandatory numerical screens, including true section curvature in BOTH U/V.
    A low quadratic value can never by itself replace the previous candidate.
    Native Join/parent-intersection checks remain explicitly unexecuted here.
    """
    from local_regularity import inspect
    if baseline.net.shape!=proposal.net.shape:raise ValueError('SAME_BASELINE_BASIS_REQUIRED')
    a,b=active_interval;lo,hi=core_interval
    def locked(p):
        delta=p.net-baseline.net
        if max(np.linalg.norm(delta[0],axis=1).max(),np.linalg.norm(delta[-1],axis=1).max(),
               np.linalg.norm(delta[:,0],axis=1).max(),np.linalg.norm(delta[:,-1],axis=1).max())>1e-9:return False
        active=[j for j in range(p.nv) if p.kv[j]<b-1e-13 and p.kv[j+p.q+1]>a+1e-13]
        for u in (0.,1.):
            for degree in (1,2):
                diff=np.einsum('i,ijc->jc',p.bu(u,nu=degree),delta)
                if np.linalg.norm(diff[active],axis=1).max()>1e-7:return False
        core=[i for i in range(p.nu) if p.ku[i]<hi-1e-13 and p.ku[i+p.p+1]>lo+1e-13]
        return np.linalg.norm(delta[core],axis=2).max()<1e-9
    Q=fairness_matrix(baseline,lengths)
    energy=lambda t:float(np.einsum('ic,ij,jc',t.net.reshape(-1,3),Q,t.net.reshape(-1,3)))
    checks=[('COMPLETE_BOUNDARIES_CORE_ACTIVE_TWO_JETS',locked),
            ('BOTH_FAMILIES_GEOMETRIC_CURVATURE_NONREGRESSION',lambda t:curvature_nonregression(baseline,t)['ok']),
            ('LOCAL_NUMERICAL_REGULARITY',lambda t:inspect(t)['ok'])]
    return guarded_selection(baseline,proposal,checks,energy,maximum_backtracks)
