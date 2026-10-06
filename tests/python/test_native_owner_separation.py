"""Public synthetic adapter tests. Licensed Rhino execution: NOT VERIFIED."""
import copy
import json
from pathlib import Path
import sys
import unittest
from dataclasses import replace
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/SmartSkin.Rhino8/Python'))
import native_owner_separation as n


class Geometry:
    def __init__(self, name, bbox=((0., 0., 0.), (2., 2., 2.)), witnesses=((1., 1., 1.),)):
        self.name, self.bbox, self.witnesses = name, bbox, witnesses
        self.version = 0; self.disposed = False
    def Dispose(self): self.disposed = True


class Curve(Geometry):
    def __init__(self, name, domain=(0., 1.)):
        super().__init__(name); self.domain = domain


class Adapter:
    def __init__(self):
        self.brep_results = {}; self.curve_results = {}; self.overlap_results = {}
        self.distances = {}; self.calls = []; self.point_membership = {}
        self.after_events = None
    def fingerprint(self, geometry, budget):
        budget.check()
        if geometry.disposed: raise n.SeparationError('DISPOSED', 'Geometry disposed')
        return geometry.name + ':' + str(geometry.version)
    def prepare(self, geometry, tolerance, budget):
        budget.call(self.calls.append, ('prepare', geometry.name))
        return n._Prepared(geometry.bbox, (Curve(geometry.name + '.edge'),), geometry.witnesses, 1, 1, 4)
    def contact_curves(self, patch, owner, selected, contact, budget):
        budget.call(self.calls.append, ('contact', patch.name, owner.name))
        return Curve('source:' + selected.source_key), Curve('generated:' + patch.name)
    def contact_points(self, patch, owner, selected, contact, tolerance, budget):
        return (0., 0., 0.), (0., 0., 0.)
    def same_point(self, a, b, tolerance):
        return sum((x-y)**2 for x, y in zip(a, b)) <= tolerance*tolerance
    def brep_events(self, patch, owner, tolerance, budget):
        budget.call(self.calls.append, ('brep', patch.name, owner.name))
        if self.after_events: self.after_events()
        result = self.brep_results.get((patch.name, owner.name), ([], []))
        if isinstance(result, Exception): raise result
        return result
    def curve_events(self, curve, other, tolerance, budget):
        budget.call(self.calls.append, ('curve', curve.name, other.name))
        return self.curve_results.get((curve.name, other.name), ([], []))
    def curve_domain(self, curve, budget): return curve.domain
    def overlaps(self, curve, boundary, tolerance, budget):
        budget.call(self.calls.append, ('overlap', curve.name, boundary.name))
        return self.overlap_results.get((curve.name, boundary.name), ())
    def point_on_curve(self, point, curve, tolerance, budget):
        budget.call(self.calls.append, ('point', curve.name))
        return self.point_membership.get((point, curve.name), False)
    def distance_to_brep(self, point, geometry, budget):
        budget.call(self.calls.append, ('distance', point, geometry.name))
        return self.distances.get((point, geometry.name), 1.)


def ledger(contacts=(), points=()):
    return dict(schema='smartskin.native-contact-ledger.v1', checked=True, source_digest='source',
                geometry_digest='geometry', contacts=list(contacts), point_contacts=list(points),
                interval_units='actual generated varying-axis and original selected source-curve parameters',
                internal_seams_are_allowed_contacts=False)


def contact(patch=0, key='owner:0', interval=(0., 1.)):
    return dict(surface_index=patch, edge='left', source_key=key,
                native_parameter_interval=list(interval), generated_parameter_interval=[0., 1.])


