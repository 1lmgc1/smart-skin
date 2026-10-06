"""Rhino UI-thread boundary capture for the bounded experimental field builder.

No source geometry or attributes are ever modified. All source data stays in
memory; logs deliberately contain counts, codes and scalar metrics only.
"""
import hashlib
import json
import math
import time
import numpy as np
try:
    from _smartskin_p08e1_native_family import build_spec, UnsupportedFamily, require_native_provenance
except ModuleNotFoundError as error:
    if error.name != '_smartskin_p08e1_native_family':
        raise
    from native_family import build_spec, UnsupportedFamily, require_native_provenance  # Headless test import.


class InputCancelled(Exception):
    pass


def _xyz(point):
    return [float(point.X),float(point.Y),float(point.Z)]


def _curve_record(curve):
    c=curve.ToNurbsCurve()
    if c is None or not c.IsValid:
        raise UnsupportedFamily('INVALID_NATIVE_CURVE','Could not copy native NURBS curve.')
    try:
        if c.Points.Count>512 or c.Degree>7:
            raise UnsupportedFamily("CURVE_COMPLEXITY","Source curve exceeds the bounded native-copy budget.")
        cp=[]
        for i in range(c.Points.Count):
            p=c.Points[i]
            cp.append([float(p.X),float(p.Y),float(p.Z),float(p.Weight)])
        knots=[float(c.Knots[i]) for i in range(c.Knots.Count)]
        return dict(degree=int(c.Degree),knots=[knots[0]]+knots+[knots[-1]],homogeneous_cp=cp,domain=[float(c.Domain.T0),float(c.Domain.T1)])
    finally:c.Dispose()


def _surface_record(face):
    s=face.ToNurbsSurface()
    if s is None or not s.IsValid:
        raise UnsupportedFamily('INVALID_NATIVE_SURFACE','Could not copy owning native surface.')
    try:
        if s.Points.CountU>512 or s.Points.CountV>128 or s.Degree(0)>5 or s.Degree(1)>7:
            raise UnsupportedFamily("SURFACE_COMPLEXITY","Owning native surface exceeds the bounded copy budget.")
        cp=[]
        for i in range(s.Points.CountU):
            row=[]
            for j in range(s.Points.CountV):
                p=s.Points.GetControlPoint(i,j)
                row.append([float(p.X),float(p.Y),float(p.Z),float(p.Weight)])
            cp.append(row)
        ku=[float(s.KnotsU[i]) for i in range(s.KnotsU.Count)]
        kv=[float(s.KnotsV[i]) for i in range(s.KnotsV.Count)]
        return dict(degree_u=int(s.Degree(0)),degree_v=int(s.Degree(1)),knots_u=[ku[0]]+ku+[ku[-1]],knots_v=[kv[0]]+kv+[kv[-1]],homogeneous_cp=cp)
    finally:s.Dispose()


# Native-side contract v1. Every vector is in document/world coordinates. The
# co-normal points into the *trimmed owning face*, not its rectangular surface.
# Public API references (all available in Rhino 8):
# https://developer.rhino3d.com/api/rhinocommon/rhino.geometry.brepface/ispointonface
# https://developer.rhino3d.com/api/rhinocommon/rhino.geometry.breptrim/isreversed
# https://mcneel.github.io/rhinocommon-api-docs/api/RhinoCommon/html/M_Rhino_Geometry_Surface_Evaluate.htm
# IsPointOnFace's tolerance is a 3D tolerance; Evaluate(1) returns {Su,Sv}.
# This is sampled local sidedness evidence, not a whole-surface overlap proof.
class _SideBudget:
    def __init__(self, cancelled=None, max_calls=12000, seconds=12.):
        self.cancelled=cancelled
        self.remaining=max_calls
        self.deadline=time.monotonic()+seconds

    def check(self):
        if self.cancelled and self.cancelled():raise InputCancelled()
        self.remaining-=1
        if self.remaining<0 or time.monotonic()>self.deadline:
            raise UnsupportedFamily('OWNER_SIDE_BUDGET','Native trim-sidedness capture exceeded its bounded work budget.')


def _side_fail(detail):
    raise UnsupportedFamily('AMBIGUOUS_OWNER_SIDE',detail)


def _unit_side(vector):
    v=np.asarray(vector,dtype=float);length=float(np.linalg.norm(v))
    if not np.all(np.isfinite(v)) or length<=0.:
        _side_fail('A native trim or surface tangent is singular.')
    return v/length


