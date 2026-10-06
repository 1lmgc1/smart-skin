"""Generic numerical fixtures, without production capture or private models."""
import copy
import pathlib
import sys
import types
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'src/SmartSkin.Rhino8/Python'))
import atlas_separation as atlas
import repaired_validation as rv
import skin_kernel as sk
import upper_corner_certificate as upper


def plane(x0=0.,x1=1.,y0=0.,y1=1.):
    return dict(degree_u=1,degree_v=1,knots_u=[0.,0.,1.,1.],knots_v=[0.,0.,1.,1.],
                domain=[[0.,1.],[0.,1.]],homogeneous_cp=[[[x,y,0.,1.] for y in (y0,y1)] for x in (x0,x1)])


def bind(surfaces, seams=None, request=None):
    spec=dict(absolute_tolerance=1e-8,source_boundaries=dict(roles={'synthetic': [{'role':'numeric test boundary'}]}))
    model=types.SimpleNamespace(spec=spec,tolerance=1e-8)
    ledger=dict(schema='smartskin.atlas-adjacency.v1',checked=True,
                source_digest=rv._digest(spec['source_boundaries']['roles']),geometry_digest=rv._digest(surfaces),
                shared_edges=seams or [],interval_units='normalized local chart-edge fraction',
                additional_point_contacts='only endpoint equivalence induced by these checked shared edges')
    result=dict(surfaces=surfaces,report=dict(checked=True,failures=[],atlas_adjacency=ledger,
                 source_digest=ledger['source_digest'],geometry_digest=ledger['geometry_digest']))
    if request is not None:
        result['edit_request']=copy.deepcopy(request)
    return model,result


def seam(a=0,b=1,edge_a='right',edge_b='left',intervals=None,normal=1):
    intervals=intervals or [[0.,1.],[0.,1.]]
    return dict(surface_indices=[a,b],edges=[edge_a,edge_b],normalized_intervals=intervals,
                parameter_orientation=1 if np.prod(np.diff(intervals,axis=1))>0 else -1,
                normal_orientation=normal,role='synthetic-shared')


