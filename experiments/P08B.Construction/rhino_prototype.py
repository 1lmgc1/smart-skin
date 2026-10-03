# -*- coding: utf-8 -*-
"""P08B.2F2 Rhino adapter: one constructive preview experiment, never a document edit.
Run the BUNDLED file with _RunPythonScript. No installation or numpy is required.
"""
from __future__ import division
from mixed_kernel import *
from adaptive_boundary import adaptive_coons
import io
import os
import time
import json
import hashlib
import traceback

EXPERIMENT = 'P08B.2F2'
CODE_COMMIT = 'WORKTREE'
try: text_type=unicode
except NameError: text_type=str

def text(x): return x if isinstance(x,text_type) else text_type(x)
def compact(x): return text(x).replace('\r',' ').replace('\n',' ').replace('|','/')
def xyz(p): return (float(p.X),float(p.Y),float(p.Z))

class StopExperiment(Exception): pass

class Report(object):
    def __init__(self,path,console):
        self.path=path; self.console=console; self.error=None; self.lines=[]
        # Plain UTF-8 plus exactly one explicit BOM avoids codec state resets
        # observed with some IronPython utf-8-sig writers.
        self.file=io.open(path,'w',encoding='utf-8',newline='')
        self.file.write(u'\ufeff'); self.file.flush()
    def emit(self,kind,**data):
        row=u'SMARTSKIN_P08B2_'+text(kind)+u' | '+u' | '.join(text(k)+u'='+compact(data[k]) for k in sorted(data))
        self.lines.append(row)
        if self.error is None:
            try: self.file.write(row+u'\r\n'); self.file.flush()
            except Exception as err: self.error=text(err)
        if kind in ('BEGIN','SELECTION','LAYOUT','BEST','STOP','END','SAFETY'):
            try: self.console('SMARTSKIN_P08B2_'+str(kind)+' | details in TXT')
            except Exception: pass
    def close(self):
        try: self.file.close()
        except Exception as err: self.error=text(err)

def save_path():
    import rhinoscriptsyntax as rs
    while True:
        path=rs.SaveFileName(u'Smart Skin: сохранить отчёт построения '+EXPERIMENT,'Text files (*.txt)|*.txt||',None,'SmartSkin_Mixed_'+time.strftime('%Y%m%d_%H%M%S')+'.txt','txt')
        if not path: return None
        path=text(path)
        if not path.lower().endswith('.txt'): path+=u'.txt'
        if os.path.exists(path) and rs.MessageBox(u'Заменить существующий TXT?\n'+path,4|32|256,u'Smart Skin')!=6: continue
        return path

def curve_loop(R,edges,tol):
    copies=[e.DuplicateCurve() for e in edges]; joined=None
    try:
        joined=R.Geometry.Curve.JoinCurves(copies,tol,False)
        if joined is None or len(joined)!=1 or not joined[0].IsClosed: raise ValueError('NOT_ONE_CLOSED_LOOP')
        result=joined[0]; joined[0]=None
        return result
    finally:
        for e in copies: e.Dispose()
        if joined is not None:
            for e in joined:
                if e is not None: e.Dispose()

class Chain(object):
    def __init__(self,items,features,offset):
        self.items=items; self.features=features; self.offset=offset; self.length=sum(float(e['edge'].GetLength()) for e in items)
        if self.length<=0: raise ValueError('ZERO_LENGTH_CHAIN')
        self.ends=[]; current=0; self.cache={}; self.parameters=[0.0,1.0]
        for e in items:
            length=float(e['edge'].GetLength()); start=current/self.length; current+=length; end=current/self.length
            self.ends.append((start,end,e,length))
            # Every original interval, including tiny fragments, gets its own
            # endpoints, near-end samples and interior observations.
            self.parameters.extend(start+(end-start)*a for a in (0,1e-5,.25,.5,.75,1-1e-5,1))
    def __call__(self,t):
        key=round(float(t),14)
        if key in self.cache: return self.cache[key]
        chosen=self.ends[-1]
        for entry in self.ends:
            if t<=entry[1]: chosen=entry; break
        start,end,e,length=chosen; local=max(0.0,min(1.0,(t-start)/(end-start)))
        if e['flip']: local=1-local
        edge=e['edge']; ok,parameter=edge.NormalizedLengthParameter(local)
        if not ok: raise ValueError('EDGE_ARCLENGTH_PARAMETER_FAILED')
        point=edge.PointAt(parameter); trim=edge.Brep.Trims[edge.TrimIndices()[0]]
        normal=None; H=None; ok,tt=trim.GetTrimParameter(parameter)
        try:
            if ok:
                uv=trim.PointAt(tt); face=trim.Face
                evaluated=face.Evaluate(uv.X,uv.Y,2)
                if evaluated[0] and evaluated[2] is not None and len(evaluated[2])==5:
                    values=(xyz(evaluated[1]),)+tuple(xyz(d) for d in evaluated[2])
                    normal,H=frame(values)
                    if face.OrientationIsReversed:
                        normal=mul(normal,-1); H=tuple(mul(row,-1) for row in H)
            if normal is not None and (not all(finite(x) for x in normal) or norm(normal)<1e-14): normal=None
            if H is not None and not all(finite(x) for row in H for x in row): H=None
        except Exception:
            normal=None; H=None
        result=Support(sub(xyz(point),self.offset),normal,H,e['key'],0 if e['key'] in self.features else 2,length)
        self.cache[key]=result
        return result

