# -*- coding: utf-8 -*-
"""P08B.3: regularized vector G1, bounded rollback, G1 gate before G2.
Pure Python 2/3; no native/runtime dependencies. Geometry is measured after each
step. Fixed outer rows, source roles and tolerances are never changed.
"""
from __future__ import division
import math
from mixed_kernel import *
from shape_guard import FastEvaluator, ShapePolicy, spans, harmonic_seed


def stable_sites(func,K,count=65):
    points=set(sample_parameters(func,count))
    for a,b in spans(K):
        points.update(a+(b-a)*f for f in (0.,.1127016654,.5,.8872983346,1.))
    return sorted(points)


def stable_measure(patch,boundaries,policy,tolerance=.01,angle_deg=1.,curvature_pct=5.,anchor=None,checkpoint=None):
    evaluator=FastEvaluator(patch); edges={}
    for side in SIDES:
        for t in stable_sites(boundaries[side],patch.K):
            if checkpoint is not None: checkpoint()
            support=boundaries[side](t); u,v=side_uv(side,t); values=evaluator.eval(u,v)
            key=support.key
            if key not in edges:
                edges[key]=dict(gap=0.,normal_deg=0.,curvature_pct=0.,count=0,frames=True,curvatures=True,
                                preferred=support.preferred,weight=support.weight,angle_sum2=0.,angle_count=0,
                                tangent_plane_deg=0.,normal_witness=None,curve_sum2=0.,curve_count=0)
            e=edges[key]; e['count']+=1; e['gap']=max(e['gap'],norm(sub(values[0],support.point)))
            if support.preferred==0: continue
            try:
                normal,H=frame(values)
                if support.normal is None: raise ValueError('NO_SUPPORT_NORMAL')
                d=max(-1.,min(1.,dot(normal,support.normal))); angle=math.degrees(math.acos(abs(d)))
                if angle>=e['normal_deg']: e['normal_deg']=angle; e['normal_witness']=(side,t)
                e['angle_sum2']+=angle*angle; e['angle_count']+=1
                tangent=values[1] if side in ('bottom','top') else values[2]
                tangerr=math.degrees(math.asin(min(1.,abs(dot(unit(tangent),support.normal)))))
                e['tangent_plane_deg']=max(e['tangent_plane_deg'],tangerr)
                if support.H is None: e['curvatures']=False
                else:
                    ce=tensor_error(H,support.H,d); e['curvature_pct']=max(e['curvature_pct'],ce)
                    e['curve_sum2']+=ce*ce; e['curve_count']+=1
            except ValueError: e['frames']=False; e['curvatures']=False
    if not edges: raise ValueError('EMPTY_MEASUREMENT')
    for e in edges.values():
        e['achieved']=0 if e['gap']<=tolerance else -1
        e['normal_rms_deg']=math.sqrt(e['angle_sum2']/e['angle_count']) if e['angle_count'] else 90.
        if e['preferred']>0 and e['achieved']>=0 and e['frames'] and e['normal_deg']<=angle_deg:
            e['achieved']=1
            if e['curvatures'] and e['curvature_pct']<=curvature_pct: e['achieved']=2
        e['curvature_rms_pct']=math.sqrt(e['curve_sum2']/e['curve_count']) if e['curve_count'] else 200.
        if not e['frames']: e['normal_deg']=90.
    smooth=[e for e in edges.values() if e['preferred']>0]
    g1=bool(smooth) and all(e['achieved']>=1 for e in smooth)
    total=sum(e['weight'] for e in smooth) or 1.
    normal_rms=math.sqrt(sum(e['weight']*e['normal_rms_deg']**2 for e in smooth)/total)
    normal_max=max([e['normal_deg'] for e in smooth] or [0.])
    curve=max([e['curvature_pct'] if e['curvatures'] else 200. for e in smooth if e['preferred']>=2] or [0.])
    curve_rms=math.sqrt(sum(e['weight']*e['curvature_rms_pct']**2 for e in smooth if e['preferred']>=2)/total)
    desired=all(e['achieved']>=e['preferred'] for e in edges.values())
    shape=policy.inspect(patch,anchor,checkpoint)
    return dict(edges=edges,position_sampled_ok=all(e['gap']<=tolerance for e in edges.values()),
                regularity_sampled_ok=shape['ok'],shape=shape,g1_all=g1,
                desired_sampled_met=desired and shape['ok'],gap_sampled=max(e['gap'] for e in edges.values()),
                normal_rms_deg=normal_rms,normal_max_deg=normal_max,curvature_max_pct=curve,curvature_rms_pct=curve_rms,
                score=(sum(e['weight']*min(max(e['achieved'],0),e['preferred']) for e in smooth)/total,
                       -normal_rms,-normal_max,-curve_rms if g1 else 0.),
                scope='KNOT_AWARE_BOUNDARY_SAMPLES;NUMERICAL_BERNSTEIN_SHAPE;NOT_GLOBAL_SELF_INTERSECTION_CERTIFICATE',commit_allowed=False)


