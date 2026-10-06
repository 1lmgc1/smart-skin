"""Synthetic native-API mocks only: NOT VERIFIED in licensed Rhino or its GUI.

These tests exercise bounded classification and the serialized record contract.
They do not assert RhinoCommon's Python binding behavior or native tolerances.
All fixtures below are redistributable synthetic polygons, not user geometry.
"""
import copy
import math
import pathlib
import sys
import unittest
import numpy as np

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'src/SmartSkin.Rhino8/Python'))
from native_input import _capture_owner_side, _edge_probe_parameters, _SideBudget, InputCancelled
from native_family import UnsupportedFamily


class Point:
    def __init__(self,x,y,z=0.):self.X,self.Y,self.Z=map(float,(x,y,z))


class Domain:
    def __init__(self,a,b):self.T0,self.T1=float(a),float(b)
    def ParameterAt(self,f):return self.T0+(self.T1-self.T0)*f


class Items(list):
    @property
    def Count(self):return len(self)


def inside(point,polygon):
    x,y=point;result=False
    for a,b in zip(polygon,np.roll(polygon,-1,axis=0)):
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:result=not result
    return result


class Face:
    FaceIndex=13
    OrientationIsReversed=False
    def __init__(self,outer,holes=(),jac=None,origin=None,domains=None):
        self.jac=np.array([[1.,0.],[0.,1.],[0.,0.]]) if jac is None else np.asarray(jac,float)
        self.origin=np.zeros(3) if origin is None else np.asarray(origin,float)
        self.outer=np.asarray(outer,float);self.holes=[np.asarray(h,float) for h in holes]
        self.domains=domains or [Domain(-10,10),Domain(-10,10)]
        self.calls=[];self.point_calls=[];self.forced_relation=None
    def Domain(self,k):return self.domains[k]
    def IsClosed(self,k):return False
    def IsPeriodic(self,k):return False
    def world(self,u,v):return self.origin+self.jac@np.array([u,v])
    def PointAt(self,u,v):
        if any(not self.domains[k].T0<=q<=self.domains[k].T1 for k,q in enumerate((u,v))):
            raise AssertionError('PointAt must never evaluate outside the underlying domain')
        self.point_calls.append((u,v))
        return Point(*self.world(u,v))
    def Evaluate(self,u,v,n):
        assert n==1
        return True,self.PointAt(u,v),[Point(*self.jac[:,0]),Point(*self.jac[:,1])]
    def IsPointOnFace(self,u,v,tolerance):
        self.calls.append((u,v,tolerance))
        if self.forced_relation:return self.forced_relation
        if any(not self.domains[k].T0<=q<=self.domains[k].T1 for k,q in enumerate((u,v))):return 'Exterior'
        p=self.world(u,v)
        for polygon in [self.outer]+self.holes:
            for a,b in zip(polygon,np.roll(polygon,-1,axis=0)):
                x,y=self.world(*a),self.world(*b);d=y-x
                if np.linalg.norm(d)==0:continue
                t=np.clip((p-x)@d/(d@d),0.,1.)
                if np.linalg.norm(p-(x+t*d))<=tolerance:return 'Boundary'
        return 'Interior' if inside((u,v),self.outer) and not any(inside((u,v),h) for h in self.holes) else 'Exterior'


class CurvedFace(Face):
    # Synthetic analytic parabolic cylinder. Classification remains a mock;
    # only the exact point/derivative and physical retry behavior are tested.
    bend=3.
    def world(self,u,v):return np.array([u,v,self.bend*v*v])
    def Evaluate(self,u,v,n):
        assert n==1
        return True,self.PointAt(u,v),[Point(1,0,0),Point(0,1,2*self.bend*v)]


class Edge:
    Domain=Domain(-7,3)
    def __init__(self,trim,reversed=False):self.trim=trim;self.reversed=reversed;self.parameter_scale=1.
    def PointAt(self,t):
        f=(t-self.Domain.T0)/(self.Domain.T1-self.Domain.T0)
        f=f/(self.parameter_scale+(1.-self.parameter_scale)*f)
        if self.reversed:f=1.-f
        q=self.trim.a+f*(self.trim.b-self.trim.a)
        return Point(*self.trim.Face.world(*q))
    def NormalizedLengthParameter(self,fraction):
        a=self.parameter_scale
        return True,self.Domain.ParameterAt(a*fraction/(1.-(1.-a)*fraction))
    def TangentAt(self,t):
        d=self.trim.Face.jac@(self.trim.b-self.trim.a)
        return Point(*(-d if self.reversed else d))
    def GetLength(self):return float(np.linalg.norm(self.trim.Face.jac@(self.trim.b-self.trim.a)))