def flip_items(items):
    return [dict(e,flip=not e['flip']) for e in reversed(items)]

def boundary_role_runs(ordered,features):
    """Partition an already ordered CLOSED ring by explicit role, not by edge count.

    This does not join/split/rebuild curves. Every item keeps its original key,
    edge/trim/face data and traversal direction. Geometry closure is checked by
    capture(), not invented by this metadata-only helper.
    """
    keys=[e['key'] for e in ordered]; n=len(keys); features=set(features)
    if n<4 or n>8: raise ValueError('LAYOUT_REQUIRES_FOUR_TO_EIGHT_SOURCE_EDGES')
    if len(set(keys))!=n: raise ValueError('LAYOUT_DUPLICATE_SOURCE_KEY')
    if not features.issubset(set(keys)): raise ValueError('LAYOUT_UNKNOWN_G0_KEY')
    if not features or len(features)==n: raise ValueError('MIXED_CONTRACT_REQUIRED')
    starts=[i for i in range(n) if keys[i] in features and keys[i-1] not in features]
    # Canonical cyclic start affects only U/V placement, never a source's role.
    start=min(starts,key=lambda i:keys[i])
    ring=list(ordered[start:])+list(ordered[:start]); runs=[]
    for e in ring:
        role=e['key'] in features
        if not runs or (runs[-1][0]['key'] in features)!=role: runs.append([])
        runs[-1].append(dict(e))
    return runs

