"""Synthetic numeric tests only; no private geometry, Rhino UI, or native Join."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
import numpy as np
from uv_basis_fairing import Tensor
from structured_transition import *
from structured_flow import *
from structured_validation import *


def tensor():
    n=6;x=np.linspace(0,1,n);x2=np.arange(n)*(np.arange(n)-1)/(5*4)
    P=np.zeros((n,n,3));P[:,:,0]=x[:,None]*4;P[:,:,1]=x[None,:]*3
    P[:,:,2]=.2*x2[:,None]+.1*x2[None,:]+.4*(x-x2)[:,None]*(x-x2)[None,:]
    return Tensor(P,[0.]*6+[1.]*6,[0.]*6+[1.]*6,5,5)


def source():
    return [SourceInterval('b0','bottom',0,.5),SourceInterval('b1','bottom',.5,1),SourceInterval('r','right',0,1),SourceInterval('t0','top',0,.5),SourceInterval('t1','top',.5,1),SourceInterval('l','left',0,1)]


def graph():return PatchGraph.from_tensor(tensor(),(.2,.73),source=source())


class GraphTests(unittest.TestCase):
    def test_roundoff_duplicate_sites_are_not_false_degeneracy(self):
        v=sample_sites([0,1],9,9);self.assertGreater(np.diff(v).min(),1e-10)
    def test_true_too_short_knot_span_is_not_discarded(self):
        with self.assertRaises(ValueError):sample_sites([0,1e-12,1],9,9)
    def test_three_patches_and_two_single_shared_records(self):
        g=graph();self.assertEqual(len(g.patches),3);self.assertEqual(len(g.seams),2)
    def test_exact_split_is_only_representation(self):
        g=graph();a=tensor();us=np.linspace(0,1,37);vs=np.linspace(0,1,31)
        for d in JET_ORDERS:
            self.assertLess(np.linalg.norm(grid(g,us,vs,*d)-a.grid(us,vs,*d),axis=-1).max(),1e-10)
    def test_unequal_widths_require_derivative_scaling(self):
        g=graph();L,R=g.patches[:2];vs=np.linspace(0,1,31)
        wrong=np.linalg.norm(L.grid([1],vs,1,0)[0]-R.grid([0],vs,1,0)[0],axis=-1).max()
        self.assertGreater(wrong,1)
        for e in seam_evidence(g):self.assertLess(e['common_d2_coefficient_gap'],1e-10)
    def test_joint_nullspace_is_real_and_nonempty(self):
        M,e,A=joint_modes(graph(),(.2,.8));self.assertGreater(e['scalar_modes'],0);self.assertLess(np.abs(A@M).max(),1e-10)
    def test_shared_fields_can_move_while_profile_remains(self):
        g=graph();M,e,A=joint_modes(g,(.2,.8));rng=np.random.default_rng(7)
        new=g.replace(g.control+M@rng.normal(scale=.001,size=(M.shape[1],3)))
        self.assertTrue(lock_evidence(g,new,(.2,.8))['ok'])
        self.assertGreater(np.linalg.norm(g.shared_fields(g.seams[0])[0]-new.shared_fields(new.seams[0])[0]).max(),1e-6)
        v=np.linspace(0,1,101);self.assertLess(np.linalg.norm(grid(g,[.5],v)-grid(new,[.5],v),axis=-1).max(),1e-11)
    def test_deliberate_seam_position_error_is_detected(self):
        g=graph();cp=g.control.copy();p=g.patches[0];cp[p.nu*p.nv-3,2]+=.01;n=g.replace(cp)
        self.assertGreater(seam_evidence(n)[0]['position_coefficient_gap'],.005)
        with self.assertRaises(ValueError):JointProblem(n,(.2,.8),SolveLimits())
    def test_deliberate_seam_twist_is_detected(self):
        g=graph();cp=g.control.copy();p=g.patches[0];cp[(p.nu-2)*p.nv+3,2]+=.01;n=g.replace(cp)
        self.assertGreater(seam_evidence(n)[0]['common_d1_coefficient_gap'],.01)
    def test_boundary_is_not_silently_relaxed(self):
        g=graph();cp=g.control.copy();cp[0,2]+=.01
        self.assertFalse(lock_evidence(g,g.replace(cp),(.2,.8))['ok'])
    def test_active_outer_second_jets_preserved(self):
        g=graph();M,e,A=joint_modes(g,(.2,.8));n=g.replace(g.control+M@np.ones((M.shape[1],3))*.001)
        for k,x in ((0,0),(2,1)):
            for d in (0,1,2):self.assertLess(np.linalg.norm(g.patches[k].grid([x],[.4,.7],d,0)-n.patches[k].grid([x],[.4,.7],d,0)).max(),1e-10)
    def test_input_not_mutated(self):
        t=tensor();old=t.net.copy();g=PatchGraph.from_tensor(t,(.2,.73));g.control[0,2]+=1
        self.assertTrue(np.array_equal(t.net,old))
    def test_bad_station_layout_rejected(self):
        for ab in ((0.,.7),(.6,.8),(.2,.2),(.2,1.),(.001,.7)):
            with self.assertRaises(ValueError):PatchGraph.from_tensor(tensor(),ab)
    def test_unknown_policy_rejected(self):
        with self.assertRaises(ValueError):PatchGraph.from_tensor(tensor(),(.2,.7),boundary_policy='AUTO_RELAX')
    def test_relief_needs_explicit_policy(self):
        with self.assertRaises(ValueError):PatchGraph.from_tensor(tensor(),(.2,.7),inherited_relief_bound=.001,relief_budget=.0025)
    def test_relief_budget_is_cumulative(self):
        with self.assertRaises(ValueError):PatchGraph.from_tensor(tensor(),(.2,.7),boundary_policy='CAP_EDGE_RELIEF',inherited_relief_bound=.003,relief_budget=.0025)
    def test_hash_tracks_geometry(self):
        g=graph();cp=g.control.copy();cp[6,2]+=.001;self.assertNotEqual(g.digest(),g.replace(cp).digest())
    def test_complete_compound_coverage_not_edge_count(self):
        g=graph();self.assertEqual(len(g.coverage()),6);self.assertEqual(len(g.allocated_sources()),10)
    def test_missing_piece_rejected(self):
        g=graph();pieces=[(k,a,b) for k,a,b,i in g.allocated_sources()][1:]
        with self.assertRaises(ValueError):check_cover(g.source,pieces)
    def test_duplicate_piece_rejected(self):
        g=graph();p=[(k,a,b) for k,a,b,i in g.allocated_sources()]
        with self.assertRaises(ValueError):check_cover(g.source,p+p[:1])
    def test_unknown_piece_rejected(self):
        with self.assertRaises(ValueError):check_cover(source(),[('unknown',0,1)])
    def test_reverse_source_parameter_correspondence(self):
        r=SourceInterval('x','top',.5,1,10,20,True)
        self.assertEqual(r.source_parameter(.5),20);self.assertEqual(r.source_parameter(.75),15)
        with self.assertRaises(ValueError):r.source_parameter(.4)


class FlowTests(unittest.TestCase):
    def setUp(self):
        r=np.random.default_rng(21);self.P=r.normal(size=(2,7,3));self.N=r.normal(size=(2,7,3));self.N/=np.linalg.norm(self.N,axis=-1,keepdims=True);self.d=r.normal(size=self.P.shape)
    def test_position_gradient_with_chord_lengths(self):
        f,gp,gn=normal_flow_energy(self.P,self.N);h=1e-6
        fd=(normal_flow_energy(self.P+h*self.d,self.N)[0]-normal_flow_energy(self.P-h*self.d,self.N)[0])/(2*h)
        self.assertAlmostEqual(fd,float(np.sum(gp*self.d)),places=6)
    def test_normal_gradient_on_unit_sphere(self):
        f,gp,gn=normal_flow_energy(self.P,self.N);h=1e-6;d=self.d-self.N*np.sum(self.d*self.N,axis=-1,keepdims=True)
        n1=self.N+h*d;n1/=np.linalg.norm(n1,axis=-1,keepdims=True);n0=self.N-h*d;n0/=np.linalg.norm(n0,axis=-1,keepdims=True)
        self.assertAlmostEqual((normal_flow_energy(self.P,n1)[0]-normal_flow_energy(self.P,n0)[0])/(2*h),float(np.sum(gn*d)),places=6)
    def test_scale_units_per_mm4(self):
        f=normal_flow_energy(self.P,self.N)[0];self.assertAlmostEqual(normal_flow_energy(self.P*3,self.N)[0],f/81,places=10)
    def test_constant_normal_has_zero_flow_energy(self):
        N=np.zeros_like(self.N);N[:,:,2]=1;self.assertEqual(normal_flow_energy(self.P,N)[0],0)
    def test_signed_normal_flip_is_not_hidden(self):
        N=np.zeros_like(self.N);N[:,:,2]=1;N[:,3]*=-1;self.assertGreater(normal_flow_energy(self.P,N)[0],0)
    def test_degenerate_path_rejected(self):
        self.P[:,1]=self.P[:,0]
        with self.assertRaises(ValueError):normal_flow_energy(self.P,self.N)
    def test_nonfinite_not_discarded(self):
        self.P[0,2,0]=np.nan
        with self.assertRaises(ValueError):normal_flow_energy(self.P,self.N)
    def test_joint_objective_gradient(self):
        pr=JointProblem(graph(),(.2,.8),SolveLimits(training_density=9));r=np.random.default_rng(20)
        x=r.normal(scale=1e-4,size=pr.m*3);d=r.normal(size=x.shape);d/=np.linalg.norm(d);h=1e-7
        f,grad=pr.value_gradient(x);fd=(pr.value_gradient(x+h*d)[0]-pr.value_gradient(x-h*d)[0])/(2*h)
        self.assertAlmostEqual(fd,float(grad@d),delta=1e-4*max(abs(fd),1))
    def test_cancellation_propagates(self):
        def cancel():raise RuntimeError('CANCEL')
        with self.assertRaisesRegex(RuntimeError,'CANCEL'):optimize_joint(graph(),(.2,.8),checkpoint=cancel)
    def test_invalid_budgets_rejected(self):
        for lim in (SolveLimits(iterations=0),SolveLimits(seconds=np.inf),SolveLimits(training_density=2),SolveLimits(max_control_step=-1)):
            with self.assertRaises(ValueError):lim.validate()
    def test_actual_joint_solve_bounded_and_locked(self):
        g=graph();old=g.digest();n,r=optimize_joint(g,(.2,.8),SolveLimits(iterations=15,evaluations=60,training_density=9,max_control_step=.01))
        self.assertEqual(g.digest(),old);self.assertLessEqual(r['locks']['step'],.01000000001);self.assertTrue(r['locks']['ok'])
        self.assertFalse(r['geometry_commit']);self.assertEqual(r['native_Join'],'NOT_RUN');self.assertLessEqual(r['after_objective'],r['before_objective']+1e-7)
    def test_symmetry_must_be_verified(self):
        with self.assertRaises(ValueError):JointProblem(graph(),(.2,.8),SolveLimits(),mirror_axis=1)


class ScreenTests(unittest.TestCase):
    def test_physical_plane_residual_and_implicit_curvature(self):
        g=graph();m=fixed_plane_section(g,0,2,np.linspace(0,1,121));self.assertLess(m['max_plane_residual'],1e-9);self.assertTrue(np.isfinite(m['curvature']['maximum']))
    def test_unbracketed_plane_not_zero(self):
        with self.assertRaises(ValueError):fixed_plane_section(graph(),0,100,np.linspace(0,1,31))
    def test_physical_section_same_after_exact_split_at_other_stations(self):
        a=graph();b=PatchGraph.from_tensor(tensor(),(.31,.83));v=np.linspace(0,1,171)
        x=fixed_plane_section(a,0,2,v);y=fixed_plane_section(b,0,2,v)
        self.assertAlmostEqual(x['curvature']['maximum'],y['curvature']['maximum'],places=9)
        self.assertAlmostEqual(x['normal_flow_energy'],y['normal_flow_energy'],places=8)
    def test_same_count_other_sampling_rejected(self):
        import copy
        a=graph_metrics(graph(),density=21,per_span=5);b=copy.deepcopy(a);b['sampling_id']='other'
        with self.assertRaises(ValueError):nonregression(a,b)
    def test_missing_regularity_is_not_pass(self):
        a=graph_metrics(graph(),density=21,per_span=5)
        self.assertIn('REGULARITY_NOT_EVALUATED',nonregression(a,a)['reasons'])
    def test_false_better_mean_worse_peak_rejected(self):
        import copy
        a=graph_metrics(graph(),density=21,per_span=5);b=copy.deepcopy(a);b['regularity']=[dict(ok=True)]*3;b['u']['curvature']['maximum']+=1
        self.assertIn('u.curvature.maximum',nonregression(a,b)['reasons'])
    def test_representation_only_never_claims_repair(self):
        g=graph();out,r=screen_and_retain(g,g,(.2,.8),.1,physical_planes=[(0,2)])
        self.assertIs(out,g);self.assertEqual(r['status'],'REPRESENTATION_ONLY_NOT_FORM_REPAIR');self.assertFalse(r['geometry_commit'])
    def test_rollback_on_bad_boundary_and_shape(self):
        g=graph();cp=g.control.copy();cp[0,2]+=.05
        out,r=screen_and_retain(g,g.replace(cp),(.2,.8),.001,physical_planes=[(0,2)],maximum_backtracks=0)
        self.assertIs(out,g);self.assertIn('COEFFICIENT_LOCKS',r['attempts'][0]['reasons']);self.assertEqual(r['status'],'BASELINE_RETAINED_FORM_NOT_ACCEPTED')
    def test_native_roundtrip_of_three_synthetic_patches(self):
        try:import rhino3dm as R
        except ImportError:
            if os.environ.get('GITHUB_ACTIONS'):self.fail('rhino3dm must be installed in CI')
            self.skipTest('rhino3dm unavailable locally; native roundtrip not run here')
        g=graph();f=R.File3dm()
        for p in g.patches:
            n=R.NurbsSurface.Create(3,False,p.p+1,p.q+1,p.nu,p.nv)
            for i,k in enumerate(p.ku[1:-1]):n.KnotsU[i]=float(k)
            for i,k in enumerate(p.kv[1:-1]):n.KnotsV[i]=float(k)
            for i in range(p.nu):
                for j in range(p.nv):n.Points[i,j]=R.Point4d(*map(float,p.net[i,j]),1.)
            self.assertTrue(n.IsValid);b=R.Brep.CreateFromSurface(n);self.assertTrue(b.IsValid);f.Objects.AddBrep(b,R.ObjectAttributes())
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/'test.3dm');self.assertTrue(f.Write(path,8));loaded=R.File3dm.Read(path);self.assertEqual(len(loaded.Objects),3)
            for obj,p in zip(loaded.Objects,g.patches):
                s=obj.Geometry.Faces[0];q=s.PointAt(.37,.42);want=p.grid([.37],[.42])[0,0]
                self.assertLess(np.linalg.norm(np.array([q.X,q.Y,q.Z])-want),1e-10)


if __name__=='__main__':unittest.main(verbosity=2)
