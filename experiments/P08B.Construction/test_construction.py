"""Actual constructed surfaces and their derivatives, not supplied policy grades."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import random
import unittest
from unittest.mock import Mock
import numpy as np
from scipy.interpolate import BSpline
from mixed_kernel import *
from synthetic_cases import boundaries, surface, curved_boundaries

class ConstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.smooth=boundaries()
        cls.mixed=boundaries(sharp_top=True,split=True)
        cls.pool=solve(cls.mixed,n=8,steps=4)
        cls.patch=cls.pool.best[1]
    def test_basis_values_against_independent_scipy(self):
        for p in (3,5):
            for n in (p+1,10):
                K=knots(n,p); ref=BSpline(K,np.eye(n),p)
                for t in (0,.00001,.127,.5,.999999,1):
                    for k in range(3): np.testing.assert_allclose(basis(n,p,t)[k],ref(t,nu=k),atol=2e-10,rtol=2e-12)
    def test_partition_of_unity_and_derivative_sums(self):
        for t in (0,.01,.3,.99,1):
            b=basis(12,5,t)
            self.assertAlmostEqual(sum(b[0]),1,places=12)
            self.assertAlmostEqual(sum(b[1]),0,places=10)
            self.assertAlmostEqual(sum(b[2]),0,places=8)
    def test_qr_against_independent_numpy_lstsq(self):
        rng=np.random.default_rng(7); A=rng.normal(size=(40,8)); Y=rng.normal(size=(40,3))
        np.testing.assert_allclose(qr_fit(A.tolist(),Y.tolist()),np.linalg.lstsq(A,Y,rcond=None)[0],atol=1e-11)
    def test_rank_deficient_position_fit_is_not_a_surface(self):
        with self.assertRaises(ValueError): qr_fit([[1,1],[2,2]],[[0],[1]])
    def test_sparse_solver_against_independent_numpy(self):
        rng=np.random.default_rng(3); A=rng.normal(size=(30,12)); y=rng.normal(size=30)
        rows=[list(enumerate(row)) for row in A]
        x,it=pcg(rows,y,np.zeros(12)); np.testing.assert_allclose(x,np.linalg.lstsq(A,y,rcond=None)[0],atol=1e-7)
    def test_constructed_flat_surface_satisfies_smooth_edges(self):
        f=boundaries(0); p=construct_coons(f,n=8); e=measure(p,f)
        self.assertTrue(e['desired_sampled_met']); self.assertLess(e['gap_sampled'],1e-12)
    def test_actual_mixed_4G2_2G0_surface_not_just_policy(self):
        e=self.pool.best[2]
        self.assertTrue(e['desired_sampled_met']); self.assertFalse(e['commit_allowed'])
        self.assertEqual(len(e['edges']),6)
        self.assertTrue(all(e['edges'][s]['achieved']==2 for s in ('bottom_a','bottom_b','left','right')))
        self.assertEqual(e['edges']['top_a']['preferred'],0)
        self.assertGreater(e['edges']['top_a']['normal_deg'],89)
    def test_shape_really_changed_from_flat_coons(self):
        before=self.pool.history[0][3]; base=construct_coons(self.mixed,n=8)
        self.assertLess(before['score'][0],self.pool.best[2]['score'][0])
        self.assertGreater(abs(self.patch.eval(.4,.4)[0][2]-base.eval(.4,.4)[0][2]),.001)
    def test_every_refinement_keeps_every_boundary_control_point(self):
        p=construct_coons(self.mixed,n=8); snap=p.boundary_snapshot()
        for use_k in (False,True,True):
            p,_=refine(p,self.mixed,use_k); self.assertEqual(snap,p.boundary_snapshot())
    def test_dense_independent_position_check_not_training_grid(self):
        for side in SIDES:
            for t in np.linspace(0,1,302):
                pt=self.patch.eval(*side_uv(side,t))[0]
                self.assertLess(norm(sub(pt,self.mixed[side](t).point)),1e-10)
    def test_dense_independent_full_shape_operator(self):
        maximum=0
        for side in ('bottom','right','left'):
            for t in np.linspace(.0001,.9999,139):
                values=self.patch.eval(*side_uv(side,t)); n,H=frame(values); s=self.mixed[side](t)
                maximum=max(maximum,tensor_error(H,s.H,dot(n,s.normal)))
        self.assertLess(maximum,5)
    def test_uniform_smooth_construction(self):
        pool=solve(self.smooth,n=8,steps=4)
        self.assertTrue(pool.best[2]['desired_sampled_met'])
    def test_conflicting_normals_do_not_masquerade_as_G2(self):
        f=boundaries(conflicting_top=True); pool=solve(f,n=8,steps=2)
        self.assertIsNotNone(pool.best)
        self.assertFalse(pool.best[2]['desired_sampled_met'])
    def test_curvature_can_fail_while_position_and_tangency_hold(self):
        f=boundaries(0); p=construct_coons(f,n=8)
        net=[[list(x) for x in row] for row in p.net]
        for i in range(2,6):
            for j in range(2,6): net[i][j][2]=.01
        e=measure(Patch(net),f)
        self.assertTrue(e['position_sampled_ok'])
        self.assertTrue(any(x['achieved']==1 for x in e['edges'].values()))
    def test_bad_later_gap_preserves_previous_candidate(self):
        pool=CandidatePool(); e=measure(self.patch,self.mixed); pool.offer('good',self.patch,e)
        net=[[list(x) for x in row] for row in self.patch.net]; net[0][0][2]+=.1; bad=Patch(net)
        self.assertFalse(pool.offer('bad',bad,measure(bad,self.mixed)))
        self.assertEqual(pool.best[0],'good')
    def test_interior_fold_cannot_replace_sampled_baseline(self):
        pool=CandidatePool(); pool.offer('good',self.patch,measure(self.patch,self.mixed))
        net=[[list(x) for x in row] for row in self.patch.net]; net[3][3][0]=5
        p=Patch(net); e=measure(p,self.mixed)
        self.assertFalse(e['regularity_sampled_ok']); self.assertFalse(pool.offer('fold',p,e)); self.assertEqual(pool.best[0],'good')
    def test_missing_parent_normal_remains_unverified(self):
        f=boundaries(); original=f['left']
        f['left']=lambda t:Support(original(t).point,None,None,'left',2)
        e=measure(self.patch,f)
        self.assertFalse(e['edges']['left']['frames']); self.assertEqual(e['edges']['left']['achieved'],0)
    def test_locked_or_preferred_conditions_not_mutated_by_solver(self):
        before=[(s,t,self.mixed[s](t).preferred,self.mixed[s](t).point) for s in SIDES for t in (0,.4,1)]
        solve(self.mixed,n=8,steps=2)
        after=[(s,t,self.mixed[s](t).preferred,self.mixed[s](t).point) for s in SIDES for t in (0,.4,1)]
        self.assertEqual(before,after)
    def test_fragmentation_does_not_multiply_quality_credit(self):
        a=measure(self.patch,boundaries(sharp_top=True,split=True))
        b=measure(self.patch,boundaries(sharp_top=True,split=False))
        self.assertAlmostEqual(a['score'][0],b['score'][0],places=10)
    def test_opposite_parent_orientation_preserves_geometric_grade(self):
        f=boundaries(sharp_top=True,split=True)
        for side,original in list(f.items()):
            f[side]=lambda t,o=original:Support(o(t).point,mul(o(t).normal,-1),[mul(row,-1) for row in o(t).H],o(t).key,o(t).preferred,o(t).weight)
        self.assertTrue(measure(self.patch,f)['desired_sampled_met'])
    def test_sampler_includes_fragment_boundaries_and_small_intervals(self):
        f=lambda t:None; f.parameters=[.12345,.123451,.123452]
        self.assertTrue(set(f.parameters)<=set(sample_parameters(f,41)))
    def test_nonfinite_data_rejected(self):
        with self.assertRaises(ValueError): Support((math.nan,0,0),(0,0,1),None,'bad')
    def test_open_boundary_is_not_repaired_by_tolerance_change(self):
        f=boundaries(); old=f['top']; f['top']=lambda t:Support(add(old(t).point,(0,0,.1)),old(t).normal,old(t).H,'top')
        with self.assertRaises(ValueError): construct_coons(f,corner_tolerance=.01)
    def test_cancel_observed_during_iteration(self):
        stop=Mock(side_effect=RuntimeError('cancel'))
        with self.assertRaises(RuntimeError): refine(self.patch,self.mixed,checkpoint=stop)
    def test_patch_snapshot_is_immutable(self):
        net=[[list(x) for x in row] for row in self.patch.net]; p=Patch(net); old=p.eval(.5,.5)[0]
        net[3][3][2]=500; self.assertEqual(old,p.eval(.5,.5)[0])
    def test_two_actual_surface_seam_continuity_and_failed_gap(self):
        def plane_patch(xoffset=0,zoffset=0):
            f=boundaries(0)
            for side,old in list(f.items()): f[side]=lambda t,o=old:Support(add(o(t).point,(xoffset,0,zoffset)),o(t).normal,o(t).H,o(t).key)
            return construct_coons(f,n=8)
        a=plane_patch(); b=plane_patch(1); good=seam_measure(a,'right',b,'left')
        self.assertLess(good['gap_sampled'],1e-12); self.assertLess(good['normal_deg'],1e-5); self.assertEqual(good['curvature_pct'],0)
        bad=seam_measure(a,'right',plane_patch(1,.02),'left'); self.assertGreater(bad['gap_sampled'],.01)
    def test_internal_tangent_kink_measured(self):
        a=construct_coons(boundaries(0),n=8); net=[[list(x) for x in row] for row in a.net]
        for row in net:
            for pt in row: pt[2]=.1*pt[0]; pt[0]+=1
        b=Patch(net); e=seam_measure(a,'right',b,'left')
        self.assertLess(e['gap_sampled'],1e-12); self.assertGreater(e['normal_deg'],5)

    def test_nonplanar_curved_boundary_construction(self):
        f=curved_boundaries(); pool=solve(f,n=8,steps=4)
        self.assertTrue(pool.best[2]['desired_sampled_met'])
        self.assertLess(pool.best[2]['gap_sampled'],1e-10)
    def test_shape_operator_against_paraboloid_at_stationary_point(self):
        n,H=frame(((0,0,0),(1,0,0),(0,1,0),(0,0,.4),(0,0,.1),(0,0,.6)))
        np.testing.assert_allclose(H,[[.4,.1,0],[.1,.6,0],[0,0,0]],atol=1e-14)
    def test_internal_curvature_discontinuity_with_shared_tangent(self):
        a=construct_coons(boundaries(0),n=8); f=boundaries(0)
        for side,old in list(f.items()):
            def g(t,o=old):
                s=o(t); u,v=s.point[0:2]
                vals=((1+u,v,.1*u*u),(1,0,.2*u),(0,1,0),(0,0,.2),(0,0,0),(0,0,0))
                n,H=frame(vals); return Support(vals[0],n,H,s.key)
            f[side]=g
        b=construct_coons(f,n=8); e=seam_measure(a,'right',b,'left')
        self.assertLess(e['gap_sampled'],1e-12); self.assertLess(e['normal_deg'],1e-5)
        self.assertGreater(e['curvature_pct'],5)

if __name__=='__main__': unittest.main(verbosity=2)
