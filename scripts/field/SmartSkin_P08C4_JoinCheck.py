# -*- coding: utf-8 -*-
"""Rhino 8 / RunPythonScript. P08C.4 native seam check on selected prepared cap.
IronPython 2.7 / CPython syntax. No NumPy, no .NET changes, no document writes.
Works on the supplied P08C4 .3dm result, NOT a developer test module.
One save dialog, no save-retry loop. Native geometry remains copy-only.
"""
from __future__ import print_function
import os
import json
import time
import hashlib
import traceback

PATCH='P08C.4'
try:
    TEXT=unicode
except NameError:
    TEXT=str


def text(x):
    if isinstance(x,TEXT):return x
    if isinstance(x,bytes):return x.decode('utf-8','replace')
    return TEXT(x)


class Report(object):
    def __init__(self,path,console):
        self.path=path;self.console=console;self.lines=[];self.handle=None;self.failed=None
        try:
            self.handle=open(path,'wb')
            self.handle.write(b'\xef\xbb\xbf');self.handle.flush()
        except BaseException:
            if self.handle is not None:self.handle.close()
            raise
    def emit(self,event,**fields):
        row=u'SMARTSKIN_P08C4_'+event+u' | '+u' | '.join(text(k)+u'='+text(fields[k]).replace(u'\n',u' ').replace(u'\r',u' ') for k in sorted(fields))
        raw=(row+u'\r\n').encode('utf-8');self.lines.append(raw)
        if self.failed is None:
            try:self.handle.write(raw);self.handle.flush()
            except Exception as exc:self.failed=text(exc)
        if event in ('BEGIN','JOIN','SEGMENT','COMPLETE','STOP','SAFETY'):
            try:self.console('SMARTSKIN_P08C4_'+event+' | details in TXT')
            except Exception:pass
    def finish(self):
        try:
            checksum=hashlib.sha256(b''.join(self.lines)).hexdigest()
            self.emit('INTEGRITY',preceding_records=len(self.lines),preceding_sha256=checksum)
        except Exception as exc:self.failed=self.failed or text(exc)
        finally:
            if self.handle is not None:
                try:self.handle.close()
                except Exception as exc:self.failed=self.failed or text(exc)
        if self.failed is None:
            try:
                with open(self.path,'rb') as check:actual=check.read()
                if actual!=b'\xef\xbb\xbf'+b''.join(self.lines):self.failed='READBACK_MISMATCH'
            except Exception as exc:self.failed=text(exc)
        if self.failed:self.console('SMARTSKIN_P08C4_REPORT_STOP | '+text(self.failed))
        else:self.console('SMARTSKIN_P08C4_SAVED | '+text(self.path))


def count_objects(doc,R):
    s=R.DocObjects.ObjectEnumeratorSettings()
    s.ActiveObjects=True;s.DeletedObjects=False;s.NormalObjects=True
    s.LockedObjects=True;s.HiddenObjects=True;s.ReferenceObjects=True;s.IdefObjects=False
    return sum(1 for unused in doc.Objects.GetObjectList(s))


def native_gap(R,a,b,tol):
    # Check each returned direction; failure is unavailable, never zero.
    values=[]
    for x,y in ((a,b),(b,a)):
        result=R.Geometry.Curve.GetDistancesBetweenCurves(x,y,max(tol*.1,1e-9))
        if not result[0]:raise ValueError('NATIVE_DISTANCE_UNAVAILABLE')
        gap=float(result[1])
        if gap<0 or not R.RhinoMath.IsValidDouble(gap):raise ValueError('INVALID_NATIVE_DISTANCE')
        values.append(gap)
    return max(values)