def prefer_evidence(new,old):
    """No curvature-only promotion while any required G1 is still missing."""
    if not new['position_sampled_ok'] or not new['shape']['ok']: return False
    if old is None: return True
    if set(new['edges'])!=set(old['edges']): return False
    for key,e in old['edges'].items():
        other=new['edges'][key]
        if e['preferred']!=other['preferred']: return False
        if e['preferred']>0 and min(e['achieved'],e['preferred'])>min(other['achieved'],other['preferred']): return False
    if new['score'][0]>old['score'][0]+1e-9: return True
    if old['g1_all'] and not new['g1_all']: return False
    if new['g1_all']:
        return (new['curvature_max_pct']<=old['curvature_max_pct']+.01
                and new['curvature_rms_pct']<old['curvature_rms_pct']-max(.01,.002*old['curvature_rms_pct']))
    return (new['normal_max_deg']<=old['normal_max_deg']+.01
            and new['normal_rms_deg']<old['normal_rms_deg']-max(.02,.002*old['normal_rms_deg']))


def _weighted_sparse(row,rhs,weight):
    length=math.sqrt(sum(c*c for _,c in row))
    if length<=1e-14: return None
    factor=weight/length
    return [(i,c*factor) for i,c in row],rhs*factor


def vector_proposal(current,anchor,boundaries,policy,curvature=False,checkpoint=None):
    """Solve full transverse vectors for G1, not just n dot derivative = 0.
    A nonzero conormal speed is anchored to the opening scale. Positive-weight
    displacement regularization limits unconstrained modes before line search.
    G2 adds normal acceleration and mixed-derivative targets only after G1.
    """
    n,p,K=current.n,current.p,current.K
    ids={(i,j,k):((i-1)*(n-2)+(j-1))*3+k for i in range(1,n-1) for j in range(1,n-1) for k in range(3)}
    initial=[x for i in range(1,n-1) for j in range(1,n-1) for x in current.net[i][j]]
    rows=[]; rhs=[]; unavailable=0; uncontrollable=0
    now,base=FastEvaluator(current),FastEvaluator(anchor)
    def equation(u,v,du,dv,axis,value,weight):
        bu,bv=now.weights(u)[du],now.weights(v)[dv]; row=[]; fixed=0.
        for i,a in bu:
            for j,b in bv:
                c=a*b
                if i in (0,n-1) or j in (0,n-1): fixed+=c*dot(axis,current.net[i][j])
                else:
                    for k in range(3):
                        if abs(c*axis[k])>1e-15: row.append((ids[i,j,k],c*axis[k]))
        wr=_weighted_sparse(row,value-fixed,weight)
        if wr is not None: rows.append(wr[0]); rhs.append(wr[1]); return True
        return False
    for side in SIDES:
        for t in stable_sites(boundaries[side],K,41):
            if checkpoint is not None: checkpoint()
            support=boundaries[side](t)
            if support.preferred==0: continue
            if support.normal is None: unavailable+=1; continue
            u,v=side_uv(side,t); values=now.eval(u,v); original=base.eval(u,v)
            along_index=1 if side in ('bottom','top') else 2
            cross_index=2 if along_index==1 else 1
            tangent=unit(values[along_index]); normal=support.normal
            if dot(normal,policy.normal)<0: normal=mul(normal,-1)
            # Conormal sign preserves the intended U/V sheet orientation.
            co=cross(normal,tangent) if along_index==1 else cross(tangent,normal)
            if norm(co)<1e-10:
                unavailable+=1; continue  # incompatible fixed tangent; measurement stays failed
            conormal=unit(co)
            D=original[cross_index]
            speed=max(.15*policy.scale,min(2.5*policy.scale,norm(sub(D,mul(tangent,dot(D,tangent))))))
            target=add(mul(tangent,dot(D,tangent)),mul(conormal,speed))
            du,dv=(0,1) if along_index==1 else (1,0)
            for k in range(3):
                axis=tuple(1. if j==k else 0. for j in range(3))
                if not equation(u,v,du,dv,axis,target[k],1. if not curvature else 3.): uncontrollable+=1
            if curvature and support.preferred>=2 and support.H is not None:
                # Keep support-normal sign coupled to its shape operator.
                sn=support.normal
                d=values[cross_index]; d=sub(d,mul(sn,dot(d,sn)))
                ta=values[along_index]; ta=sub(ta,mul(sn,dot(ta,sn)))
                second=support.second(d)
                mixed=sum(ta[i]*support.H[i][j]*d[j] for i in range(3) for j in range(3))
                equation(u,v,2*du,2*dv,sn,second,.5)
                equation(u,v,1,1,sn,mixed,.5)
    # Regularize the displacement field, not surface coordinates toward zero.
    g=[sum(K[i+1:i+p+1])/p for i in range(n)]
    for i in range(1,n-1):
        if checkpoint is not None: checkpoint()
        for j in range(1,n-1):
            for k in range(3):
                rows.append([(ids[i,j,k],.015)]); rhs.append(.015*anchor.net[i][j][k])
                for axis in (0,1):
                    q=i if axis==0 else j; a=g[q]-g[q-1]; b=g[q+1]-g[q]
                    weights=(b/(a+b),-1.,a/(a+b)); positions=((i-1,j),(i,j),(i+1,j)) if axis==0 else ((i,j-1),(i,j),(i,j+1))
                    row=[]; value=0.
                    for w,(ii,jj) in zip(weights,positions):
                        value+=w*anchor.net[ii][jj][k]
                        if ii in (0,n-1) or jj in (0,n-1): value-=w*current.net[ii][jj][k]
                        else: row.append((ids[ii,jj,k],w))
                    wr=_weighted_sparse(row,value,.05)
                    if wr: rows.append(wr[0]); rhs.append(wr[1])
    solved,iterations=pcg(rows,rhs,initial,ridge=1e-7,limit=350,checkpoint=checkpoint)
    net=[[tuple(point) for point in row] for row in current.net]
    for i in range(1,n-1):
        for j in range(1,n-1): net[i][j]=tuple(solved[ids[i,j,0]:ids[i,j,0]+3])
    proposal=Patch(net,p,K)
    return proposal,dict(iterations=iterations,rows=len(rows),missing_support_samples=unavailable,
                         fixed_endpoint_equations=uncontrollable,solver='REGULARIZED_FULL_VECTOR_G1')