def _relation(face,uv,tolerance,budget):
    budget.check()
    value=str(face.IsPointOnFace(float(uv[0]),float(uv[1]),float(tolerance)))
    if value not in ('Interior','Exterior','Boundary'):
        _side_fail('Native face membership returned an unsupported relation.')
    return value


def _frame(face,uv,budget):
    budget.check()
    result=face.Evaluate(float(uv[0]),float(uv[1]),1)
    if not result[0] or result[2] is None or len(result[2])<2:
        _side_fail('The owning surface could not evaluate its first derivatives.')
    p=np.asarray(_xyz(result[1]));su=np.asarray(_xyz(result[2][0]));sv=np.asarray(_xyz(result[2][1]))
    if not np.all(np.isfinite(np.r_[p,su,sv])):
        _side_fail('The owning surface returned nonfinite geometry.')
    # Normalize the Jacobian columns before conditioning checks. UV units are
    # arbitrary and changing the UV scale must not change world-space sign.
    lu=float(np.linalg.norm(su));lv=float(np.linalg.norm(sv))
    if min(lu,lv)<=0.:_side_fail('The owning surface has a singular local metric.')
    scaled=np.column_stack([su/lu,sv/lv]);gram=scaled.T@scaled
    if np.linalg.det(gram)<1e-12:_side_fail('The owning surface has a singular local metric.')
    inverse=np.diag([1./lu,1./lv])@np.linalg.solve(gram,scaled.T)
    normal=_unit_side(np.cross(scaled[:,0],scaled[:,1]))
    if face.OrientationIsReversed:normal=-normal
    return p,np.column_stack([su,sv]),inverse,normal


def _probe(face,uv,frame,direction,distance,tolerance,budget):
    """Map a physical tangent displacement through this face's local metric.

    PointAt outside a surface domain is not reliable. Such UVs may establish
    Exterior only, from IsPointOnFace, and are never evaluated or wrapped. An
    in-domain UV is still classified against actual trims; it is not assumed
    to be inside the face. Periodic/closed owners are rejected by the caller.
    """
    p,jac,inverse,normal=frame
    direction=_unit_side(direction)
    target=np.asarray(uv)+inverse@direction*distance
    if not np.all(np.isfinite(target)):_side_fail('Nonfinite physical-to-UV probe.')
    relation=_relation(face,target,tolerance,budget)
    in_domain=all(float(face.Domain(k).T0)<=target[k]<=float(face.Domain(k).T1) for k in (0,1))
    if not in_domain:
        if relation!='Exterior':return None
        return dict(direction=direction.tolist(),relation=relation,distance=float(distance),
                    uv=target.tolist(),mapping='native_domain_exterior')
    budget.check()
    q=np.asarray(_xyz(face.PointAt(float(target[0]),float(target[1]))));delta=q-p
    if not np.all(np.isfinite(q)) or np.linalg.norm(delta-distance*direction)>max(tolerance*.25,distance*.025):
        return None
    return dict(direction=direction.tolist(),relation=relation,distance=float(distance),
                uv=target.tolist(),point=q.tolist(),mapping='physical_surface_probe')


def _radii(maximum,tolerance):
    # At most nine attempts, each with two independently classified radii.
    return [maximum*.5**i for i in range(9) if maximum*.5**(i+1)>=16.*tolerance]


def _smooth_side(face,uv,frame,tangent,maximum,tolerance,budget):
    conormal=_unit_side(np.cross(frame[3],tangent))
    for radius in _radii(maximum,tolerance):
        pairs=[]
        for distance in (radius,radius*.5):
            pairs.append([_probe(face,uv,frame,sign*conormal,distance,tolerance,budget) for sign in (1.,-1.)])
        if any(p is None for pair in pairs for p in pair):continue
        relations=[[p['relation'] for p in pair] for pair in pairs]
        if any(set(r)!=set(('Interior','Exterior')) for r in relations):continue
        if relations[0]!=relations[1]:_side_fail('Native trim side changes across nested physical probes.')
        inside=0 if relations[0][0]=='Interior' else 1
        inward=conormal if inside==0 else -conormal
        return dict(inward_conormal=inward.tolist(),outward_conormal=(-inward).tolist(),
                    probe_distance=float(radius),inside_uv=pairs[0][inside]['uv'],
                    outside_uv=pairs[0][1-inside]['uv'],probes=[p for pair in pairs for p in pair])
    _side_fail('The selected trim has no unambiguous local inside/outside physical probe pair.')


