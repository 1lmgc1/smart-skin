"""P08D.1B independent research screening; no Rhino/Join/product acceptance.
Retraction is in nonlinear chart coordinates, NEVER a linear average of nets.
Station alternatives are finite paired placements, not a general endpoint-map
optimizer. Comparison uses the same sites BEFORE/AFTER inside each layout and
fixed physical planes. Do not compare raw different-layout percentiles directly.
"""
import numpy as np
from structured_transition import PatchGraph, sample_sites, finite_scalar
from structured_validation import graph_metrics, fixed_plane_section, nonregression


def station_graphs(tensor, stations, **policies):
    if not 1<=len(stations)<=5:raise ValueError('ONE_TO_FIVE_EXPLICIT_STATION_LAYOUTS')
    out=[];seen=set()
    for pair in stations:
        if len(pair)!=2 or not all(finite_scalar(x) for x in pair):raise ValueError('FINITE_STATION_PAIR_REQUIRED')
        pair=tuple(map(float,pair))
        if pair in seen:raise ValueError('DUPLICATE_STATION_LAYOUT')
        seen.add(pair)
        g=PatchGraph.from_tensor(tensor,pair,**policies)
        g.coverage()
        # Exact split initializes each graph; this call does NOT change shape.
        out.append(g)
    return tuple(out)


def screen_attachment(problem, vector, planes=(), physical_planes=(), maximum_backtracks=4,
                      density=151, per_span=23, checkpoint=None):
    if type(maximum_backtracks) is not int or not 0<=maximum_backtracks<=6:raise ValueError('BOUNDED_PARAMETER_SCREEN_REQUIRED')
    if not physical_planes:raise ValueError('PHYSICAL_SECTIONS_REQUIRED')
    baseline=problem.space.graph;original=baseline.digest();x=np.asarray(vector,float).copy()
    proposal=problem.candidate(x)
    if np.linalg.norm(proposal.control-baseline.control,axis=1).max()<=1e-10:
        return baseline,dict(status='REPRESENTATION_ONLY_NOT_FORM_REPAIR',attempts=[],geometry_commit=False,native_Join='NOT_RUN')
    before=graph_metrics(baseline,density,per_span,planes,checkpoint=checkpoint)
    vs=sample_sites(baseline.patches[0].kv,density,per_span)
    physical_before=[fixed_plane_section(baseline,axis,value,vs) for axis,value in physical_planes]
    events=[]
    for index in range(maximum_backtracks+1):
        if checkpoint:checkpoint()
        alpha=2.**(-index)
        # Second jet targets contain alpha^2: scaling the control displacement
        # would violate G2 even when both the baseline and full proposal pass.
        trial=problem.candidate(x,alpha)
        lock=problem.space.evidence_on(trial,(alpha*x)[problem.nfree:])
        after=graph_metrics(trial,density,per_span,planes,regularity=True,checkpoint=checkpoint)
        reasons=nonregression(before,after)['reasons'][:]
        if not lock['ok']:reasons.append('GEOMETRIC_ATTACHMENT_OR_FIXED_FUNCTIONS')
        if lock['step']>problem.limits.max_control_step*(1+1e-12):reasons.append('CONTROL_STEP')
        physical=[]
        for old,(axis,value) in zip(physical_before,physical_planes):
            if checkpoint:checkpoint()
            try:
                new=fixed_plane_section(trial,axis,value,vs)
                physical.append(dict(before=old,after=new))
                if new['normal_flow_energy']>old['normal_flow_energy']+1e-7:reasons.append('physical_flow_'+str(value))
                for key in ('curvature','curvature_variation','normal_rate_rad_per_mm'):
                    if new[key]['maximum']>old[key]['maximum']+1e-7:reasons.append('physical_'+key+'_'+str(value))
            except ValueError as exc:
                physical.append(dict(unavailable=str(exc)));reasons.append('PHYSICAL_SECTION_UNAVAILABLE')
        if after['u']['normal_flow_energy']+after['v']['normal_flow_energy']>=before['u']['normal_flow_energy']+before['v']['normal_flow_energy']-1e-9:
            reasons.append('NO_MEASURED_FLOW_IMPROVEMENT')
        events.append(dict(alpha=alpha,retraction='CHART_PARAMETERS_REBUILT',candidate_hash=trial.digest(),reasons=sorted(set(reasons)),
                           locks=lock,after=after,physical=physical))
        if not reasons:
            if baseline.digest()!=original:raise ValueError('BASELINE_MUTATED')
            return trial,dict(status='RESEARCH_SCREEN_PASSED_NOT_JOINED',selected_hash=trial.digest(),attempts=events,before=before,
                              geometry_commit=False,native_Join='NOT_RUN')
    if baseline.digest()!=original:raise ValueError('BASELINE_MUTATED')
    return baseline,dict(status='BASELINE_RETAINED_FORM_NOT_ACCEPTED',selected_hash=original,attempts=events,before=before,
                         geometry_commit=False,native_Join='NOT_RUN')