def main():
    import Rhino as R
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    import System
    doc=R.RhinoDoc.ActiveDoc
    path=rs.SaveFileName(u'Smart Skin P08C.4 — сохранить проверку Join','Text files (*.txt)|*.txt||',None,
                         'SmartSkin_P08C4_'+time.strftime('%Y%m%d_%H%M%S')+'.txt','txt')
    if not path:return
    path=text(path)
    if not path.lower().endswith('.txt'):path+=u'.txt'
    if os.path.exists(path):
        answer=rs.MessageBox(u'Заменить существующий TXT?\n'+path,4|32|256,'Smart Skin P08C.4')
        if answer!=6:return
    report=None;owned=[];sources=[];go=None;start_count=None;state='STOPPED'
    started=time.time()
    def own(g):
        if g is not None:owned.append(g)
        return g
    def checkpoint():
        if sc.escape_test(False):raise ValueError('CANCELLED')
        if time.time()-started>90:raise ValueError('NATIVE_CHECK_BUDGET')
        if report.failed:raise ValueError('REPORT_WRITE_FAILED')
    try:
        report=Report(path,R.RhinoApp.WriteLine)
        report.emit('BEGIN',patch=PATCH,rhino=R.RhinoApp.Version,mode='READ_ONLY;NO_ADD;NO_SOURCE_REPLACE',
                    native_join='PENDING',tol=doc.ModelAbsoluteTolerance)
        go=R.Input.Custom.GetObject();go.SetCommandPrompt('P08C.4: select the new P08C4 cap (not the grey baseline); Enter is not Accept')
        go.GeometryFilter=R.DocObjects.ObjectType.Surface|R.DocObjects.ObjectType.Brep
        go.SubObjectSelect=False;go.EnablePreSelect(False,True);go.Get()
        if go.CommandResult()!=R.Commands.Result.Success:raise ValueError('SELECTION_CANCELLED')
        started=time.time()
        ref=go.Object(0);obj=ref.Object();raw=obj.Attributes.GetUserString('SmartSkin.P08C4.Contract')
        if not raw or len(raw)>32768:raise ValueError('SELECT_THE_P08C4_RESULT_IN_THE_SUPPLIED_MODEL')
        contract=json.loads(raw)
        if contract.get('schema')!=1 or contract.get('patch')!=PATCH:raise ValueError('UNSUPPORTED_PATCH_CONTRACT')
        records=contract.get('source_edges',[])
        if len(records)!=6 or len(set((r['object_id'],int(r['edge'])) for r in records))!=6:
            raise ValueError('SIX_UNIQUE_SOURCE_SEGMENTS_REQUIRED')
        tolerance=float(doc.ModelAbsoluteTolerance)
        if doc.ModelUnitSystem!=R.UnitSystem.Millimeters:raise ValueError('MODEL_UNITS_MUST_BE_MILLIMETERS')
        if not R.RhinoMath.IsValidDouble(tolerance) or tolerance<=0 or tolerance>float(contract['maximum_doc_tolerance'])+1e-12:
            raise ValueError('DOCUMENT_TOLERANCE_DIFFERS_FROM_TEST_CONTRACT')
        cap=own(ref.Brep().DuplicateBrep())
        if cap is None or not cap.IsValid or cap.Faces.Count!=1:raise ValueError('ONE_VALID_PREPARED_CAP_REQUIRED')
        start_count=count_objects(doc,R);parent_map={};target_records=[]
        for rec in records:
            checkpoint();guid=System.Guid(rec['object_id']);parent=doc.Objects.FindId(guid)
            if parent is None:raise ValueError('SOURCE_OBJECT_MISSING_OPEN_THE_SUPPLIED_MODEL_WITHOUT_EXPLODE')
            owner=parent.Geometry
            if not isinstance(owner,R.Geometry.Brep):raise ValueError('SOURCE_IS_NOT_BREP')
            key=text(guid)
            if key not in parent_map:
                copy=own(owner.DuplicateBrep());parent_map[key]=copy;sources.append((guid,copy))
            copy=parent_map[key];idx=int(rec['edge']);fi=int(rec['face'])
            if idx<0 or idx>=copy.Edges.Count or fi<0 or fi>=copy.Faces.Count:raise ValueError('SOURCE_INDEX_CHANGED')
            edge=copy.Edges[idx]
            if edge.Valence!=R.Geometry.EdgeAdjacency.Naked or edge.TrimCount!=1:raise ValueError('SOURCE_EDGE_NOT_NAKED')
            if copy.Trims[edge.TrimIndices()[0]].Face.FaceIndex!=fi:raise ValueError('SOURCE_FACE_CHANGED')
            target_records.append((rec,edge,copy.Faces[fi]))
        report.emit('INPUT',segments=6,parents=len(sources),cap_edge_relief=contract['cap_edge_relief'],
                    relief_coefficient_bound=contract['boundary_bound_mm'],source_edit=False,
                    shape_status='RESEARCH;NO_PRODUCT_ACCEPTANCE')
        checkpoint()
        inp=System.Collections.Generic.List[R.Geometry.Brep]();inp.Add(cap)
        for copy in parent_map.values():inp.Add(copy)
        result=R.Geometry.Brep.JoinBreps(inp,tolerance,doc.ModelAngleToleranceRadians)
        if result is not None:
            for b in result:own(b)
        if result is None or len(result)!=1:raise ValueError('NATIVE_JOIN_DID_NOT_RETURN_ONE_CONNECTED_BREP')
        joined=result[0]
        if not joined.IsValid or not joined.IsManifold:raise ValueError('JOINED_BREP_INVALID_OR_NONMANIFOLD')
        cap_surface=own(cap.Faces[0].DuplicateSurface());cap_faces=[]
        for face in joined.Faces:
            surface=own(face.DuplicateSurface())
            if R.Geometry.GeometryBase.GeometryEquals(surface,cap_surface):cap_faces.append(face.FaceIndex)
        if len(cap_faces)!=1:raise ValueError('CANNOT_IDENTIFY_JOINED_CAP_FACE')
        cfi=cap_faces[0];seams=[]
        for edge in joined.Edges:
            adj=list(edge.AdjacentFaces())
            if cfi not in adj:continue
            if edge.Valence!=R.Geometry.EdgeAdjacency.Interior or len(adj)!=2 or edge.TrimCount!=2:
                raise ValueError('FREE_OR_NONMANIFOLD_EDGE_REMAINS_ON_CAP')
            seams.append((edge,[f for f in adj if f!=cfi][0]))
        used=set()
        for index,(rec,target,face) in enumerate(target_records):
            checkpoint();expected=own(face.DuplicateSurface());pieces=[]
            for seam,other in seams:
                if seam.EdgeIndex in used:continue
                other_surface=own(joined.Faces[other].DuplicateSurface())
                if R.Geometry.GeometryBase.GeometryEquals(other_surface,expected):
                    on_target=True
                    for fraction in (.1,.5,.9):
                        point=seam.PointAt(seam.Domain.ParameterAt(fraction))
                        ok,parameter=target.ClosestPoint(point)
                        if not ok or point.DistanceTo(target.PointAt(parameter))>tolerance:on_target=False;break
                    if on_target:pieces.append(seam)
            if not pieces:raise ValueError('NO_CAP_TO_EXPECTED_PARENT_SEAM_FOR_SEGMENT_'+str(index))
            curves=System.Collections.Generic.List[R.Geometry.Curve]()
            for seam in pieces:curves.Add(own(seam.DuplicateCurve()))
            chains=R.Geometry.Curve.JoinCurves(curves,tolerance)
            if chains is not None:
                for c in chains:own(c)
            if chains is None or len(chains)!=1:raise ValueError('SEGMENT_SEAM_IS_NOT_ONE_CHAIN')
            gap=native_gap(R,chains[0],target,tolerance)
            if gap>tolerance:raise ValueError('SEGMENT_POSITION_OUT_OF_TOLERANCE_'+str(index))
            for seam in pieces:used.add(seam.EdgeIndex)
            report.emit('SEGMENT',index=index,source_edge=rec['edge'],source_face=rec['face'],
                        seam_edges=','.join(str(e.EdgeIndex) for e in pieces),maximum_gap=gap,
                        result='COVERED_BY_INTERIOR_SEAM')
        if len(used)!=len(seams):raise ValueError('UNACCOUNTED_CAP_SEAM')
        report.emit('JOIN',result='ALL_SIX_SEGMENTS_VERIFIED',joined_faces=joined.Faces.Count,
                    cap_interior_seams=len(seams),cap_naked_edges=0,is_solid=joined.IsSolid,
                    note='Other source holes may remain; Solid is not required')
        # Native parent intersection screen: useful evidence, NOT a global certificate.
        cap_boundaries=[e for e in cap.Edges];off_boundary=0;events=0
        for unused,copy in sources:
            checkpoint()
            success,curves,points=R.Geometry.Intersect.Intersection.BrepBrep(cap,copy,tolerance)
            if not success:raise ValueError('PARENT_INTERSECTION_UNAVAILABLE')
            for curve in curves or []:
                own(curve)
                for j in range(65):
                    p=curve.PointAt(curve.Domain.ParameterAt(j/64.0));best=None
                    for edge in cap_boundaries:
                        ok,par=edge.ClosestPoint(p)
                        if ok:
                            gap=p.DistanceTo(edge.PointAt(par));best=gap if best is None else min(best,gap)
                    events+=1
                    if best is None or best>tolerance:off_boundary+=1
            for p in points or []:
                best=None
                for edge in cap_boundaries:
                    ok,par=edge.ClosestPoint(p)
                    if ok:
                        gap=p.DistanceTo(edge.PointAt(par));best=gap if best is None else min(best,gap)
                events+=1
                if best is None or best>tolerance:off_boundary+=1
        report.emit('PARENT_INTERSECTION_SCREEN',samples=events,off_boundary_samples=off_boundary,
                    scope='FINITE_SAMPLES;NOT_GLOBAL_CERTIFICATE',self_intersection='NOT_CERTIFIED')
        state='COMPLETE'
        report.emit('COMPLETE',join='VERIFIED_ALL_SIX_SEGMENTS',parent_screen='REVIEW' if off_boundary else 'NO_OFF_BOUNDARY_SAMPLE_FOUND',
                    added=0,source_replaced=0,geometry_acceptance='NOT_GRANTED_BY_THIS_CHECK')
    except BaseException as exc:
        if report:
            report.emit('STOP',error=text(exc),traceback=traceback.format_exc())
        else:R.RhinoApp.WriteLine('SMARTSKIN_P08C4_REPORT_STOP | '+text(exc))
    finally:
        if report:
            try:
                same=True
                for guid,snapshot in sources:
                    original=doc.Objects.FindId(guid)
                    equal=original is not None and R.Geometry.GeometryBase.GeometryEquals(original.Geometry,snapshot)
                    same=same and equal
                    report.emit('SOURCE_CHECK',object_id=guid,geometry_equal=equal)
                after=count_objects(doc,R)
                report.emit('SAFETY',objects_before=start_count,objects_after=after,
                            count_equal=(after==start_count) if start_count is not None else 'NOT_MEASURED',
                            source_geometry_equal=same if sources else 'NOT_MEASURED',added=0,source_replaced=0)
            except Exception as exc:report.emit('SAFETY',result='CHECK_FAILED',error=text(exc))
        for g in reversed(owned):
            try:g.Dispose()
            except Exception:pass
        if go is not None:go.Dispose()
        if report:
            report.emit('END',state=state,geometry_commit=False);report.finish()

if __name__=='__main__':main()