class NativeOwnerScreenTests(unittest.TestCase):
    def setUp(self):
        self.adapter = Adapter(); self.owner = Geometry('owner'); self.patch = Geometry('patch')
        self.context = n.NativeOwnerContext([n.OwnerSnapshot('owner', self.owner,
            (n.SelectedSpan('owner:0', 0, (0., 1.)),))], {'source': 1}, .001, self.adapter)
        self.addCleanup(self.context.dispose)
    def screen(self, contacts=None, patches=None, request=None):
        return n.screen_native_owners(patches or [self.patch], self.context,
                                      ledger() if contacts is None else contacts, request)
    def test_empty_brep_result_still_runs_bidirectional_complement(self):
        result = self.screen(); report = result.report
        self.assertTrue(report['checked']); self.assertFalse(report['global_injectivity_certified'])
        self.assertEqual((report['expected_pairs'], report['completed_pairs']), (1, 1))
        self.assertEqual(report['boundary_screens'], 2)
        self.assertEqual(report['interior_queries'], 2)
        self.assertTrue(n.verify_receipt(result, [self.patch], self.context, ledger()))
    def test_coincident_interior_rejects_despite_empty_brep_result(self):
        self.adapter.distances[((1., 1., 1.), 'owner')] = 0.
        with self.assertRaisesRegex(n.SeparationError, 'OWNER_INTERIOR_OVERLAP'): self.screen()
    def test_reciprocal_containment_is_screened(self):
        self.adapter.distances[((1., 1., 1.), 'patch')] = 0.
        with self.assertRaisesRegex(n.SeparationError, 'OWNER_INTERIOR_OVERLAP'): self.screen()
    def test_conservative_bbox_prunes_complete_pair(self):
        self.patch.bbox = ((4., 4., 4.), (5., 5., 5.))
        report = self.screen().report
        self.assertEqual(report['completed_pairs'], 1); self.assertEqual(report['bbox_pruned_pairs'], 1)
        self.assertFalse(any(call[0] == 'brep' for call in self.adapter.calls))
    def test_near_boxes_are_not_pruned(self):
        self.patch.bbox = ((2.0005, 0., 0.), (4., 2., 2.))
        self.assertEqual(self.screen().report['intersection_pairs'], 1)
    def test_all_pairs_including_other_owners(self):
        other = Geometry('other')
        self.context = n.NativeOwnerContext(self.context.owners +
            (n.OwnerSnapshot('other', other, (n.SelectedSpan('other:0', 0, (0.,1.)),)),),
            {'source':1}, .001, self.adapter)
        self.addCleanup(self.context.dispose)
        report = self.screen(patches=[self.patch, Geometry('patch2')]).report
        self.assertEqual(report['completed_pairs'], 4)
        self.assertEqual(report['intersection_pairs'], 4)
    def test_forbidden_native_curve_disposed(self):
        curve = Curve('hit'); self.adapter.brep_results['patch', 'owner'] = ([curve], [])
        with self.assertRaisesRegex(n.SeparationError, 'FORBIDDEN'): self.screen()
        self.assertTrue(curve.disposed)
    def test_whole_curve_contact_requires_both_bindings(self):
        for boundary in ('source:owner:0', 'generated:patch'):
            self.adapter.overlap_results['hit', boundary] = [(0., 1.)]
        self.adapter.brep_results['patch','owner'] = ([Curve('hit')], [])
        result = self.screen(ledger([contact()]))
        self.assertEqual(result.report['curve_events'], 1)
    def test_positive_interval_gap_never_excused(self):
        self.adapter.overlap_results['hit', 'source:owner:0'] = [(0., .5), (.50000000000001, 1.)]
        self.adapter.overlap_results['hit', 'generated:patch'] = [(0., 1.)]
        self.adapter.brep_results['patch','owner'] = ([Curve('hit')], [])
        with self.assertRaisesRegex(n.SeparationError, 'FORBIDDEN'): self.screen(ledger([contact()]))
    def test_wrong_pair_cannot_combine_source_and_generated_coverage(self):
        self.adapter.overlap_results['hit', 'source:owner:0'] = [(0., .5)]
        self.adapter.overlap_results['hit', 'generated:patch'] = [(.5, 1.)]
        self.adapter.brep_results['patch','owner'] = ([Curve('hit')], [])
        with self.assertRaisesRegex(n.SeparationError, 'FORBIDDEN'): self.screen(ledger([contact()]))
    def test_boundary_curve_overlap_complement_rejects(self):
        self.adapter.curve_results['patch.edge', 'owner'] = ([Curve('overlap')], [])
        with self.assertRaisesRegex(n.SeparationError, 'FORBIDDEN'): self.screen()
    def test_point_requires_same_source_and_generated_binding(self):
        point = (0.,0.,0.); self.adapter.brep_results['patch','owner'] = ([], [point])
        self.adapter.point_membership[point, 'source:owner:0'] = True
        with self.assertRaisesRegex(n.SeparationError, 'FORBIDDEN'): self.screen(ledger([contact()]))
        self.adapter.point_membership[point, 'generated:patch'] = True
        self.assertTrue(self.screen(ledger([contact()])).report['checked'])
    def test_isolated_corner_contact_never_authorizes_curve(self):
        other = Geometry('patch2'); point = (0.,0.,0.)
        points = [dict(surface_index=1, generated_uv=[0.,0.], source_key='owner:0', native_parameter=0.)]
        data = ledger([contact()], points)
        self.adapter.brep_results['patch2','owner'] = ([], [point])
        self.assertTrue(self.screen(data, [self.patch, other]).report['checked'])
        self.adapter.brep_results['patch2','owner'] = ([Curve('internal-seam')], [])
        with self.assertRaisesRegex(n.SeparationError, 'FORBIDDEN'): self.screen(data, [self.patch, other])
    def test_unknown_selected_source_and_fake_endpoint_reject(self):
        with self.assertRaisesRegex(n.SeparationError, 'selected native'): self.screen(ledger([contact(key='owner:9')]))
        point = dict(surface_index=0, generated_uv=[0.,0.], source_key='owner:0', native_parameter=.5)
        with self.assertRaisesRegex(n.SeparationError, 'checked exterior-trace endpoint'): self.screen(ledger([contact()], [point]))
    def test_reversed_native_parameter_interval_is_supported(self):
        self.assertTrue(self.screen(ledger([contact(interval=(1.,0.))])).report['checked'])
    def test_receipt_is_not_a_result_dictionary(self):
        with self.assertRaisesRegex(n.SeparationError, 'in-process'): n.verify_receipt({'checked':True}, [self.patch], self.context, ledger())
    def test_changed_request_geometry_contacts_and_source_invalidate(self):
        result = self.screen(request={'revision':1})
        with self.assertRaisesRegex(n.SeparationError, 'changed after'): n.verify_receipt(result, [self.patch], self.context, ledger(), {'revision':2})
        self.patch.version += 1
        with self.assertRaisesRegex(n.SeparationError, 'changed after'): n.verify_receipt(result, [self.patch], self.context, ledger(), {'revision':1})
        self.patch.version -= 1
        self.owner.version += 1
        with self.assertRaisesRegex(n.SeparationError, 'immutable copied owner'): n.verify_receipt(result, [self.patch], self.context, ledger(), {'revision':1})
    def test_cached_owner_preparation_reused_but_mutation_rejects(self):
        self.screen(); self.screen()
        self.assertEqual(sum(x == ('prepare','owner') for x in self.adapter.calls), 1)
        self.owner.version += 1
        with self.assertRaisesRegex(n.SeparationError, 'immutable copied owner'): self.screen()
    def test_geometry_change_during_native_screen_rejects(self):
        self.adapter.after_events = lambda: setattr(self.patch, 'version', 1)
        with self.assertRaisesRegex(n.SeparationError, 'changed while screening'): self.screen()
    def test_cancellation_has_no_receipt(self):
        with self.assertRaisesRegex(n.SeparationError, 'CANCELLED'):
            n.screen_native_owners([self.patch], self.context, ledger(), cancelled=lambda:True)
    def test_native_call_and_pair_caps_fail_closed(self):
        self.context.limits = replace(self.context.limits, max_native_calls=1)
        with self.assertRaisesRegex(n.SeparationError, 'BUDGET'): self.screen()
        self.context.limits = replace(self.context.limits, max_native_calls=20000, max_pairs=1)
        with self.assertRaisesRegex(n.SeparationError, 'pair count'): self.screen(patches=[self.patch, Geometry('second')])
    def test_live_source_change_and_disposal_invalidate(self):
        result = self.screen()
        def changed(): raise n.SeparationError('OWNER_SCREEN_STALE','Live source changed')
        self.context.live_check = changed
        with self.assertRaisesRegex(n.SeparationError, 'Live source'): n.verify_receipt(result, [self.patch], self.context, ledger())
        self.context.live_check = None; self.context.dispose()
        with self.assertRaisesRegex(n.SeparationError, 'disposed'): n.verify_receipt(result, [self.patch], self.context, ledger())
    def test_report_is_defensive_copy(self):
        receipt = self.screen(); report = receipt.report; report['checked'] = False
        self.assertTrue(receipt.report['checked'])
    def test_deadline_checked_after_native_call(self):
        t = [0.]; budget = n._Budget(n.ScreenLimits(seconds=1.), clock=lambda:t[0])
        with self.assertRaisesRegex(n.SeparationError, 'between supported'):
            budget.call(lambda: t.__setitem__(0, 2.))



# Rhino-shaped public rectangle fixtures below exercise the REAL adapter code.
# Their analytic intersection/closest-point implementation is still a mock.
from types import SimpleNamespace
import math


class NativePoint:
    def __init__(self, x, y, z=0.): self.X, self.Y, self.Z = float(x), float(y), float(z)


class NativeInterval:
    def __init__(self, a, b): self.T0, self.T1 = a, b


class NativeItems(list):
    @property
    def Count(self): return len(self)


