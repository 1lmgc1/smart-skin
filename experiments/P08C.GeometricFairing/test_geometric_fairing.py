"""P08C.3 synthetic-only numerical and native OpenNURBS tests. Not Rhino UI/Join."""
import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
from uv_basis_fairing import Tensor,free_modes
from geometric_fairing import *


def plane():
    p=5;ku=np.r_[np.zeros(6),np.repeat(.2,3),np.repeat(.5,5),np.repeat(.8,3),np.ones(6)]
    kv=np.r_[np.zeros(6),np.repeat(.2,3),np.repeat(.8,3),np.ones(6)]
    gu=[np.mean(ku[i+1:i+6]) for i in range(len(ku)-6)]
    gv=[np.mean(kv[i+1:i+6]) for i in range(len(kv)-6)]
    return Tensor([[(u-.5,v,0.) for v in gv] for u in gu],ku,kv,p,p)


def bump():
    t=plane();m,_=free_modes(t,(.2,.8),(.2,.8))
    delta=(m@np.random.default_rng(9).normal(size=(m.shape[1],3)))*.004
    delta=delta.reshape(t.net.shape);delta[:,:,:2]*=.1
    delta=(delta+delta[::-1]*[-1,1,1])/2
    return Tensor(t.net+delta,t.ku,t.kv,t.p,t.q)


class DerivativeTests(unittest.TestCase):
    def test_known_circle_derivatives(self):
        r=3.;u=np.linspace(0,2*np.pi,13)
        D=np.c_[-r*np.sin(u),r*np.cos(u),np.zeros(len(u))]
        DD=np.c_[-r*np.cos(u),-r*np.sin(u),np.zeros(len(u))]
        k,*_=squared_curvature_gradient(D,DD);np.testing.assert_allclose(k,1/r**2,atol=1e-14)
    def test_analytic_gradient_against_finite_difference(self):
        rng=np.random.default_rng(4);D=rng.normal(size=(9,3));A=rng.normal(size=(9,3));_,g,h=squared_curvature_gradient(D,A)
        for src,ref in [('D',g),('A',h)]:
            for i,c in [(0,0),(2,1),(8,2)]:
                diff=np.zeros_like(D);diff[i,c]=1e-6
                f1=squared_curvature_gradient(D+diff if src=='D' else D,A+diff if src=='A' else A)[0][i]
                f0=squared_curvature_gradient(D-diff if src=='D' else D,A-diff if src=='A' else A)[0][i]
                self.assertAlmostEqual(ref[i,c],(f1-f0)/2e-6,places=5)
    def test_linear_reparameterization_invariant_curvature(self):
        D=np.array([[1.,2,0]]);A=np.array([[0.,1,2]])
        a=squared_curvature_gradient(D,A)[0];b=squared_curvature_gradient(-3*D,9*A)[0]
        np.testing.assert_allclose(a,b)
    def test_uniform_geometry_scale(self):
        D=np.array([[1.,2,0]]);A=np.array([[0.,1,2]])
        np.testing.assert_allclose(squared_curvature_gradient(4*D,4*A)[0],squared_curvature_gradient(D,A)[0]/16)
    def test_no_epsilon_hides_degenerate_sample(self):
        with self.assertRaises(ValueError):squared_curvature_gradient(np.zeros((1,3)),np.ones((1,3)))
    def test_nan_not_removed(self):
        with self.assertRaises(ValueError):squared_curvature_gradient(np.array([[np.nan,1,1]]),np.ones((1,3)))
    def test_plane_principal_curvature_zero(self):
        v=principal_curvature_stats(plane(),[.13,.37,.66],[.14,.47,.83]);self.assertLess(v['maximum'],1e-11)
    def test_paraboloid_principal_curvature_at_origin(self):
        ku=np.r_[np.zeros(3),np.ones(3)];net=np.zeros((3,3,3))
        for i in range(3):
            for j in range(3):net[i,j]=[i/2,j/2,(1 if i==2 else 0)+(2 if j==2 else 0)]
        v=principal_curvature_stats(Tensor(net,ku,ku,2,2),[0.],[0.]);self.assertAlmostEqual(v['maximum'],4.)


