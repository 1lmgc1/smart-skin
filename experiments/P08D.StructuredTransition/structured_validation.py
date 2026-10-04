"""P08D.1A independent finite-site measurements. No native Join or CAD acceptance.
Metrics include physical fixed-plane sections; changing an inspected UV path is
not a license to declare better geometry. Degenerate/ambiguous sections fail.
"""
import numpy as np
import hashlib
from structured_transition import seam_evidence,sample_sites
from structured_flow import normal_flow_energy
from local_regularity import inspect


def grid(graph,us,vs,du=0,dv=0):
    us=np.asarray(us,float);vs=np.asarray(vs,float)
    out=np.zeros((len(us),len(vs),3));which=np.searchsorted([graph.intervals[0][1],graph.intervals[1][1]],us,side='right')
    for k,p in enumerate(graph.patches):
        ix=np.flatnonzero(which==k)
        if len(ix):out[ix]=p.grid((us[ix]-graph.intervals[k][0])/graph.width(k),vs,du,dv)/graph.width(k)**du
    return out


def stats(values):
    v=np.asarray(values,float)
    if not np.isfinite(v).all():raise ValueError('NONFINITE_VALIDATION_SAMPLE')
    return dict(maximum=float(v.max()),p99=float(np.quantile(v,.99)),mean=float(v.mean()))


def path_stats(P,N,K):
    d=np.diff(P,axis=1);l=np.linalg.norm(d,axis=-1)
    if l.min()<=1e-12:raise ValueError('DEGENERATE_VALIDATION_PATH')
    angles=np.arctan2(np.linalg.norm(np.cross(N[:,:-1],N[:,1:]),axis=-1),np.sum(N[:,:-1]*N[:,1:],axis=-1))
    return dict(normal_flow_energy=normal_flow_energy(P,N)[0],normal_total_turn_deg=stats(np.degrees(angles.sum(axis=1))),
                normal_rate_rad_per_mm=stats(angles/l),curvature_variation=stats(np.sum(np.abs(np.diff(K,axis=1)),axis=1)),
                curvature_rate_per_mm2=stats(np.abs(np.diff(K,axis=1))/l),curvature=stats(K))


def graph_metrics(graph,density=151,per_span=23,planes=(),regularity=False,checkpoint=None):
    if type(density) is not int or not 11<=density<=501 or not 5<=per_span<=51:raise ValueError('FINITE_VALIDATION_BUDGET_REQUIRED')
    ku=np.unique(np.concatenate([a+(b-a)*p.ku for p,(a,b) in zip(graph.patches,graph.intervals)]))
    us=sample_sites(ku,density,per_span);vs=sample_sites(graph.patches[0].kv,density,per_span)
    if len(us)*len(vs)>500000:raise ValueError('VALIDATION_SITE_BUDGET')
    if checkpoint:checkpoint()
    P,A,B,C,D,F=[grid(graph,us,vs,*key) for key in ((0,0),(1,0),(0,1),(2,0),(1,1),(0,2))]
    area=np.linalg.norm(np.cross(A,B),axis=-1);la=np.linalg.norm(A,axis=-1);lb=np.linalg.norm(B,axis=-1)
    if min(area.min(),la.min(),lb.min())<=1e-12:raise ValueError('DEGENERATE_VALIDATION_FRAME')
    N=np.cross(A,B)/area[:,:,None]
    ku0=np.linalg.norm(np.cross(A,C),axis=-1)/la**3;kv0=np.linalg.norm(np.cross(B,F),axis=-1)/lb**3
    # Symmetric shape operator in an orthonormal tangent frame, not raw H=I^-1 II.
    E=la*la;s=np.sum(A*B,axis=-1)/la;r=area/la
    e=np.sum(N*C,axis=-1);f=np.sum(N*D,axis=-1);g=np.sum(N*F,axis=-1)
    h11=e/E;h12=(f/la-e*s/E)/r;h22=(g-2*s*f/la+s*s*e/E)/(r*r)
    half=(h11+h22)/2;rad=np.hypot((h11-h22)/2,h12);principal=np.maximum(np.abs(half+rad),np.abs(half-rad))
    silhouette=[]
    for plane in planes:
        nn,dd,scale=plane.data();v=np.maximum(P@nn-dd,0.)
        silhouette.append(dict(maximum=float(v.max()),rms=float(np.sqrt(np.mean(v*v)))))
    out=dict(sampling_id=hashlib.sha256(us.astype('<f8').tobytes()+vs.astype('<f8').tobytes()).hexdigest(),sample_count=len(us)*len(vs),u=path_stats(P.swapaxes(0,1),N.swapaxes(0,1),ku0.T),v=path_stats(P,N,kv0),
             principal=stats(principal),silhouette=silhouette,min_area=float(area.min()),seams=seam_evidence(graph),
             scope='FINITE_KNOT_AWARE_SAMPLES;NOT_NATIVE_JOIN_OR_GLOBAL_SHAPE_CERTIFICATE')
    if regularity:out['regularity']=[inspect(p,checkpoint=checkpoint) for p in graph.patches]
    return out