class NativeNurbs:
    def __init__(self, surface=False):
        self.Points = SimpleNamespace(Count=2, CountU=2, CountV=2)
        self.Degree = (lambda axis: 1) if surface else 1
        self.disposed = False
    def Dispose(self): self.disposed = True


class NativeLine:
    IsValid = True; Valence = 'Naked'
    def __init__(self, a, b, domain=(0.,1.)):
        self.a, self.b = tuple(a), tuple(b); self.Domain = NativeInterval(*domain); self.disposed = False
    def Dispose(self): self.disposed = True
    def TrimIndices(self): return [getattr(self,'EdgeIndex',0)]
    def DuplicateCurve(self): return NativeLine(self.a, self.b, (self.Domain.T0,self.Domain.T1))
    def ToNurbsCurve(self): return NativeNurbs()
    def PointAt(self, t):
        f = (t-self.Domain.T0)/(self.Domain.T1-self.Domain.T0)
        return NativePoint(*(a+(b-a)*f for a,b in zip(self.a,self.b)))
    def Trim(self, a, b): return NativeLine(xyz(self.PointAt(a)), xyz(self.PointAt(b)), (a,b))
    def TangentAt(self, parameter):return NativePoint(*(b-a for a,b in zip(self.a,self.b)))
    def ClosestPoint(self, point):
        p=xyz(point); d=[b-a for a,b in zip(self.a,self.b)]
        f=max(0.,min(1.,sum((x-a)*v for x,a,v in zip(p,self.a,d))/sum(v*v for v in d)))
        return True, self.Domain.T0+f*(self.Domain.T1-self.Domain.T0)


def xyz(p): return p.X,p.Y,p.Z


class NativeFace:
    FaceIndex=0; OrientationIsReversed=False
    def __init__(self, u=(0.,1.), v=(0.,1.), hole=None): self.u,self.v,self.hole=u,v,hole;self.samples=[]
    def Domain(self, axis): return NativeInterval(*(self.u if axis==0 else self.v))
    def ToNurbsSurface(self): return NativeNurbs(True)
    def PointAt(self, u, v): return NativePoint(u,v,0.)
    def ClosestPoint(self,point):return True,min(self.u[1],max(self.u[0],point.X)),min(self.v[1],max(self.v[0],point.Y))
    def Evaluate(self,u,v,degree):return True,self.PointAt(u,v),[NativePoint(1,0),NativePoint(0,1)]
    def IsPointOnFace(self, u, v, tolerance):
        self.samples.append((u,v))
        if not self.u[0]<=u<=self.u[1] or not self.v[0]<=v<=self.v[1]:return 'Exterior'
        if min(u-self.u[0],self.u[1]-u,v-self.v[0],self.v[1]-v)<=tolerance:return 'Boundary'
        if self.hole and self.hole[0]<u<self.hole[1] and self.hole[2]<v<self.hole[3]: return 'Exterior'
        return 'Interior'
    def IsoCurve(self, axis, constant):
        if axis==0:return NativeLine((self.u[0],constant,0.),(self.u[1],constant,0.),self.u)
        return NativeLine((constant,self.v[0],0.),(constant,self.v[1],0.),self.v)


class NativeTrim:
    def __init__(self,face,edge):self.Face,self.Edge=face,edge
    @property
    def Domain(self):return self.Edge.Domain
    def IsReversed(self):return False
    def ClosestPoint(self,point):return self.Edge.ClosestPoint(point)
    def PointAt(self,t):return self.Edge.PointAt(t)
    def TangentAt(self,t):return self.Edge.TangentAt(t)


class NativeBrep:
    IsValid=True
    IsSolid=False
    def __init__(self, u=(0.,1.), v=(0.,1.), hole=None):
        self.Faces=NativeItems([NativeFace(u,v,hole)]);self.disposed=False
        self.Trims=NativeItems([SimpleNamespace(Face=self.Faces[0])])
        self.Edges=NativeItems([NativeLine((u[0],v[0],0.),(u[0],v[1],0.),v),
                               NativeLine((u[1],v[0],0.),(u[1],v[1],0.),v),
                               NativeLine((u[0],v[0],0.),(u[1],v[0],0.),u),
                               NativeLine((u[0],v[1],0.),(u[1],v[1],0.),u)])
        for index,edge in enumerate(self.Edges):edge.EdgeIndex=index
        self.Trims=NativeItems([NativeTrim(self.Faces[0],edge) for edge in self.Edges])
    def Dispose(self): self.disposed=True
    def MemoryEstimate(self): return 256
    def DuplicateBrep(self):
        f=self.Faces[0];return NativeBrep(f.u,f.v,f.hole)
    def ToJSON(self, serialization):
        f=self.Faces[0];return json.dumps([f.u,f.v,f.hole,self.disposed])
    def GetBoundingBox(self, accurate):
        f=self.Faces[0];return SimpleNamespace(IsValid=True,Min=NativePoint(f.u[0],f.v[0]),Max=NativePoint(f.u[1],f.v[1]))
    def ClosestPoint(self, point, maximumDistance):
        assert maximumDistance==0.0
        f=self.Faces[0];x=min(f.u[1],max(f.u[0],point.X));y=min(f.v[1],max(f.v[0],point.Y));kind='BrepFace'
        if x in f.u or y in f.v:kind='BrepEdge'
        if f.hole and f.hole[0]<x<f.hole[1] and f.hole[2]<y<f.hole[3]:
            candidates=[(f.hole[0],y),(f.hole[1],y),(x,f.hole[2]),(x,f.hole[3])]
            x,y=min(candidates,key=lambda p:(p[0]-point.X)**2+(p[1]-point.Y)**2);kind='BrepEdge'
        index=(0 if x==f.u[0] else 1 if x==f.u[1] else 2 if y==f.v[0] else 3) if kind=='BrepEdge' else 0
        a,b=(y,0.) if kind=='BrepEdge' and index<2 else (x,0.) if kind=='BrepEdge' else (x,y)
        return True,NativePoint(x,y),SimpleNamespace(ComponentIndexType=kind,Index=index),a,b,NativePoint(0,0,1)


class NativeEvents(NativeItems):
    def Dispose(self): self.disposed=True


