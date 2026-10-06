"""Pure validation/copying of native trim provenance; no Rhino or fixture data.

Curve/surface evaluators are supplied by the family module, avoiding loader
cycles. Missing evidence is never inferred from a surface rectangle or profile.
Shape operators use the captured parent orientation and the immutable native
surface two-jet, including both principal and mixed normal curvatures.
"""
import copy
import math
import numpy as np


class BoundaryEvidenceError(ValueError):
    pass


def _fail(detail):
    raise BoundaryEvidenceError('NATIVE_BOUNDARY_EVIDENCE: '+detail)


def _array(value,shape,name):
    a=np.asarray(value,dtype=float)
    if a.shape!=shape or not np.all(np.isfinite(a)):_fail('Invalid '+name+'.')
    return a


def _unit(value,name):
    a=_array(value,(3,),name)
    length=float(np.linalg.norm(a))
    if abs(length-1.)>1e-5:_fail('Non-unit '+name+'.')
    return a/length


def _close(a,b,tol,detail):
    b=np.asarray(b,dtype=float);a=_array(a,b.shape,'native comparison')
    if np.linalg.norm(a-b)>tol:_fail(detail)


def _check(cancelled):
    if cancelled and cancelled():_fail('Cancelled while validating native evidence.')


def _reference(surface,uv,point,normal,tol):
    uv=_array(uv,(2,),'native UV')
    if not surface.ud[0]<=uv[0]<=surface.ud[1] or not surface.vd[0]<=uv[1]<=surface.vd[1]:
        _fail('Captured UV is outside the immutable native surface domain.')
    p,su,sv,suu,suv,svv=surface.jet(*uv)
    _close(p,point,tol,'Captured owner point does not match its immutable surface.')
    n=_unit(normal,'captured parent normal');cross=np.cross(su,sv)
    if np.linalg.norm(cross)<=0.:_fail('Singular native parent two-jet.')
    if abs(float(n@(cross/np.linalg.norm(cross))))<1.-1e-7:_fail('Captured parent normal disagrees with its native surface.')
    lengths=np.array([np.linalg.norm(su),np.linalg.norm(sv)])
    if min(lengths)<=0.:_fail('Singular native parent metric.')
    basis=np.column_stack([su,sv])/lengths
    gram=basis.T@basis
    if np.linalg.det(gram)<1e-12:_fail('Singular native parent metric.')
    second=np.array([[n@suu,n@suv],[n@suv,n@svv]])/np.outer(lengths,lengths)
    dual=basis@np.linalg.inv(gram)
    shape=dual@second@dual.T
    if not np.all(np.isfinite(shape)):_fail('Nonfinite native full shape operator.')
    return dict(point=np.asarray(p).tolist(),uv=uv.tolist(),parent_normal=n.tolist(),shape_operator=shape.tolist())


