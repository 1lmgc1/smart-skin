"""Synthetic source-evidence and capture-gate tests; NOT VERIFIED in Rhino.

Native occupancy is supplied explicitly by test_native_attachment_side's mock
capture. No production bypass manufactures evidence for numerical fixtures.
"""
import copy
import pathlib
import sys
import unittest
from types import SimpleNamespace
from scipy.integrate import quad
from scipy.optimize import brentq
from unittest import mock
import numpy as np

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'src/SmartSkin.Rhino8/Python'))
from native_boundary_evidence import (build_source_boundaries,require_complete_evidence,
                                     BoundaryEvidenceError,_reference)
from native_family import (Curve,Surface,build_spec,require_native_provenance,
                           UnsupportedFamily,_source_side_map)
from native_input import Capture
from test_native_attachment_side import Face,CurvedFace,Loop,Domain,Point,capture
from test_native_family import synthetic_edges


def surface_record(curved=False):
    if curved:
        return dict(degree_u=1,degree_v=2,knots_u=[0,0,2,2],knots_v=[0,0,0,2,2,2],
                    homogeneous_cp=[[[u,0,0,1],[u,1,0,1],[u,2,12,1]] for u in (0,2)])
    return dict(degree_u=1,degree_v=1,knots_u=[0,0,2,2],knots_v=[0,0,2,2],
                homogeneous_cp=[[[u,v,0,1] for v in (0,2)] for u in (0,2)])


def captured_edges():
    polygon=np.array([[0,0],[2,0],[2,2],[0,2]],float)
    face=Face(polygon,domains=[Domain(0,2),Domain(0,2)]);loop=Loop(polygon,face)
    result=[]
    for i,trim in enumerate(loop.Trims):
        points=[trim.Edge.PointAt(t) for t in (-7,3)]
        curve=dict(degree=1,knots=[-7,-7,3,3],domain=[-7,3],
                   homogeneous_cp=[[p.X,p.Y,p.Z,1] for p in points])
        result.append(dict(key='synthetic-owner-edge-'+str(i),curve=curve,surface=surface_record(),
                           owner_side=capture(face,trim,trim.Edge)))
    return result


def inputs():
    edges=captured_edges()
    roles=dict(side0=[(edges[3],False)],side1=[(edges[1],True)],upper=[(edges[2],True)],lower=[(edges[0],False)])
    maps=dict(side0=_source_side_map(edges[3],(0,0),np.array([0,2,0.]),1e-5),
              side1=_source_side_map(edges[1],(0,1),np.array([2,2,0.]),1e-5))
    return edges,roles,maps


def evidence(roles,maps):return build_source_boundaries(roles,1e-5,Curve,Surface,maps)


def model(records):
    return dict(source_boundaries=records,absolute_tolerance=1e-5,extraction_report=dict(source_edge_count=4))