class NativeIntersector:
    @staticmethod
    def CurveCurve(a,b,tolerance,overlapTolerance):
        events=NativeEvents(); da=[y-x for x,y in zip(a.a,a.b)];db=[y-x for x,y in zip(b.a,b.b)]
        axis=max(range(3),key=lambda i:abs(da[i]))
        if any(abs(da[i]*db[axis]-db[i]*da[axis])>1e-12 for i in range(3)):return events
        if any(abs((b.a[i]-a.a[i])*da[axis]-(b.a[axis]-a.a[axis])*da[i])>1e-12 for i in range(3)):return events
        ts=[a.Domain.T0+(p[axis]-a.a[axis])/da[axis]*(a.Domain.T1-a.Domain.T0) for p in (b.a,b.b)]
        lo=max(a.Domain.T0,min(ts));hi=min(a.Domain.T1,max(ts))
        if lo<hi:events.append(SimpleNamespace(IsOverlap=True,IsPoint=False,OverlapA=NativeInterval(lo,hi)))
        return events
    @staticmethod
    def CurveBrep(curve,brep,tolerance):
        f=brep.Faces[0];lo,hi=0.,1.
        for axis,domain in enumerate((f.u,f.v)):
            delta=curve.b[axis]-curve.a[axis]
            if delta==0:
                if not domain[0]<=curve.a[axis]<=domain[1]:return True,[],[]
                continue
            a,b=sorted(((domain[0]-curve.a[axis])/delta,(domain[1]-curve.a[axis])/delta))
            lo=max(lo,a);hi=min(hi,b)
        if lo>hi:return True,[],[]
        a=curve.Domain.T0+lo*(curve.Domain.T1-curve.Domain.T0);b=curve.Domain.T0+hi*(curve.Domain.T1-curve.Domain.T0)
        if lo==hi:return True,[],[curve.PointAt(a)]
        return True,[curve.Trim(a,b)],[]
    @staticmethod
    def BrepBrep(a,b,tolerance,join):
        assert join is False
        fa,fb=a.Faces[0],b.Faces[0]
        u=(max(fa.u[0],fb.u[0]),min(fa.u[1],fb.u[1]));v=(max(fa.v[0],fb.v[0]),min(fa.v[1],fb.v[1]))
        if u[0]>u[1] or v[0]>v[1]:return True,[],[]
        if u[0]==u[1] and v[0]==v[1]:return True,[],[NativePoint(u[0],v[0])]
        if u[0]==u[1]:return True,[NativeLine((u[0],v[0],0.),(u[0],v[1],0.),v)],[]
        if v[0]==v[1]:return True,[NativeLine((u[0],v[0],0.),(u[1],v[0],0.),u)],[]
        return True,[],[]  # Deliberately simulate missing coincident-area event output.


def native_adapter():
    return n.RhinoAdapter(SimpleNamespace(Geometry=SimpleNamespace(Brep=NativeBrep,Point3d=NativePoint,Intersect=SimpleNamespace(Intersection=NativeIntersector)),
                           FileIO=SimpleNamespace(SerializationOptions=lambda:SimpleNamespace())))


class RhinoAdapterSyntheticTests(unittest.TestCase):
    def test_fingerprints_include_userdata_but_exclude_runtime_mesh_caches(self):
        options=native_adapter().serialization
        self.assertTrue(options.WriteUserData)
        self.assertFalse(options.WriteRenderMeshes)
        self.assertFalse(options.WriteAnalysisMeshes)
    def test_adjacent_rectangles_with_exact_shared_edge_pass_adapter(self):
        owner=NativeBrep((-1.,0.));patch=NativeBrep();adapter=native_adapter()
        context=n.NativeOwnerContext([n.OwnerSnapshot('owner',owner,(n.SelectedSpan('owner:1',1,(0.,1.)),))],{},.001,adapter)
        self.addCleanup(context.dispose)
        receipt=n.screen_native_owners([patch],context,ledger([contact(key='owner:1')]))
        self.assertTrue(receipt.report['checked']);self.assertGreater(receipt.report['interior_queries'],0)
        self.assertTrue(n.verify_receipt(receipt,[patch],context,ledger([contact(key='owner:1')])))
    def test_empty_intersector_does_not_pass_identical_surfaces(self):
        owner=NativeBrep();patch=NativeBrep();adapter=native_adapter()
        context=n.NativeOwnerContext([n.OwnerSnapshot('owner',owner,(n.SelectedSpan('owner:0',0,(0.,1.)),))],{},.001,adapter)
        self.addCleanup(context.dispose)
        with self.assertRaisesRegex(n.SeparationError,'FORBIDDEN|INTERIOR_OVERLAP'):
            n.screen_native_owners([patch],context,ledger([contact()]))
    def test_trim_hole_witnesses_are_excluded(self):
        adapter=native_adapter();geometry=NativeBrep(hole=(.2,.8,.2,.8));budget=n._Budget(n.ScreenLimits())
        prepared=adapter.prepare(geometry,.001,budget);self.addCleanup(prepared.dispose)
        self.assertTrue(prepared.witnesses)
        self.assertFalse(any(.2<p.X<.8 and .2<p.Y<.8 for p in prepared.witnesses))
    def test_insufficient_actual_trim_interior_fails(self):
        adapter=native_adapter();geometry=NativeBrep(hole=(-1.,2.,-1.,2.))
        with self.assertRaisesRegex(n.SeparationError,'TRIM_COVERAGE'):
            adapter.prepare(geometry,.001,n._Budget(n.ScreenLimits()))
        self.assertEqual(len(geometry.Faces[0].samples),25+81)
    def test_false_partial_native_result_disposes_curves(self):
        adapter=native_adapter();curve=NativeLine((0.,0.,0.),(1.,0.,0.))
        with self.assertRaisesRegex(n.SeparationError,'partial/unknown'):
            adapter._intersection(lambda:(False,[curve],[]),(),n._Budget(n.ScreenLimits()))
        self.assertTrue(curve.disposed)
    def test_post_call_cancellation_disposes_allocated_native_output(self):
        cancelled=[False];curve=NativeLine((0.,0.,0.),(1.,0.,0.))
        def allocate():cancelled[0]=True;return True,[curve],[]
        with self.assertRaisesRegex(n.SeparationError,'CANCELLED'):
            n._Budget(n.ScreenLimits(),lambda:cancelled[0]).call(allocate)
        self.assertTrue(curve.disposed)
    def test_intersection_output_cap_disposes_all_returned_curves(self):
        adapter=native_adapter();curves=[NativeLine((0.,0.,0.),(1.,0.,0.)) for i in range(2)]
        with self.assertRaisesRegex(n.SeparationError,'event budget'):
            adapter._intersection(lambda:(True,curves,[]),(),n._Budget(n.ScreenLimits(max_events=1)))
        self.assertTrue(all(c.disposed for c in curves))
    def test_curvebrep_four_item_overload_is_validated(self):
        adapter=native_adapter();curve=NativeLine((0.,0.,0.),(1.,0.,0.));point=NativePoint(.5,0.)
        adapter.rg.Intersect.Intersection=SimpleNamespace(CurveBrep=lambda a,b,t:(True,[],[point],[.5]))
        curves,points=adapter.curve_events(curve,NativeBrep(),.001,n._Budget(n.ScreenLimits()))
        self.assertEqual(points,(point,));self.assertEqual(curves,())
        for parameters in (None,[],[float('nan')],[1.1]):
            with self.assertRaisesRegex(n.SeparationError,'CurveBrep'):
                adapter._intersection(lambda:(True,[],[point],parameters),(),n._Budget(n.ScreenLimits()),parameter_curve=curve)
    def test_brepbrep_still_rejects_four_item_result(self):
        with self.assertRaisesRegex(n.SeparationError,'Unexpected Rhino intersection'):
            native_adapter()._intersection(lambda:(True,[],[],[]),(),n._Budget(n.ScreenLimits()))
    def test_closest_point_false_is_failure_not_clearance(self):
        adapter=native_adapter();geometry=NativeBrep();geometry.ClosestPoint=lambda p,d:(False,None,None,0.,0.,None)
        with self.assertRaisesRegex(n.SeparationError,'closest-point query failed'):
            adapter.distance_to_brep(NativePoint(.5,.5),geometry,n._Budget(n.ScreenLimits()))
    def test_isolated_contact_requires_exact_generated_corner(self):
        adapter=native_adapter();owner=NativeBrep((-1.,0.));patch=NativeBrep()
        c=dict(generated_uv=[0.,.5],native_parameter=.5)
        with self.assertRaisesRegex(n.SeparationError,'exact generated atlas corner'):
            adapter.contact_points(patch,owner,n.SelectedSpan('owner:1',1,(0.,1.)),c,.001,n._Budget(n.ScreenLimits()))