def fixed_plane_section(graph,coordinate,value,vs):
    """Intersect each longitudinal station with a coordinate plane using bracketed Newton.
    Locate one sampled crossing bracket per station, then use bracketed Newton.
    Multiple sampled crossings or singular crossings fail. This is not a proof
    that no additional crossings exist between the bracket-screen samples.
    """
    if coordinate not in (0,1,2) or not np.isfinite(value):raise ValueError('FIXED_COORDINATE_PLANE_REQUIRED')
    vs=np.asarray(vs,float)
    if vs.ndim!=1 or len(vs)<3 or len(vs)>2001 or not np.isfinite(vs).all() or np.any(np.diff(vs)<=0) or vs[0]<0 or vs[-1]>1:
        raise ValueError('BOUNDED_ORDERED_SECTION_SITES_REQUIRED')
    uq=np.unique(np.r_[np.linspace(0,1,101),[v for pair in graph.intervals for v in pair]])
    values=grid(graph,uq,vs)[:,:,coordinate]-value
    lo=[];hi=[];signs=[]
    for col in values.T:
        exact=np.flatnonzero(np.abs(col)<=1e-12)
        if len(exact)==1:
            i=int(exact[0]);j=max(0,i-1);k=min(len(uq)-1,i+1)
            brackets=[(j,k)]
        elif len(exact)>1:raise ValueError('MULTIPLE_SAMPLED_PLANE_CROSSINGS')
        else:
            indices=np.flatnonzero(col[:-1]*col[1:]<0)
            brackets=[(int(i),int(i+1)) for i in indices]
        if len(brackets)!=1:raise ValueError('UNIQUE_SAMPLED_PLANE_BRACKET_REQUIRED')
        j,k=brackets[0]
        if col[j]*col[k]>0:raise ValueError('PLANE_TANGENCY_WITHOUT_CROSSING')
        lo.append(uq[j]);hi.append(uq[k]);signs.append(1. if col[k]>col[j] else -1.)
    lo=np.array(lo);hi=np.array(hi);sign=np.array(signs);u=(lo+hi)/2
    for unused in range(55):
        P=graph.evaluate(u,vs);f=sign*(P[:,coordinate]-value)
        if np.max(np.abs(f))<1e-10:break
        lo=np.where(f<0,u,lo);hi=np.where(f>0,u,hi)
        slope=sign*graph.evaluate(u,vs,1,0)[:,coordinate]
        if slope.min()<=1e-12:raise ValueError('SINGULAR_SECTION_CROSSING')
        trial=u-f/slope;u=np.where((trial>lo)&(trial<hi),trial,(lo+hi)/2)
    if np.max(np.abs(graph.evaluate(u,vs)[:,coordinate]-value))>1e-9:raise ValueError('SECTION_ROOT_BUDGET')
    P,A,B,C,D,F=[graph.evaluate(u,vs,*key) for key in ((0,0),(1,0),(0,1),(2,0),(1,1),(0,2))]
    w=-B[:,coordinate]/A[:,coordinate]
    w2=-(F[:,coordinate]+2*w*D[:,coordinate]+w*w*C[:,coordinate])/A[:,coordinate]
    first=B+w[:,None]*A;second=F+2*w[:,None]*D+(w*w)[:,None]*C+w2[:,None]*A
    speed=np.linalg.norm(first,axis=1);area=np.linalg.norm(np.cross(A,B),axis=1)
    if min(speed.min(),area.min())<=1e-12:raise ValueError('DEGENERATE_PHYSICAL_SECTION')
    curvature=np.linalg.norm(np.cross(first,second),axis=1)/speed**3;N=np.cross(A,B)/area[:,None]
    metrics=path_stats(P[None],N[None],curvature[None]);metrics.update(coordinate=coordinate,value=float(value),sites=len(vs),
        max_plane_residual=float(np.max(np.abs(P[:,coordinate]-value))),scope='SAMPLED_FIXED_PHYSICAL_PLANE;IMPLICIT_DERIVATIVES;NOT_GLOBAL_INTERSECTION_PROOF')
    return metrics


