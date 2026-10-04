"""Synthetic regression cases: no user's coordinates, UUIDs, or private data."""
import os
from pathlib import Path
import tempfile
import unittest
import numpy as np
from scipy.interpolate import BSpline
from uv_basis_fairing import Tensor
from structured_transition import PatchGraph,SourceInterval,seam_evidence
from structured_flow import SolveLimits
from structured_validation import fixed_plane_section
from geometric_attachment import transform_jet,world_shape,AttachmentSpace,AttachmentProblem,optimize_attachment
from attachment_validation import station_graphs,screen_attachment

ACTIVE=(.2,.8)

def tensor():
    x=np.arange(6)/5.;x2=np.arange(6)*(np.arange(6)-1)/20.;arch=x-x2
    P=np.zeros((6,6,3));P[:,:,0]=4*(2*x[:,None]-1);P[:,:,1]=3*x[None,:]
    P[:,:,2]=.25*arch[:,None]+.15*x2[None,:]+.08*arch[:,None]*arch[None,:]
    bs=BSpline([0.]*6+[1.]*6,P,5,axis=1)
    for knot in ACTIVE:bs=bs.insert_knot(knot,3)
    # scipy places the interpolation axis first in .c.
    net=np.moveaxis(bs.c,0,1)
    return Tensor(net,[0.]*6+[1.]*6,bs.t,5,5)

def source():
    return (SourceInterval('b0','bottom',0,.5),SourceInterval('b1','bottom',.5,1),SourceInterval('r','right',0,1),
            SourceInterval('t0','top',0,.5),SourceInterval('t1','top',.5,1),SourceInterval('l','left',0,1))

def graph(stations=(.2,.8)):
    return PatchGraph.from_tensor(tensor(),stations,source=source())

def problem(corners=True):
    return AttachmentProblem(graph(),ACTIVE,SolveLimits(iterations=8,evaluations=40,training_density=9,max_control_step=.03),mirror_axis=0,chart_symmetry=True,corner_tangent_freedom=corners)


class GeometryTests(unittest.TestCase):
    def setUp(self):
        v=np.linspace(.2,.8,13);g=graph();self.jets=[g.evaluate(np.zeros_like(v),v,*k) for k in ((1,0),(0,1),(2,0),(1,1),(0,2))]
    def test_speed_shear_acceleration_preserve_normal_and_shape(self):
        changed=transform_jet(*self.jets,(1.4,.3,-.2,.15))
        n,H=world_shape(*self.jets);m,J=world_shape(*changed)
        self.assertLess(np.max(np.abs(n-m)),1e-12);self.assertLess(np.max(np.abs(H-J)),1e-12)
    def test_parameter_derivatives_really_change(self):
        changed=transform_jet(*self.jets,(1.4,.3,-.2,.15))
        self.assertGreater(np.max(np.abs(changed[0]-self.jets[0])),1)
    def test_reversed_chart_is_rejected(self):
        for a in (0,-1,np.nan):
            with self.assertRaises(ValueError):transform_jet(*self.jets,(a,0,0,0))
    def test_nonfinite_and_malformed_jet_rejected(self):
        for bad in (np.full_like(self.jets[0],np.nan),np.array(1)):
            with self.assertRaises(ValueError):transform_jet(bad,*self.jets[1:],(1,0,0,0))
    def test_degenerate_shape_is_not_zero(self):
        with self.assertRaises(ValueError):world_shape(self.jets[0],self.jets[0],*self.jets[2:])
    def test_linear_net_blend_breaks_two_jet(self):
        new=transform_jet(*self.jets,(1.5,.7,0,0))
        halfway=[.5*(a+b) for a,b in zip(self.jets,new)]
        _,old=world_shape(*self.jets);_,wrong=world_shape(*halfway)
        self.assertGreater(np.max(np.abs(old-wrong)),1e-4)
        right=transform_jet(*self.jets,(1.25,.35,0,0));_,H=world_shape(*right)
        self.assertLess(np.max(np.abs(old-H)),1e-12)
    def test_constant_identity(self):
        out=transform_jet(*self.jets,(1,0,0,0))
        for a,b in zip(out,self.jets):self.assertTrue(np.array_equal(a,b))
    def test_geometry_scale(self):
        n,H=world_shape(*self.jets);m,J=world_shape(*[x*7 for x in self.jets])
        self.assertLess(np.max(np.abs(n-m)),1e-12);self.assertLess(np.max(np.abs(H-7*J)),1e-12)


class SpaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.pr=problem()
    def test_response_is_compatible_not_least_squares_approximation(self):
        self.assertLess(self.pr.space.evidence['response_constraint_residual'],1e-10)
    def test_mid_profile_and_compound_sides_locked(self):
        p=self.pr;x=np.zeros(p.size);x[-6:]=[.1,.03,.1,-.02,.01,-.02];out=p.candidate(x)
        v=np.linspace(0,1,51)
        for u in (0,.5,1):self.assertLess(np.linalg.norm(p.space.graph.evaluate(u,v)-out.evaluate(u,v),axis=1).max(),1e-10)
        for s in (0,1):self.assertLess(np.linalg.norm(p.space.graph.evaluate(v,s)-out.evaluate(v,s),axis=1).max(),1e-10)
    def test_active_geometric_agreement_and_lower_corner_shape(self):
        p=self.pr;x=np.zeros(p.size);x[-6:]=[.1,.03,.1,-.02,.01,-.02]
        evidence=p.space.evidence_on(p.candidate(x),x[p.nfree:],101)
        self.assertTrue(evidence['ok'])
        self.assertGreater(evidence['lower_corner_geometry'][0]['mixed_vector_change'],.01)
        self.assertLess(evidence['lower_corner_geometry'][0]['shape_absolute'],1e-8)
    def test_independent_side_parameters(self):
        g=graph((.23,.76));space=AttachmentSpace(g,ACTIVE,False,None)
        self.assertEqual(space.count,12);e=np.zeros(12);e[:4]=[.1,.02,.05,.03];e[4:8]=[-.1,.03,-.05,.01]
        out=g.replace(g.control+space.displacement(e));self.assertTrue(space.evidence_on(out,e,101)['ok'])
    def test_two_internal_seams_not_broken_by_attachment(self):
        p=self.pr;x=np.zeros(p.size);x[-6:]=[.1,.03,.1,-.02,.01,-.02]
        for e in seam_evidence(p.candidate(x)):
            self.assertLess(e['position_coefficient_gap'],1e-10);self.assertLess(e['common_d2_coefficient_gap'],1e-8)
    def test_symmetry_required_for_linked_charts(self):
        with self.assertRaises(ValueError):AttachmentSpace(graph(),ACTIVE,True,None)
        with self.assertRaises(ValueError):AttachmentSpace(graph((.2,.75)),ACTIVE,True,0)
    def test_boundary_damage_fails(self):
        p=self.pr;cp=p.space.graph.control.copy();cp[0,2]+=.01
        self.assertFalse(p.space.evidence_on(p.space.graph.replace(cp),np.zeros(6),101)['ok'])
    def test_wrong_linear_rollback_detected(self):
        p=self.pr;x=np.zeros(p.size);x[-6:-2]=[.4,.4,.2,.1]
        wrong=p.space.graph.replace((p.space.graph.control+p.candidate(x).control)/2)
        self.assertFalse(p.space.evidence_on(wrong,.5*x[p.nfree:],101)['ok'])
        self.assertTrue(p.space.evidence_on(p.candidate(x,.5),.5*x[p.nfree:],101)['ok'])
    def test_unresolved_active_span_rejected(self):
        with self.assertRaises(ValueError):AttachmentSpace(graph(),(.15,.85))
    def test_no_new_boundary_relief(self):
        t=tensor();g=PatchGraph.from_tensor(t,(.2,.8),source=source(),boundary_policy='CAP_EDGE_RELIEF',inherited_relief_bound=.002,relief_budget=.0025)
        p=AttachmentSpace(g,ACTIVE);e=np.zeros(p.count);e[0]=.1;o=g.replace(g.control+p.displacement(e))
        self.assertEqual(o.relief_bound,.002);self.assertEqual(o.relief_budget,.0025)
    def test_chart_policy_rejects_bad_parameters(self):
        p=self.pr
        for x in (np.zeros(5),np.full(6,np.nan),np.array([-2,0,0,0,0,0])):
            with self.assertRaises(ValueError):p.space.displacement(x)
    def test_homogeneous_random_change_preserves_attachment(self):
        p=self.pr;r=np.random.default_rng(72);x=r.normal(scale=.00001,size=p.size);x[-6:]=[.1,.03,.1,-.02,.01,-.02]
        self.assertTrue(p.space.evidence_on(p.candidate(x),x[p.nfree:],101)['ok'])