class CopiedContextTests(unittest.TestCase):
    def fixture(self):
        geometry=NativeBrep((-1.,0.));obj=SimpleNamespace(Geometry=geometry,IsDeleted=False,RuntimeSerialNumber=2)
        doc=SimpleNamespace(RuntimeSerialNumber=1,ModelAbsoluteTolerance=.001,ModelAngleToleranceRadians=.01,
                            Objects=SimpleNamespace(FindId=lambda key:obj if key=='owner' else None))
        model={'absolute_tolerance':.001,'angle_tolerance':.01,'source_boundaries':{'roles':{'side0':[{'source_key':'owner:1','original_curve_domain':[0.,1.]}]}}}
        capture=SimpleNamespace(model=model,source_proof=[('owner',2,('geometry','attributes'))],verify_sources=lambda doc:(True,''))
        rhino=SimpleNamespace(Geometry=SimpleNamespace(Brep=NativeBrep,Point3d=NativePoint,Intersect=SimpleNamespace(Intersection=NativeIntersector)),
                               FileIO=SimpleNamespace(SerializationOptions=lambda:SimpleNamespace()))
        return geometry,doc,capture,rhino
    def test_factory_copies_full_owner_and_disposes_only_copies(self):
        original,doc,capture,rhino=self.fixture()
        context=n.create_owner_context(doc,capture,rhino)
        self.assertIsNot(context.owners[0].geometry,original)
        self.assertEqual(context.owners[0].selected_spans[0].edge_index,1)
        context.dispose();context.dispose()
        self.assertFalse(original.disposed);self.assertTrue(context.owners[0].geometry.disposed)
    def test_live_tolerance_and_provenance_changes_reject(self):
        original,doc,capture,rhino=self.fixture();context=n.create_owner_context(doc,capture,rhino)
        self.addCleanup(context.dispose)
        doc.ModelAbsoluteTolerance=.002
        with self.assertRaisesRegex(n.SeparationError,'tolerances changed'):context.check_live()
        doc.ModelAbsoluteTolerance=.001;capture.model['source_boundaries']['roles']['side0'][0]['source_key']='other:1'
        with self.assertRaisesRegex(n.SeparationError,'provenance changed'):context.check_live()
    def test_context_creation_rejects_changed_captured_angle(self):
        original,doc,capture,rhino=self.fixture();doc.ModelAngleToleranceRadians=.02
        with self.assertRaisesRegex(n.SeparationError,'tolerances changed'):
            n.create_owner_context(doc,capture,rhino)
    def test_copy_mutation_before_first_screen_rejects(self):
        original,doc,capture,rhino=self.fixture();context=n.create_owner_context(doc,capture,rhino)
        self.addCleanup(context.dispose)
        context.owners[0].geometry.Faces[0].u=(-2.,0.)
        with self.assertRaisesRegex(n.SeparationError,'immutable copied owner'):
            n.screen_native_owners([NativeBrep()],context,ledger([contact(key='owner:1')]))

class AffineFace(NativeFace):
    def __init__(self, u=(0.,1.), v=(0.,1.), ud=(-7.,13.), vd=(100.,1000.)):
        super().__init__(u,v);self.ud,self.vd=ud,vd
    def Domain(self, axis):return NativeInterval(*(self.ud if axis==0 else self.vd))
    def world(self,u,v):
        return (self.u[0]+(u-self.ud[0])/(self.ud[1]-self.ud[0])*(self.u[1]-self.u[0]),
                self.v[0]+(v-self.vd[0])/(self.vd[1]-self.vd[0])*(self.v[1]-self.v[0]))
    def PointAt(self,u,v):return NativePoint(*self.world(u,v))
    def IsPointOnFace(self,u,v,tolerance):return super().IsPointOnFace(*self.world(u,v),tolerance)
    def IsoCurve(self,axis,constant):
        if axis==0:return NativeLine(xyz(self.PointAt(self.ud[0],constant)),xyz(self.PointAt(self.ud[1],constant)),self.ud)
        return NativeLine(xyz(self.PointAt(constant,self.vd[0])),xyz(self.PointAt(constant,self.vd[1])),self.vd)


class RepresentationTests(unittest.TestCase):
    def screen(self,owner,patch,edge_index,edge_name,source_interval,generated_interval):
        key='owner:'+str(edge_index);adapter=native_adapter()
        context=n.NativeOwnerContext([n.OwnerSnapshot('owner',owner,(n.SelectedSpan(key,edge_index,source_interval),))],{},.001,adapter)
        try:
            c=contact(key=key,interval=source_interval);c['edge']=edge_name;c['generated_parameter_interval']=list(generated_interval)
            return n.screen_native_owners([patch],context,ledger([c])).report
        finally:context.dispose()
    def test_generated_affine_reparameterization_keeps_contact(self):
        patch=NativeBrep();patch.Faces[0]=AffineFace()
        self.assertTrue(self.screen(NativeBrep((-1.,0.)),patch,1,'left',(0.,1.),(100.,1000.))['checked'])
    def test_translated_public_rectangles_keep_contact(self):
        self.assertTrue(self.screen(NativeBrep((99.,100.),(-100.,-99.)),NativeBrep((100.,101.),(-100.,-99.)),
                                    1,'left',(-100.,-99.),(-100.,-99.))['checked'])
    def test_quarter_turn_changes_named_edge_without_changing_contact(self):
        self.assertTrue(self.screen(NativeBrep((-1.,0.),(-1.,0.)),NativeBrep((-1.,0.),(0.,1.)),
                                    3,'bottom',(-1.,0.),(-1.,0.))['checked'])
    def test_reversed_selected_edge_keeps_contact_locus(self):
        owner=NativeBrep((-1.,0.));edge=owner.Edges[1];edge.a,edge.b=edge.b,edge.a
        self.assertTrue(self.screen(owner,NativeBrep(),1,'left',(0.,1.),(0.,1.))['checked'])


