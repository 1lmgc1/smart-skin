# -*- coding: utf-8 -*-
"""P08D1B-FIELD01F1: native checks on copies, never CAD acceptance."""
from __future__ import print_function
import time, traceback, math
from field_core import Report, text, PACKAGE

def check_case(doc, manifest, case, report_folder, snapshots, cancelled=lambda: False, document_available=lambda: True):
    import Rhino as R
    import System
    import scriptcontext as sc
    report = Report(report_folder, R.RhinoApp.WriteLine)
    owned=[]; start=time.time(); state='STOPPED'; joined_ok=False
    initial_count=None; document_serial=doc.RuntimeSerialNumber
    def document_alive():
        return document_available() and R.RhinoDoc.FromRuntimeSerialNumber(document_serial) is not None
    def own(g):
        if g is not None: owned.append(g)
        return g
    def checkpoint():
        R.RhinoApp.Wait()
        if not document_alive(): raise ValueError('FIELD_DOCUMENT_CLOSED')
        if cancelled() or sc.escape_test(False): raise ValueError('CANCELLED')
        if time.time()-start>120: raise ValueError('CHECK_TIME_BUDGET_120_SECONDS')
    def count():
        es=R.DocObjects.ObjectEnumeratorSettings()
        es.ActiveObjects=True; es.DeletedObjects=False; es.NormalObjects=True
        es.HiddenObjects=True; es.LockedObjects=True; es.ReferenceObjects=True
        es.IdefObjects=False
        return sum(1 for unused in doc.Objects.GetObjectList(es))
    def gap(a,b,tol):
        values=[]
        for x,y in ((a,b),(b,a)):
            checkpoint()
            result=R.Geometry.Curve.GetDistancesBetweenCurves(x,y,max(tol*.1,1e-9))
            if not result[0]: raise ValueError('NATIVE_DISTANCE_UNAVAILABLE')
            v=float(result[1])
            if not R.RhinoMath.IsValidDouble(v) or v<0: raise ValueError('INVALID_DISTANCE')
            values.append(v)
        return max(values)
    def close_to(curve,point):
        ok,t=curve.ClosestPoint(point)
        if not ok: raise ValueError('CURVE_CLOSEST_POINT_UNAVAILABLE')
        return point.DistanceTo(curve.PointAt(t)),t
    def same_surface(a,b):
        return R.Geometry.GeometryBase.GeometryEquals(a,b)
    def split_assign(curve,targets,tolerance):
        """Partition at original source junctions before assigning curved pieces."""
        d=curve.Domain; values=[d.T0,d.T1]
        for unused,target,unused_face in targets:
            for point in (target.PointAtStart,target.PointAtEnd):
                dist,t=close_to(curve,point)
                if dist<=tolerance and d.T0<t<d.T1: values.append(t)
        values=sorted(values); cuts=[]; eps=max(abs(d.Length)*1e-10,1e-13)
        for x in values:
            if not cuts or x-cuts[-1]>eps: cuts.append(x)
        result=[]
        for a,b in zip(cuts[:-1],cuts[1:]):
            checkpoint(); piece=own(curve.Trim(a,b))
            if piece is None: raise ValueError('CURVE_PARTITION_FAILED')
            choices=[]
            for index,(_,target,_) in enumerate(targets):
                if all(close_to(target,piece.PointAt(piece.Domain.ParameterAt(f)))[0]<=tolerance for f in (.05,.25,.5,.75,.95)):
                    choices.append(index)
            if len(choices)!=1: raise ValueError('AMBIGUOUS_OR_UNCOVERED_BOUNDARY_PIECE')
            result.append((choices[0],piece))
        return result
    def chain_check(pieces,target,tol):
        if not pieces: raise ValueError('MISSING_SOURCE_SEGMENT')
        curves=System.Collections.Generic.List[R.Geometry.Curve]()
        for p in pieces: curves.Add(p)
        joined=R.Geometry.Curve.JoinCurves(curves,tol)
        for c in joined or []: own(c)
        if joined is None or len(joined)!=1: raise ValueError('SOURCE_COVERAGE_IS_NOT_ONE_CHAIN')
        distance=gap(joined[0],target,tol)
        # Bidirectional native distance checks full target, not only a few witnesses.
        if distance>tol: raise ValueError('SOURCE_CHAIN_OUT_OF_TOLERANCE')
        return distance
    def shape(face,u,v):
        curv=face.CurvatureAt(u,v)
        if curv is None: raise ValueError('CURVATURE_UNAVAILABLE')
        n=face.NormalAt(u,v)
        if not n.Unitize(): raise ValueError('NORMAL_UNAVAILABLE')
        sign=-1. if face.OrientationIsReversed else 1.
        n=n*sign; mat=[0.]*9
        for i in (0,1):
            direction=curv.Direction(i)
            if not direction.Unitize(): raise ValueError('PRINCIPAL_DIRECTION_UNAVAILABLE')
            k=float(curv.Kappa(i))*sign
            if not R.RhinoMath.IsValidDouble(k): raise ValueError('INVALID_CURVATURE')
            vec=[direction.X,direction.Y,direction.Z]
            for row in range(3):
                for col in range(3): mat[3*row+col]+=k*vec[row]*vec[col]
        return n,mat
    def trace_metrics(edge,internal,tol):
        indices=list(edge.TrimIndices())
        if len(indices)!=2: raise ValueError('TWO_TRIMS_REQUIRED')
        trims=[edge.Brep.Trims[i] for i in indices]
        max_gap=[0.,0.]; max_pair=0.; max_angle=0.; max_shape=0.; max_absolute=0.
        # Same 3D edge parameter is mapped independently through each trim.
        fractions=[i/64. for i in range(65)]
        for f in fractions:
            checkpoint(); t=edge.Domain.ParameterAt(f); p=edge.PointAt(t); lifted=[]; jets=[]
            for i,tr in enumerate(trims):
                ok,tp=tr.GetTrimParameter(t)
                if not ok: raise ValueError('TRIM_PARAMETER_UNAVAILABLE')
                uv=tr.PointAt(tp); point=tr.Face.PointAt(uv.X,uv.Y)
                if not point.IsValid: raise ValueError('INVALID_TRIM_IMAGE')
                lifted.append(point); max_gap[i]=max(max_gap[i],point.DistanceTo(p))
                if internal: jets.append(shape(tr.Face,uv.X,uv.Y))
            max_pair=max(max_pair,lifted[0].DistanceTo(lifted[1]))
            if internal:
                n0,k0=jets[0]; n1,k1=jets[1]
                dot=max(-1.,min(1.,n0*n1)); angle=math.degrees(math.acos(dot))
                diff=math.sqrt(sum((a-b)**2 for a,b in zip(k0,k1)))
                scale=max(math.sqrt(sum(x*x for x in k0)),math.sqrt(sum(x*x for x in k1)),1e-8)
                max_angle=max(max_angle,angle); max_shape=max(max_shape,100.*diff/scale); max_absolute=max(max_absolute,diff)
        report.emit('TRIM_IMAGES',edge_index=edge.EdgeIndex,kind='CAP_CAP' if internal else 'CAP_PARENT',
                    face_indices=[tr.Face.FaceIndex for tr in trims],samples=len(fractions),
                    image_to_common_edge_mm=max_gap,image_to_image_mm=max_pair,
                    oriented_normal_deg=max_angle if internal else 'NOT_EVALUATED',
                    shape_operator_percent=max_shape if internal else 'NOT_EVALUATED',
                    shape_operator_absolute=max_absolute if internal else 'NOT_EVALUATED',
                    scope='FINITE_COMMON_EDGE_PARAMETER_SAMPLES;NOT_GLOBAL_CERTIFICATE')
        if max(max_gap)>tol or max_pair>tol: raise ValueError('TRIM_IMAGE_POSITION_OUT_OF_TOLERANCE')
        if internal and (max_angle>math.degrees(doc.ModelAngleToleranceRadians) or (max_shape>5. and max_absolute>1e-7)):
            raise ValueError('INTERNAL_SAMPLED_G2_FAILED')
    try:
        initial_count=count(); tol=float(doc.ModelAbsoluteTolerance)
        report.emit('BEGIN',package=PACKAGE,case=case['id'],candidate_hash=case['candidate_hash'],
                    upstream_form=case['form_status'],mode='COPIES_ONLY;NO_ADD;NO_DELETE;NO_REPLACE',
                    rhino=text(R.RhinoApp.Version),geometry_acceptance=False)
        if doc.ModelUnitSystem!=R.UnitSystem.Millimeters or not 0<tol<=.01+1e-12:
            raise ValueError('UNITS_OR_TOLERANCE_CHANGED')
        for oid,snapshot in snapshots.items():
            obj=doc.Objects.FindId(System.Guid(oid))
            if obj is None or not R.Geometry.GeometryBase.GeometryEquals(obj.Geometry,snapshot):
                raise ValueError('FIELD_FIXTURE_EDITED_OR_MISSING_'+oid)
        parent_map={}; targets=[]; caps=[]; cap_specs=case['caps']
        for rec in manifest['source_edges']:
            key=rec['object_id']
            if key not in parent_map:
                obj=doc.Objects.FindId(System.Guid(key)); parent_map[key]=own(obj.Geometry.DuplicateBrep())
            b=parent_map[key]; e=b.Edges[rec['edge']]; f=b.Faces[rec['face']]
            if e.Valence!=R.Geometry.EdgeAdjacency.Naked or e.TrimCount!=1 or b.Trims[e.TrimIndices()[0]].Face.FaceIndex!=rec['face']:
                raise ValueError('SOURCE_TOPOLOGY_CHANGED')
            targets.append((rec,e,f))
        for spec in cap_specs:
            obj=doc.Objects.FindId(System.Guid(spec['object_id'])); b=own(obj.Geometry.DuplicateBrep())
            if not b.IsValid or b.Faces.Count!=1: raise ValueError('INVALID_PREPARED_CAP_FACE')
            caps.append(b)
        pre=[[] for unused in targets]
        for cap,spec in zip(caps,cap_specs):
            face=cap.Faces[0]
            for side in spec['exterior_sides']:
                varying=1 if side in ('left','right') else 0
                const_dir=1-varying
                value=face.Domain(const_dir).T0 if side in ('left','bottom') else face.Domain(const_dir).T1
                iso=own(face.IsoCurve(varying,value))
                if iso is None: raise ValueError('EXTERIOR_ISOCURVE_UNAVAILABLE')
                # These prepared faces are untrimmed; verify the iso is a Brep edge.
                matches=[]
                for e in cap.Edges:
                    if all(close_to(e,iso.PointAt(iso.Domain.ParameterAt(f)))[0]<1e-7 for f in (0.,.5,1.)):
                        if gap(e,iso,tol)<1e-7: matches.append(e)
                if len(matches)!=1: raise ValueError('PREPARED_CAP_NOT_NATURAL_OR_AMBIGUOUS')
                for i,piece in split_assign(matches[0],targets,tol): pre[i].append(piece)
        for i,(_,target,_) in enumerate(targets):
            value=chain_check(pre[i],target,tol)
            report.emit('PREJOIN_BOUNDARY',segment=i,parts=len(pre[i]),native_bidirectional_gap_mm=value,
                        inherited_relief_bound_mm=case['relief_bound_mm'],relief_budget_mm=.0025)
        checkpoint(); inp=System.Collections.Generic.List[R.Geometry.Brep]()
        for b in caps+list(parent_map.values()): inp.Add(b)
        result=R.Geometry.Brep.JoinBreps(inp,tol,doc.ModelAngleToleranceRadians)
        for b in result or []: own(b)
        if result is None or len(result)!=1: raise ValueError('JOIN_NOT_ONE_CONNECTED_BREP')
        joined=result[0]
        if not joined.IsValid or not joined.IsManifold: raise ValueError('INVALID_JOINED_BREP')
        surfaces=[own(cap.Faces[0].DuplicateSurface()) for cap in caps]; cap_faces={}
        face_surfaces={f.FaceIndex:own(f.DuplicateSurface()) for f in joined.Faces}
        for ci,s in enumerate(surfaces):
            found=[i for i,v in face_surfaces.items() if same_surface(v,s)]
            if len(found)!=1 or found[0] in cap_faces: raise ValueError('JOIN_FACE_PROVENANCE_UNAVAILABLE')
            cap_faces[found[0]]=ci
        post=[[] for unused in targets]; internal={}; external=[]
        parent_surfaces=[own(f.DuplicateSurface()) for _,_,f in targets]
        for edge in joined.Edges:
            adjacent=list(edge.AdjacentFaces()); cf=[f for f in adjacent if f in cap_faces]
            if not cf: continue
            if len(adjacent)!=2 or edge.TrimCount!=2 or edge.Valence!=R.Geometry.EdgeAdjacency.Interior:
                raise ValueError('NAKED_OR_NONMANIFOLD_CAP_EDGE')
            if len(cf)==2:
                pair=tuple(sorted(cap_faces[f] for f in cf))
                if pair not in ((0,1),(1,2)): raise ValueError('UNEXPECTED_INTERNAL_SEAM')
                internal.setdefault(pair,[]).append(edge)
            else:
                other=[f for f in adjacent if f not in cap_faces][0]
                for i,piece in split_assign(edge,targets,tol):
                    if not same_surface(face_surfaces[other],parent_surfaces[i]): raise ValueError('WRONG_PARENT_FACE_AT_SEAM')
                    post[i].append(piece)
                external.append(edge)
            trace_metrics(edge,len(cf)==2,tol)
        if len(caps)==3 and set(internal)!=set(((0,1),(1,2))): raise ValueError('MISSING_INTERNAL_SEAM_PAIR')
        if len(caps)==1 and internal: raise ValueError('UNEXPECTED_INTERNAL_SEAM')
        # Prove each full intended internal iso is covered, allowing native edge splitting.
        for pair,edges in sorted(internal.items()):
            expected=own(caps[pair[0]].Faces[0].IsoCurve(1,caps[pair[0]].Faces[0].Domain(0).T1))
            igap=chain_check([own(e.DuplicateCurve()) for e in edges],expected,tol)
            report.emit('INTERNAL_COVERAGE',pair=list(pair),edge_indices=[e.EdgeIndex for e in edges],native_gap_mm=igap)
        for i,(_,target,_) in enumerate(targets):
            value=chain_check(post[i],target,tol)
            report.emit('SOURCE_COVERAGE',segment=i,parts=len(post[i]),common_edge_to_source_mm=value,
                        result='NATIVE_CHAIN_COVERED',note='This is not the trim-image distance')
        joined_ok=True
        report.emit('JOIN',result='ALL_SIX_SOURCE_INTERVALS_AND_INTERNAL_CHAINS_VERIFIED',
                    cap_faces=len(caps),cap_naked_edges=0,external_edge_count=len(external),
                    internal_pairs=len(internal),joined_faces=joined.Faces.Count,is_solid=joined.IsSolid,
                    full_external_G2='NOT_CERTIFIED',form=case['form_status'])
        state='COMPLETE'
        report.emit('COMPLETE',connection='VERIFIED',form_acceptance=False,parent_intersections='NOT_RUN_BY_FIELD01',
                    self_intersections='NOT_CERTIFIED',geometry_commit=False)
    except BaseException as exc:
        report.emit('STOP',error=text(exc),traceback=traceback.format_exc(),join_stage_passed=joined_ok,
                    form_acceptance=False,geometry_commit=False)
    finally:
        try:
            equal='NOT_VERIFIED_DOCUMENT_CLOSED'; after='NOT_MEASURED_DOCUMENT_CLOSED'
            if document_alive():
                equal=True
                for oid,snapshot in snapshots.items():
                    obj=doc.Objects.FindId(System.Guid(oid))
                    equal=equal and obj is not None and R.Geometry.GeometryBase.GeometryEquals(obj.Geometry,snapshot)
                after=count()
            report.emit('SAFETY',all_fixture_geometry_equal=equal,objects_before=initial_count,objects_after=after,
                        added=0,deleted=0,replaced=0,display_layer_changes_only=True)
            report.emit('END',state=state,geometry_commit=False)
        finally:
            for b in reversed(owned):
                try: b.Dispose()
                except Exception: pass
            report.finish()
    return report.path,state