def _trim_ray(trim,at_start,jac,budget):
    budget.check()
    tangent=trim.TangentAt(float(trim.Domain.T0 if at_start else trim.Domain.T1))
    direction=jac@np.asarray([float(tangent.X),float(tangent.Y)])
    return _unit_side(direction if at_start else -direction)


def _corner_side(edge,trim,face,edge_end,maximum,tolerance,mapping_tolerance,budget):
    loop=trim.Loop
    if loop is None or loop.Trims.Count<2 or loop.Trims.Count>256:
        _side_fail('An endpoint requires a bounded owning trim loop with an adjacent trim.')
    matches=[i for i in range(loop.Trims.Count) if int(loop.Trims[i].TrimIndex)==int(trim.TrimIndex)]
    if len(matches)!=1:_side_fail('The selected trim is not unique in its owning loop.')
    # IsReversed() relates the trim direction to the 3D edge direction. The
    # adjacent trim is chosen topologically, never by nearest unrelated edge.
    at_start=(edge_end==0)!=bool(trim.IsReversed())
    adjacent=loop.Trims[(matches[0]+(-1 if at_start else 1))%loop.Trims.Count]
    if adjacent.Face is None or int(adjacent.Face.FaceIndex)!=int(face.FaceIndex) or adjacent.Edge is None:
        _side_fail('The adjacent corner trim has no regular edge on this owning face.')
    budget.check()
    adjacent_length=float(adjacent.Edge.GetLength())
    if not math.isfinite(adjacent_length) or adjacent_length<=0.:_side_fail('The adjacent corner edge is degenerate.')
    tolerance=max(min(tolerance,adjacent_length*1e-5),1e-12)
    trim_uv=trim.PointAt(float(trim.Domain.T0 if at_start else trim.Domain.T1))
    adjacent_uv=adjacent.PointAt(float(adjacent.Domain.T1 if at_start else adjacent.Domain.T0))
    uv=np.asarray([float(trim_uv.X),float(trim_uv.Y)]);auv=np.asarray([float(adjacent_uv.X),float(adjacent_uv.Y)])
    frame=_frame(face,uv,budget);p=frame[0]
    budget.check()
    if np.linalg.norm(np.asarray(_xyz(face.PointAt(float(auv[0]),float(auv[1]))))-p)>mapping_tolerance:
        _side_fail('The actual adjacent trim does not meet the selected edge corner.')
    # A coincident world point on another UV branch is not a valid adjacency.
    if np.linalg.norm(frame[1]@(auv-uv))>mapping_tolerance:
        _side_fail('The adjacent trim corner belongs to an ambiguous UV branch.')
    budget.check()
    edgepoint=np.asarray(_xyz(edge.PointAt(float(edge.Domain.T0 if edge_end==0 else edge.Domain.T1))))
    if np.linalg.norm(edgepoint-p)>mapping_tolerance:_side_fail('Trim orientation does not reproduce the selected edge endpoint.')
    if _relation(face,uv,tolerance,budget)!='Boundary':_side_fail('The native corner is not on the owning trim boundary.')
    ray=_trim_ray(trim,at_start,frame[1],budget)
    adjacent_ray=_trim_ray(adjacent,not at_start,frame[1],budget)
    normal=frame[3];cross_ray=_unit_side(np.cross(normal,ray))
    angle=math.atan2(float(adjacent_ray@cross_ray),float(adjacent_ray@ray))%(2.*math.pi)
    if min(angle,2.*math.pi-angle)<1e-5:_side_fail('The actual corner rays are coincident or unresolved.')
    maximum=min(maximum,adjacent_length*.01)
    directions=[(math.cos(a)*ray+math.sin(a)*cross_ray) for lo,hi in ((0.,angle),(angle,2.*math.pi)) for a in (lo+(hi-lo)*.25,lo+(hi-lo)*.5,lo+(hi-lo)*.75)]
    for radius in _radii(maximum,tolerance):
        probes=[_probe(face,uv,frame,d,r,tolerance,budget) for r in (radius,radius*.5) for d in directions]
        if any(p is None for p in probes):continue
        relations=[p['relation'] for p in probes]
        first,second=relations[0],relations[3]
        if set((first,second))!=set(('Interior','Exterior')):continue
        if relations!=[first]*3+[second]*3+[first]*3+[second]*3:continue
        first_inside=first=='Interior'
        inward=cross_ray if first_inside else -cross_ray
        adjacent_inward=-np.cross(normal,adjacent_ray) if first_inside else np.cross(normal,adjacent_ray)
        start=adjacent_ray if first_inside else ray
        sweep=2.*math.pi-angle if first_inside else angle
        return dict(edge_end=int(edge_end),trim_at_start=bool(at_start),point=p.tolist(),uv=uv.tolist(),trim_ray=ray.tolist(),
                    classification_tolerance=float(tolerance),edge_inward_cross_sign=float((1. if first_inside else -1.)*(1. if edge_end==0 else -1.)),
                    adjacent_trim_index=int(adjacent.TrimIndex),adjacent_ray=adjacent_ray.tolist(),
                    oriented_normal=normal.tolist(),inward_conormal=inward.tolist(),
                    outward_conormal=(-inward).tolist(),adjacent_inward_conormal=_unit_side(adjacent_inward).tolist(),
                    exterior_wedge=dict(start_ray=start.tolist(),sweep_radians=float(sweep),oriented_normal=normal.tolist()),
                    probe_distance=float(radius),probes=probes)
    _side_fail('The actual adjacent trim rays do not define an unambiguous local exterior wedge.')