def _probes(witness,normal,inward,tol,surface,classification_tolerance,corner=False):
    probes=witness.get('probes',[]);count=12 if corner else 4
    if len(probes)!=count:_fail('Missing bounded native probe witnesses.')
    radius=float(witness.get('probe_distance',0.))
    if not math.isfinite(radius) or radius<=0.:_fail('Invalid native probe radius.')
    classify=float(classification_tolerance)
    if not math.isfinite(classify) or classify<=0. or radius*.5<16.*classify:_fail('Native probe classification tolerance is unresolved.')
    origin_uv=_array(witness.get('uv'),(2,),'native station UV')
    origin,su,sv,*_=surface.jet(*origin_uv);jac=np.column_stack([su,sv])
    group=6 if corner else 2
    for i,p in enumerate(probes):
        d=_unit(p.get('direction'),'probe direction')
        if abs(float(d@normal))>1e-5:_fail('Native probe is outside the owner tangent plane.')
        expected=radius if i<group else radius*.5
        if abs(float(p.get('distance',0.))-expected)>max(radius*1e-10,1e-14):_fail('Native probe radii are not nested.')
        relation=p.get('relation');mapping=p.get('mapping')
        if relation not in ('Interior','Exterior'):_fail('Ambiguous native probe membership.')
        uv=_array(p.get('uv'),(2,),'probe UV')
        _close(jac@(uv-origin_uv),d*expected,max(classify*.25,expected*.025),
               'Native probe UV does not represent its physical tangent displacement.')
        in_domain=surface.ud[0]<=uv[0]<=surface.ud[1] and surface.vd[0]<=uv[1]<=surface.vd[1]
        if mapping=='native_domain_exterior':
            if relation!='Exterior' or in_domain:_fail('Surface-domain exterior was used as unsupported membership evidence.')
        elif mapping=='physical_surface_probe':
            if not in_domain:_fail('Physical probe leaves the native surface evaluation domain.')
            point=_array(p.get('point'),(3,),'physical probe point')
            _close(surface.jet(*uv)[0],point,tol,'Native physical probe does not match its immutable surface.')
            _close(point-origin,d*expected,max(classify*.25,expected*.025)+tol*1e-5,
                   'Native physical probe is not locally resolved.')
        else:_fail('Missing native physical-probe provenance.')
        if not corner and float(d@inward)*(1. if relation=='Interior' else -1.)<1.-1e-5:
            _fail('Native interior/exterior witness contradicts its signed co-normal.')
    relations=[p['relation'] for p in probes]
    if corner:
        a,b=relations[0],relations[3]
        if a==b or relations!=[a]*3+[b]*3+[a]*3+[b]*3:_fail('Corner sectors are not complementary at both radii.')
        wedge=witness.get('exterior_wedge',{});start=_unit(wedge.get('start_ray'),'exterior wedge ray')
        _close(wedge.get('oriented_normal'),normal,1e-5,'Exterior wedge has the wrong parent orientation.')
        ray=_unit(witness.get('trim_ray'),'native corner ray');adjacent=_unit(witness.get('adjacent_ray'),'adjacent native trim ray')
        angle=math.atan2(float(adjacent@np.cross(normal,ray)),float(adjacent@ray))%(2.*math.pi)
        _close(start,adjacent if a=='Interior' else ray,1e-5,'Exterior wedge does not start on the actual corner ray.')
        _close(witness.get('adjacent_inward_conormal'),(-1. if a=='Interior' else 1.)*np.cross(normal,adjacent),
               1e-5,'Adjacent native trim co-normal contradicts corner membership.')
        expected_sweep=2.*math.pi-angle if a=='Interior' else angle
        sweep=float(wedge.get('sweep_radians',0.))
        if abs(sweep-expected_sweep)>1e-7:_fail('Exterior wedge does not end on the actual adjacent trim ray.')
        if not math.isfinite(sweep) or not 1e-5<sweep<2.*math.pi-1e-5:_fail('Degenerate native exterior wedge.')
        for p in probes:
            d=np.asarray(p['direction']);angle=math.atan2(float(d@np.cross(normal,start)),float(d@start))%(2.*math.pi)
            if (angle<sweep)!=(p['relation']=='Exterior'):_fail('Corner wedge contradicts native membership probes.')
    elif relations[:2]!=relations[2:] or set(relations[:2])!={'Interior','Exterior'}:
        _fail('Smooth native side is not complementary at both radii.')
    else:
        for relation,field in (('Interior','inside_uv'),('Exterior','outside_uv')):
            _close(witness.get(field),probes[relations.index(relation)]['uv'],1e-12,'Native inside/outside UV witness was changed.')


