"""Synthetic native-corner and exact-evaluator safety regressions."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock
import types
import numpy as np
import mpmath as mp
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'/'SmartSkin.Rhino8'/'Python'))
import skin_kernel as sk
from test_upper_corner_geometry import jets as mp_jets,geo as mp_geometry


def evidence_fixture(reverse=False):
    def corner(x,parameter,operator=None):
        return dict(point=list(x),edge_parameter=parameter,parent_normal=[0,0,1],shape_operator=np.zeros((3,3)).tolist() if operator is None else operator)
    roles={'side0':[],'side1':[],'lower':[]}
    for side,x in enumerate((-2.,2.)):
        top=corner([x,0,0],1 if reverse else 0);bottom=corner([x,1,0],0 if reverse else 1)
        roles['side'+str(side)]=[dict(traversal_domain=[top['edge_parameter'],bottom['edge_parameter']],reference_corners=[bottom,top] if reverse else [top,bottom])]
        roles['lower'].append(dict(reference_corners=[corner([x,1,0],0),corner([0,1,0],1)]))
    return dict(absolute_tolerance=1e-5,angle_tolerance=.01,curvature_tolerance=1e-6,source_boundaries=dict(complete=True,roles=roles))


class NativeRepairGateTests(unittest.TestCase):
    def prepared_shell(self):
        model=sk._PreparedNativeRepairs.__new__(sk._PreparedNativeRepairs)
        model._baseline_geometry=None;model._baseline_result=None;model._uv_edits=None
        model.cancelled=None;model.prepare_seconds=.25;model.base=object()
        return model
    def test_repaired_geometry_cached_but_every_value_revalidated(self):
        model=self.prepared_shell();calls=[];checks=[]
        def construct(h,cancelled):
            calls.append(h);return dict(surfaces=[],guides=[],network={},valid=False)
        def validate(base,result,cancelled=None):
            checks.append(result)
            return dict(valid=False,fatal=True,geometry_valid=True,reason='Separation pending',report=dict(checked=True,fatal=True,full_boundary_pass=False))
        model._construct_geometry=construct
        with mock.patch.dict(sys.modules,{'_smartskin_p08e1_repaired_validation':types.SimpleNamespace(validate_repaired=validate)}):
            first=model.evaluate();second=model.evaluate()
        self.assertEqual(calls,[1.]);self.assertEqual(len(checks),2)
        self.assertTrue(first['timing']['cold_geometry']);self.assertFalse(second['timing']['cold_geometry'])
        self.assertFalse(model.handle_edit_catalog()['enabled'])
        self.assertNotIn('attachment_proof',second)
        with self.assertRaises(sk.UnsupportedFamily):model.evaluate_edit({})
    def test_failed_repair_is_not_cached(self):
        model=self.prepared_shell()
        def fail(h,cancelled):raise sk.UnsupportedFamily('Construction failed')
        model._construct_geometry=fail
        with self.assertRaises(sk.UnsupportedFamily):model.evaluate()
        self.assertIsNone(model._baseline_geometry)
    def test_production_rejects_global_handle_and_unvalidated_acceptance(self):
        model=self.prepared_shell();model._construct_geometry=lambda h,c:dict(surfaces=[],guides=[],network={},attachment_proof={'checked':True})
        with self.assertRaises(sk.UnsupportedFamily):model.evaluate(.5)
        result=model.evaluate(validate=False)
        self.assertFalse(result['valid']);self.assertFalse(result['experimental_commit_allowed'])
        self.assertNotIn('attachment_proof',result)

    def test_failed_atlas_screen_blocks_native_screen_stage(self):
        model=self.prepared_shell()
        result=dict(valid=True,geometry_valid=True,fatal=False,experimental_commit_allowed=False,
                    disposition='native_screen_pending',report=dict(fatal=False))
        screen=dict(checked=True,passed=False,reason='Unrelated projected overlap')
        with mock.patch.dict(sys.modules,{'_smartskin_p08e1_atlas_separation':types.SimpleNamespace(screen_atlas=lambda *a,**k:screen)}):
            checked=model._screen_atlas_result(result)
        self.assertFalse(checked['valid']);self.assertTrue(checked['fatal'])
        self.assertEqual(checked['disposition'],'atlas_screen_failed')
        self.assertIs(checked['atlas_separation'],screen)
    def test_edit_validator_receives_current_generated_guides(self):
        model=self.prepared_shell();model._uv_edits=object();model._baseline_result={'guides':['neutral']}
        candidate=dict(surfaces=[],patches=[],guides=['current'],network={'row_count':8},edit_request={'revision':2})
        seen=[]
        def validate(base,value,cancelled=None):
            seen.append(value);return dict(valid=False,fatal=True,report=dict(checked=True,fatal=True))
        with mock.patch.dict(sys.modules,{'_smartskin_p08e1_repaired_validation':types.SimpleNamespace(validate_repaired=validate)}):
            result=model._validate_edit_candidate(candidate)
        self.assertIs(seen[0],candidate);self.assertEqual(result['guides'],['current'])
        self.assertEqual(result['edit_request'],{'revision':2})

    def test_source_frame_scale_is_rigid_and_scale_covariant(self):
        points=[dict(p0=[x,0.,.1*x],p1=[x,2.,3.+.2*x]) for x in (-2.,-1.,0.,1.,2.)]
        spec=dict(profiles=points,upper_plane_normal=[0.,1.,0.],transverse_direction=[1.,0.,0.])
        expected=float(np.linalg.norm(np.ptp(np.array([p[k] for p in points for k in ('p0','p1')]),axis=0)))
        self.assertAlmostEqual(sk._source_frame_scale(spec),expected,places=14)
        axis=np.array([1.,2.,-3.]);axis/=np.linalg.norm(axis);angle=.71
        K=np.array([[0,-axis[2],axis[1]],[axis[2],0,-axis[0]],[-axis[1],axis[0],0]])
        R=np.eye(3)+np.sin(angle)*K+(1-np.cos(angle))*(K@K)
        for scale in (.1,1.,7.):
            changed=copy.deepcopy(spec)
            for p in changed['profiles']:
                for key in ('p0','p1'):p[key]=(scale*(R@p[key])+[17.,-29.,41.]).tolist()
            for key in ('upper_plane_normal','transverse_direction'):changed[key]=(R@np.asarray(spec[key])).tolist()
            self.assertAlmostEqual(sk._source_frame_scale(changed),scale*expected,places=12)

    def test_matching_regular_lower_corners(self):
        for reverse in (False,True):
            self.assertEqual(len(sk._regular_lower_corner_preflight(evidence_fixture(reverse),4.)),2)
    def test_incompatible_lower_is_not_an_upper_exception(self):
        spec=evidence_fixture();spec['source_boundaries']['roles']['lower'][0]['reference_corners'][0]['shape_operator'][0][0]=1e-3
        with self.assertRaisesRegex(sk.UnsupportedFamily,'LOWER_REGULAR_CORNER_INCOMPATIBLE'):
            sk._regular_lower_corner_preflight(spec,4.)
    def test_incomplete_owner_evidence_rejected(self):
        spec=evidence_fixture();spec['source_boundaries']['complete']=False
        with self.assertRaisesRegex(sk.UnsupportedFamily,'NATIVE_BOUNDARY_EVIDENCE'):sk._regular_lower_corner_preflight(spec,4.)
    def test_precise_sparse_readback_matches_independent_basis(self):
        p=q=2
        cp=np.array([[[i,j,.03*i*j,1.] for j in range(3)] for i in range(3)],float)
        record=dict(degree_u=p,degree_v=q,knots_u=[0,0,0,1,1,1],knots_v=[0,0,0,1,1,1],homogeneous_cp=cp.tolist())
        evaluator=sk._PreciseEvaluator(record)
        with mp.workdps(80):
            for u,v in ((0.,1e-12),(.2,.7),(1.,1.)):
                actual=evaluator.jets(u,v);reference=mp_jets(record,u,v)
                for a,b in zip(actual,reference):self.assertLess(float(mp.norm(a-b)),1e-60)
                self.assertLess(sk._precise_compare(actual,reference)[1],1e-60)
        self.assertLessEqual(len(sk._precise_basis(tuple(record['knots_u']),2,.5,1)),3)

    def test_exact_local_evaluator_preserves_descriptor(self):
        # A translated rational surface with a highly sheared chart.
        p=q=5;cp=np.zeros((p+1,q+1,4))
        for i in range(p+1):
            for j in range(q+1):
                weight=1.+.03*i/p
                point=np.array([12345.+.02*i/p+j/q,-8765.+.001*j/q,431.+1e-4*i*(i-1)/(p*(p-1))])
                cp[i,j]=np.r_[point*weight,weight]
        s=dict(degree_u=p,degree_v=q,knots_u=[0]*(p+1)+[1]*(p+1),knots_v=[0]*(q+1)+[1]*(q+1),homogeneous_cp=cp.tolist())
        before=copy.deepcopy(s);E=sk._Evaluator(s);ordinary=E.jets(.37,.61)
        with mp.workdps(80):reference=mp_jets(s,.37,.61);n,w=mp_geometry(reference)
        self.assertEqual(s,before)
        for a,b in zip(ordinary[1:],reference[1:]):self.assertLess(np.linalg.norm(a-np.asarray(b,float).ravel()),1e-11)
        geometry,_=sk._geometry(ordinary);self.assertLess(np.linalg.norm(geometry[1]-np.asarray(w.tolist(),float),2),1e-6)

if __name__=='__main__':unittest.main()
