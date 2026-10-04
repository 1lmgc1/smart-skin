"""Synthetic numerical/native-OpenNURBS tests. No private model or Rhino host."""
import unittest
import tempfile
from pathlib import Path
import numpy as np
from scipy.interpolate import BSpline
from uv_basis_fairing import (Tensor,transform_second_jet,compact_basis,remove_one_knot,
                             change_degree,axis_conversion_bound,free_modes,fair_candidate,
                             fairness_matrix,guarded_selection,curvature_nonregression,screen_proposal)
from local_regularity import inspect,bernstein_cross


def plane(p=5,q=5,inner_u=(),inner_v=()):
    ku=np.r_[np.zeros(p+1),inner_u,np.ones(p+1)];kv=np.r_[np.zeros(q+1),inner_v,np.ones(q+1)]
    gu=[np.mean(ku[i+1:i+p+1]) for i in range(len(ku)-p-1)]
    gv=[np.mean(kv[i+1:i+q+1]) for i in range(len(kv)-q-1)]
    return Tensor([[(u,v,0) for v in gv] for u in gu],ku,kv,p,q)


def strip():
    return plane(inner_u=[.2]*3+[.5]*5+[.8]*3,inner_v=[.2]*3+[.8]*3)


class RepresentationTests(unittest.TestCase):
    def test_nonfinite_control_rejected(self):
        x=plane();x.net[0,0,0]=np.nan
        with self.assertRaises(ValueError):Tensor(x.net,x.ku,x.kv,5,5)
    def test_invalid_knots_rejected(self):
        x=plane();x.ku[5]=.8
        with self.assertRaises(ValueError):Tensor(x.net,x.ku,x.kv,5,5)
    def test_plain_grid_is_identity(self):
        x=plane();np.testing.assert_allclose(x.grid([.3],[.7])[0,0],[.3,.7,0],atol=1e-14)
    def test_exact_inserted_knots_removed(self):
        x=strip();y,e=compact_basis(x,1e-11)
        self.assertEqual(y.net.shape,(6,6,3));self.assertLess(e['accumulated_position_bound'],1e-11)
        np.testing.assert_allclose(x.grid(np.linspace(0,1,39),[.4]),y.grid(np.linspace(0,1,39),[.4]),atol=1e-12)
    def test_protected_junction_retained(self):
        x=strip();y,_=compact_basis(x,1e-11,protected=((0,.5),))
        self.assertEqual(sum(y.ku==.5),5)
    def test_real_kink_not_silently_removed(self):
        x=plane(inner_u=[.5]*5);x.net[5:,:,2]=np.arange(x.nu-5)[:,None]*.1
        y,e=remove_one_knot(x,0,.5,1e-11)
        self.assertFalse(e['accepted']);self.assertIs(x,y)
    def test_elevation_retains_geometry(self):
        x=strip();x.net[:,:,2]=np.outer(x.net[:,0,0]**2,np.ones(x.nv))
        y,e=change_degree(x,0,7);self.assertTrue(e['accepted'])
        self.assertEqual(y.p,7);self.assertLess(e['bound'],1e-9)
        np.testing.assert_allclose(x.grid([.02,.3,.9],[.17,.68]),y.grid([.02,.3,.9],[.17,.68]),atol=1e-12)
    def test_elevation_does_not_claim_shape_improvement(self):
        x=plane();x.net[2,3,2]=2
        y,e=change_degree(x,1,7)
        self.assertTrue(e['accepted']);np.testing.assert_allclose(x.grid([.25,.6],[.4,.8]),y.grid([.25,.6],[.4,.8]),atol=1e-12)
    def test_linear_degree_reduction_allowed(self):
        x=plane();y,e=change_degree(x,0,3);self.assertTrue(e['accepted']);self.assertEqual(y.p,3)
    def test_true_quintic_not_approximated_as_cubic(self):
        x=plane();x.net[-1,:,2]=1
        y,e=change_degree(x,0,3,1e-10);self.assertFalse(e['accepted']);self.assertIs(x,y)
    def test_conversion_compares_one_axis_only(self):
        x=plane();y,_=change_degree(x,1,7)
        with self.assertRaises(ValueError):axis_conversion_bound(x,y,0)
    def test_budget_and_axis_validation(self):
        x=plane()
        with self.assertRaises(ValueError):compact_basis(x,-1)
        with self.assertRaises(ValueError):remove_one_knot(x,0,0)
        with self.assertRaises(ValueError):change_degree(x,2,7)