def blend_patch(current,proposal,alpha):
    if current.n!=proposal.n or current.K!=proposal.K or not 0<=alpha<=1: raise ValueError('BLEND_BASIS_OR_STEP')
    net=[[add(a,mul(sub(b,a),alpha)) for a,b in zip(row,other)] for row,other in zip(current.net,proposal.net)]
    # Copy rather than reconstruct locked rows, avoiding rounding changes.
    n=current.n
    for i in range(n): net[i][0]=current.net[i][0]; net[i][-1]=current.net[i][-1]
    for j in range(n): net[0][j]=current.net[0][j]; net[-1][j]=current.net[-1][j]
    return Patch(net,current.p,current.K)


def bounded_step(current,proposal,anchor,boundaries,policy,evidence,tolerance=.01,angle_deg=1.,curvature_pct=5.,checkpoint=None,on_trial=None):
    delta=max(norm(sub(b,a)) for row,other in zip(current.net,proposal.net) for a,b in zip(row,other))
    if not finite(delta) or delta<1e-13: return current,evidence,False
    alpha=min(1.,policy.step_limit/delta)
    for attempt in range(8):
        if checkpoint is not None: checkpoint()
        candidate=blend_patch(current,proposal,alpha)
        e=stable_measure(candidate,boundaries,policy,tolerance,angle_deg,curvature_pct,anchor,checkpoint)
        kept=prefer_evidence(e,evidence)
        if on_trial: on_trial(dict(alpha=alpha,attempt=attempt,raw_control_step=delta,
                                    actual_control_step=alpha*delta,step_limit=policy.step_limit,
                                    kept=kept,shape=e['shape'],normal_rms_deg=e['normal_rms_deg'],
                                    normal_max_deg=e['normal_max_deg'],g1_all=e['g1_all']))
        if kept: return candidate,e,True
        alpha*=.5
    return current,evidence,False