def _make_record(edge,reverse,tolerance,curve_factory,surface_factory,cancelled):
    _check(cancelled)
    key=edge.get('source_key',edge.get('key'))
    if not isinstance(key,str) or not key:_fail('A native boundary has no source key.')
    if type(reverse) is not bool:_fail('Native traversal reversal must be explicit.')
    curve=curve_factory(edge['curve']);surface=surface_factory(edge['surface']);lo,hi=curve.domain
    owner=edge.get('owner_side')
    if not isinstance(owner,dict) or owner.get('schema')!='native-trim-side-v1':_fail('Missing captured native owner-side evidence.')
    for name in ('face_index','trim_index','loop_index'):
        if type(owner.get(name)) is not int or owner[name]<0:_fail('Missing native owner/trim provenance.')
    for name in ('face_orientation_reversed','trim_reversed'):
        if type(owner.get(name)) is not bool:_fail('Missing native orientation provenance.')
    sign=owner.get('edge_inward_cross_sign')
    if sign not in (-1.,1.):_fail('Missing signed native edge traversal.')
    samples=owner.get('samples',[]);corners=owner.get('corners',[])
    if len(samples)!=15 or len(corners)!=2:_fail('Incomplete native edge or corner witnesses.')
    position_tol=max(float(tolerance)*.05,1e-9);references=[];corner_refs=[];previous=lo
    for i,w in enumerate(samples+corners):
        _check(cancelled)
        corner=i>=len(samples)
        if corner:
            end=w.get('edge_end')
            if type(end) is not int or end!=i-len(samples):_fail('Native endpoint witnesses are missing or reordered.')
            parameter=(lo,hi)[end]
        else:
            parameter=float(w.get('edge_parameter',float('nan')))
            if not previous<parameter<hi:_fail('Native arc stations are not strictly ordered.')
            previous=parameter
            if abs(float(w.get('edge_arc_fraction',0.))-(i+1)/16.)>1e-12:_fail('Missing native arc-length station provenance.')
            if abs(float(w.get('edge_fraction',-1.))-(parameter-lo)/(hi-lo))>1e-10:_fail('Native station parameter bookkeeping is inconsistent.')
        point=_array(w.get('point'),(3,),'native owner point')
        _close(curve(parameter),point,position_tol,'Native witness does not lie on its original selected edge.')
        normal=_unit(w.get('oriented_normal'),'native parent normal');inward=_unit(w.get('inward_conormal'),'native inward co-normal')
        _close(w.get('outward_conormal'),-inward,1e-5,'Native outward co-normal is inconsistent.')
        tangent=np.asarray(curve(parameter,1));length=np.linalg.norm(tangent)
        if length<=0.:_fail('Singular native edge tangent.')
        tangent/=length
        if abs(float(normal@tangent))>1e-5 or abs(float(normal@inward))>1e-5 or abs(float(inward@tangent))>1e-5:
            _fail('Native owner frame is not orthogonal.')
        if w.get('edge_inward_cross_sign')!=sign or float(inward@np.cross(normal,tangent))*sign<1.-1e-5:
            _fail('Native owner side contradicts edge traversal.')
        if corner:
            _close(w.get('trim_ray'),tangent*(1. if end==0 else -1.),1e-5,'Corner trim ray does not follow the original native edge.')
            if type(w.get('trim_at_start')) is not bool or w['trim_at_start']!=((end==0)!=owner['trim_reversed']):
                _fail('Corner does not preserve original trim/edge traversal.')
            adjacent=_unit(w.get('adjacent_ray'),'adjacent native trim ray')
            if abs(float(adjacent@normal))>1e-5 or type(w.get('adjacent_trim_index')) is not int:
                _fail('Missing adjacent native trim provenance.')
        else:_close(w.get('tangent'),tangent,1e-5,'Captured native tangent disagrees with its exact edge.')
        _probes(w,normal,inward,position_tol,surface,w.get('classification_tolerance',owner.get('classification_tolerance')),corner)
        ref=_reference(surface,w.get('uv'),point,normal,position_tol)
        natural=np.cross(surface.jet(*w['uv'])[1],surface.jet(*w['uv'])[2]);natural/=np.linalg.norm(natural)
        if float(normal@natural)*( -1. if owner['face_orientation_reversed'] else 1.)<1.-1e-7:
            _fail('Captured parent orientation contradicts its immutable surface.')
        ref.update(edge_parameter=float(parameter),edge_arc_fraction=float(end if corner else w['edge_arc_fraction']))
        if corner:ref['edge_end']=end;corner_refs.append(ref)
        else:references.append(ref)
    return dict(source_key=key,curve=copy.deepcopy(edge['curve']),surface=copy.deepcopy(edge['surface']),
                original_curve_domain=[float(lo),float(hi)],active_domain=[float(lo),float(hi)],reverse=reverse,
                traversal_domain=[float(hi),float(lo)] if reverse else [float(lo),float(hi)],
                owner_side=copy.deepcopy(owner),reference_stations=references,reference_corners=corner_refs)


def _validate_side_map(record,mapping,tolerance,curve_factory,surface_factory):
    surface=surface_factory(record['surface']);curve=curve_factory(record['curve'])
    a=_array(mapping.get('native_uv_from_chart_uv',{}).get('matrix'),(2,2),'native UV map matrix')
    b=_array(mapping.get('native_uv_from_chart_uv',{}).get('offset'),(2,),'native UV map offset')
    chart=_array(mapping.get('chart_domain'),(2,2),'chart domain')
    native=np.asarray([surface.ud,surface.vd],float)
    uv_tol=max(1e-12,128.*np.finfo(float).eps*max(1.,float(np.max(abs(native)))))
    _close(mapping.get('native_surface_domain'),native,1e-12,'Native surface domain map changed.')
    if abs(np.linalg.det(a))<=0. or any(sum(abs(row)>1e-15)!=1 for row in a) or any(sum(abs(col)>1e-15)!=1 for col in a.T):
        _fail('Side map must be an exact affine axis permutation/reversal.')
    if not np.all(chart[:,1]>chart[:,0]) or not np.array_equal(chart[1],[0.,1.]):_fail('Side chart must retain normalized boundary V.')
    mapped=np.asarray([a@np.array([u,v])+b for u in chart[0] for v in chart[1]])
    _close(mapped.min(axis=0),native[:,0],uv_tol,'Side map does not cover original native parameter domain.')
    _close(mapped.max(axis=0),native[:,1],uv_tol,'Side map does not cover original native parameter domain.')
    boundary=float(mapping.get('boundary_chart_u',float('nan')))
    if boundary!=chart[0,0]:_fail('Missing oriented side boundary chart coordinate.')
    slope,offset=_array(mapping.get('edge_parameter_from_chart_v'),(2,),'native edge parameter map')
    _close([min(offset,slope+offset),max(offset,slope+offset)],curve.domain,1e-10,'Side map changed native edge domain.')
    if bool(slope<0.)!=record['reverse']:_fail('Side map and native edge traversal disagree.')
    for v in (0.,.25,.5,.75,1.):
        uv=a@np.array([boundary,v])+b
        _close(surface.jet(*uv)[0],curve(slope*v+offset),max(tolerance*.05,1e-9),
               'Side chart mapping does not reproduce the original native edge.')