def nonregression(before,after,relative_slack=0.,absolute_slack=1e-7):
    """Conservative rank filter. Passing is research screening, never cap acceptance."""
    if not np.isfinite([relative_slack,absolute_slack]).all() or min(relative_slack,absolute_slack)<0:raise ValueError('FINITE_NONNEGATIVE_SCREEN_SLACK_REQUIRED')
    reasons=[]
    def check(a,b,name):
        if b>a*(1+relative_slack)+absolute_slack:reasons.append(name)
    if before['sample_count']!=after['sample_count'] or before['sampling_id']!=after['sampling_id']:raise ValueError('COMMON_SAMPLE_COUNT_REQUIRED')
    for family in ('u','v'):
        for prop in ('curvature','curvature_variation','normal_rate_rad_per_mm'):
            for stat in ('maximum','p99'):check(before[family][prop][stat],after[family][prop][stat],family+'.'+prop+'.'+stat)
        check(before[family]['normal_flow_energy'],after[family]['normal_flow_energy'],family+'.normal_flow_energy')
    for stat in ('maximum','p99'):check(before['principal'][stat],after['principal'][stat],'principal.'+stat)
    if len(before['silhouette'])!=len(after['silhouette']):raise ValueError('COMMON_SILHOUETTE_PLANES_REQUIRED')
    for i,(a,b) in enumerate(zip(before['silhouette'],after['silhouette'])):
        for stat in ('maximum','rms'):check(a[stat],b[stat],'silhouette'+str(i)+'.'+stat)
    if len(after.get('regularity',[]))!=3:reasons.append('REGULARITY_NOT_EVALUATED')
    for i,e in enumerate(after.get('regularity',[])):
        if not e['ok']:reasons.append('regularity'+str(i))
    return dict(passed=not reasons,reasons=reasons,geometry_commit=False,native_Join='NOT_RUN')


def screen_and_retain(baseline,proposal,active,max_step,planes=(),physical_planes=(),maximum_backtracks=4,checkpoint=None):
    """Immutable baseline, finite backtracking. No old Join passes propagate.
    Each changed candidate is independently measured. Missing physical-plane
    checks reject this stage's selection, even if an isocurve metric improves.
    """
    from structured_transition import lock_evidence
    if type(maximum_backtracks) is not int or not 0<=maximum_backtracks<=6 or not np.isfinite(max_step) or max_step<=0:
        raise ValueError('BOUNDED_SCREEN_REQUIRED')
    if not physical_planes:raise ValueError('EXPLICIT_PHYSICAL_CHECK_PLANES_REQUIRED')
    lock_evidence(baseline,proposal,active)
    if np.linalg.norm(proposal.control-baseline.control,axis=1).max()<=1e-10:
        return baseline,dict(status='REPRESENTATION_ONLY_NOT_FORM_REPAIR',attempts=[],geometry_commit=False,native_Join='NOT_RUN')
    before=graph_metrics(baseline,planes=planes,checkpoint=checkpoint)
    vs=sample_sites(baseline.patches[0].kv,151,23)
    pbefore=[fixed_plane_section(baseline,coord,value,vs) for coord,value in physical_planes]
    original_hash=baseline.digest();delta=proposal.control-baseline.control;events=[]
    for attempt in range(maximum_backtracks+1):
        if checkpoint:checkpoint()
        alpha=2.**(-attempt);trial=baseline.replace(baseline.control+alpha*delta)
        lock=lock_evidence(baseline,trial,active)
        after=graph_metrics(trial,planes=planes,regularity=True,checkpoint=checkpoint)
        screen=nonregression(before,after);reasons=screen['reasons'][:]
        if not lock['ok']:reasons.append('COEFFICIENT_LOCKS')
        if lock['step']>max_step*(1+1e-12):reasons.append('CONTROL_STEP')
        physical=[]
        for old,(coord,value) in zip(pbefore,physical_planes):
            if checkpoint:checkpoint()
            try:
                new=fixed_plane_section(trial,coord,value,vs);physical.append(dict(before=old,after=new))
                if new['normal_flow_energy']>old['normal_flow_energy']+1e-7:reasons.append('physical_flow_'+str(value))
                for key in ('curvature','curvature_variation','normal_rate_rad_per_mm'):
                    if new[key]['maximum']>old[key]['maximum']+1e-7:reasons.append('physical_'+key+'_'+str(value))
            except ValueError as e:
                physical.append(dict(unavailable=str(e)));reasons.append('PHYSICAL_SECTION_UNAVAILABLE')
        if not (after['u']['normal_flow_energy']+after['v']['normal_flow_energy'] < before['u']['normal_flow_energy']+before['v']['normal_flow_energy']-1e-9):reasons.append('NO_MEASURED_FLOW_IMPROVEMENT')
        events.append(dict(alpha=alpha,candidate_hash=trial.digest(),reasons=sorted(set(reasons)),locks=lock,after=after,physical=physical))
        if not reasons:
            if baseline.digest()!=original_hash:raise ValueError('BASELINE_MUTATED')
            return trial,dict(status='RESEARCH_SCREEN_PASSED_NOT_JOINED',selected_hash=trial.digest(),attempts=events,before=before,geometry_commit=False,native_Join='NOT_RUN')
    if baseline.digest()!=original_hash:raise ValueError('BASELINE_MUTATED')
    return baseline,dict(status='BASELINE_RETAINED_FORM_NOT_ACCEPTED',selected_hash=original_hash,attempts=events,before=before,geometry_commit=False,native_Join='NOT_RUN')