class ParameterJetTests(unittest.TestCase):
    def test_full_nonlinear_second_chain_rule(self):
        s,t=.3,.4;x=s+.2*s*t;y=t+.1*s*s
        f=lambda a,b:np.array([a+.2*a*b,b+.1*a*a,(a+.2*a*b)**2+2*(a+.2*a*b)*(b+.1*a*a)+3*(b+.1*a*a)**2])
        jet=([x,y,x*x+2*x*y+3*y*y],[1,0,2*x+2*y],[0,1,2*x+6*y],[0,0,2],[0,0,2],[0,0,6])
        A=[[1+.2*t,.2*s],[.2*s,1.]];H=[[[0,.2],[.2,0]],[[.2,0],[0,0]]]
        out=transform_second_jet(jet,A,H);h=1e-4
        np.testing.assert_allclose(out[1],(f(s+h,t)-f(s-h,t))/(2*h),atol=1e-8)
        np.testing.assert_allclose(out[3],(f(s+h,t)-2*f(s,t)+f(s-h,t))/h**2,atol=1e-7)
        np.testing.assert_allclose(out[4],(f(s+h,t+h)-f(s+h,t-h)-f(s-h,t+h)+f(s-h,t-h))/(4*h*h),atol=1e-7)
    def test_reversal_transforms_mixed_derivative(self):
        x=plane().jet(.3,.7);x=list(x);x[4]=np.array([1,2,3])
        out=transform_second_jet(x,[[-1,0],[0,1]],np.zeros((2,2,2)))
        np.testing.assert_allclose(out[1],-x[1]);np.testing.assert_allclose(out[4],-x[4])
    def test_singular_parameter_map_rejected(self):
        with self.assertRaises(ValueError):transform_second_jet(plane().jet(.2,.4),[[0,0],[0,1]],np.zeros((2,2,2)))
    def test_invalid_second_map_derivative_rejected(self):
        H=np.zeros((2,2,2));H[0,0,1]=1
        with self.assertRaises(ValueError):transform_second_jet(plane().jet(.2,.4),np.eye(2),H)


class FairingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=strip();M,e=free_modes(cls.base,(.2,.8),(.2,.8));cls.M=M
        rng=np.random.default_rng(53);delta=(M@rng.normal(size=(M.shape[1],3)))*.006
        cls.bump=Tensor(cls.base.net+delta.reshape(cls.base.net.shape),cls.base.ku,cls.base.kv,5,5)
        cls.candidate,cls.info=fair_candidate(cls.bump,(.2,.8),(.2,.8),(1.,1.),.03)
    def test_coeff_space_locks_complete_boundary(self):
        x=self.bump;ts=np.linspace(0,1,103)
        for u in (0.,1.):np.testing.assert_allclose(x.grid([u],ts),self.base.grid([u],ts),atol=1e-12)
        for v in (0.,1.):np.testing.assert_allclose(x.grid(ts,[v]),self.base.grid(ts,[v]),atol=1e-12)
    def test_active_full_two_jets_locked(self):
        for u in (0.,1.):
            for d in (0,1,2):
                np.testing.assert_allclose(self.bump.grid([u],np.linspace(.2,.8,67),d,0),self.base.grid([u],np.linspace(.2,.8,67),d,0),atol=1e-10)
    def test_entire_core_not_only_midline_locked(self):
        np.testing.assert_allclose(self.bump.grid(np.linspace(.2,.8,31),np.linspace(0,1,39)),self.base.grid(np.linspace(.2,.8,31),np.linspace(0,1,39)),atol=1e-12)
    def test_fairness_decreases_after_actual_solve(self):
        self.assertTrue(self.info['proposed']);self.assertLess(self.info['energy_after'],self.info['energy_before'])
    def test_actual_euclidean_control_step_bound(self):
        self.assertLessEqual(np.linalg.norm(self.candidate.net-self.bump.net,axis=2).max(),.03*(1+1e-8))
    def test_both_source_junctions_unchanged(self):
        for v in (0,1):np.testing.assert_allclose(self.candidate.grid([.5],[v]),self.base.grid([.5],[v]),atol=1e-12)
    def test_fairing_never_assigns_join_or_g2(self):
        self.assertIn('NONE',self.info['acceptance']);self.assertNotIn('G2_PASS',str(self.info))
    def test_input_control_net_is_not_mutated(self):
        before=self.bump.net.copy();fair_candidate(self.bump,(.2,.8),(.2,.8),(1.,1.),.03)
        np.testing.assert_array_equal(before,self.bump.net)
    def test_increment_does_not_add_a_knot_kink(self):
        for d in (0,1,2):
            a=self.candidate.grid([.5-1e-10],[.1,.9],d,0)-self.bump.grid([.5-1e-10],[.1,.9],d,0)
            b=self.candidate.grid([.5+1e-10],[.1,.9],d,0)-self.bump.grid([.5+1e-10],[.1,.9],d,0)
            np.testing.assert_allclose(a,b,atol=1e-6)
    def test_invalid_step_rejected(self):
        with self.assertRaises(ValueError):fair_candidate(self.base,(.2,.8),(.2,.8),(1,1),np.nan)
    def test_native_surface_roundtrip(self):
        import rhino3dm as rg
        p=self.candidate;sf=rg.NurbsSurface.Create(3,False,p.p+1,p.q+1,p.nu,p.nv)
        for i,x in enumerate(p.ku[1:-1]):sf.KnotsU[i]=float(x)
        for j,x in enumerate(p.kv[1:-1]):sf.KnotsV[j]=float(x)
        for i in range(p.nu):
            for j in range(p.nv):sf.Points[i,j]=rg.Point4d(*p.net[i,j],1)
        brep=rg.Brep.CreateFromSurface(sf);self.assertTrue(brep.IsValid)
        with tempfile.TemporaryDirectory() as tmp:
            f=rg.File3dm();f.Objects.AddBrep(brep,rg.ObjectAttributes());path=str(Path(tmp)/'synthetic.3dm')
            self.assertTrue(f.Write(path,8));r=rg.File3dm.Read(path);s=r.Objects[0].Geometry.Faces[0]
            for u in np.linspace(0,1,21):
                for v in (.07,.41,.91):
                    x=s.PointAt(float(u),float(v));np.testing.assert_allclose([x.X,x.Y,x.Z],p.grid([u],[v])[0,0],atol=1e-12)