def captured_side():
    return dict(schema='native-trim-side-v1',face_index=0,trim_index=1,trim_reversed=False,
                face_orientation_reversed=False,edge_inward_cross_sign=1.,corners=[
                    dict(edge_end=0,uv=[0.,0.],exterior_wedge=dict(start_ray=[-1.,0.,0.],sweep_radians=1.5*math.pi,oriented_normal=[0.,0.,1.])),
                    dict(edge_end=1,uv=[0.,1.],frame_contract='separate-edge-trim-v1',adjacent_trim_index=3,adjacent_trim_endpoint=1,adjacent_trim_parameter=0.,adjacent_trim_domain=[-1.,0.],adjacent_trim_inward_cross_sign=-1.,adjacent_inward_conormal=[0.,-1.,0.],exterior_wedge=dict(start_ray=[0.,-1.,0.],sweep_radians=1.5*math.pi,oriented_normal=[0.,0.,1.]))])


class NarrowExteriorTests(unittest.TestCase):
    def fixture(self,side=True):
        owner=NativeBrep((-1.,0.));patch=NativeBrep((0.,.0001));adapter=native_adapter()
        span=n.SelectedSpan('owner:1',1,(0.,1.),json.dumps(captured_side()) if side else None)
        context=n.NativeOwnerContext([n.OwnerSnapshot('owner',owner,(span,))],{},.001,adapter)
        self.addCleanup(context.dispose)
        return owner,patch,adapter,span,context
    def test_width_below_model_tolerance_has_genuine_interior_and_passes(self):
        owner,patch,adapter,span,context=self.fixture()
        self.assertEqual(patch.Faces[0].IsPointOnFace(.00005,.5,.001),'Boundary')
        self.assertEqual(patch.Faces[0].IsPointOnFace(.00005,.5,0.),'Interior')
        report=n.screen_native_owners([patch],context,ledger([contact(key='owner:1')])).report
        self.assertTrue(report['checked']);self.assertEqual(report['exterior_edge_near_witnesses'],25)
        self.assertLess(report['minimum_sampled_clearance'],.001)
    def test_near_edge_requires_captured_side_evidence(self):
        owner,patch,adapter,span,context=self.fixture(False)
        with self.assertRaisesRegex(n.SeparationError,'INTERIOR_OVERLAP'):
            n.screen_native_owners([patch],context,ledger([contact(key='owner:1')]))
    def test_positive_clearance_and_current_contact_are_mandatory(self):
        owner,patch,adapter,span,context=self.fixture();budget=n._Budget(n.ScreenLimits())
        for point,bindings in ((NativePoint(.00001,.5),[]),(NativePoint(0.,.5),[(span,contact(key='owner:1'))])):
            distance,classification=adapter.owner_witness_clearance(point,owner,bindings,[],.001,budget)
            self.assertIsNone(classification)
    def test_approximate_surface_uv_is_remapped_to_exact_selected_trim(self):
        owner,patch,adapter,span,context=self.fixture()
        original=owner.Faces[0].ClosestPoint
        owner.Faces[0].ClosestPoint=lambda p:(True,original(p)[1]-1e-9,original(p)[2])
        distance,classification=adapter.owner_witness_clearance(NativePoint(.00001,.5),owner,[(span,contact(key='owner:1'))],[],.001,n._Budget(n.ScreenLimits()))
        self.assertEqual(classification,'edge_conormal')
    def test_owner_face_interior_still_rejects(self):
        owner,patch,adapter,span,context=self.fixture()
        distance,classification=adapter.owner_witness_clearance(NativePoint(-.00001,.5),owner,[(span,contact(key='owner:1'))],[],.001,n._Budget(n.ScreenLimits()))
        self.assertEqual(distance,0.);self.assertIsNone(classification)
    def test_endpoint_uses_captured_exterior_wedge_not_edge_halfplane(self):
        owner,patch,adapter,span,context=self.fixture()
        point=NativePoint(.00001,1.00001)
        distance,classification=adapter.owner_witness_clearance(point,owner,[(span,contact(key='owner:1'))],[],.001,n._Budget(n.ScreenLimits()))
        self.assertGreater(distance,0.);self.assertEqual(classification,'corner_wedge')
    def test_incident_adjacent_edge_uses_wedge_and_reevaluated_local_frame(self):
        owner,patch,adapter,span,context=self.fixture()
        point=NativePoint(-.0001,1.0001)
        # Nearest point lies in the top adjacent edge interior, not selected
        # edge1. The displacement is INWARD of selected edge1's half-plane.
        self.assertEqual(owner.ClosestPoint(point,0.)[2].Index,3)
        endpoint=dict(surface_index=0,generated_uv=[0.,1.],source_key='owner:1',native_parameter=1.)
        distance,classification=adapter.owner_witness_clearance(point,owner,[],[(span,endpoint)],.001,n._Budget(n.ScreenLimits()))
        self.assertGreater(distance,0.);self.assertEqual(classification,'adjacent_corner_wedge')
        # A vertex wedge alone is insufficient when the local adjacent normal
        # turns over. Re-evaluating the actual closest frame must reject this.
        original=owner.Faces[0].Evaluate
        owner.Faces[0].Evaluate=lambda u,v,n: original(u,v,n) if u==0. else (True,NativePoint(u,v),[NativePoint(1,0),NativePoint(0,-1)])
        distance,classification=adapter.owner_witness_clearance(point,owner,[],[(span,endpoint)],.001,n._Budget(n.ScreenLimits()))
        self.assertIsNone(classification)
    def test_adjacent_proximity_without_exact_corner_binding_rejects(self):
        owner,patch,adapter,span,context=self.fixture()
        distance,classification=adapter.owner_witness_clearance(NativePoint(-.0001,1.0001),owner,[(span,contact(key='owner:1'))],[],.001,n._Budget(n.ScreenLimits()))
        self.assertIsNone(classification)
    def test_exterior_proximity_does_not_authorize_intersection_curve(self):
        owner,patch,adapter,span,context=self.fixture()
        adapter.rg.Intersect.Intersection=SimpleNamespace(BrepBrep=lambda *args:(True,[NativeLine((.5,.2,0.),(.5,.8,0.))],[]),
                                                         CurveCurve=NativeIntersector.CurveCurve,CurveBrep=NativeIntersector.CurveBrep)
        with self.assertRaisesRegex(n.SeparationError,'FORBIDDEN'):
            n.screen_native_owners([patch],context,ledger([contact(key='owner:1')]))