def four_side_layouts(ordered,features):
    runs=boundary_role_runs(ordered,features)
    if len(runs)==4:
        # Two opposing G0 chains, separated by two G2 chains. A logical side
        # may contain several source edges; none is relabelled or discarded.
        # In tensor-product coordinates top and left run opposite the ring.
        return [{'bottom':runs[0],'right':runs[1],
                 'top':flip_items(runs[2]),'left':flip_items(runs[3])}]
    if len(runs)!=2:
        raise ValueError('LAYOUT_UNSUPPORTED_ROLE_RUNS: g0_chains='+str(len(runs)//2)
                         +'; four_side_route_supports_one_or_two; no_roles_changed')
    # Preserve the existing one-feature-chain search without requiring it for
    # every input. Its three smooth sides are partitions of the other run.
    sharp,smooth=runs
    if len(smooth)<3: raise ValueError('ONE_G0_CHAIN_NEEDS_THREE_SMOOTH_SOURCE_INTERVALS')
    layouts=[]
    for a in range(1,len(smooth)-1):
        for b in range(a+1,len(smooth)):
            layouts.append({'bottom':sharp,'right':smooth[:a],
                            'top':flip_items(smooth[a:b]),'left':flip_items(smooth[b:])})
    layouts.sort(key=lambda d:abs(len(d['left'])-len(d['right']))+abs(len(d['bottom'])-len(d['top'])))
    return layouts[:6]

class Experiment(object):
    def __init__(self,report):
        import Rhino as R
        import System as S
        import scriptcontext as sc
        self.R,self.S,self.sc=R,S,sc; self.doc=R.RhinoDoc.ActiveDoc; self.report=report
        self.getters=[]; self.parents={}; self.refs=[]; self.ordered=[]; self.best=None
        self.before=None; self.started=None; self.cancelled=False; self.attempts=0
        self.tol=float(self.doc.ModelAbsoluteTolerance); self.angle=float(self.doc.ModelAngleToleranceRadians)
        if self.tol<=0 or not finite(self.tol): raise ValueError('INVALID_DOCUMENT_TOLERANCE')
        self.offset=(0,0,0)
    def count(self):
        settings=self.R.DocObjects.ObjectEnumeratorSettings()
        settings.ActiveObjects=True; settings.DeletedObjects=False; settings.NormalObjects=True
        settings.LockedObjects=True; settings.HiddenObjects=True; settings.ReferenceObjects=False
        settings.IdefObjects=False; settings.IncludeGrips=False; settings.IncludeLights=False; settings.IncludePhantoms=False
        return sum(1 for _ in self.doc.Objects.GetObjectList(settings))
    def check(self):
        if self.report.error is not None: raise StopExperiment('TXT_WRITE_FAILED')
        if self.sc.escape_test(False): self.cancelled=True; raise StopExperiment('CANCELLED')
        if self.started is not None and time.time()-self.started>120: raise StopExperiment('TIME_BUDGET;best_completed_candidate_retained')
    def select(self,prompt,min_count,max_count):
        R=self.R; go=R.Input.Custom.GetObject(); self.getters.append(go)
        go.SetCommandPrompt(prompt); go.GeometryFilter=R.DocObjects.ObjectType.Curve
        go.SubObjectSelect=True; go.GroupSelect=False; go.EnablePreSelect(False,True)
        go.GetMultiple(min_count,max_count)
        if go.CommandResult()!=R.Commands.Result.Success: raise StopExperiment('SELECTION_CANCELLED')
        return [go.Object(i) for i in range(go.ObjectCount)]
    def capture(self):
        self.before=self.count()
        refs=self.select(EXPERIMENT+': select ALL opening Brep edges, then Enter',5,8)
        self.refs=refs; items=[]; seen=set(); faces=0; edges=0
        for ref in refs:
            e=ref.Edge()
            if e is None or e.Valence!=self.R.Geometry.EdgeAdjacency.Naked or e.TrimCount!=1: raise ValueError('NAKED_BREP_EDGE_REQUIRED')
            oid=str(ref.ObjectId); identity=(oid,e.EdgeIndex)
            if identity in seen: raise ValueError('DUPLICATE_BOUNDARY')
            seen.add(identity)
            if oid not in self.parents:
                faces+=e.Brep.Faces.Count; edges+=e.Brep.Edges.Count
                if faces>96 or edges>448: raise ValueError('CONTEXT_COMPLEXITY_LIMIT')
                self.parents[oid]=(ref,e.Brep.DuplicateBrep())
            copied=self.parents[oid][1].Edges[e.EdgeIndex]; trim=copied.Brep.Trims[copied.TrimIndices()[0]]
            stable=oid+':edge='+str(e.EdgeIndex)+':trim='+str(trim.TrimIndex)+':face='+str(trim.Face.FaceIndex)+':domain='+str(e.Domain)
            items.append({'edge':copied,'key':stable,'identity':identity,'flip':False})
        order=[items[0]]; unused=items[1:]
        while unused:
            last=order[-1]; end=last['edge'].PointAtStart if last['flip'] else last['edge'].PointAtEnd; hits=[]
            for e in unused:
                if end.DistanceTo(e['edge'].PointAtStart)<=self.tol: hits.append((e,False))
                if end.DistanceTo(e['edge'].PointAtEnd)<=self.tol: hits.append((e,True))
            if len(hits)!=1: raise ValueError('AMBIGUOUS_OR_OPEN_BOUNDARY')
            e,reverse=hits[0]; unused.remove(e); order.append(dict(e,flip=reverse))
        end=order[-1]['edge'].PointAtStart if order[-1]['flip'] else order[-1]['edge'].PointAtEnd
        if end.DistanceTo(order[0]['edge'].PointAtStart)>self.tol: raise ValueError('OPEN_BOUNDARY')
        self.ordered=order
        refs_g0=self.select(EXPERIMENT+': select ALL source edge segments to keep G0 (include every segment of each chosen side), then Enter',1,0)
        identities={(str(r.ObjectId),r.Edge().EdgeIndex) for r in refs_g0 if r.Edge() is not None}
        if len(identities)!=len(refs_g0) or not identities.issubset(seen): raise ValueError('G0_SELECTION_MUST_BE_SUBSET_OF_OPENING')
        features={e['key'] for e in order if e['identity'] in identities}
        if not features or len(features)>=len(order): raise ValueError('MIXED_CONTRACT_REQUIRED')
        self.features=features; self.contract_id=hashlib.sha256(';'.join(sorted(e['key']+(':G0' if e['key'] in features else ':G2') for e in order)).encode('utf-8')).hexdigest()
        pts=[xyz(e['edge'].PointAtStart) for e in order]
        self.offset=tuple(sum(p[k] for p in pts)/len(pts) for k in range(3))
        for e in order: self.report.emit('RULE',edge=e['key'],preferred='G0_FEATURE' if e['key'] in features else 'G2',source_edit='FORBIDDEN',contract=self.contract_id)
        self.report.emit('SELECTION',edges=len(order),parents=len(self.parents),sharp=len(features),smooth=len(order)-len(features),objects=self.before)
    def make_brep(self,patch):
        R=self.R; surface=R.Geometry.NurbsSurface.Create(3,False,patch.p+1,patch.p+1,patch.n,patch.n)
        if surface is None: raise ValueError('NURBS_ALLOCATION_FAILED')
        try:
            for i,value in enumerate(patch.K[1:-1]): surface.KnotsU[i]=value; surface.KnotsV[i]=value
            for i in range(patch.n):
                for j in range(patch.n):
                    p=add(patch.net[i][j],self.offset)
                    if not surface.Points.SetPoint(i,j,R.Geometry.Point3d(*p)): raise ValueError('CONTROL_POINT_WRITE_FAILED')
            if not surface.IsValid: raise ValueError('NURBS_INVALID')
            brep=surface.ToBrep()
            if brep is None or not brep.IsValid:
                if brep is not None: brep.Dispose()
                raise ValueError('BREP_INVALID')
            return brep
        finally: surface.Dispose()
    def gap(self,a,b):
        # Evaluate both directions, without short-circuit loss of available data.
        vals=[]
        for x,y in ((a,b),(b,a)):
            self.check(); result=self.R.Geometry.Curve.GetDistancesBetweenCurves(x,y,max(self.tol*.1,1e-9))
            value=float(result[1]) if result[0] else None
            vals.append(value if value is not None and finite(value) and value>=0 else None)
        return max(vals) if all(v is not None for v in vals) else None,vals
    def native_evidence(self,cap,patch):
        R=self.R; source_loop=None; output_loop=None; joined=None; seam_loop=None; cap_surface=None; extra=[]
        try:
            source_loop=curve_loop(R,[e['edge'] for e in self.ordered],self.tol)
            output_loop=curve_loop(R,[e for e in cap.Edges if e.Valence==R.Geometry.EdgeAdjacency.Naked],self.tol)
            gap,values=self.gap(source_loop,output_loop)
            result={'native_max_gap':gap,'native_directions':str(values),'join_proof':False,'interop_max_gap':0.0,'interop_normal_deg':0.0,'interop_tensor_pct':0.0,'interop_singular_samples':0,'cap_internal_seams':0,'commit_allowed':False}
            for u in (0,.173,.5,.837,1):
                for v in (0,.241,.5,.913,1):
                    evaluated=cap.Faces[0].Evaluate(u,v,2)
                    if not evaluated[0] or len(evaluated[2])!=5: raise ValueError('NATIVE_EVALUATION_FAILED')
                    actual=(xyz(evaluated[1]),)+tuple(xyz(d) for d in evaluated[2]); expected=patch.eval(u,v)
                    result['interop_max_gap']=max(result['interop_max_gap'],norm(sub(actual[0],add(expected[0],self.offset))))
                    try:
                        an,ah=frame(actual); en,eh=frame(expected); d=dot(an,en)
                        result['interop_normal_deg']=max(result['interop_normal_deg'],math.degrees(math.acos(min(1,abs(d)))))
                        result['interop_tensor_pct']=max(result['interop_tensor_pct'],tensor_error(ah,eh,d))
                    except ValueError:
                        # A singular corner cannot certify G1/G2, but should not
                        # erase an otherwise valid positional preview.
                        result['interop_singular_samples']+=1
            if gap is None or gap>self.tol or result['interop_max_gap']>max(1e-7,self.tol*1e-4) or result['interop_normal_deg']>0.001 or result['interop_tensor_pct']>0.1: return result
            # Fresh parents per attempt. Join is never performed on originals or the retained cap.
            extra=[p.DuplicateBrep() for _,p in self.parents.values()]+[cap.DuplicateBrep()]
            self.check(); joined=R.Geometry.Brep.JoinBreps(extra,self.tol,self.angle)
            if joined is None or len(joined)!=1 or not joined[0].IsValid: return result
            proof=joined[0]; cap_surface=cap.Faces[0].DuplicateSurface(); matches=[]
            for face in proof.Faces:
                s=face.DuplicateSurface()
                try:
                    if R.Geometry.GeometryBase.GeometryEquals(s,cap_surface): matches.append(face.FaceIndex)
                finally: s.Dispose()
            if len(matches)!=1: return result
            seams=[]
            for edge in proof.Edges:
                af=list(edge.AdjacentFaces())
                if matches[0] not in af: continue
                if edge.Valence==R.Geometry.EdgeAdjacency.Naked: return result
                if edge.Valence!=R.Geometry.EdgeAdjacency.Interior or len(af)!=2: return result
                seams.append(edge)
            if not seams: return result
            seam_loop=curve_loop(R,seams,self.tol); seam_gap,unused=self.gap(source_loop,seam_loop)
            result['seam_max_gap']=seam_gap
            result['join_proof']=seam_gap is not None and seam_gap<=self.tol
            result['joined_cap_seams']=len(seams)
            return result
        finally:
            for item in (source_loop,output_loop,seam_loop,cap_surface):
                if item is not None: item.Dispose()
            if joined is not None:
                for item in joined: item.Dispose()
            for item in extra: item.Dispose()
    def candidate(self,label,patch,evidence,unused_kept):
        self.check(); self.attempts+=1; candidate_id=self.contract_id[:12]+':'+label
        for key,e in evidence['edges'].items():
            self.report.emit('EDGE',candidate=candidate_id,edge=key,preferred=e['preferred'],achieved_sampled=e['achieved'],gap_sampled=e['gap'],normal_deg=e['normal_deg'] if e['frames'] else 'UNAVAILABLE',shape_operator_error_pct=e['curvature_pct'] if e['curvatures'] else 'UNAVAILABLE',samples=e['count'])
        self.report.emit('CANDIDATE',candidate=candidate_id,position_sampled=evidence['position_sampled_ok'],regularity_sampled=evidence['regularity_sampled_ok'],scope=evidence['scope'],desired_sampled=evidence['desired_sampled_met'])
        if not evidence['position_sampled_ok'] or not evidence['regularity_sampled_ok']: return
        cap=None
        try:
            cap=self.make_brep(patch); native=self.native_evidence(cap,patch)
            self.report.emit('NATIVE',candidate=candidate_id,**native)
            if native['join_proof'] and (self.best is None or evidence['score']>self.best[2]['score']):
                old=self.best; self.best=(candidate_id,cap,evidence,native); cap=None
                if old is not None: old[1].Dispose()
                self.report.emit('BEST',candidate=candidate_id,status='PREFERRED_SAMPLED_MET' if evidence['desired_sampled_met'] else 'LOCAL_COMPROMISE_PREVIEW',commit_allowed=False)
        except StopExperiment: raise
        except Exception as error:
            self.report.emit('CANDIDATE_ERROR',candidate=candidate_id,error=error,previous_best_retained=self.best is not None)
        finally:
            if cap is not None: cap.Dispose()
    def run(self):
        self.report.emit('BEGIN',experiment=EXPERIMENT,commit=CODE_COMMIT,rhino=self.R.RhinoApp.Version,tol=self.tol,angle_deg=math.degrees(self.angle),curvature_percent=5,mode='PREVIEW_ONLY;FIXED_PARENTS;NO_DOCUMENT_WRITES')
        self.capture(); runs=boundary_role_runs(self.ordered,self.features)
        self.report.emit('ROLE_CHAINS',g0_chains=len(runs)//2,g2_chains=len(runs)//2,
                         source_edges_per_chain=','.join(str(len(r)) for r in runs),
                         roles=';'.join('G0' if r[0]['key'] in self.features else 'G2' for r in runs))
        layouts=four_side_layouts(self.ordered,self.features); self.started=time.time()
        for index,layout in enumerate(layouts):
            self.report.emit('LAYOUT_PLAN',layout=index,logical_sides=4,
                             source_edges=sum(len(layout[s]) for s in SIDES),
                             side_edge_counts=','.join(str(len(layout[s])) for s in SIDES))
            for side in SIDES:
                items=layout[side]
                self.report.emit('SIDE',layout=index,side=side,source_edges=len(items),
                                 role='G0_FEATURE' if items[0]['key'] in self.features else 'G2',
                                 keys=';'.join(e['key'] for e in items),
                                 flips=','.join(str(e['flip']) for e in items),
                                 source_intervals_preserved=True)
        for n in (10,16):
            for index,layout in enumerate(layouts):
                self.check(); name='layout'+str(index)+'_n'+str(n)
                sides={s:Chain(layout[s],self.features,self.offset) for s in SIDES}
                self.report.emit('LAYOUT',name=name,sides=';'.join(s+':'+','.join(e['key'] for e in layout[s]) for s in SIDES),method='ADAPTIVE_BOUNDARY_COONS_PLUS_FIXED_ROW_JETS')
                try:
                    def fit_step(record):
                        details=record.get('evidence')
                        if details is None:
                            self.report.emit('BOUNDARY_FIT_ERROR',layout=name,round=record['round'],error=record.get('error'),previous_fitted_baseline_retained=True)
                            return
                        self.report.emit('BOUNDARY_FIT',layout=name,round=record['round'],controls=record['controls'],gap_sampled=details['gap'],target=details['target'],document_tolerance=self.tol,target_sampled=details['target_sampled_met'],document_sampled=details['document_sampled_met'],kept=record['kept'],best_gap=record['best_gap'],knots=','.join('%.12g'%k for k in record['knots']),scope=details['scope'])
                        for side in SIDES:
                            item=details['sides'][side]; witness=item['witness']
                            self.report.emit('BOUNDARY_FIT_SIDE',layout=name,round=record['round'],side=side,gap_sampled=item['gap'],samples=item['samples'],witness_parameter=witness['parameter'],source_key=witness['source_key'],target_point=witness['target_point'],fitted_point=witness['fitted_point'],coordinate_frame='LOCAL_ORIGIN',original_intervals=len(item['sources']))
                    self.report.emit('BOUNDARY_FIT_BEGIN',layout=name,start_controls=n,max_controls=32,max_rounds=10,document_tolerance=self.tol,fit_target=self.tol*.25,method='RESIDUAL_DIRECTED_SIMPLE_KNOTS_AND_REFIT',role_changes=0)
                    fit=adaptive_coons(sides,n=n,p=3,tolerance=self.tol,checkpoint=self.check,on_step=fit_step)
                    base=fit.patch; name=name+'_adaptive_n'+str(base.n)
                    self.report.emit('BOUNDARY_FIT_END',layout=name,result=fit.reason,rounds=len(fit.history),gap_sampled=fit.evidence['gap'],document_sampled=fit.evidence['document_sampled_met'],target_sampled=fit.evidence['target_sampled_met'],outer_rows_frozen_after_fit=True,native_join='NOT_RUN_YET')
                    if not fit.evidence['document_sampled_met']:
                        self.report.emit('STAGE_SKIPPED',layout=name,stage='JETS_AND_NATIVE_JOIN',reason='BOUNDARY_POSITION_UNRESOLVED',previous_best_retained=self.best is not None)
                        continue
                    initial=measure(base,sides,self.tol,math.degrees(self.angle),5,checkpoint=self.check)
                    self.candidate(name+'_COONS',base,initial,False)
                    if not initial['position_sampled_ok'] or not initial['regularity_sampled_ok']:
                        self.report.emit('STAGE_SKIPPED',layout=name,stage='JETS',reason='WHOLE_BASELINE_CHECK_FAILED',previous_best_retained=self.best is not None)
                        continue
                    current=base
                    for step in range(4):
                        self.report.emit('JET_START',layout=name,step=step,level='G1' if step==0 else 'G2',outer_rows_frozen=True)
                        current,iterations=refine(current,sides,curvature=step>0,checkpoint=self.check)
                        e=measure(current,sides,self.tol,math.degrees(self.angle),5,checkpoint=self.check)
                        self.candidate(name+'_JET'+str(step),current,e,False)
                except StopExperiment: raise
                except Exception as error: self.report.emit('LAYOUT_ERROR',name=name,error=error)
            if self.best is not None and self.best[2]['desired_sampled_met']: break
        self.report.emit('SEARCH_END',attempts=self.attempts,best=self.best[0] if self.best else 'NONE',result='PREVIEW_AVAILABLE' if self.best else 'NO_CANDIDATE',commit_allowed=False)
    def preview(self):
        if self.best is None or self.cancelled: return
        R=self.R; import System.Drawing as Drawing
        brep=self.best[1]
        class Preview(R.Display.DisplayConduit):
            def __init__(self):
                R.Display.DisplayConduit.__init__(self)
                self.material=R.Display.DisplayMaterial(Drawing.Color.Cyan,0.35)
            def CalculateBoundingBox(self,e): e.IncludeBoundingBox(brep.GetBoundingBox(True))
            def PostDrawObjects(self,e):
                e.Display.DrawBrepShaded(brep,self.material)
                e.Display.DrawBrepWires(brep,Drawing.Color.Cyan,1)
        conduit=Preview(); getter=R.Input.Custom.GetOption()
        try:
            conduit.Enabled=True; self.doc.Views.Redraw()
            getter.SetCommandPrompt(EXPERIMENT+' PREVIEW ONLY: Enter or Esc closes; no object is added. Full per-edge result is in TXT')
            getter.AcceptNothing(True); getter.Get()
            self.report.emit('PREVIEW_CLOSED',candidate=self.best[0],added=0)
        finally:
            conduit.Enabled=False; self.doc.Views.Redraw(); conduit.material.Dispose(); getter.Dispose()
    def close(self):
        try:
            unchanged=True
            for oid,(ref,snapshot) in self.parents.items():
                equal=self.R.Geometry.GeometryBase.GeometryEquals(ref.Edge().Brep,snapshot)
                unchanged=unchanged and equal; self.report.emit('SOURCE_CHECK',parent=oid,geometry_equal=equal)
            after=self.count()
            self.report.emit('SAFETY',objects_before=self.before,objects_after=after,count_equal=after==self.before if self.before is not None else 'NOT_CAPTURED',parent_geometry_equal=unchanged,added_by_experiment=0)
        finally:
            if self.best is not None: self.best[1].Dispose()
            for _,snapshot in self.parents.values(): snapshot.Dispose()
            for go in self.getters: go.Dispose()

def run_experiment():
    import Rhino
    import rhinoscriptsyntax as rs
    report=None; experiment=None; state='STOPPED'
    while report is None:
        path=save_path()
        if not path: return
        try: report=Report(path,Rhino.RhinoApp.WriteLine)
        except Exception as error: rs.MessageBox(text(error),0|16,u'TXT: выберите другой путь')
    try:
        experiment=Experiment(report)
        try:
            experiment.run(); state='COMPLETE'
        except StopExperiment as error: report.emit('STOP',error=error,previous_best_retained=experiment.best is not None)
        experiment.preview()
    except Exception as error:
        report.emit('STOP',error=error,traceback=traceback.format_exc())
    finally:
        try:
            if experiment is not None: experiment.close()
        except Exception as error:
            state='STOPPED'; report.emit('SAFETY',state='CHECK_FAILED;NOT_PROVEN',error=error)
        report.emit('END',state=state,commit_allowed=False,file_error=report.error or 'none')
        report.close()
        if report.error is not None:
            # Retry saving retained complete records; never rerun construction.
            while report.error is not None:
                Rhino.RhinoApp.WriteLine('TXT incomplete; select a replacement path, or cancel')
                path=save_path()
                if path is None: break
                try:
                    replacement=Report(path,Rhino.RhinoApp.WriteLine)
                    for row in report.lines: replacement.file.write(row+u'\r\n')
                    replacement.file.flush(); replacement.close(); report=replacement
                except Exception as err: Rhino.RhinoApp.WriteLine(text(err))
        Rhino.RhinoApp.WriteLine(('SMARTSKIN_P08B2_SAVED | ' if report.error is None else 'SMARTSKIN_P08B2_TXT_INCOMPLETE | ')+report.path)

if __name__=='__main__': run_experiment()