class AtlasTests(unittest.TestCase):
    def screen(self,surfaces,seams=None,request=None):
        model,result=bind(surfaces,seams,request)
        receipt=atlas.screen_atlas(model,result)
        return model,result,receipt

    def test_two_quads_and_no_global_claim(self):
        model,result,receipt=self.screen([plane(),plane(1.,2.)],[seam()])
        self.assertTrue(receipt['passed'],receipt['reason'])
        self.assertTrue(atlas.verify_atlas_separation(result,model.spec))
        self.assertFalse(receipt['global_injectivity_certified'])
        self.assertEqual(receipt['metrics']['positive_radius_excluded'],0.)
        self.assertGreater(receipt['metrics']['intersection_tests'],0)

    def test_adjacent_pair_extra_overlap_is_not_blanket_exempt(self):
        # Both charts extend to the same side of a declared common edge.
        model,result,receipt=self.screen([plane(),plane(1.,0.)],[seam(normal=-1)])
        self.assertFalse(receipt['passed'])
        self.assertTrue(any(x in receipt['reason'] for x in ('overlapping chart interiors','contact')),receipt['reason'])

    def test_undeclared_overlap_crossing_and_containment(self):
        for other in (plane(.5,1.5,.25,.75),plane(.2,.8,.2,.8),plane(0.,1.)):
            with self.subTest(other=other):
                _,_,receipt=self.screen([plane(),other])
                self.assertFalse(receipt['passed'])
                self.assertTrue(any(x in receipt['reason'] for x in ('crossing','containment','contact','coincident')),receipt['reason'])

    def test_undeclared_point_touch_rejected(self):
        _,_,receipt=self.screen([plane(),plane(1.,2.,1.,2.)])
        self.assertFalse(receipt['passed']);self.assertIn('contact',receipt['reason'])

    def test_partial_seam_station_union(self):
        surfaces=[plane(),plane(1.,2.,0.,.5),plane(1.,2.,.5,1.)]
        seams=[seam(0,1,intervals=[[0.,.5],[0.,1.]]),
               seam(0,2,intervals=[[.5,1.],[0.,1.]]),seam(1,2,'top','bottom')]
        _,_,receipt=self.screen(surfaces,seams)
        self.assertTrue(receipt['passed'],receipt['reason'])

    def test_reflected_parameter_orientation(self):
        second=plane(1.,2.,1.,0.)
        _,_,receipt=self.screen([plane(),second],[seam(intervals=[[0.,1.],[1.,0.]],normal=-1)])
        self.assertTrue(receipt['passed'],receipt['reason'])

    def test_rotation_reflection_translation_and_scale(self):
        angle=.57
        rotation=np.array([[np.cos(angle),0,np.sin(angle)],[0,1,0],[-np.sin(angle),0,np.cos(angle)]])
        for scale,reflection in ((1e-4,1.),(17.,-1.),(1e5,1.)):
            surfaces=[plane(),plane(1.,2.)]
            transform=rotation@np.diag([reflection,1.,1.])
            for record in surfaces:
                cp=np.asarray(record['homogeneous_cp']);cp[:,:,:3]=scale*(cp[:,:,:3]@transform.T+np.array([3.,-7.,2.]))
                record['homogeneous_cp']=cp.tolist()
            _,_,receipt=self.screen(surfaces,[seam()])
            self.assertTrue(receipt['passed'],receipt['reason'])

    def test_common_homogeneous_weight_gauge(self):
        for factor in (1e-80,1e80):
            surfaces=[plane(),plane(1.,2.)]
            for record in surfaces:
                record['homogeneous_cp']=(np.asarray(record['homogeneous_cp'])*factor).tolist()
            _,_,receipt=self.screen(surfaces,[seam()])
            self.assertTrue(receipt['passed'],receipt['reason'])

    def test_stale_ledger_and_report_fail_before_screen(self):
        model,result=bind([plane(),plane(1.,2.)],[seam()])
        result['surfaces'][0]['homogeneous_cp'][0][0][2]=.1
        receipt=atlas.screen_atlas(model,result)
        self.assertFalse(receipt['passed']);self.assertIn('Stale',receipt['reason'])

    def test_commit_verifier_recomputes_all_three_bindings(self):
        model,result,receipt=self.screen([plane(),plane(1.,2.)],[seam()],dict(handle='u0',value=1.))
        self.assertTrue(receipt['passed'],receipt['reason'])
        self.assertTrue(atlas.verify_atlas_separation(result,model.spec,result['edit_request']))
        with self.assertRaises(ValueError):atlas.verify_atlas_separation(result,model.spec)
        with self.assertRaises(ValueError):atlas.verify_atlas_separation(result,model.spec,dict(handle='u0',value=2.))
        for mutate in ('geometry','source','request'):
            m,r=copy.deepcopy(model),copy.deepcopy(result)
            if mutate=='geometry':r['surfaces'][0]['homogeneous_cp'][0][0][2]=1.
            elif mutate=='source':m.spec['source_boundaries']['roles']['synthetic'][0]['role']='changed'
            else:r['edit_request']['value']=2.
            with self.assertRaises(ValueError):atlas.verify_atlas_separation(r,m.spec,r['edit_request'])

    def test_receipt_rejects_modified_adjacency_and_baseline_edit_key(self):
        model,result,receipt=self.screen([plane(),plane(1.,2.)],[seam()])
        self.assertTrue(receipt['passed'],receipt['reason'])
        result['report']['atlas_adjacency']['shared_edges'][0]['role']='changed'
        with self.assertRaises(ValueError):atlas.verify_atlas_separation(result,model.spec)
        model,result,receipt=self.screen([plane()])
        result['edit_request']=None
        with self.assertRaises(ValueError):atlas.verify_atlas_separation(result,model.spec)

    def test_replaced_hashes_do_not_substitute_for_actual_source_and_geometry(self):
        model,result,receipt=self.screen([plane()])
        self.assertTrue(receipt['passed'],receipt['reason'])
        for key in ('source_digest','geometry_digest'):
            r=copy.deepcopy(result)
            for target in (r['atlas_separation'],r['report'],r['report']['atlas_adjacency']):
                target[key]='not-the-actual-digest'
            with self.assertRaises(ValueError):atlas.verify_atlas_separation(r,model.spec)

    def test_self_fold_and_interior_extra_overlap_are_rejected(self):
        folded=plane();folded['homogeneous_cp'][1].reverse()
        _,_,receipt=self.screen([folded])
        self.assertFalse(receipt['passed'])
        _,_,receipt=self.screen([plane(),plane(1.,2.),plane(.25,.75,.25,.75)],[seam()])
        self.assertFalse(receipt['passed']);self.assertIn('containment',receipt['reason'])

    def test_normal_and_surface_count_budgets(self):
        model,result=bind([plane()])
        with mock.patch.object(atlas,'MAX_NORMAL_SAMPLES',1):
            receipt=atlas.screen_atlas(model,result)
        self.assertFalse(receipt['passed']);self.assertIn('normal-sample budget',receipt['reason'])
        _,_,receipt=self.screen([plane() for _ in range(65)])
        self.assertFalse(receipt['passed']);self.assertIn('surface-count budget',receipt['reason'])

    def test_cancel_clears_old_receipt_and_work_budget_fails(self):
        model,result=bind([plane()]);result['atlas_separation']={'passed':True}
        with self.assertRaises(sk.Cancelled):atlas.screen_atlas(model,result,lambda:True)
        self.assertNotIn('atlas_separation',result)
        with mock.patch.object(atlas,'MAX_PAIR_WORK',1):
            receipt=atlas.screen_atlas(model,result)
        self.assertFalse(receipt['passed']);self.assertIn('budget',receipt['reason'])
        with mock.patch.object(atlas,'MAX_SECONDS',0.):
            receipt=atlas.screen_atlas(model,result)
        self.assertFalse(receipt['passed']);self.assertIn('budget',receipt['reason'])

    def test_degree_and_control_budgets(self):
        for field,value in (('degree_u',41),('homogeneous_cp',np.ones((129,129,4)).tolist())):
            record=plane();record[field]=value
            _,_,receipt=self.screen([record])
            self.assertFalse(receipt['passed'])

    def test_only_exact_approved_pole_can_collapse(self):
        record=plane();record['homogeneous_cp']=[[[0.,0.,0.,1.],[0.,1.,0.,1.]],[[0.,0.,0.,1.],[1.,1.,0.,1.]]]
        _,_,receipt=self.screen([record])
        self.assertFalse(receipt['passed'])
        record.update(kind='upper_hard_corner',side=0,collapsed_parameter_edge='v=0',approved_physical_corner_id='upper:side0',
                      boundary_roles=dict(bottom=dict(role='approved_source_vertex',corner_id='upper:side0',physical_dimension=0)))
        model,result=bind([record])
        cert=upper.certify_isolated_upper_chart(record,[0.,0.,1.],1)
        self.assertTrue(cert['passed'],cert)
        result['report'].update(upper_radial_certificates=[dict(surface_index=0,**cert)],
                                hard_corner_curvature=dict(physical_points=['upper:side0']))
        receipt=atlas.screen_atlas(model,result)
        self.assertTrue(receipt['passed'],receipt['reason'])
        result['report']['upper_radial_certificates'][0]['proof']['excluded_positive_radius']=.01
        receipt=atlas.screen_atlas(model,result)
        self.assertFalse(receipt['passed']);self.assertIn('positive-radius',receipt['reason'])


if __name__=='__main__':unittest.main()
