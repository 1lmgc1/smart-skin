"""Exact-neutral cache contract tests with explicit synthetic proof fixtures.

These are numerical/API tests; no Rhino capture or owner receipt is fabricated.
"""
import copy
import pathlib
import sys
import types
import unittest
from unittest import mock
import numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'src'/'SmartSkin.Rhino8'/'Python'))
import skin_kernel as sk
import constrained_uv as uv
import atlas_separation as atlas
from test_atlas_separation import bind,plane,seam


def prepared_fixture():
    surfaces=[]
    for i in range(4):
        r=plane(float(i),float(i+1));r.update(kind='middle',side=None,piece=i,orientation_reversed=False);surfaces.append(r)
    model,baseline=bind(surfaces,[seam(i,i+1) for i in range(3)])
    model.scale=5.;model.tolerance=1e-8
    baseline.update(patches=copy.deepcopy(surfaces),guides=[dict(degree=1,knots=[0,0,1,1],domain=[0,1],homogeneous_cp=[[0,.5,0,1],[4,.5,0,1]],guide_id='row:0')],network=dict(native_v=[.5],row_count=1,profile_count=5),valid=True,geometry_valid=True,fatal=False,disposition='native_screen_pending',experimental_commit_allowed=False)
    report=baseline['report'];report.update(fatal=False,full_boundary_pass=True,seam_position_error=0.,seam_angle_degrees=0.,seam_curvature_error=0.,position_tolerance=1e-8,angle_tolerance_degrees=.1,curvature_tolerance=1e-7)
    baseline['metrics']=report
    baseline['attachment_proof']=dict(schema='smartskin.attachments.v2',checked=True,source_full_finite_boundary_pass=True,shared_full_finite_boundary_pass=True,corner_policy='hard_upper_source_corners',excluded_intervals=[],excluded_points=[])
    atlas.screen_atlas(model,baseline)
    edit=uv.PreparedUVEdits.__new__(uv.PreparedUVEdits);edit.model=model;edit.kernel=sk;edit.cancelled=None;edit.differential_only=False
    edit._baseline=copy.deepcopy(baseline);edit._source_digest=edit._digest(model.spec);edit.basis_id='synthetic-unit-test-basis'
    edit.rows=np.array([.5]);edit.row_count=1;edit._cross_breaks=np.linspace(0,1,5);edit._profile_supports={'lift':(.25,.75)}
    edit._mirror_origin=np.array([2.,0.,0.]);edit._mirror_normal=np.array([1.,0.,0.]);edit.symmetry_tolerance=1e-8
    edit.shared_tolerances=dict(position=1e-8,normal_angle_degrees=.1,shape_operator=1e-7)
    edit.source_response_error=0.;edit.guide_coverage={'checked':True};edit._shoulder_range_evidence={};edit._handle_range_evidence={}
    edit._handle_specs=[dict(id='row:0:lift',guide_id='row:0',varying_axis='u',label='Row',minimum=-.1,maximum=.1,neutral=0.,units='model units',position=[2.,.5,0.],anchor=[2.,.5,0.],direction=[0,0,1])]
    edit._records=[{k:v for k,v in r.items() if k!='homogeneous_cp'} for r in surfaces]
    edit._baseline_cp=[np.asarray(r['homogeneous_cp'],float) for r in surfaces]
    edit._responses={'row:0:lift':[np.zeros_like(x) for x in edit._baseline_cp]}
    for a in edit._baseline_cp+edit._responses['row:0:lift']:a.setflags(write=False)
    edit.validator=mock.Mock(side_effect=AssertionError('Initial neutral must not rerun validator'))
    prepared=sk._PreparedNativeRepairs.__new__(sk._PreparedNativeRepairs)
    prepared.spec=copy.deepcopy(model.spec);prepared.base=model;prepared.cancelled=None;prepared._uv_edits=edit
    prepared._baseline_result=copy.deepcopy(baseline);prepared._initial_neutral_seal=prepared._initial_neutral_binding()
    return prepared,edit,baseline