class Trim:
    Domain=Domain(4,9)
    def __init__(self,a,b,index,face):
        self.a,self.b=np.asarray(a,float),np.asarray(b,float)
        self.TrimIndex=index;self.Face=face;self.Edge=Edge(self);self.Loop=None
    def IsReversed(self):return self.Edge.reversed
    def PointAt(self,t):
        f=(t-self.Domain.T0)/(self.Domain.T1-self.Domain.T0)
        return Point(*(self.a+f*(self.b-self.a)))
    def TangentAt(self,t):return Point(*(self.b-self.a))


class Loop:
    LoopIndex=23
    def __init__(self,polygon,face):
        self.Trims=Items(Trim(a,b,i+31,face) for i,(a,b) in enumerate(zip(polygon,np.roll(polygon,-1,axis=0))))
        for trim in self.Trims:trim.Loop=self


def fixture(polygon=None,holes=(),jac=None,origin=None,domains=None,index=0):
    polygon=np.asarray(polygon if polygon is not None else [[0,0],[2,0],[2,2],[0,2]],float)
    face=Face(polygon,holes,jac,origin,domains)
    loop=Loop(polygon,face)
    trim=loop.Trims[index]
    return face,trim,trim.Edge


def capture(face,trim,edge,tolerance=1e-5,budget=None):
    samples=[]
    budget=budget or _SideBudget(seconds=60.)
    for t,f in _edge_probe_parameters(edge,budget):
        tf=1.-f if edge.reversed else f
        q=trim.PointAt(trim.Domain.ParameterAt(tf));p=edge.PointAt(t)
        samples.append(dict(edge_parameter=t,edge_fraction=(t-edge.Domain.T0)/(edge.Domain.T1-edge.Domain.T0),
                            edge_arc_fraction=f,trim_parameter=trim.Domain.ParameterAt(tf),
                            uv=[q.X,q.Y],point=[p.X,p.Y,p.Z]))
    return _capture_owner_side(edge,trim,face,tolerance,samples,budget)


def wedge_contains(corner,direction):
    wedge=corner['exterior_wedge'];n=np.asarray(wedge['oriented_normal']);a=np.asarray(wedge['start_ray'])
    d=np.asarray(direction,float);d/=np.linalg.norm(d)
    angle=math.atan2(float(d@np.cross(n,a)),float(d@a))%(2.*math.pi)
    return angle<float(wedge['sweep_radians'])