class PolynomialTopTrim(NativeTrim):
    """Public C1 piecewise polynomial trim with a tolerance-consistent bend.

    The endpoint remains exactly on its independent straight3Dedge. A small
    local polynomial produces a nonzero trim/edge tangent angle, without
    substituting private geometry or inconsistent PointAt/TangentAt mocks.
    """
    h=.01
    endpoint_slope=.002
    def jet(self,t):
        if t<=-self.h:return 0.,0.,0.
        a=self.endpoint_slope/(self.h*self.h)
        return a*t*(t+self.h)**2,a*(t+self.h)*(3*t+self.h),a*(6*t+4*self.h)
    def PointAt(self,t):return NativePoint(t,1.+self.jet(t)[0])
    def TangentAt(self,t):
        d=self.jet(t)[1];length=math.sqrt(1.+d*d)
        return NativePoint(1./length,d/length)
    def ClosestPoint(self,point):
        t=min(0.,max(-1.,point.X))
        for unused in range(8):
            y,d,dd=self.jet(t);error=1.+y-point.Y
            t=min(0.,max(-1.,t-((t-point.X)+error*d)/(1.+d*d+error*dd)))
        return True,t


class ReversedNativeTrim(NativeTrim):
    def IsReversed(self):return True
    def PointAt(self,t):return self.Edge.PointAt(self.Domain.T0+self.Domain.T1-t)
    def TangentAt(self,t):
        direction=self.Edge.TangentAt(t);return NativePoint(-direction.X,-direction.Y,-direction.Z)
    def ClosestPoint(self,point):
        ok,t=self.Edge.ClosestPoint(point);return ok,self.Domain.T0+self.Domain.T1-t


class PairedEdgeTrimFrameTests(unittest.TestCase):
    def fixture(self):
        owner=NativeBrep((-1.,0.));adapter=native_adapter()
        trim=PolynomialTopTrim(owner.Faces[0],owner.Edges[3]);owner.Trims[3]=trim
        side=captured_side();corner=side['corners'][1]
        slope=trim.endpoint_slope;length=math.sqrt(1.+slope*slope)
        corner['adjacent_inward_conormal']=[slope/length,-1./length,0.]
        corner['exterior_wedge']['sweep_radians']=1.5*math.pi+math.atan(slope)
        span=n.SelectedSpan('owner:1',1,(0.,1.),json.dumps(side))
        point_contact=dict(surface_index=0,generated_uv=[0.,1.],source_key='owner:1',native_parameter=1.)
        return owner,adapter,trim,side,span,point_contact
    def classify(self,owner,adapter,span,point_contact):
        return adapter.owner_witness_clearance(NativePoint(-.0001,1.0001),owner,[],[(span,point_contact)],.001,n._Budget(n.ScreenLimits()))[1]
    def test_actual_trim_frame_accepts_tolerance_consistent_endpoint_tangent_difference(self):
        owner,adapter,trim,side,span,point_contact=self.fixture()
        self.assertEqual(xyz(trim.PointAt(0.)),xyz(owner.Edges[3].PointAt(0.)))
        self.assertLess(abs(trim.jet(-trim.h/3.)[0]),.001*.05)
        # The previous mixed-frame near-unit comparison would fail.
        self.assertLess(abs(side['corners'][1]['adjacent_inward_conormal'][1]),1.-1e-8)
        self.assertEqual(self.classify(owner,adapter,span,point_contact),'adjacent_corner_wedge')
    def test_exact_edge_conormal_cannot_replace_actual_trim_occupancy_frame(self):
        owner,adapter,trim,side,span,point_contact=self.fixture()
        side['corners'][1]['adjacent_inward_conormal']=[0.,-1.,0.]
        span=n.SelectedSpan('owner:1',1,(0.,1.),json.dumps(side))
        self.assertIsNone(self.classify(owner,adapter,span,point_contact))
    def test_adjacent_trim_sign_domain_endpoint_and_contract_are_required(self):
        for key,value in [('adjacent_trim_inward_cross_sign',1.),('adjacent_trim_parameter',-1.),
                          ('adjacent_trim_endpoint',0),('adjacent_trim_domain',[-2.,0.]),
                          ('frame_contract','mixed-frames')]:
            owner,adapter,trim,side,span,point_contact=self.fixture()
            side['corners'][1][key]=value;span=n.SelectedSpan('owner:1',1,(0.,1.),json.dumps(side))
            self.assertIsNone(self.classify(owner,adapter,span,point_contact),key)
    def test_current_trim_frame_is_rechecked_not_replaced_by_endpoint_frame(self):
        owner,adapter,trim,side,span,point_contact=self.fixture();original=trim.TangentAt
        def changed(t):
            p=original(t);return p if t==0. else NativePoint(-p.X,-p.Y,-p.Z)
        trim.TangentAt=changed
        self.assertIsNone(self.classify(owner,adapter,span,point_contact))
    def test_smooth_occupancy_origin_is_actual_trim_not_offset_exact_edge(self):
        owner=NativeBrep((-1.,0.));adapter=native_adapter();trim=owner.Trims[1]
        shift=1e-5
        trim.PointAt=lambda t:NativePoint(shift,t)
        # The underlying plane extends beyond its trimmed region.
        owner.Faces[0].Domain=lambda axis:NativeInterval(-1.,1.) if axis==0 else NativeInterval(0.,1.)
        span=n.SelectedSpan('owner:1',1,(0.,1.),json.dumps(captured_side()))
        for x,expected in ((shift*.5,None),(shift,None),(shift*2.,'edge_conormal')):
            result=adapter.owner_witness_clearance(NativePoint(x,.5),owner,[(span,contact(key='owner:1'))],[],.001,n._Budget(n.ScreenLimits()))
            self.assertEqual(result[1],expected)
    def test_adjacent_occupancy_origin_is_current_actual_trim_point(self):
        owner,adapter,trim,side,span,point_contact=self.fixture()
        x=-.0001;offset=trim.jet(x)[0]
        # The native3Dedge and actual surface trim need not have the same
        # point within their existing representation tolerance. Simulate a
        # native closest result anchored to its3Dedge, as the contract allows.
        original=owner.ClosestPoint
        def edge_anchor(point,maximum):
            return True,NativePoint(x,1.),SimpleNamespace(ComponentIndexType='BrepEdge',Index=3),x,0.,NativePoint(1,0)
        owner.ClosestPoint=edge_anchor
        result=adapter.owner_witness_clearance(NativePoint(x,1.+offset*.5),owner,[],[(span,point_contact)],.001,n._Budget(n.ScreenLimits()))
        self.assertEqual(result[1],'adjacent_corner_wedge')
        result=adapter.owner_witness_clearance(NativePoint(x,1.+offset*1.5),owner,[],[(span,point_contact)],.001,n._Budget(n.ScreenLimits()))
        self.assertIsNone(result[1])
    def test_smooth_occupancy_respects_captured_and_live_trim_reversal(self):
        owner=NativeBrep((-1.,0.));adapter=native_adapter();owner.Trims[1]=ReversedNativeTrim(owner.Faces[0],owner.Edges[1])
        side=captured_side();side['trim_reversed']=True
        span=n.SelectedSpan('owner:1',1,(0.,1.),json.dumps(side))
        result=adapter.owner_witness_clearance(NativePoint(.00001,.5),owner,[(span,contact(key='owner:1'))],[],.001,n._Budget(n.ScreenLimits()))
        self.assertEqual(result[1],'edge_conormal')
        side['trim_reversed']=False;span=n.SelectedSpan('owner:1',1,(0.,1.),json.dumps(side))
        self.assertIsNone(adapter.owner_witness_clearance(NativePoint(.00001,.5),owner,[(span,contact(key='owner:1'))],[],.001,n._Budget(n.ScreenLimits()))[1])