class InitialNeutralTests(unittest.TestCase):
    def test_verbatim_geometry_guides_network_fresh_positions_and_request(self):
        prepared,edit,baseline=prepared_fixture();request=edit.neutral_request(7)
        result=prepared.evaluate_initial_neutral(request)
        for key in ('surfaces','patches','guides','network'):self.assertEqual(result[key],baseline[key])
        self.assertEqual(result['edit_request'],request);self.assertEqual(result['handle_positions_request'],request)
        self.assertEqual(result['handle_positions'],{'row:0:lift':[2.,.5,0.]})
        self.assertTrue(result['edit_proof']['source_2jets_unchanged']);self.assertTrue(result['edit_proof']['symmetry_compatible'])
        self.assertFalse(result['experimental_commit_allowed']);self.assertFalse(result['initial_neutral_reuse']['native_owner_receipt_reused'])
        self.assertTrue(atlas.verify_atlas_separation(result,prepared.spec,request));edit.validator.assert_not_called()
        with self.assertRaisesRegex(sk.UnsupportedFamily,'stale'):prepared.evaluate_initial_neutral(request)

    def test_nonzero_request_requires_the_ordinary_path(self):
        prepared,edit,_=prepared_fixture();request=edit.neutral_request(1);request['values']['row:0:lift']=.01
        with self.assertRaisesRegex(ValueError,'exact zero'):prepared.evaluate_initial_neutral(request)
        with mock.patch.object(edit,'evaluate_edit',return_value={'ordinary':True}) as ordinary:
            self.assertEqual(prepared.evaluate_edit(request),{'ordinary':True});ordinary.assert_called_once()
        self.assertIsNone(prepared._initial_neutral_seal)

    def test_changed_source_tolerances_basis_responses_and_evidence_rejected(self):
        mutations=(lambda p,e:p.spec.update(changed=True),lambda p,e:setattr(p.base,'tolerance',2e-8),
                   lambda p,e:p._baseline_result['guides'][0]['homogeneous_cp'][0].__setitem__(0,.01),
                   lambda p,e:p._baseline_result['report'].__setitem__('seam_curvature_error',1e-3),
                   lambda p,e:setattr(e,'basis_id','changed'),
                   lambda p,e:e._handle_specs[0].__setitem__('maximum',.2),
                   lambda p,e:e._responses['row:0:lift'].__setitem__(0,np.ones_like(e._responses['row:0:lift'][0])))
        for change in mutations:
            with self.subTest(change=change):
                prepared,edit,_=prepared_fixture();request=edit.neutral_request(1);change(prepared,edit)
                with self.assertRaises((sk.UnsupportedFamily,ValueError)):prepared.evaluate_initial_neutral(request)
                edit.validator.assert_not_called()

    def test_changed_state_during_handoff_rejected(self):
        prepared,edit,_=prepared_fixture();request=edit.neutral_request(1);original=edit._anchor
        def mutate(*args):
            point=original(*args);edit._handle_specs[0]['maximum']=.2;return point
        with mock.patch.object(edit,'_anchor',side_effect=mutate):
            with self.assertRaisesRegex(sk.UnsupportedFamily,'changed during'):prepared.evaluate_initial_neutral(request)

    def test_native_receipt_never_reused(self):
        prepared,edit,_=prepared_fixture()
        for baseline in (prepared._baseline_result,edit._baseline):baseline['native_receipt']={'synthetic_marker':'must not transfer'}
        prepared._initial_neutral_seal=prepared._initial_neutral_binding()
        result=prepared.evaluate_initial_neutral(edit.neutral_request(1))
        self.assertNotIn('native_receipt',result);self.assertFalse(result['experimental_commit_allowed'])

    def test_atlas_rebind_rechecks_geometry_guides_receipt_and_zero_request(self):
        for kind in ('geometry','guides','report','source','nonzero','receipt'):
            with self.subTest(kind=kind):
                prepared,edit,baseline=prepared_fixture();request=edit.neutral_request(1);result=copy.deepcopy(baseline);result['edit_request']=copy.deepcopy(request)
                if kind=='geometry':result['surfaces'][0]['homogeneous_cp'][0][0][2]+=.01
                elif kind=='guides':result['guides'][0]['domain']=[0,2]
                elif kind=='report':result['report']['source_digest']='changed'
                elif kind=='source':prepared.spec['source_boundaries']['roles']['synthetic'][0]['changed']=True
                elif kind=='nonzero':request['values']['row:0:lift']=.1;result['edit_request']=copy.deepcopy(request)
                elif kind=='receipt':baseline['atlas_separation']['passed']=False
                with self.assertRaises(atlas.AtlasSeparationError):atlas.rebind_identical_neutral_request(baseline,result,prepared.spec,request)

    def test_cancellation_rejects_without_issuing_result(self):
        prepared,edit,_=prepared_fixture()
        with self.assertRaises(sk.Cancelled):prepared.evaluate_initial_neutral(edit.neutral_request(1),lambda:True)
        edit.validator.assert_not_called()

if __name__=='__main__':unittest.main()