def _build_source_boundaries(role_chains,tolerance,curve_factory,surface_factory,side_maps=None,cancelled=None):
    """Validate all four roles. Never infer or synthesize missing owner evidence."""
    if set(role_chains)!={'side0','side1','upper','lower'}:_fail('Exactly four boundary roles are required.')
    result={};keys=[]
    for role,chain in role_chains.items():
        if not 1<=len(chain)<=16 or (role.startswith('side') and len(chain)!=1):_fail('Unsupported native role edge count.')
        records=[]
        for edge,reverse in chain:
            record=_make_record(edge,reverse,tolerance,curve_factory,surface_factory,cancelled)
            if role.startswith('side'):
                mapping=(side_maps or {}).get(role)
                if not isinstance(mapping,dict):_fail('Missing exact side-chart/native parameter map.')
                _validate_side_map(record,mapping,tolerance,curve_factory,surface_factory)
                record['parameter_map']=copy.deepcopy(mapping)
            keys.append(record['source_key']);records.append(record)
        result[role]=records
    if len(keys)>16 or len(set(keys))!=len(keys):_fail('Source boundary roles duplicate or exceed the selected native edges.')
    def endpoint(record,end):
        curve=curve_factory(record['curve']);return curve(record['traversal_domain'][end])
    for chain in result.values():
        for left,right in zip(chain[:-1],chain[1:]):
            _close(endpoint(left,1),endpoint(right,0),tolerance,'Native role chain traversal is disconnected.')
    for role,side_end in (('upper',0),('lower',1)):
        _close(endpoint(result[role][0],0),endpoint(result['side0'][0],side_end),tolerance,'Native role start no longer meets side0.')
        _close(endpoint(result[role][-1],1),endpoint(result['side1'][0],side_end),tolerance,'Native role end no longer meets side1.')
    return dict(schema='native-boundaries-v1',complete=True,status='validated',source_edge_count=len(keys),roles=result,
                shape_operator_convention='oriented parent normal; ambient symmetric 3x3 normal-curvature operator')


def _require_complete_evidence(evidence,tolerance,curve_factory,surface_factory,cancelled=None):
    """Independent production/fan gate; replay validation and check native W."""
    if not isinstance(evidence,dict) or evidence.get('schema')!='native-boundaries-v1' or evidence.get('complete') is not True or evidence.get('status')!='validated':
        _fail('Complete validated native boundary evidence is required before preview.')
    roles=evidence.get('roles',{});chains={};maps={}
    for role,records in roles.items():
        chains[role]=[(r,r.get('reverse')) for r in records]
        if role.startswith('side') and len(records)==1:maps[role]=records[0].get('parameter_map')
    checked=build_source_boundaries(chains,tolerance,curve_factory,surface_factory,maps,cancelled)
    if checked['source_edge_count']!=evidence.get('source_edge_count'):_fail('Native source coverage count changed.')
    for role,records in checked['roles'].items():
        for expected,actual in zip(records,roles[role]):
            for field in ('original_curve_domain','active_domain','traversal_domain'):
                _close(actual.get(field),expected[field],1e-12,'Original native domain or traversal was changed.')
            for field in ('reference_stations','reference_corners'):
                if len(actual.get(field,[]))!=len(expected[field]):_fail('Missing full native parent references.')
                for a,b in zip(actual[field],expected[field]):
                    for name in ('point','uv','edge_parameter','edge_arc_fraction'):
                        _close(a.get(name),b[name],1e-10,'Native reference location or station was changed.')
                    if field=='reference_corners' and a.get('edge_end')!=b['edge_end']:_fail('Native reference corner identity was changed.')
                    _close(a.get('parent_normal'),b['parent_normal'],1e-8,'Native reference normal was changed.')
                    _close(a.get('shape_operator'),b['shape_operator'],1e-10*max(1.,np.linalg.norm(b['shape_operator'])),
                           'Full native shape operator was replaced or changed.')
    return True


def build_source_boundaries(*args,**kwargs):
    try:return _build_source_boundaries(*args,**kwargs)
    except BoundaryEvidenceError:raise
    except (KeyError,TypeError,ValueError,OverflowError):
        _fail('Malformed native provenance cannot be validated.')


def require_complete_evidence(*args,**kwargs):
    try:return _require_complete_evidence(*args,**kwargs)
    except BoundaryEvidenceError:raise
    except (KeyError,TypeError,ValueError,OverflowError):
        _fail('Malformed native provenance cannot enter preview.')