def _edge_probe_parameters(edge,budget):
    # Physical arc-length stations avoid crowding probes into a corner when
    # native rational weights or parameter domains are strongly nonuniform.
    # RhinoCommon Curve.NormalizedLengthParameter(s,out t), available since 5.0.
    lo,hi=float(edge.Domain.T0),float(edge.Domain.T1)
    previous=None
    for j in range(17):
        budget.check()
        fraction=j/16.
        if j in (0,16):parameter=lo if j==0 else hi
        else:
            mapped=edge.NormalizedLengthParameter(float(fraction))
            if not mapped[0]:_side_fail('Native edge arc-length station could not be located.')
            parameter=float(mapped[1])
        if not math.isfinite(parameter) or not lo<=parameter<=hi or (previous is not None and parameter<=previous):
            _side_fail('Native edge arc-length stations are not finite and strictly ordered.')
        previous=parameter
        yield parameter,fraction


def _capture_owner_side(edge,trim,face,tolerance,mapped_samples,budget):
    """Read-only native witnesses. Mocks test the algorithm, not Rhino binding."""
    if any(face.IsClosed(k) or face.IsPeriodic(k) for k in (0,1)):
        _side_fail('Closed or periodic owning surfaces require unsupported seam-aware side capture.')
    budget.check()
    length=float(edge.GetLength())
    if not math.isfinite(length) or length<=0.:_side_fail('The selected native edge is degenerate.')
    # Membership needs finer resolution than the geometric acceptance gate on
    # short native trims. This only measures topology and never relaxes G0/G1/G2.
    mapping_tolerance=max(float(tolerance)*.05,1e-9)
    measure=max(min(float(tolerance)*.05,length*1e-5),length*1e-12,1e-12)
    ends=[np.asarray(mapped_samples[i]['point']) for i in (0,-1)]
    samples=[]
    for sample in mapped_samples[1:-1]:
        budget.check()
        uv=np.asarray(sample['uv']);frame=_frame(face,uv,budget)
        if _relation(face,uv,measure,budget)!='Boundary':_side_fail('A mapped source point is not on its actual trim boundary.')
        if np.linalg.norm(frame[0]-np.asarray(sample['point']))>mapping_tolerance:
            _side_fail('The owning trim does not reproduce its selected edge point.')
        tangent=_unit_side(_xyz(edge.TangentAt(sample['edge_parameter'])))
        trim_tangent=trim.TangentAt(sample['trim_parameter'])
        mapped_tangent=_unit_side(frame[1]@np.asarray([trim_tangent.X,trim_tangent.Y]))
        expected=-tangent if trim.IsReversed() else tangent
        if float(mapped_tangent@expected)<.99999 or abs(float(tangent@frame[3]))>1e-5:
            _side_fail('The actual trim and selected edge tangents do not define the same local branch.')
        distance=min(float(np.linalg.norm(frame[0]-p)) for p in ends)
        maximum=min(length*.01,distance*.2)
        side=_smooth_side(face,uv,frame,tangent,maximum,measure,budget)
        side.update(edge_parameter=float(sample['edge_parameter']),edge_fraction=float(sample['edge_fraction']),
                    edge_arc_fraction=float(sample['edge_arc_fraction']),
                    point=frame[0].tolist(),uv=uv.tolist(),tangent=tangent.tolist(),oriented_normal=frame[3].tolist(),
                    edge_inward_cross_sign=float(np.sign(np.dot(side['inward_conormal'],np.cross(frame[3],tangent)))))
        samples.append(side)
    if len(samples)<3:_side_fail('Insufficient native interior witnesses.')
    corners=[_corner_side(edge,trim,face,end,length*.01,measure,mapping_tolerance,budget) for end in (0,1)]
    signs={s['edge_inward_cross_sign'] for s in samples+corners}
    if len(signs)!=1:_side_fail('Corner and smooth native trim witnesses disagree on the owning side.')
    return dict(schema='native-trim-side-v1',face_index=int(face.FaceIndex),trim_index=int(trim.TrimIndex),
                loop_index=int(trim.Loop.LoopIndex),face_orientation_reversed=bool(face.OrientationIsReversed),
                trim_reversed=bool(trim.IsReversed()),edge_inward_cross_sign=float(samples[0]['edge_inward_cross_sign']),
                classification_tolerance=float(measure),samples=samples,corners=corners)