def approximate_edge_inputs(epsilon=2e-4,reverse=False,normal_bow=False):
    """Explicit synthetic Brep-style approximation, no private field geometry.

    The true trim stays straight. Its separately stored 3D edge has matching
    endpoints and a small in-plane quadratic bow, within the position budget.
    Arc stations use numerical integration of this exact synthetic polynomial.
    """
    edges,roles,maps=inputs();polygon=np.array([[0,0],[2,0],[2,2],[0,2]],float)
    face=Face(polygon,domains=[Domain(0,2),Domain(0,2)]);trim=Loop(polygon,face).Trims[0]
    class ApproximateEdge:
        Domain=Domain(-7,3);reversed=reverse
        def PointAt(self,t):
            f=(t+7.)/10.;f=1.-f if self.reversed else f
            bow=epsilon*f*(1.-f)
            return Point(2.*f,0. if normal_bow else bow,bow if normal_bow else 0.)
        def TangentAt(self,t):
            f=(t+7.)/10.;f=1.-f if self.reversed else f
            result=np.array([2.,0. if normal_bow else epsilon*(1.-2.*f),epsilon*(1.-2.*f) if normal_bow else 0.])
            return Point(*(-result if self.reversed else result))
        def GetLength(self):return quad(lambda f:np.hypot(2.,epsilon*(1.-2.*f)),0.,1.,epsabs=1e-13)[0]
        def NormalizedLengthParameter(self,fraction):
            total=self.GetLength()
            f=brentq(lambda t:quad(lambda f:np.hypot(2.,epsilon*(1.-2.*f)),0.,t,epsabs=1e-13)[0]-fraction*total,0.,1.,xtol=1e-14)
            return True,self.Domain.ParameterAt(f)
    trim.Edge=ApproximateEdge()
    cp=[[0,0,0,1],[1,0. if normal_bow else epsilon/2.,epsilon/2. if normal_bow else 0.,1],[2,0,0,1]]
    edges[0]['curve']=dict(degree=2,knots=[-7]*3+[3]*3,domain=[-7,3],homogeneous_cp=cp[::-1] if reverse else cp)
    edges[0]['owner_side']=capture(face,trim,trim.Edge,tolerance=.01)
    roles['lower']=[(edges[0],reverse)]
    return edges,roles,maps