class SolveTests(unittest.TestCase):
    def test_coupled_analytic_gradient(self):
        p=problem();rng=np.random.default_rng(90);x=rng.normal(scale=1e-5,size=p.size);x[-6:]=[.05,.02,.07,-.04,.01,-.02]
        f,G=p.value_gradient(x)
        for index in list(range(p.nfree,p.size))+[0,13]:
            eps=2e-7;step=np.zeros(p.size);step[index]=eps
            fd=(p.value_gradient(x+step)[0]-p.value_gradient(x-step)[0])/(2*eps)
            self.assertAlmostEqual(float(G[index]),fd,delta=3e-5*max(1,abs(fd)))
    def test_bounded_real_solve(self):
        g=graph();digest=g.digest();out,r,p,x=optimize_attachment(g,ACTIVE,SolveLimits(iterations=12,evaluations=60,training_density=9,max_control_step=.02),mirror_axis=0,chart_symmetry=True)
        self.assertEqual(digest,g.digest());self.assertTrue(r['evidence']['ok']);self.assertLessEqual(r['evidence']['step'],.020000000001)
        self.assertFalse(r['geometry_commit']);self.assertEqual(r['native_Join'],'NOT_RUN')
        self.assertLessEqual(r['after_objective'],r['before_objective']+1e-6)
    def test_cancellation_is_not_success(self):
        def stop():raise RuntimeError('CANCEL')
        with self.assertRaisesRegex(RuntimeError,'CANCEL'):optimize_attachment(graph(),ACTIVE,checkpoint=stop)
    def test_old_baseline_not_mutated(self):
        p=problem();old=p.space.graph.digest();x=np.zeros(p.size);x[-6]=.1;p.candidate(x)
        self.assertEqual(old,p.space.graph.digest())
    def test_unknown_native_evidence_not_fabricated(self):
        e=problem().space.evidence
        self.assertEqual(e['native_parent_measurement'],'NOT_RUN')
    def test_identity_screen_not_form_repair(self):
        p=problem();out,r=screen_attachment(p,np.zeros(p.size),physical_planes=[(0,0)],density=21,per_span=7)
        self.assertEqual(r['status'],'REPRESENTATION_ONLY_NOT_FORM_REPAIR');self.assertFalse(r['geometry_commit'])
    def test_non_improving_chart_rolls_back(self):
        p=problem();x=np.zeros(p.size);x[-6]=.2
        out,r=screen_attachment(p,x,physical_planes=[(0,-2),(0,0),(0,2)],maximum_backtracks=0,density=21,per_span=7)
        self.assertEqual(r['status'],'BASELINE_RETAINED_FORM_NOT_ACCEPTED');self.assertEqual(out.digest(),p.space.graph.digest())
    def test_screen_requires_physical_sections(self):
        p=problem()
        with self.assertRaises(ValueError):screen_attachment(p,np.zeros(p.size))
    def test_parameter_backtrack_input_validation(self):
        p=problem()
        for x in (-1,2,np.nan):
            with self.assertRaises(ValueError):p.candidate(np.zeros(p.size),x)


class StationTests(unittest.TestCase):
    def test_explicit_alternatives_are_shape_identity_until_solved(self):
        t=tensor();gs=station_graphs(t,[(.2,.8),(.27,.72)],source=source());u=np.linspace(0,1,31);v=np.linspace(0,1,31)
        for g in gs:
            self.assertEqual(len(g.coverage()),6);self.assertEqual(len(g.allocated_sources()),10)
            self.assertLess(np.max(np.abs(g.evaluate(u,v)-t.grid(u,v)[np.arange(31),np.arange(31)])),1e-10)
    def test_station_budget_and_duplicates(self):
        for stations in ([],[(.2,.8)]*2,[(.2,.8)]*6,[(.6,.8)]):
            with self.assertRaises(ValueError):station_graphs(tensor(),stations)
    def test_physical_plane_same_for_different_initial_layouts(self):
        a,b=station_graphs(tensor(),[(.2,.8),(.28,.74)])
        x=fixed_plane_section(a,0,1,np.linspace(0,1,41));y=fixed_plane_section(b,0,1,np.linspace(0,1,41))
        self.assertAlmostEqual(x['curvature']['maximum'],y['curvature']['maximum'],places=9)
    def test_native_three_brep_export_of_changed_two_jets(self):
        try:import rhino3dm as R
        except ImportError:
            if os.environ.get('GITHUB_ACTIONS'):self.fail('rhino3dm required in CI')
            self.skipTest('OpenNURBS not installed locally; no native test claimed')
        p=problem();x=np.zeros(p.size);x[-6:]=[.1,.03,.1,-.02,.01,-.02];g=p.candidate(x)
        f=R.File3dm()
        for t in g.patches:
            n=R.NurbsSurface.Create(3,False,t.p+1,t.q+1,t.nu,t.nv)
            for i,k in enumerate(t.ku[1:-1]):n.KnotsU[i]=float(k)
            for i,k in enumerate(t.kv[1:-1]):n.KnotsV[i]=float(k)
            for i in range(t.nu):
                for j in range(t.nv):n.Points[i,j]=R.Point4d(*map(float,t.net[i,j]),1.)
            b=R.Brep.CreateFromSurface(n);self.assertTrue(b.IsValid);f.Objects.AddBrep(b,R.ObjectAttributes())
        with tempfile.TemporaryDirectory() as tmp:
            name=str(Path(tmp)/'synthetic.3dm');self.assertTrue(f.Write(name,8));loaded=R.File3dm.Read(name)
            self.assertEqual(len(loaded.Objects),3)
            for obj,t in zip(loaded.Objects,g.patches):
                q=obj.Geometry.Faces[0].PointAt(.41,.36);v=t.grid([.41],[.36])[0,0]
                self.assertLess(np.linalg.norm(np.array([q.X,q.Y,q.Z])-v),1e-10)

if __name__=='__main__':unittest.main(verbosity=2)