def _source_hash(obj,serialization):
    # SHA snapshots are never transmitted or written to disk.
    geometry=obj.Geometry.ToJSON(serialization)
    attributes=obj.Attributes.ToJSON(serialization)
    return (hashlib.sha256(geometry.encode('utf-8')).hexdigest(),hashlib.sha256(attributes.encode('utf-8')).hexdigest())


class Capture:
    def __init__(self,doc,model,proof,serialization,references):
        require_native_provenance(model)
        self.model=model
        self.source_proof=proof
        self.document_serial=int(doc.RuntimeSerialNumber)
        self._serialization=serialization
        self._references=references
        self._disposed=False

    def verify_sources(self,doc):
        if self._disposed:
            return False,'Capture has already been disposed.'
        if int(doc.RuntimeSerialNumber)!=self.document_serial:
            return False,'The active document changed during preview.'
        for object_id,serial,digests in self.source_proof:
            obj=doc.Objects.FindId(object_id)
            if obj is None or obj.IsDeleted or int(obj.RuntimeSerialNumber)!=serial:
                return False,'A selected source owner was deleted or replaced during preview.'
            if _source_hash(obj,self._serialization)!=digests:
                return False,'Selected source geometry or attributes changed during preview.'
        return True,'All selected source geometry and attributes are unchanged.'

    def dispose(self):
        if self._disposed:return
        self._disposed=True
        for reference in self._references:
            reference.Dispose()
        self._references=[]