class NativeBoundaryEvidenceTests(unittest.TestCase):
    def test_native_approximation_preserves_distinct_frames_through_capture(self):
        for reverse in (False,True):
            edges,roles,maps=approximate_edge_inputs(reverse=reverse);before=copy.deepcopy(edges)
            result=build_source_boundaries(roles,.01,Curve,Surface,maps)
            spec=model(result);spec['absolute_tolerance']=.01
            captured=Capture(SimpleNamespace(RuntimeSerialNumber=1),spec,[],None,[])
            self.assertIs(captured.model,spec)
            self.assertEqual(edges,before)
            for corner in result['roles']['lower'][0]['owner_side']['corners']:
                self.assertEqual(corner['frame_contract'],'separate-edge-trim-v1')
                self.assertLess(abs(np.dot(corner['inward_conormal'],corner['tangent'])),1e-12)
                self.assertLess(abs(np.dot(corner['trim_inward_conormal'],corner['trim_ray'])),1e-12)
                # This valid native representation difference caused the F3
                # mixed-frame orthogonality failure. Neither frame is erased.
                self.assertGreater(abs(np.dot(corner['trim_inward_conormal'],corner['tangent'])),1e-5)
                self.assertGreater(corner['edge_trim_tangent_angle_degrees'],0.)
                self.assertGreater(corner['edge_trim_tangent_alignment'],.99999)
            captured.dispose()

    def test_non_tangent_and_incompatible_native_branches_still_fail(self):
        with self.assertRaisesRegex(UnsupportedFamily,'local branch'):
            approximate_edge_inputs(normal_bow=True)
        with self.assertRaises(UnsupportedFamily):approximate_edge_inputs(epsilon=.04)
        edges,roles,maps=approximate_edge_inputs();corner=edges[0]['owner_side']['corners'][0]
        corner['trim_ray']=(-np.array(corner['trim_ray'])).tolist()
        with self.assertRaisesRegex(BoundaryEvidenceError,'role=lower; source_ordinal=0.*endpoint=0.*branch_dot'):
            build_source_boundaries(roles,.01,Curve,Surface,maps)

    def test_paired_frame_metadata_and_actual_trim_occupancy_cannot_be_forged(self):
        for mutate in (lambda c:c.update(trim_inward_conormal=c['inward_conormal']),
                       lambda c:c.update(edge_trim_tangent_alignment=1.),
                       lambda c:c.update(adjacent_trim_inward_cross_sign=-c['adjacent_trim_inward_cross_sign']),
                       lambda c:c.update(adjacent_trim_parameter=c['adjacent_trim_parameter']+.1),
                       lambda c:c.pop('frame_contract')):
            edges,roles,maps=approximate_edge_inputs();mutate(edges[0]['owner_side']['corners'][0])
            with self.assertRaises(BoundaryEvidenceError):build_source_boundaries(roles,.01,Curve,Surface,maps)

    def test_exact_records_roles_and_ownership_are_retained_without_mutation(self):
        edges,roles,maps=inputs();before=copy.deepcopy(edges);result=evidence(roles,maps)
        self.assertTrue(result['complete']);self.assertEqual(result['source_edge_count'],4)
        self.assertEqual(edges,before)
        self.assertTrue(require_complete_evidence(result,1e-5,Curve,Surface))
        for role,chain in roles.items():
            record=result['roles'][role][0];edge=chain[0][0]
            self.assertEqual(record['curve'],edge['curve']);self.assertEqual(record['surface'],edge['surface'])
            self.assertEqual(record['owner_side'],edge['owner_side'])
            self.assertEqual(record['original_curve_domain'],[-7.,3.])
            self.assertEqual(record['active_domain'],[-7.,3.])
            self.assertEqual(len(record['reference_stations']),15)
        self.assertEqual(result['roles']['upper'][0]['traversal_domain'],[3.,-7.])
        result['roles']['upper'][0]['curve']['homogeneous_cp'][0][0]=99.
        self.assertEqual(edges,before)

    def test_side_chart_mapping_reproduces_original_native_parameterization(self):
        edges,roles,maps=inputs();result=evidence(roles,maps)
        for role in ('side0','side1'):
            record=result['roles'][role][0];mapping=record['parameter_map']
            a=np.array(mapping['native_uv_from_chart_uv']['matrix']);b=np.array(mapping['native_uv_from_chart_uv']['offset'])
            slope,offset=mapping['edge_parameter_from_chart_v']
            for v in (.03,.47,.91):
                uv=a@np.array([mapping['boundary_chart_u'],v])+b
                np.testing.assert_allclose(Surface(record['surface']).jet(*uv)[0],Curve(record['curve'])(slope*v+offset))

    def test_native_uv_units_and_offsets_do_not_change_physical_evidence(self):
        edges,roles,maps=inputs();baseline=evidence(roles,maps)
        scales=np.array([.0001,400.]);shift=np.array([200000.,-5678.])
        for edge in edges:
            for axis,name in enumerate(('knots_u','knots_v')):
                edge['surface'][name]=(shift[axis]+scales[axis]*np.array(edge['surface'][name])).tolist()
            for w in edge['owner_side']['samples']+edge['owner_side']['corners']:
                w['uv']=(shift+scales*w['uv']).tolist()
                for name in ('inside_uv','outside_uv'):
                    if name in w:w[name]=(shift+scales*w[name]).tolist()
                for p in w['probes']:p['uv']=(shift+scales*p['uv']).tolist()
        maps=dict(side0=_source_side_map(edges[3],(0,0),np.array([0,2,0.]),1e-5),
                  side1=_source_side_map(edges[1],(0,1),np.array([2,2,0.]),1e-5))
        result=evidence(roles,maps)
        for role in result['roles']:
            for a,b in zip(result['roles'][role][0]['reference_stations'],baseline['roles'][role][0]['reference_stations']):
                np.testing.assert_allclose(a['point'],b['point'],atol=5e-7)
                np.testing.assert_allclose(a['shape_operator'],b['shape_operator'],atol=1e-12)

    def test_missing_or_partial_native_evidence_never_becomes_valid(self):
        edges,roles,maps=inputs();del edges[0]['owner_side']
        with self.assertRaisesRegex(BoundaryEvidenceError,'Missing captured'):evidence(roles,maps)
        with self.assertRaisesRegex(BoundaryEvidenceError,'before preview'):require_complete_evidence(None,1e-5,Curve,Surface)
        with self.assertRaisesRegex(BoundaryEvidenceError,'before preview'):require_complete_evidence(dict(complete=False),1e-5,Curve,Surface)

    def test_contradictory_occupancy_frame_and_arc_station_are_rejected(self):
        for mutate in (lambda w:w.update(inward_conormal=[0,-1,0]),
                       lambda w:w['probes'][0].update(relation='Exterior'),
                       lambda w:w.update(edge_arc_fraction=.95),
                       lambda w:w.update(point=[1,1,9]),
                       lambda w:w['probes'][0].update(uv=[100,100]),
                       lambda w:w['probes'][0].update(point=[1,1,99])):
            edges,roles,maps=inputs();mutate(edges[0]['owner_side']['samples'][0])
            with self.assertRaises(BoundaryEvidenceError):evidence(roles,maps)

    def test_wrong_domain_orientation_and_corner_wedge_are_rejected(self):
        edges,roles,maps=inputs();maps['side0']['native_uv_from_chart_uv']['offset'][0]=.1
        with self.assertRaises(BoundaryEvidenceError):evidence(roles,maps)
        edges,roles,maps=inputs();edges[0]['owner_side']['face_orientation_reversed']=True
        with self.assertRaisesRegex(BoundaryEvidenceError,'orientation'):evidence(roles,maps)
        edges,roles,maps=inputs();edges[0]['owner_side']['corners'][0]['exterior_wedge']['sweep_radians']=.1
        with self.assertRaisesRegex(BoundaryEvidenceError,'wedge'):evidence(roles,maps)

    def test_lower_full_native_shape_operator_is_not_a_profile_jet(self):
        edges,roles,maps=inputs();polygon=np.array([[0,0],[2,0],[2,2],[0,2]],float)
        face=CurvedFace(polygon,domains=[Domain(0,2),Domain(0,2)]);trim=Loop(polygon,face).Trims[0]
        lower=copy.deepcopy(edges[0]);lower['key']='synthetic-curved-lower';lower['surface']=surface_record(True)
        lower['owner_side']=capture(face,trim,trim.Edge);roles['lower']=[(lower,False)]
        result=evidence(roles,maps)
        for reference in result['roles']['lower'][0]['reference_stations']:
            np.testing.assert_allclose(reference['shape_operator'],np.diag([0.,6.,0.]),atol=1e-10)
        forged=copy.deepcopy(result);forged['roles']['lower'][0]['reference_stations'][0]['shape_operator']=[[0,0,0]]*3
        with self.assertRaisesRegex(BoundaryEvidenceError,'Full native shape operator'):
            require_complete_evidence(forged,1e-5,Curve,Surface)

    def test_full_mixed_curvature_is_retained_in_world_coordinates(self):
        class AnalyticSurface:
            ud=vd=(-1.,1.)
            def jet(self,u,v):
                return tuple(np.array(x,float) for x in ([u,v,u*u+3*u*v+2*v*v],[1,0,2*u+3*v],
                    [0,1,3*u+4*v],[0,0,2],[0,0,3],[0,0,4]))
        reference=_reference(AnalyticSurface(),[0,0],[0,0,0],[0,0,1],1e-8)
        np.testing.assert_allclose(reference['shape_operator'],[[2,3,0],[3,4,0],[0,0,0]])
        reversed_ref=_reference(AnalyticSurface(),[0,0],[0,0,0],[0,0,-1],1e-8)
        np.testing.assert_allclose(reversed_ref['shape_operator'],-np.array(reference['shape_operator']))

    def test_reference_locations_and_role_traversal_cannot_be_replaced(self):
        edges,roles,maps=inputs();result=evidence(roles,maps)
        for field,value in (('point',[0,0,99]),('uv',[1,1]),('edge_parameter',42.)):
            forged=copy.deepcopy(result);forged['roles']['lower'][0]['reference_stations'][0][field]=value
            with self.assertRaisesRegex(BoundaryEvidenceError,'reference location'):
                require_complete_evidence(forged,1e-5,Curve,Surface)
        roles['upper']=[(edges[2],False)]
        with self.assertRaisesRegex(BoundaryEvidenceError,'role start'):evidence(roles,maps)

    def test_world_full_shape_operator_rotation_and_scale(self):
        angle=.6;rotation=np.array([[np.cos(angle),0,np.sin(angle)],[0,1,0],[-np.sin(angle),0,np.cos(angle)]])
        scale=2.7;shift=np.array([17,-9,4.])
        class RotatedSurface:
            ud=vd=(-1.,1.)
            def jet(self,u,v):
                raw=([u,v,u*u+3*u*v+2*v*v],[1,0,2*u+3*v],[0,1,3*u+4*v],[0,0,2],[0,0,3],[0,0,4])
                result=[scale*rotation@np.array(x,float) for x in raw];result[0]+=shift
                return tuple(result)
        reference=_reference(RotatedSurface(),[0,0],shift,rotation@np.array([0,0,1.]),1e-8)
        expected=rotation@np.array([[2,3,0],[3,4,0],[0,0,0]])@rotation.T/scale
        np.testing.assert_allclose(reference['shape_operator'],expected,atol=1e-12)

    def test_numerical_build_marks_absence_but_capture_blocks_preview(self):
        spec=build_spec(synthetic_edges(),1e-5)
        self.assertFalse(spec['source_boundaries']['complete']);self.assertEqual(spec['source_boundaries']['status'],'missing')
        with self.assertRaisesRegex(UnsupportedFamily,'NATIVE_BOUNDARY_EVIDENCE'):Capture(None,spec,[],None,[])
        for path in spec['upper_paths']:
            for span in path:
                self.assertEqual(span['source_boundary_role'],'upper')
                self.assertTrue(span['source_key'])
                np.testing.assert_allclose(span['source_active_domain'],span['curve']['domain'])

    def test_capture_constructor_independently_blocks_contradictory_evidence(self):
        edges,roles,maps=inputs();spec=model(evidence(roles,maps))
        spec['source_boundaries']['roles']['upper'][0]['owner_side']['samples'][0]['probes'][0]['relation']='Boundary'
        with self.assertRaisesRegex(UnsupportedFamily,'NATIVE_BOUNDARY_EVIDENCE'):Capture(None,spec,[],None,[])
        spec=model(evidence(roles,maps));spec['extraction_report']['source_edge_count']=9
        with self.assertRaisesRegex(UnsupportedFamily,'coverage'):Capture(None,spec,[],None,[])

    def test_build_spec_routes_exact_role_chains_to_validator(self):
        edges=synthetic_edges()
        for edge in edges:edge['owner_side']={'explicit':'synthetic wiring sentinel'}
        with mock.patch('native_family.build_source_boundaries',return_value={'wiring_sentinel':True}) as check:
            result=build_spec(edges,1e-5)
        self.assertEqual(result['source_boundaries'],{'wiring_sentinel':True})
        roles=check.call_args.args[0]
        self.assertEqual(set(roles),{'side0','side1','upper','lower'})
        self.assertEqual(sum(len(v) for v in roles.values()),6)
        # This mock checks wiring only; its result cannot cross the real gate.
        with self.assertRaises(UnsupportedFamily):Capture(None,result,[],None,[])

    def test_duplicate_sources_malformed_fields_and_cancellation_fail_closed(self):
        edges,roles,maps=inputs();roles['upper']=[(edges[0],False)]
        with self.assertRaisesRegex(BoundaryEvidenceError,'duplicate'):evidence(roles,maps)
        edges,roles,maps=inputs();edges[0]['owner_side']['samples'][0]['point']=None
        with self.assertRaises(BoundaryEvidenceError):evidence(roles,maps)
        edges,roles,maps=inputs()
        with self.assertRaisesRegex(BoundaryEvidenceError,'Cancelled'):
            build_source_boundaries(roles,1e-5,Curve,Surface,maps,lambda:True)


if __name__=='__main__':unittest.main()
