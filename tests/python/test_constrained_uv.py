"""Redistributable coupled-edit algebra and source-derived kernel tests.

These tests are not licensed Rhino GUI verification or full native-attachment
acceptance. The generic fixture baseline is used only for differential evidence.
"""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
ASSETS=ROOT/'src/SmartSkin.Rhino8/Python'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
uv=load('constrained_uv_test',ASSETS/'constrained_uv.py')
sk=load('constrained_uv_kernel_test',ASSETS/'skin_kernel.py')
fixtures=load('constrained_uv_fixture',ROOT/'tests/test_skin_kernel.py')
preview=load('constrained_uv_preview',ASSETS/'preview.py')
proof_fixtures=load('constrained_uv_proof_fixtures',ROOT/'tests/python/attachment_proof_fixtures.py')


class CoupledSharedJetTests(unittest.TestCase):
    def setUp(self):
        with uv.mp.workdps(70):
            self.common=tuple(uv._BUMP[:,None]*uv._poly([[0,0,f]]) for f in (1,.2,-.15))
            self.transport=tuple(uv._poly(x) for x in ([1.3,.2],[.3,-.1],[.1],[-.15,.04]))
            self.left,self.right=uv.coupled_seam_displacements(self.common,self.transport)

    def test_changed_shared_curve_and_nontrivial_transported_two_jets(self):
        A,B,G,D=self.transport
        for v in np.linspace(0,1,33):
            L=lambda i,j:uv.tensor_value(self.left,1,v,i,j)
            R=lambda i,j:uv.tensor_value(self.right,0,v,i,j)
            a,b,g,d=[float(uv._value(x,v)) for x in (A,B,G,D)]
            np.testing.assert_allclose(R(0,0),L(0,0),atol=3e-11)
            np.testing.assert_allclose(R(1,0),a*L(1,0)+b*L(0,1),atol=3e-10)
            np.testing.assert_allclose(R(2,0),a*a*L(2,0)+2*a*b*L(1,1)+b*b*L(0,2)+g*L(1,0)+d*L(0,1),atol=3e-9)
        self.assertGreater(np.linalg.norm(uv.tensor_value(self.left,1,.5)),.99)
        self.assertGreater(np.linalg.norm(uv.tensor_value(self.right,0,.5)),.99)
        self.assertGreater(np.linalg.norm(uv.tensor_value(self.left,1,.3,1,0)-uv.tensor_value(self.right,0,.3,1,0)),.01)

    def test_all_original_outer_source_two_jets_unchanged(self):
        for poly,outer in ((self.left,0),(self.right,1)):
            for t in np.linspace(0,1,23):
                for du in range(3):
                    for dv in range(3-du):
                        np.testing.assert_allclose(uv.tensor_value(poly,outer,t,du,dv),0,atol=2e-9)
                        for endpoint in (0,1):
                            np.testing.assert_allclose(uv.tensor_value(poly,t,endpoint,du,dv),0,atol=2e-8)

    def test_endpoint_order_four_is_needed_by_sheared_mixed_corner_jets(self):
        for derivative in range(5):
            for endpoint in (0,1):
                self.assertEqual(float(uv._value(uv._der(uv._BUMP,derivative),endpoint)),0.)
        # A merely third-order bubble leaves a second V derivative of the
        # transported R_uu nonzero at the source corner when beta != zero.
        cubic_bubble=uv._poly([0,0,0,64,-192,192,-64])
        weak=(cubic_bubble[:,None]*uv._poly([[0,0,1]]),uv._zeros((1,3)),uv._zeros((1,3)))
        transported=uv.transported_jets(weak,*self.transport)
        self.assertGreater(np.linalg.norm(np.asarray(uv._value(uv._der(transported[2],2),0),float)),1.)

    def test_u_and_v_shared_selections_both_move_incident_patches(self):
        # Swapping the atlas axes makes the same coupled construction a U-row
        # edit rather than a V-profile edit. It is not a one-patch bubble.
        upper=np.moveaxis(self.left,0,1);lower=np.moveaxis(self.right,0,1)
        for u in (.2,.4,.5,.7):
            np.testing.assert_allclose(uv.tensor_value(upper,u,1),uv.tensor_value(lower,u,0),atol=1e-10)
        self.assertGreater(np.linalg.norm(uv.tensor_value(upper,.5,1)),.99)
        self.assertGreater(np.linalg.norm(uv.tensor_value(lower,.5,0)),.99)

    def test_coincident_guides_allow_degree_knots_and_rational_gauge_changes(self):
        first=dict(degree=2,knots=[0.]*3+[1.]*3,domain=[0.,1.],
                   homogeneous_cp=[[0.,0.,0.,1.],[.4,.08,0.,.8],[1.,0.,0.,1.]])
        cp=uv._elevate(first['homogeneous_cp'],5,0)
        spline=sk.BSpline([0.]*6+[1.]*6,cp,5).insert_knot(.37,5)
        second=dict(degree=5,knots=spline.t.tolist(),domain=[0.,1.],homogeneous_cp=spline.c.tolist())
        self.assertLessEqual(uv._coincident_curve_bound(first,second,1e-8),1e-8)
        with uv.mp.workdps(70):
            power=uv._mul(uv._poly([1.,.3]),uv._b2p(uv._poly(first['homogeneous_cp'])))
            cp=np.asarray(uv._p2b(power),float)
        gauge=dict(degree=3,knots=[0.]*4+[1.]*4,domain=[0.,1.],homogeneous_cp=cp.tolist())
        self.assertLessEqual(uv._coincident_curve_bound(first,gauge,1e-8),1e-8)
        wrong=copy.deepcopy(second);wrong['homogeneous_cp'][0][0]+=.1
        self.assertGreater(uv._coincident_curve_bound(first,wrong,1e-8),1e-8)


class SourceDerivedEditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model=sk.build_model(fixtures.fixture())
        cls.baseline=cls.model.evaluate(1,validate=False)
        cls.prepared=uv.PreparedUVEdits(cls.model,cls.baseline,cls.model._validate,sk,differential_only=True)

    def request(self, changes):
        request=self.prepared.neutral_request(3)
        request['values'].update(changes)
        return request

    def test_actual_native_coefficient_cache_contains_eighteen_source_derived_handles(self):
        catalog=self.prepared.handle_edit_catalog()
        self.assertEqual(len(catalog['handles']),18)
        self.assertEqual(sum(h['varying_axis']=='u' for h in catalog['handles']),9)
        self.assertEqual(sum(h['varying_axis']=='v' for h in catalog['handles']),9)
        self.assertLessEqual(self.prepared.coefficient_count,65536)
        self.assertFalse(catalog['enabled'])
        self.assertTrue(any(s is not None for s in self.prepared._responses['profile:0:lift']))

    def test_actual_profile_edit_moves_both_neighbors_and_mirror(self):
        amount=.015
        result=self.prepared.evaluate_edit(self.request({'profile:0:lift':amount,'profile:4:lift':amount}))
        old=self.baseline['surfaces'];new=result['surfaces'];v=sum(self.prepared._profile_support)/2
        for side,piece,edge in ((0,0,0.),(1,3,1.)):
            ci=next(i for i,s in enumerate(old) if s['kind']=='collar' and s['side']==side and s['piece']==2)
            mi=next(i for i,s in enumerate(old) if s['kind']=='middle' and s['piece']==piece)
            dc=sk.evaluate_surface(new[ci],1,v)-sk.evaluate_surface(old[ci],1,v)
            dm=sk.evaluate_surface(new[mi],edge,v)-sk.evaluate_surface(old[mi],edge,v)
            np.testing.assert_allclose(dc,[0,0,amount],atol=1e-11)
            np.testing.assert_allclose(dm,dc,atol=1e-11)
        self.assertTrue(result['edit_proof']['shared_2jets_compatible'],result['report'])
        self.assertTrue(result['edit_proof']['symmetry_checked'])
        self.assertTrue(result['edit_proof']['symmetry_compatible'])
        self.assertLessEqual(result['edit_proof']['symmetry_residual'],self.prepared.handle_edit_catalog()['symmetry_tolerance'])
        preview.verify_edit_result(result['edit_request'],result)
        self.assertNotIn('attachment_proof',result)
        self.assertFalse(result['experimental_commit_allowed'])

    def test_actual_row_edit_moves_trace_from_both_v_sides(self):
        amount=.012;row=4
        result=self.prepared.evaluate_edit(self.request({'row:%d:lift'%row:amount}))
        index=next(i for i,s in enumerate(result['surfaces']) if s['kind']=='middle' and s['piece']==1)
        v=float(self.model.rows[row]);before=float(np.nextafter(v,-np.inf));after=float(np.nextafter(v,np.inf))
        old,new=self.baseline['surfaces'][index],result['surfaces'][index]
        for parameter in (before,v,after):
            delta=sk.evaluate_surface(new,1,parameter)-sk.evaluate_surface(old,1,parameter)
            np.testing.assert_allclose(delta,[0,0,amount],atol=1e-10)
        self.assertTrue(result['edit_proof']['shared_2jets_compatible'],result['report'])
        self.assertEqual(result['edit_request']['values']['profile:2:lift'],0.)
        moved=result['handle_positions']['profile:2:lift']
        base=next(h['position'] for h in self.prepared.handle_edit_catalog()['handles'] if h['id']=='profile:2:lift')
        self.assertGreater(abs(moved[2]-base[2]),1e-5)

    def test_original_source_loci_and_two_jets_stay_unchanged_after_combined_edits(self):
        request=self.request({'row:0:lift':.01,'row:8:lift':-.009,'row:4:lift':.02,
                              'profile:0:lift':.012,'profile:4:lift':.012,
                              'profile:1:lift':-.006,'profile:3:lift':-.006,'profile:2:lift':.005})
        before=copy.deepcopy(self.model.spec)
        result=self.prepared.evaluate_edit(request)
        self.assertEqual(before,self.model.spec)
        for original,edited in zip(self.baseline['surfaces'],result['surfaces']):
            ua,ub=original['domain'][0]
            points=[(u,v) for u in np.linspace(ua,ub,5) for v in (self.model.v0,self.model.v1)]
            if original['kind']=='collar' and original['piece']==0:
                points += [(ua,v) for v in np.linspace(self.model.v0,self.model.v1,11)]
            for u,v in points:
                for du,dv in ((0,0),(1,0),(0,1),(2,0),(1,1),(0,2)):
                    np.testing.assert_allclose(sk.evaluate_surface(edited,u,v,du,dv),sk.evaluate_surface(original,u,v,du,dv),atol=3e-8)
        self.assertTrue(result['edit_proof']['shared_2jets_compatible'],result['report'])

    def test_exact_guides_are_traces_of_edited_surfaces(self):
        result=self.prepared.evaluate_edit(self.request({'row:4:lift':.01,'profile:2:lift':.005}))
        for guide in result['guides']:
            if guide['kind']=='profile':
                j=guide['piece'];s=next(s for s in result['surfaces'] if s['kind']=='middle' and s['piece']==min(j,3))
                for v in np.linspace(*guide['domain'],7):
                    h=sk.BSpline(guide['knots'],guide['homogeneous_cp'],guide['degree'])(v)
                    np.testing.assert_allclose(h[:3]/h[3],sk.evaluate_surface(s,1 if j==4 else 0,v),atol=1e-10)
            elif guide['kind']=='row_middle':
                s=next(s for s in result['surfaces'] if s['kind']=='middle' and s['piece']==guide['piece'])
                for u in (.1,.5,.9):
                    h=sk.BSpline(guide['knots'],guide['homogeneous_cp'],guide['degree'])(u)
                    np.testing.assert_allclose(h[:3]/h[3],sk.evaluate_surface(s,u,self.model.rows[guide['row']]),atol=1e-10)

    def test_fail_closed_on_missing_validator_bad_mirror_foreign_request_and_cancellation(self):
        with self.assertRaisesRegex(ValueError,'validator'):
            uv.PreparedUVEdits(self.model,self.baseline,None,sk)
        with self.assertRaisesRegex(ValueError,'separately validated'):
            uv.PreparedUVEdits(self.model,self.baseline,self.model._validate,sk)
        with self.assertRaisesRegex(ValueError,'Mirror'):
            self.prepared.evaluate_edit(self.request({'profile:0:lift':.01}))
        request=self.request({});request['basis_id']='foreign'
        with self.assertRaisesRegex(ValueError,'foreign'):self.prepared.evaluate_edit(request)
        with self.assertRaises(sk.Cancelled):self.prepared.evaluate_edit(self.request({}),cancelled=lambda:True)

    def test_actual_affine_response_matches_analytic_guide_displacement(self):
        # Independent pointwise expected field, including intersecting handles.
        request=self.request({'row:4:lift':.013,'profile:1:lift':.009,'profile:3:lift':.009})
        result=self.prepared.evaluate_edit(request)
        for old,new in zip(self.baseline['surfaces'],result['surfaces']):
            if old['kind']!='middle':continue
            j=old['piece'];a,b=self.prepared._cross_breaks[j:j+2]
            for u,v in ((.15,.43),(.5,.55),(.82,.61)):
                q=a+(b-a)*u
                vcard=uv._scalar_span('row',(v,v),tuple(self.model.rows[[3,4,5]]))
                expected=.013*1024*q**5*(1-q)**5*float(vcard[0])
                lo,hi=self.prepared._profile_support;t=(v-lo)/(hi-lo)
                profile=1024*t**5*(1-t)**5
                if j in (1,3):expected+=.009*profile*float(uv._value(uv._HERMITE[0],u))
                if j+1 in (1,3):expected+=.009*profile*float(uv._value(uv._HERMITE[3],u))
                delta=sk.evaluate_surface(new,u,v)-sk.evaluate_surface(old,u,v)
                np.testing.assert_allclose(delta,self.prepared.direction*expected,atol=2e-11)

    def test_per_value_failure_is_not_replaced_by_a_cached_baseline_pass(self):
        trial=copy.copy(self.prepared);calls=[]
        report=dict(checked=True,fatal=True,full_boundary_pass=False,reason='Synthetic per-value regularity gate rejected this request.',
                    seam_position_error=0.,seam_angle_degrees=0.,seam_curvature_error=0.,
                    position_tolerance=trial.shared_tolerances['position'],
                    angle_tolerance_degrees=trial.shared_tolerances['normal_angle_degrees'],
                    curvature_tolerance=trial.shared_tolerances['shape_operator'])
        def validator(surfaces,cancelled):
            calls.append(surfaces)
            return copy.deepcopy(report)
        trial.validator=validator
        result=trial.evaluate_edit(self.request({'row:4:lift':.01}))
        self.assertEqual(len(calls),1)
        self.assertFalse(result['valid'])
        self.assertTrue(result['fatal'])
        self.assertNotIn('attachment_proof',result)
        report['position_tolerance']*=2
        with self.assertRaisesRegex(ValueError,'tolerances'):
            trial.evaluate_edit(self.request({'row:4:lift':.02}))

    def test_replaced_corner_support_and_nonconstant_denominator_fail_closed(self):
        short=copy.deepcopy(self.baseline)
        for s in short['surfaces']:
            if s['kind']=='collar' and s['piece']==2:s['domain'][1][1]=float(self.model.rows[-2])
        with self.assertRaisesRegex(ValueError,'corner chart|coverage|shoulder support'):
            uv.PreparedUVEdits(self.model,short,self.model._validate,sk,differential_only=True)
        rational=copy.deepcopy(self.baseline)
        surface=next(s for s in rational['surfaces'] if s['kind']=='middle')
        surface['homogeneous_cp'][2][4][3]=float(np.nextafter(1.,2.))
        with self.assertRaisesRegex(ValueError,'U-only'):
            uv.PreparedUVEdits(self.model,rational,self.model._validate,sk,differential_only=True)

    def test_source_mutation_during_validation_is_detected(self):
        trial=copy.copy(self.prepared);trial.model=copy.copy(self.model);trial.model.spec=copy.deepcopy(self.model.spec)
        def validator(surfaces,cancelled):
            trial.model.spec['profiles'][0]['p0'][0]+=.1
            return dict(checked=True,fatal=False)
        trial.validator=validator
        with self.assertRaisesRegex(ValueError,'during edit validation'):
            trial.evaluate_edit(self.request({}))

    def test_equal_mirror_values_do_not_hide_asymmetric_actual_geometry(self):
        trial=copy.copy(self.prepared)
        trial._baseline_cp=[cp.copy() for cp in self.prepared._baseline_cp]
        index=next(i for i,s in enumerate(self.prepared._records) if s['kind']=='middle' and s['piece']==0)
        cp=trial._baseline_cp[index]
        # Pick an interior control point of one explicit V Bezier span, away
        # from all shared rows and their first two derivative control rows.
        vi=4*self.prepared._records[index]['degree_v']+6
        cp[5,vi,2]+=.003*cp[5,vi,3]
        request=self.request({})
        self.assertTrue(all(request['values'][h['id']]==request['values'][h['mirror_handle_id']]
                            for h in self.prepared.handle_edit_catalog()['handles']))
        result=trial.evaluate_edit(request)
        self.assertTrue(result['edit_proof']['shared_2jets_compatible'])
        self.assertTrue(result['edit_proof']['symmetry_checked'])
        self.assertFalse(result['edit_proof']['symmetry_compatible'])
        self.assertGreater(result['edit_proof']['symmetry_residual'],.0029)
        self.assertFalse(result['valid'])
        self.assertFalse(result['experimental_commit_allowed'])
        with self.assertRaisesRegex(ValueError,'symmetry'):
            preview.verify_edit_result(request,result)

    def test_symmetry_checks_unknown_and_untouched_corner_charts(self):
        surfaces=copy.deepcopy(self.baseline['surfaces'])
        self.assertFalse(self.prepared._geometric_symmetry(surfaces[:-1])['checked'])
        unknown=copy.deepcopy(surfaces[0]);unknown['kind']='unknown_corner_chart';surfaces.append(unknown)
        self.assertFalse(self.prepared._geometric_symmetry(surfaces)['checked'])
        surfaces.pop()
        for side in (0,1):
            corner=copy.deepcopy(next(s for s in surfaces if s['kind']=='collar' and s['side']==side and s['piece']==0))
            corner.update(kind='upper_hard_corner',piece=0)
            surfaces.append(corner)
        checked=self.prepared._geometric_symmetry(surfaces)
        self.assertTrue(checked['compatible'],checked)
        self.assertEqual(checked['chart_pairs'],6)
        surfaces[-1]['homogeneous_cp'][2][2][2]+=.001
        checked=self.prepared._geometric_symmetry(surfaces)
        self.assertTrue(checked['checked'])
        self.assertFalse(checked['compatible'])

    def test_symmetry_bound_accepts_projective_weight_rescaling(self):
        surfaces=copy.deepcopy(self.baseline['surfaces'])
        for s in surfaces:
            if s.get('side')==1 or s['kind']=='middle' and s['piece']>=2:
                s['homogeneous_cp']=(7*np.asarray(s['homogeneous_cp'])).tolist()
        checked=self.prepared._geometric_symmetry(surfaces)
        self.assertTrue(checked['checked'])
        self.assertTrue(checked['compatible'],checked)

    @classmethod
    def regenerated_eight_row_fixture(cls,include_bridge=False):
        """Synthetic exact cell split; no actual fan-attachment claim."""
        result=copy.deepcopy(cls.baseline)
        result['network']['parameter_map']={'native_v':cls.model.vs.tolist(),
                                           'profile_t':[0.]+list(cls.baseline['network']['profile_parameters'])+[1.]}
        result['network']['native_v']=list(cls.baseline['network']['native_v'][:-1])
        result['network']['row_count']=8
        result['network']['profile_parameters']=list(cls.baseline['network']['profile_parameters'][:-1])
        result['guides']=[g for g in result['guides'] if not g['kind'].startswith('row_') or g['row']<8]
        def clipped(record,lo,hi):
            breaks,spans=uv._span_coefficients(record)
            kept=[(a,b,cp) for a,b,cp in zip(breaks[:-1],breaks[1:],spans) if lo<=a and b<=hi]
            pv=record['degree_v'];record=copy.deepcopy(record)
            record['domain'][1]=[lo,hi]
            record['knots_v']=[lo]*(pv+1)+sum(([b]*pv for _,b,_ in kept[:-1]),[])+[hi]*(pv+1)
            cp=np.concatenate([kept[0][2]]+[item[2][:,1:] for item in kept[1:]],axis=1)
            return uv._record_with_cp(record,cp)
        for side in (0,1):
            for piece,kind in ([(0,'lower_chart'),(2,'lower_bridge')] if include_bridge else [(0,'lower_chart')]):
                index=next(i for i,s in enumerate(result['surfaces']) if s['kind']=='collar' and s['side']==side and s['piece']==piece)
                original=result['surfaces'][index]
                result['surfaces'][index]=clipped(original,cls.model.v0,.9)
                lower=clipped(original,.9,cls.model.v1)
                lower.update(kind=kind,piece='synthetic_lower_cell' if kind=='lower_chart' else piece)
                index=len(result['surfaces']);result['surfaces'].append(lower)
                for axis in ('u','v'):
                    for end,parameter in enumerate(lower['domain'][1 if axis=='u' else 0]):
                        guide=uv.surface_isocurve(lower,axis,parameter)
                        guide.update(kind='fan_internal' if kind=='lower_chart' else 'lower_bridge_internal',
                                     guide_id='%s:%d:%s:%d'%(kind,side,axis,end),varying_axis=axis,
                                     binding=dict(schema='smartskin.guide-isocurve.v1',surface_index=index,
                                                  varying_axis=axis,constant_parameter=float(parameter)))
                        result['guides'].append(guide)
        return result

    def regenerated_validator(self,surfaces,cancelled):
        # Recombine the exact synthetic rectangular split for the independent
        # generic validator, after separately checking both split-boundary jets.
        ordinary=[copy.deepcopy(s) for s in surfaces if s['kind'] not in ('lower_chart','lower_bridge')]
        for lower in [s for s in surfaces if s['kind'] in ('lower_chart','lower_bridge')]:
            side=lower['side'];piece=0 if lower['kind']=='lower_chart' else lower['piece']
            index=next(i for i,s in enumerate(ordinary) if s['kind']=='collar' and s['side']==side and s['piece']==piece)
            body=ordinary[index]
            for u in np.linspace(*body['domain'][0],7):
                for du,dv in ((0,0),(1,0),(0,1),(2,0),(1,1),(0,2)):
                    np.testing.assert_allclose(sk.evaluate_surface(body,u,.9,du,dv),sk.evaluate_surface(lower,u,.9,du,dv),atol=3e-8)
            b0,s0=uv._span_coefficients(body);b1,s1=uv._span_coefficients(lower)
            spans=s0+s1;breaks=b0+b1[1:];pv=body['degree_v']
            cp=np.concatenate([spans[0]]+[s[:,1:] for s in spans[1:]],axis=1)
            body['domain'][1]=[breaks[0],breaks[-1]]
            body['knots_v']=[breaks[0]]*(pv+1)+sum(([v]*pv for v in breaks[1:-1]),[])+[breaks[-1]]*(pv+1)
            ordinary[index]=uv._record_with_cp(body,cp)
        return self.model._validate(ordinary,cancelled)

    def test_regenerated_eight_row_layout_has_seventeen_handles_and_complete_current_guides(self):
        baseline=self.regenerated_eight_row_fixture();tmap=self.model.tmap.c.copy()
        prepared=uv.PreparedUVEdits(self.model,baseline,self.regenerated_validator,sk,differential_only=True)
        catalog=prepared.handle_edit_catalog()
        self.assertEqual(len(catalog['handles']),17)
        self.assertEqual(catalog['row_count'],8)
        self.assertEqual(catalog['native_v'][-1],.9)
        self.assertNotEqual(prepared.basis_id,self.prepared.basis_id)
        self.assertEqual(prepared._profile_support,(.12,.9))
        request=prepared.neutral_request(4);request['values']['row:7:lift']=.009
        request['values']['profile:0:lift']=request['values']['profile:4:lift']=.005
        result=prepared.evaluate_edit(request)
        self.assertTrue(result['edit_proof']['shared_2jets_compatible'],result['report'])
        self.assertTrue(result['edit_proof']['symmetry_compatible'],result['report'])
        self.assertEqual(result['network']['parameter_map'],baseline['network']['parameter_map'])
        self.assertIn(.95,result['network']['parameter_map']['native_v'])
        np.testing.assert_array_equal(self.model.tmap.c,tmap)
        self.assertEqual({g['row'] for g in result['guides'] if g['kind'].startswith('row_')},set(range(8)))
        self.assertNotIn(.95,{g['native_v'] for g in result['guides'] if g['kind'].startswith('row_')})
        retained=[g for g in result['guides'] if g['kind']=='fan_internal']
        self.assertEqual(retained,[g for g in baseline['guides'] if g['kind']=='fan_internal'])
        self.assertEqual(len(retained),8)
        for guide in retained:
            binding=guide['binding'];surface=result['surfaces'][binding['surface_index']]
            self.assertEqual(guide['homogeneous_cp'],uv.surface_isocurve(surface,binding['varying_axis'],binding['constant_parameter'])['homogeneous_cp'])
        for row in range(8):
            for side in (0,1):
                intervals=sorted(g['domain'] for g in result['guides'] if g['kind']=='row_collar' and g['row']==row and g['side']==side)
                self.assertEqual(intervals[0][0],0.)
                self.assertEqual(intervals[-1][1],1.)
                self.assertTrue(all(a[1]==b[0] for a,b in zip(intervals[:-1],intervals[1:])))
        preview.verify_edit_result(request,result)

    def test_stale_partial_rows_and_unbound_or_partial_repaired_guides_are_rejected(self):
        baseline=self.regenerated_eight_row_fixture()
        bad=copy.deepcopy(baseline)
        bad['network']['native_v'].append(.95);bad['network']['row_count']=9
        with self.assertRaisesRegex(ValueError,'incomplete collar coverage'):
            uv.PreparedUVEdits(self.model,bad,self.regenerated_validator,sk,differential_only=True)
        for alteration,reason in (
                (lambda x:x['guides'].pop(),'missing complete'),
                (lambda x:x['guides'][-1].pop('binding'),'binding'),
                (lambda x:x['guides'][-1]['homogeneous_cp'][0].__setitem__(2,.1),'not on')):
            bad=copy.deepcopy(baseline);alteration(bad)
            with self.assertRaisesRegex(ValueError,reason):
                uv.PreparedUVEdits(self.model,bad,self.regenerated_validator,sk,differential_only=True)

    def test_only_captured_approved_upper_point_may_replace_a_degenerate_guide(self):
        # Source-binding metadata test, not native attachment certification.
        trial=copy.copy(self.prepared);trial.model=copy.copy(self.model)
        trial.model.spec=copy.deepcopy(self.model.spec)
        evidence=proof_fixtures.source_model()
        for records in evidence['source_boundaries']['roles'].values():
            for record in records:
                for endpoint in record['reference_corners']:
                    x,y,z=endpoint['point'];endpoint['point']=[3*x-3,-y,z]
        trial.model.spec.update(evidence)
        proof=proof_fixtures.full_attachment_result()['attachment_proof']
        proof['excluded_points']=[preview.approved_upper_source_corners(trial.model.spec)['upper:side0']]
        trial._baseline={'attachment_proof':proof,'network':{'collapsed_boundary_bindings':[
            dict(surface_index=0,edge='bottom',corner_id='upper:side0')]}}
        chart=dict(kind='upper_hard_corner',side=0,piece=0,degree_u=1,degree_v=1,
                   knots_u=[0.,0.,1.,1.],knots_v=[0.,0.,1.,1.],domain=[[0.,1.],[0.,1.]],
                   homogeneous_cp=[[[-3.,0.,0.,1.],[-3.,1.,0.,1.]],[[-3.,0.,0.,1.],[-2.,1.,0.,1.]]],
                   collapsed_parameter_edge='v=0',approved_physical_corner_id='upper:side0')
        self.assertEqual(trial._collapsed_guide_boundaries([chart]),{0})
        nonconstant=copy.deepcopy(chart);nonconstant['homogeneous_cp'][1][0][0]+=.01
        with self.assertRaisesRegex(ValueError,'constant upper source point'):
            trial._collapsed_guide_boundaries([nonconstant])
        lower=copy.deepcopy(chart);lower['kind']='lower_chart'
        with self.assertRaisesRegex(ValueError,'Only an approved upper'):
            trial._collapsed_guide_boundaries([lower])
        trial._baseline['attachment_proof']['excluded_points'][0]['upper_native_parameter']+=.1
        with self.assertRaisesRegex(ValueError,'source-vertex proof'):
            trial._collapsed_guide_boundaries([chart])

    def test_outer_shoulder_low_high_and_combined_move_actual_endpoint_regions(self):
        catalog=self.prepared.handle_edit_catalog()
        for mode in ('upper','lower'):
            handle=next(h for h in catalog['handles'] if h['id']=='profile:0:'+mode)
            v=sum(handle['native_v_support'])/2
            for value in (handle['minimum'],handle['maximum']):
                request=self.request({'profile:0:'+mode:value,'profile:4:'+mode:value})
                result=self.prepared.evaluate_edit(request)
                self.assertTrue(result['valid'],result['reason'])
                for side in (0,1):
                    ci=next(i for i,s in enumerate(result['surfaces']) if s['kind']=='collar' and s['side']==side and s['piece']==2)
                    delta=sk.evaluate_surface(result['surfaces'][ci],1.,v)-sk.evaluate_surface(self.baseline['surfaces'][ci],1.,v)
                    np.testing.assert_allclose(delta,self.prepared.direction*value,atol=2e-10)
                    first=next(i for i,s in enumerate(result['surfaces']) if s['kind']=='collar' and s['side']==side and s['piece']==0)
                    np.testing.assert_array_equal(result['surfaces'][first]['homogeneous_cp'],self.baseline['surfaces'][first]['homogeneous_cp'])
                self.assertTrue(result['edit_proof']['source_2jets_unchanged'])
                self.assertTrue(result['edit_proof']['shared_2jets_compatible'])
                preview.verify_edit_result(request,result)
        changes={}
        for mode in ('upper','lower'):
            h=next(x for x in catalog['handles'] if x['id']=='profile:0:'+mode)
            changes['profile:0:'+mode]=changes['profile:4:'+mode]=h['maximum']*.5
        self.assertTrue(self.prepared.evaluate_edit(self.request(changes))['valid'])

    def test_lower_shoulder_regenerates_its_bridge_guides_and_keeps_fan_geometry(self):
        baseline=self.regenerated_eight_row_fixture(include_bridge=True)
        prepared=uv.PreparedUVEdits(self.model,baseline,self.regenerated_validator,sk,differential_only=True)
        h=next(h for h in prepared.handle_edit_catalog()['handles'] if h['id']=='profile:0:lower')
        request=prepared.neutral_request(5)
        request['values']['profile:0:lower']=request['values']['profile:4:lower']=h['maximum']*.5
        result=prepared.evaluate_edit(request)
        self.assertTrue(result['valid'],result['reason'])
        changed=0
        for old,new in zip(baseline['surfaces'],result['surfaces']):
            if old['kind']=='lower_chart':np.testing.assert_array_equal(old['homogeneous_cp'],new['homogeneous_cp'])
        for guide in result['guides']:
            if guide['kind']!='lower_bridge_internal':continue
            binding=guide['binding'];expected=uv.surface_isocurve(result['surfaces'][binding['surface_index']],binding['varying_axis'],binding['constant_parameter'])
            self.assertEqual(guide['homogeneous_cp'],expected['homogeneous_cp'])
            old=next(g for g in baseline['guides'] if g.get('guide_id')==guide['guide_id'])
            changed+=int(guide['homogeneous_cp']!=old['homogeneous_cp'])
        self.assertGreater(changed,0)
        self.assertGreater(result['guide_coverage']['regenerated_bound_guide_count'],0)

    def test_unsupported_nonzero_shoulder_shear_fails_fresh_shared_geometry_gate(self):
        trial=copy.copy(self.prepared);trial._baseline_cp=[cp.copy() for cp in trial._baseline_cp]
        for index,record in enumerate(trial._records):
            if record.get('kind')!='middle' or record['piece'] not in (0,3):continue
            pu,pv=record['degree_u'],record['degree_v'];bu=np.asarray(uv._p2b(uv._poly([0.,1.,-1.]),pu),float)
            breaks=sorted(set(record['knots_v']))
            for span,(a,b) in enumerate(zip(breaks[:-1],breaks[1:])):
                v=uv._scalar_span('profile',(a,b),trial._profile_supports['upper'])
                bv=np.asarray(uv._p2b(v,pv),float)
                trial._baseline_cp[index][:,span*pv:span*pv+pv+1,1]+=.5*bu[:,None]*bv[None,:]
        request=self.request({'profile:0:upper':.01,'profile:4:upper':.01})
        result=trial.evaluate_edit(request)
        self.assertTrue(result['edit_proof']['source_2jets_unchanged'])
        self.assertFalse(result['edit_proof']['shared_2jets_compatible'])
        self.assertFalse(result['valid'])
        self.assertFalse(result['experimental_commit_allowed'])

    def test_full_result_validator_sees_fresh_guides_and_cannot_skip_native_screen(self):
        # Contract-only proof flags; this is not native attachment certification.
        trial=copy.copy(self.prepared);trial.validator_receives_result=True;trial.differential_only=False;calls=[]
        def validator(candidate,cancelled):
            calls.append(candidate)
            self.assertIn('network',candidate);self.assertIn('guide_coverage',candidate)
            self.assertEqual(candidate['edit_request'],candidate['handle_positions_request'])
            self.assertTrue(any(g['kind']=='profile' for g in candidate['guides']))
            report=dict(checked=True,fatal=False,full_boundary_pass=True,reason='Synthetic numeric-ready callback.',
                        seam_position_error=0.,seam_angle_degrees=0.,seam_curvature_error=0.,
                        position_tolerance=trial.shared_tolerances['position'],angle_tolerance_degrees=trial.shared_tolerances['normal_angle_degrees'],
                        curvature_tolerance=trial.shared_tolerances['shape_operator'])
            return dict(report=report,attachment_proof=proof_fixtures.full_attachment_result()['attachment_proof'],
                        disposition='native_screen_pending',experimental_commit_allowed=False)
        trial.validator=validator
        request=self.request({'profile:0:upper':.01,'profile:4:upper':.01})
        result=trial.evaluate_edit(request)
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0]['guides'],result['guides'])
        self.assertTrue(result['valid']);self.assertTrue(result['native_screen_pending'])
        self.assertEqual(result['disposition'],'native_screen_pending')
        self.assertFalse(result['experimental_commit_allowed'])

    def test_boundary_role_coverage_cannot_hide_new_shared_guides(self):
        baseline=self.regenerated_eight_row_fixture()
        guide=next(g for g in baseline['guides'] if g['kind']=='fan_internal' and g['binding']['varying_axis']=='u'
                   and g['binding']['constant_parameter']==.9)
        index=guide['binding']['surface_index'];baseline['guides'].remove(guide)
        baseline['surfaces'][index]['boundary_roles']={'bottom':{'role':'retained_body_2jet'}}
        baseline['network']['repaired_boundary_roles']=[dict(surface_index=index,edge='bottom',role='retained_body_2jet')]
        trial=uv.PreparedUVEdits(self.model,baseline,self.regenerated_validator,sk,differential_only=True)
        self.assertTrue(trial.guide_coverage['role_coverage_pending_native_attachment'])
        self.assertFalse(trial.guide_coverage['checked'])
        baseline['network']['repaired_boundary_roles'][0]['role']='new_shared_2jet'
        baseline['surfaces'][index]['boundary_roles']['bottom']['role']='new_shared_2jet'
        with self.assertRaisesRegex(ValueError,'Only named native-source'):
            uv.PreparedUVEdits(self.model,baseline,self.regenerated_validator,sk,differential_only=True)


if __name__=='__main__':unittest.main()