def capture(doc,cancelled=None):
    import Rhino
    from Rhino.Geometry import EdgeAdjacency, Point3d
    from Rhino.Input.Custom import GetObject
    from Rhino.Commands import Result
    from Rhino.DocObjects import ObjectType,ObjRef
    selection=GetObject()
    references=[]
    try:
        selection.SetCommandPrompt('Smart Skin experimental: select the complete native naked-edge loop; Enter when done')
        selection.GeometryFilter=ObjectType.Curve
        selection.SubObjectSelect=True
        selection.GroupSelect=False
        selection.EnablePreSelect(True,True)
        selection.GetMultiple(4,16)
        if selection.CommandResult()!=Result.Success:raise InputCancelled()
        serialization=Rhino.FileIO.SerializationOptions()
        serialization.WriteUserData=True
        serialization.WriteRenderMeshes=False
        serialization.WriteAnalysisMeshes=False
        proof={};records=[];source_bytes=0
        tolerance=float(doc.ModelAbsoluteTolerance)
        side_budget=_SideBudget(cancelled)
        for i in range(selection.ObjectCount):
            if cancelled and cancelled():raise InputCancelled()
            ref=selection.Object(i)
            edge=ref.Edge()
            if edge is None or edge.Valence!=EdgeAdjacency.Naked:
                raise UnsupportedFamily('NAKED_BREP_EDGES_REQUIRED','Select Brep edge subobjects, not standalone duplicate curves or entire surfaces.')
            trims=list(edge.TrimIndices())
            if len(trims)!=1:
                raise UnsupportedFamily('AMBIGUOUS_EDGE_OWNER','Each edge must have exactly one native trim and owning face.')
            owner=ref.Object();brep=ref.Brep();trim=brep.Trims[trims[0]];face=trim.Face
            if owner is None or face is None:
                raise UnsupportedFamily('MISSING_NATIVE_OWNER','A selected edge lost its native owning face.')
            if brep.Faces.Count>64 or brep.Edges.Count>256:
                raise UnsupportedFamily('OWNER_COMPLEXITY','Selected owner exceeds the bounded face/edge budget.')
            if owner.Id not in proof:
                estimate=int(owner.MemoryEstimate())
                source_bytes+=estimate
                if estimate>32*1024*1024 or source_bytes>64*1024*1024:
                    raise UnsupportedFamily("SOURCE_MEMORY_BUDGET","Selected owners exceed the bounded64MiB source snapshot budget.")
                proof[owner.Id]=(owner.Id,int(owner.RuntimeSerialNumber),_source_hash(owner,serialization))
            # Independent ObjRef remains alive after the GetObject instance is disposed.
            references.append(ObjRef(ref))
            # Reject unsupported degrees/control counts before native length,
            # mapping, or trim-domain probe work. Both copies are read-only.
            curve_record=_curve_record(edge)
            surface_record=_surface_record(face)
            plane=None
            plane_result=face.TryGetPlane(tolerance)
            if plane_result[0]:
                native_plane=plane_result[1]
                plane=dict(origin=_xyz(native_plane.Origin),normal=_xyz(native_plane.Normal))
            uv_samples=[]
            for t,arc_fraction in _edge_probe_parameters(edge,side_budget):
                point=edge.PointAt(t)
                mapped=face.ClosestPoint(point)
                if not mapped[0]:
                    raise UnsupportedFamily('SOURCE_FACE_MAPPING','The selected owning face cannot locate its own edge point.')
                u,v=float(mapped[1]),float(mapped[2])
                if face.PointAt(u,v).DistanceTo(point)>max(tolerance*.05,1e-9):
                    raise UnsupportedFamily('SOURCE_FACE_MAPPING','Native source-face mapping exceeds the measurement budget.')
                # ClosestPoint is accepted only on this edge's uniquely owning
                # trim, never an unrelated nearby face or unbounded branch.
                trim_result=trim.ClosestPoint(Point3d(u,v,0.))
                if not trim_result[0]:
                    raise UnsupportedFamily('SOURCE_TRIM_MAPPING','Owning trim parameter could not be located.')
                trim_uv=trim.PointAt(trim_result[1])
                if face.PointAt(trim_uv.X,trim_uv.Y).DistanceTo(point)>max(tolerance*.05,1e-9):
                    raise UnsupportedFamily('SOURCE_TRIM_MAPPING','Mapped point is not on the selected native trim.')
                uv_samples.append(dict(point=_xyz(point),uv=[float(trim_uv.X),float(trim_uv.Y)],
                                       edge_parameter=float(t),edge_fraction=float((t-edge.Domain.T0)/(edge.Domain.T1-edge.Domain.T0)),
                                       edge_arc_fraction=float(arc_fraction),trim_parameter=float(trim_result[1])))
            owner_side=_capture_owner_side(edge,trim,face,tolerance,uv_samples,side_budget)
            records.append(dict(key=str(owner.Id)+':'+str(edge.EdgeIndex),curve=curve_record,surface=surface_record,plane=plane,uv_samples=uv_samples,owner_side=owner_side))
        model=build_spec(records,tolerance,float(doc.ModelAngleToleranceRadians),cancelled)
        captured=Capture(doc,model,list(proof.values()),serialization,references)
        references=[]
        valid,reason=captured.verify_sources(doc)
        if not valid:
            captured.dispose();raise UnsupportedFamily('SOURCE_CHANGED_DURING_CAPTURE',reason)
        Rhino.RhinoApp.WriteLine('SMARTSKIN_P08E1 INPUT | edges='+str(len(records))+' | owners='+str(len(proof))+' | supported_family=mirrored_native_field | sources=UNCHANGED')
        return captured
    finally:
        for ref in references:ref.Dispose()
        selection.Dispose()