class NativeAttachmentSideMocks(unittest.TestCase):
    def test_signed_face_side_and_adjacent_corner_contract(self):
        face,trim,edge=fixture();before=copy.deepcopy((face.outer,trim.a,trim.b))
        record=capture(face,trim,edge)
        self.assertEqual(record['schema'],'native-trim-side-v1')
        self.assertEqual((record['face_index'],record['trim_index'],record['loop_index']),(13,31,23))
        self.assertEqual(len(record['samples']),15)
        self.assertEqual(len(record['corners']),2)
        for sample in record['samples']:
            np.testing.assert_allclose(sample['inward_conormal'],[0,1,0])
            self.assertEqual([p['relation'] for p in sample['probes']],['Interior','Exterior']*2)
        for corner in record['corners']:
            self.assertAlmostEqual(corner['exterior_wedge']['sweep_radians'],1.5*math.pi)
            self.assertTrue(wedge_contains(corner,[0,-1,0]))
        for a,b in zip(before,(face.outer,trim.a,trim.b)):np.testing.assert_array_equal(a,b)

    def test_native_edge_reversal_does_not_flip_owner_side(self):
        face,trim,edge=fixture();a=capture(face,trim,edge);edge.reversed=True;b=capture(face,trim,edge)
        self.assertTrue(b['trim_reversed'])
        for x,y in zip(a['samples'],reversed(b['samples'])):
            np.testing.assert_allclose(x['point'],y['point']);np.testing.assert_allclose(x['inward_conormal'],y['inward_conormal'])
        for x,y in zip(a['corners'],reversed(b['corners'])):
            for key in ('point','inward_conormal','trim_ray','adjacent_ray'):np.testing.assert_allclose(x[key],y[key])

    def test_reversed_face_orientation_changes_normal_only(self):
        face,trim,edge=fixture();a=capture(face,trim,edge);face.OrientationIsReversed=True;b=capture(face,trim,edge)
        for x,y in zip(a['samples'],b['samples']):
            np.testing.assert_allclose(x['oriented_normal'],-np.asarray(y['oriented_normal']))
            np.testing.assert_allclose(x['inward_conormal'],y['inward_conormal'])
        for corner in b['corners']:self.assertTrue(wedge_contains(corner,[0,-1,0]))

    def test_world_rotation_translation_and_scale_equivariance(self):
        face,trim,edge=fixture();a=capture(face,trim,edge)
        theta=.71;rotation=np.array([[math.cos(theta),0,math.sin(theta)],[0,1,0],[-math.sin(theta),0,math.cos(theta)]])
        # Mix a second rotation to exclude accidental world-axis behavior.
        phi=.43;rotation=rotation@np.array([[math.cos(phi),-math.sin(phi),0],[math.sin(phi),math.cos(phi),0],[0,0,1]])
        scale=3.7;offset=np.array([17,-9,4]);face,trim,edge=fixture(jac=scale*rotation[:,:2],origin=offset)
        b=capture(face,trim,edge,tolerance=scale*1e-5)
        for x,y in zip(a['samples'],b['samples']):
            np.testing.assert_allclose(y['inward_conormal'],rotation@x['inward_conormal'],atol=1e-12)
            np.testing.assert_allclose(y['point'],scale*rotation@x['point']+offset,atol=1e-12)

    def test_uv_metric_and_reversal_do_not_change_physical_side(self):
        poly=np.array([[0,0],[2,0],[2,2],[0,2]],float)
        mapping=np.array([[-1000.,.001],[0.,.002]])
        uvpoly=poly@np.linalg.inv(mapping).T
        jac=np.vstack([mapping,[0.,0.]])
        face,trim,edge=fixture(uvpoly,jac=jac,domains=[Domain(-2000,2000)]*2)
        record=capture(face,trim,edge)
        for sample in record['samples']:np.testing.assert_allclose(sample['inward_conormal'],[0,1,0],atol=1e-12)

    def test_natural_domain_exterior_is_not_surface_extrapolation(self):
        face,trim,edge=fixture(domains=[Domain(0,2),Domain(0,2)])
        record=capture(face,trim,edge)
        self.assertTrue(any(p['mapping']=='native_domain_exterior' for s in record['samples'] for p in s['probes']))
        self.assertTrue(all(0<=u<=2 and 0<=v<=2 for u,v in face.point_calls))

    def test_inner_trim_hole_side_uses_actual_face_membership(self):
        hole=np.array([[0,0],[0,2],[2,2],[2,0]],float)
        face=Face([[-2,-2],[4,-2],[4,4],[-2,4]],holes=[hole]);loop=Loop(hole,face);trim=loop.Trims[0]
        record=capture(face,trim,trim.Edge)
        for sample in record['samples']:np.testing.assert_allclose(sample['inward_conormal'],[-1,0,0])
        self.assertAlmostEqual(record['corners'][0]['exterior_wedge']['sweep_radians'],math.pi/2)

    def test_smooth_split_vertex_has_half_plane_wedge(self):
        face,trim,edge=fixture([[0,0],[1,0],[2,0],[2,2],[0,2]])
        record=capture(face,trim,edge)
        self.assertAlmostEqual(record['corners'][1]['exterior_wedge']['sweep_radians'],math.pi)

    def test_small_reflex_distinction_is_retained(self):
        angle=math.radians(.25)
        face,trim,edge=fixture([[0,0],[1,0],[2,-math.tan(angle)],[2,2],[0,2]])
        record=capture(face,trim,edge,tolerance=1e-7)
        self.assertAlmostEqual(record['corners'][1]['exterior_wedge']['sweep_radians'],math.pi-angle,places=10)

    def test_nonuniform_rational_line_parameterization_keeps_physical_samples(self):
        face,trim,edge=fixture();a=capture(face,trim,edge);edge.parameter_scale=100000.
        b=capture(face,trim,edge)
        for x,y in zip(a['samples'],b['samples']):
            np.testing.assert_allclose(x['point'],y['point'],atol=2e-10)
            np.testing.assert_allclose(x['inward_conormal'],y['inward_conormal'])
            self.assertEqual(x['edge_arc_fraction'],y['edge_arc_fraction'])
        self.assertGreater(b['samples'][0]['edge_fraction'],.99)

    def test_invalid_arc_length_mapping_is_rejected(self):
        face,trim,edge=fixture();edge.NormalizedLengthParameter=lambda f:(False,0.)
        with self.assertRaisesRegex(UnsupportedFamily,'arc-length station'):capture(face,trim,edge)
        edge.NormalizedLengthParameter=lambda f:(True,-7.)
        with self.assertRaisesRegex(UnsupportedFamily,'strictly ordered'):capture(face,trim,edge)

    def test_curved_owner_retries_until_physical_probe_is_local(self):
        polygon=np.array([[0,0],[2,0],[2,2],[0,2]],float)
        face=CurvedFace(polygon);loop=Loop(polygon,face);trim=loop.Trims[0]
        record=capture(face,trim,trim.Edge)
        # At radius .02 the quadratic lift is .0012, above the .0005
        # physical residual budget. At least one bounded shrink is required.
        for sample in record['samples']:
            self.assertLess(sample['probe_distance'],.02)
            np.testing.assert_allclose(sample['inward_conormal'],[0,1,0])
        for corner in record['corners']:self.assertLess(corner['probe_distance'],.02)

    def test_short_native_edge_at_coarse_document_tolerance(self):
        face,trim,edge=fixture([[0,0],[1,0],[1,1],[0,1]])
        record=capture(face,trim,edge,tolerance=.01)
        self.assertLess(record['classification_tolerance'],.01*.05)
        self.assertEqual(len(record['samples']),15)
        for corner in record['corners']:self.assertTrue(wedge_contains(corner,[0,-1,0]))

    def test_short_adjacent_trim_uses_its_own_topology_resolution(self):
        face,trim,edge=fixture([[0,0],[20,0],[20,1],[0,1]],domains=[Domain(-30,30),Domain(-10,10)])
        record=capture(face,trim,edge,tolerance=.01)
        for corner in record['corners']:
            self.assertLess(corner['classification_tolerance'],record['classification_tolerance'])
            self.assertTrue(wedge_contains(corner,[0,-1,0]))

    def test_ambiguous_classification_rejects_boundedly(self):
        face,trim,edge=fixture();face.forced_relation='Boundary'
        with self.assertRaisesRegex(UnsupportedFamily,'AMBIGUOUS_OWNER_SIDE'):capture(face,trim,edge)
        self.assertLess(len(face.calls),100)

    def test_outside_trim_on_both_sides_is_not_invented_interior(self):
        face,trim,edge=fixture()
        original=face.IsPointOnFace
        face.IsPointOnFace=lambda u,v,t:'Boundary' if abs(v)<t else 'Exterior'
        with self.assertRaisesRegex(UnsupportedFamily,'AMBIGUOUS_OWNER_SIDE'):capture(face,trim,edge)

    def test_topological_adjacent_trim_must_meet_actual_corner(self):
        face,trim,edge=fixture();trim.Loop.Trims[-1].b=np.array([-.2,0.])
        with self.assertRaisesRegex(UnsupportedFamily,'adjacent trim does not meet'):capture(face,trim,edge)

    def test_corner_and_interior_side_disagreement_fails_closed(self):
        face,trim,edge=fixture();original=face.IsPointOnFace
        def inconsistent(u,v,tolerance):
            result=original(u,v,tolerance)
            if math.hypot(u,v)<.04 and result in ('Interior','Exterior'):
                return 'Exterior' if result=='Interior' else 'Interior'
            return result
        face.IsPointOnFace=inconsistent
        with self.assertRaisesRegex(UnsupportedFamily,'witnesses disagree'):capture(face,trim,edge)

    def test_periodic_surface_rejects_without_domain_wrap(self):
        face,trim,edge=fixture();face.IsPeriodic=lambda k:k==0
        with self.assertRaisesRegex(UnsupportedFamily,'seam-aware'):capture(face,trim,edge)

    def test_cancellation_and_call_budget(self):
        face,trim,edge=fixture()
        with self.assertRaises(InputCancelled):capture(face,trim,edge,budget=_SideBudget(lambda:True))
        with self.assertRaisesRegex(UnsupportedFamily,'OWNER_SIDE_BUDGET'):capture(face,trim,edge,budget=_SideBudget(max_calls=2))
        with self.assertRaisesRegex(UnsupportedFamily,'OWNER_SIDE_BUDGET'):capture(face,trim,edge,budget=_SideBudget(seconds=0.))

    def test_singular_surface_is_rejected(self):
        face,trim,edge=fixture(jac=[[1,1],[0,0],[0,0]])
        with self.assertRaisesRegex(UnsupportedFamily,'singular local metric'):capture(face,trim,edge)


if __name__=='__main__':unittest.main()