class GuardTests(unittest.TestCase):
    def test_true_regular_curve_accepted_without_central_projection_assumption(self):
        x=plane();x.net[:,:,2]=np.outer(np.linspace(0,1,x.nu)**2,np.ones(x.nv))
        self.assertTrue(inspect(x)['ok'])
    def test_degenerate_net_not_regular(self):
        x=plane();x.net[:]=0;self.assertFalse(inspect(x)['ok'])
    def test_local_fold_is_not_hidden_by_axis_switch(self):
        x=plane(3,3);x.net[1,:,0]=2.;x.net[2,:,0]=-1.
        self.assertFalse(inspect(x,max_depth=3)['ok'])
    def test_bernstein_cross_of_constant_derivatives(self):
        A=np.zeros((3,4,3));A[:,:,0]=2;B=np.zeros((4,3,3));B[:,:,1]=3
        C=bernstein_cross(A,B);np.testing.assert_allclose(C[:,:,2],6);np.testing.assert_allclose(C[:,:,:2],0)
    def test_budget_failure_does_not_publish_fictitious_positive_bound(self):
        x=plane(3,3);x.net[1,:,0]=2.;x.net[2,:,0]=-1.
        r=inspect(x,max_nodes=1);self.assertFalse(r['ok']);self.assertIn(r['reason'],('NODE_BUDGET','LOCAL_REGULARITY_NOT_PROVEN'))
    def test_cancellation_callback_observed(self):
        def stop():raise RuntimeError('cancel')
        with self.assertRaises(RuntimeError):inspect(plane(),checkpoint=stop)
    def test_rejected_candidate_rolls_back_without_mutation(self):
        x=FairingTests.bump;y=FairingTests.candidate;snap=x.net.copy();Q=fairness_matrix(x,(1,1))
        energy=lambda t:float(np.einsum('ic,ij,jc',t.net.reshape(-1,3),Q,t.net.reshape(-1,3)))
        z,e=guarded_selection(x,y,[('force_reject',lambda t:False)],energy,maximum_backtracks=2)
        self.assertIs(z,x);self.assertEqual(len(e['events']),3);np.testing.assert_array_equal(x.net,snap)
    def test_missing_or_unknown_validator_is_not_pass(self):
        x=plane()
        with self.assertRaises(ValueError):guarded_selection(x,x,[],lambda p:1)
        z,e=guarded_selection(x,x,[('unknown',lambda p:None)],lambda p:1,0)
        self.assertIn('unknown',e['events'][0]['failed']);self.assertFalse(e['geometry_commit'])

class MandatoryScreenTests(unittest.TestCase):
    def test_straight_to_curved_is_not_an_improvement(self):
        x=plane();y=plane();y.net[2:4,2:4,2]=.2
        r=curvature_nonregression(x,y,density=31)
        self.assertFalse(r['ok']);self.assertTrue(r['failed'])
    def test_identical_geometry_in_new_degree_passes_screen(self):
        x=strip();y,_=change_degree(x,0,7)
        self.assertTrue(curvature_nonregression(x,y,density=31)['ok'])
    def test_mandatory_gate_never_pretends_to_run_rhino_join(self):
        x=strip();y=Tensor(x.net.copy(),x.ku,x.kv,x.p,x.q);y.net[1,1,2]+=.1
        p,e=screen_proposal(x,y,(.2,.8),(.2,.8),(1.,1.),maximum_backtracks=0)
        self.assertIs(p,x);self.assertEqual(e['Rhino_Join'],'NOT_RUN_BY_THIS_API')
        self.assertIn('BOTH_FAMILIES_GEOMETRIC_CURVATURE_NONREGRESSION',e['validators_run'])
    def test_profile_only_mode_is_explicit_and_preserves_the_profile(self):
        x=strip();M,e=free_modes(x,(.2,.8),(.2,.8),core_mode='profile')
        d=(M@np.random.default_rng(11).normal(size=(M.shape[1],3)))*.001
        y=Tensor(x.net+d.reshape(x.net.shape),x.ku,x.kv,x.p,x.q)
        self.assertEqual(e['core_mode'],'profile')
        np.testing.assert_allclose(x.grid([.5],np.linspace(0,1,31)),y.grid([.5],np.linspace(0,1,31)),atol=1e-11)
    def test_profile_only_mode_is_not_mislabeled_as_a_locked_band(self):
        with self.assertRaises(ValueError):free_modes(strip(),(.2,.8),(.2,.8),core_mode='unknown')

if __name__=='__main__':unittest.main(verbosity=2)