class ObjectiveTests(unittest.TestCase):
    def test_coupled_objective_gradient(self):
        t=bump();m,_=free_modes(t,(.2,.8),(.2,.8))
        p=GeometricProblem(t,m,Limits(training_density=11),[Plane((0,0,1),0.,.01)],mirror_axis=0)
        x=np.random.default_rng(3).normal(0,.000001,3*m.shape[1]);value,g=p.value_gradient(x)
        for i in (2,4,12):
            h=np.zeros_like(x);h[i]=1e-7
            diff=(p.value_gradient(x+h)[0]-p.value_gradient(x-h)[0])/2e-7
            self.assertAlmostEqual(g[i],diff,delta=2e-4*max(1,abs(diff)))
    def test_both_geometric_families_in_objective(self):
        t=bump();m,_=free_modes(t,(.2,.8),(.2,.8));p=GeometricProblem(t,m,Limits(training_density=11))
        self.assertEqual(set(p.scales),{(1,0),(0,1)})
    def test_symmetric_trial_by_construction(self):
        t=bump();m,_=free_modes(t,(.2,.8),(.2,.8));p=GeometricProblem(t,m,Limits(training_density=11),mirror_axis=0)
        d=p.delta(np.random.default_rng(2).normal(size=m.shape[1]*3)).reshape(t.net.shape)
        np.testing.assert_allclose(d,d[::-1]*[-1,1,1],atol=1e-14)
    def test_unverified_symmetry_rejected(self):
        t=bump();t.net[0,0,0]+=.01;m,_=free_modes(t,(.2,.8),(.2,.8))
        with self.assertRaises(ValueError):GeometricProblem(t,m,Limits(training_density=11),mirror_axis=0)
    def test_finite_limits_required(self):
        for v in (0,-1,float('nan')):
            with self.assertRaises(ValueError):Limits(max_control_step=v).validate()
    def test_iteration_limit_is_bounded(self):
        for v in (0,501,1.5):
            with self.assertRaises(ValueError):Limits(max_iterations=v).validate()
    def test_plane_validation(self):
        with self.assertRaises(ValueError):Plane((0,0,0),1,.01).data()
        with self.assertRaises(ValueError):Plane((1,0,0),1,0).data()
    def test_plane_unit_normal_and_offset(self):
        n,d,_=Plane((2,0,0),4,.1).data();np.testing.assert_allclose(n,[1,0,0]);self.assertEqual(d,2)
    def test_short_knot_spans_sampled(self):
        s=sites([0,0,.0001,.3,1,1],101)
        self.assertTrue(np.any((s>0)&(s<.0001)))
    def test_cancellation_never_returns_accepted_geometry(self):
        def stop():raise RuntimeError('USER_CANCEL')
        with self.assertRaises(RuntimeError):optimize_geometric(bump(),(.2,.8),(.2,.8),checkpoint=stop)
    def test_evaluation_budget_stops_cleanly(self):
        t=bump();candidate,r=optimize_geometric(t,(.2,.8),(.2,.8),limits=Limits(max_evaluations=1,backtracks=0))
        self.assertFalse(r['solve']['converged']);self.assertEqual(r['solve']['message'],'EVALUATION_BUDGET')
        self.assertIs(candidate,t);self.assertEqual(r['evaluations'],1)


class ActualSolveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=bump();cls.snapshot=cls.base.net.copy()
        cls.candidate,cls.report=optimize_geometric(cls.base,(.2,.8),(.2,.8),
            limits=Limits(max_control_step=.03,max_iterations=100,training_density=11,validation_density=101),mirror_axis=0)
    def test_real_optimization_produces_improvement(self):
        self.assertEqual(self.report['selected'],'GEOMETRIC_RESEARCH_CANDIDATE_NOT_JOINED')
        self.assertLess(self.report['events'][-1]['objective'],self.report['objective_before'])
    def test_both_families_nonregress(self):
        after=self.report['events'][-1]['sections'];before=self.report['before_sections']
        for a in ('u','v'):
            for k in ('maximum','p99'):self.assertLessEqual(after[a][k],before[a][k]+1e-8)
    def test_principal_curvature_screen_is_separate(self):
        self.assertIn('principal',self.report['events'][-1])
        self.assertLessEqual(self.report['events'][-1]['principal']['maximum'],self.report['before_principal']['maximum']+1e-8)
    def test_true_coupled_control_bound(self):
        self.assertLessEqual(np.linalg.norm(self.candidate.net-self.base.net,axis=2).max(),.03*(1+1e-10))
    def test_source_not_mutated(self):np.testing.assert_array_equal(self.base.net,self.snapshot)
    def test_entire_boundaries_and_core_locked(self):
        self.assertTrue(lock_evidence(self.base,self.candidate,(.2,.8),(.2,.8))['ok'])
        for u in (0,1):np.testing.assert_allclose(self.base.grid([u],np.linspace(0,1,151)),self.candidate.grid([u],np.linspace(0,1,151)),atol=1e-12)
        for v in (0,1):np.testing.assert_allclose(self.base.grid(np.linspace(0,1,151),[v]),self.candidate.grid(np.linspace(0,1,151),[v]),atol=1e-12)
        np.testing.assert_allclose(self.base.grid(np.linspace(.2,.8,21),np.linspace(0,1,31)),self.candidate.grid(np.linspace(.2,.8,21),np.linspace(0,1,31)),atol=1e-12)
    def test_full_active_two_jets_locked(self):
        for u in (0,1):
            for a in (1,2):np.testing.assert_allclose(self.base.grid([u],np.linspace(.2,.8,67),a,0),self.candidate.grid([u],np.linspace(.2,.8,67),a,0),atol=1e-8)
    def test_native_join_not_impersonated(self):
        self.assertFalse(self.report['geometry_commit']);self.assertEqual(self.report['Rhino_Join'],'NOT_RUN');self.assertEqual(self.report['parent_intersections'],'NOT_CHECKED')
    def test_local_regular_not_global_certification(self):
        r=self.report['events'][-1]['local_regularity'];self.assertTrue(r['ok']);self.assertIn('NOT_GLOBAL',r['scope'])
    def test_rejected_geometry_retains_input(self):
        t=bump();snap=t.net.copy()
        with patch('geometric_fairing.inspect',return_value={'ok':False,'reason':'FORCED_FAIL'}):
            c,r=optimize_geometric(t,(.2,.8),(.2,.8),limits=Limits(max_iterations=5,backtracks=1))
        self.assertIs(c,t);self.assertEqual(len(r['events']),2);self.assertEqual(r['selected'],'BASELINE_RETAINED_NOT_CERTIFIED');np.testing.assert_array_equal(t.net,snap)
    def test_native_roundtrip(self):
        import rhino3dm as rg
        t=self.candidate;s=rg.NurbsSurface.Create(3,False,t.p+1,t.q+1,t.nu,t.nv)
        for i,v in enumerate(t.ku[1:-1]):s.KnotsU[i]=float(v)
        for j,v in enumerate(t.kv[1:-1]):s.KnotsV[j]=float(v)
        for i in range(t.nu):
            for j in range(t.nv):s.Points[i,j]=rg.Point4d(*t.net[i,j],1.)
        b=rg.Brep.CreateFromSurface(s);self.assertTrue(b.IsValid)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'synthetic.3dm';f=rg.File3dm();f.Objects.AddBrep(b,rg.ObjectAttributes());self.assertTrue(f.Write(str(path),8))
            saved=rg.File3dm.Read(str(path)).Objects[0].Geometry.Faces[0]
            for u,v in np.random.default_rng(6).random((51,2)):
                x=saved.PointAt(float(u),float(v));np.testing.assert_allclose([x.X,x.Y,x.Z],t.grid([u],[v])[0,0],atol=1e-12)

if __name__=='__main__':unittest.main(verbosity=2)