class LazyArchiveBrep(NativeBrep):
    """Model only the two reproduced lazy fields plus unknown drift."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.bbox_cache=0;self.solid_cache=0;self.other_cache=0
        self.userdata={};self.orientation=False;self.trim_definition=0;self.control_value=0.
    def GetBoundingBox(self,accurate):
        self.bbox_cache=1
        return super().GetBoundingBox(accurate)
    @property
    def IsSolid(self):
        self.solid_cache=3
        return False
    def ToJSON(self,serialization):
        return json.dumps(dict(geometry=json.loads(super().ToJSON(serialization)),
             bbox_cache=self.bbox_cache,solid_cache=self.solid_cache,other_cache=self.other_cache,
             userdata=self.userdata,orientation=self.orientation,trim_definition=self.trim_definition,control_value=self.control_value))


class FingerprintCacheTests(unittest.TestCase):
    def test_reproduced_lazy_reads_are_primed_before_first_fingerprint(self):
        adapter=native_adapter();geometry=LazyArchiveBrep();options=adapter.serialization
        cold=n._hash(geometry.ToJSON(options));geometry.GetBoundingBox(True)
        self.assertNotEqual(cold,n._hash(geometry.ToJSON(options)))
        geometry=LazyArchiveBrep()
        first=adapter.fingerprint(geometry,n._Budget(n.ScreenLimits()))
        self.assertEqual((geometry.bbox_cache,geometry.solid_cache),(1,3))
        geometry.GetBoundingBox(True);unused=geometry.IsSolid
        self.assertEqual(first,adapter.fingerprint(geometry,n._Budget(n.ScreenLimits())))
    def test_full_screen_preserves_converter_fingerprint_after_read_only_prepare(self):
        adapter=native_adapter();owner=LazyArchiveBrep((-1.,0.));patch=LazyArchiveBrep()
        context=n.NativeOwnerContext([n.OwnerSnapshot('owner',owner,(n.SelectedSpan('owner:1',1,(0.,1.)),))],{},.001,adapter)
        self.addCleanup(context.dispose)
        converter_hash=adapter.fingerprint(patch,n._Budget(n.ScreenLimits()))
        data=ledger([contact(key='owner:1')])
        receipt=n.screen_native_owners([patch],context,data)
        self.assertTrue(n.verify_receipt(receipt,[patch],context,data))
        self.assertEqual(converter_hash,adapter.fingerprint(patch,n._Budget(n.ScreenLimits())))
    def test_full_serialization_still_detects_definition_orientation_trim_and_userdata(self):
        for field,value in [('control_value',.125),('orientation',True),('trim_definition',1),('userdata',{'test':'changed'})]:
            adapter=native_adapter();geometry=LazyArchiveBrep()
            before=adapter.fingerprint(geometry,n._Budget(n.ScreenLimits()))
            setattr(geometry,field,value)
            self.assertNotEqual(before,adapter.fingerprint(geometry,n._Budget(n.ScreenLimits())),field)
    def test_unknown_archive_drift_still_blocks_with_patch_component(self):
        adapter=native_adapter();owner=LazyArchiveBrep((-1.,0.));patch=LazyArchiveBrep()
        context=n.NativeOwnerContext([n.OwnerSnapshot('owner',owner,(n.SelectedSpan('owner:1',1,(0.,1.)),))],{},.001,adapter)
        self.addCleanup(context.dispose)
        def hit(*args):
            patch.other_cache=1
            return NativeIntersector.BrepBrep(*args)
        adapter.rg.Intersect.Intersection=SimpleNamespace(BrepBrep=hit,CurveBrep=NativeIntersector.CurveBrep,CurveCurve=NativeIntersector.CurveCurve)
        with self.assertRaisesRegex(n.SeparationError,'components=generated_patch_archives;patch_indices_0based=0'):
            n.screen_native_owners([patch],context,ledger([contact(key='owner:1')]))
    def test_receipt_reports_request_contact_limit_and_patch_components_without_payload(self):
        adapter=Adapter();owner=Geometry('owner');patch=Geometry('patch')
        context=n.NativeOwnerContext([n.OwnerSnapshot('private-owner-id',owner,(n.SelectedSpan('owner:0',0,(0.,1.)),))],{},.001,adapter)
        self.addCleanup(context.dispose)
        request={'revision':1};data=ledger();receipt=n.screen_native_owners([patch],context,data,request)
        variants=[('request',dict(request={'revision':2})),
                  ('contacts',dict(data={**data,'geometry_digest':'private-changed-descriptor'}))]
        for component,change in variants:
            with self.assertRaises(n.SeparationError) as caught:
                n.verify_receipt(receipt,[patch],context,change.get('data',data),change.get('request',request))
            text=str(caught.exception)
            self.assertIn('components='+component,text);self.assertNotIn('private-',text)
        context.limits=replace(context.limits,max_events=context.limits.max_events+1)
        with self.assertRaisesRegex(n.SeparationError,'components=limits'):
            n.verify_receipt(receipt,[patch],context,data,request)
    def test_snapshot_integrity_cannot_be_bypassed_by_changing_only_receipt_digest(self):
        adapter=Adapter();owner=Geometry('owner');patch=Geometry('patch')
        context=n.NativeOwnerContext([n.OwnerSnapshot('owner',owner,(n.SelectedSpan('owner:0',0,(0.,1.)),))],{},.001,adapter)
        self.addCleanup(context.dispose)
        receipt=n.screen_native_owners([patch],context,ledger())
        with self.assertRaisesRegex(n.SeparationError,'receipt_integrity'):
            n.verify_receipt(replace(receipt,_digest='changed'),[patch],context,ledger())


if __name__ == '__main__': unittest.main()