def stable_solve(base,boundaries,tolerance=.01,angle_deg=1.,curvature_pct=5.,checkpoint=None,on_candidate=None,on_event=None,steps=8):
    """Construct and keep a bounded baseline; roll back failed refinements.
    Callbacks are observations, not acceptance/commit permissions. Native G0/Join
    and the selected document's safety checks remain the Rhino adapter's job.
    """
    def event(kind,**data):
        if on_event: on_event(kind,data)
    try: policy=ShapePolicy(base,boundaries,tolerance)
    except ValueError:
        base=harmonic_seed(base,checkpoint=checkpoint); policy=ShapePolicy(base,boundaries,tolerance)
    e=stable_measure(base,boundaries,policy,tolerance,angle_deg,curvature_pct,None,checkpoint)
    event('SHAPE_BASELINE',seed='COONS',**e['shape'])
    if not e['position_sampled_ok']: return None,None
    if not e['shape']['ok']:
        alternative=harmonic_seed(base,checkpoint=checkpoint)
        policy=ShapePolicy(alternative,boundaries,tolerance)
        ae=stable_measure(alternative,boundaries,policy,tolerance,angle_deg,curvature_pct,None,checkpoint)
        event('SHAPE_BASELINE',seed='HARMONIC',**ae['shape'])
        if not ae['position_sampled_ok'] or not ae['shape']['ok']:
            event('STABLE_STOP',reason='NO_BOUNDED_SINGLE_CHART_BASELINE',commit_allowed=False)
            return None,None
        base,e=alternative,ae
    anchor=base; current=base
    event('STABILITY_LIMITS',opening_scale=policy.scale,control_step_limit=policy.step_limit,
          total_anchor_limit=policy.total_limit,source_role_changes=0)
    if on_candidate: on_candidate('STABLE_BASELINE',current,e)
    for step in range(steps):
        if checkpoint is not None: checkpoint()
        if e['desired_sampled_met']: break
        curvature=e['g1_all']
        event('STABLE_STEP_START',step=step,level='G2' if curvature else 'G1',g1_all=e['g1_all'])
        try: proposal,info=vector_proposal(current,anchor,boundaries,policy,curvature,checkpoint)
        except ValueError as error:
            event('STABLE_ROLLBACK',step=step,reason='PROPOSAL_UNAVAILABLE',detail=str(error),baseline_retained=True)
            break
        event('STABLE_PROPOSAL',step=step,**info)
        def trial(record): event('STABLE_TRIAL',step=step,**record)
        changed,ne,kept=bounded_step(current,proposal,anchor,boundaries,policy,e,tolerance,angle_deg,curvature_pct,checkpoint,trial)
        if not kept:
            event('STABLE_ROLLBACK',step=step,reason='NO_SAFE_MEANINGFUL_IMPROVEMENT',baseline_retained=True)
            break
        current,e=changed,ne
        if on_candidate: on_candidate('STABLE_'+('G2' if curvature else 'G1')+'_'+str(step),current,e)
    if not e['g1_all']: event('G2_SKIPPED',reason='G1_NOT_MEASURED_WITHIN_TOLERANCE',preferred_G2_unchanged=True)
    return current,e
