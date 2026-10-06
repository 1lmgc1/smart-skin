"""Rhino UI-thread boundary capture for the bounded experimental field builder.

No source geometry or attributes are ever modified. All source data stays in
memory; logs deliberately contain counts, codes and scalar metrics only.
"""
import hashlib
import json
try:
    from _smartskin_p08e1_native_family import build_spec, UnsupportedFamily
except ModuleNotFoundError:
    from native_family import build_spec, UnsupportedFamily  # Headless test import.


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
            p=c.Points[i];w=float(p.Weight);q=p.Location
            cp.append([q.X*w,q.Y*w,q.Z*w,w])
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
                p=s.Points.GetControlPoint(i,j);w=float(p.Weight);q=p.Location
                row.append([q.X*w,q.Y*w,q.Z*w,w])
            cp.append(row)
        ku=[float(s.KnotsU[i]) for i in range(s.KnotsU.Count)]
        kv=[float(s.KnotsV[i]) for i in range(s.KnotsV.Count)]
        return dict(degree_u=int(s.Degree(0)),degree_v=int(s.Degree(1)),knots_u=[ku[0]]+ku+[ku[-1]],knots_v=[kv[0]]+kv+[kv[-1]],homogeneous_cp=cp)
    finally:s.Dispose()


def _source_hash(obj,serialization):
    # SHA snapshots are never transmitted or written to disk.
    geometry=obj.Geometry.ToJSON(serialization)
    attributes=obj.Attributes.ToJSON(serialization)
    return (hashlib.sha256(geometry.encode('utf-8')).hexdigest(),hashlib.sha256(attributes.encode('utf-8')).hexdigest())


class Capture:
    def __init__(self,doc,model,proof,serialization,references):
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
        proof={};records=[];source_bytes=0
        tolerance=float(doc.ModelAbsoluteTolerance)
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
            plane=None
            plane_result=face.TryGetPlane(tolerance)
            if plane_result[0]:
                native_plane=plane_result[1]
                plane=dict(origin=_xyz(native_plane.Origin),normal=_xyz(native_plane.Normal))
            uv_samples=[]
            for j in range(17):
                t=edge.Domain.ParameterAt(j/16.)
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
                uv_samples.append(dict(point=_xyz(point),uv=[u,v]))
            records.append(dict(key=str(owner.Id)+':'+str(edge.EdgeIndex),curve=_curve_record(edge),surface=_surface_record(face),plane=plane,uv_samples=uv_samples))
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
