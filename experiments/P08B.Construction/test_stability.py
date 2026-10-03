"""P08B.3 synthetic geometry tests. No private model, Rhino UI or Join execution."""
import math
import unittest
import numpy as np
from scipy.interpolate import BSpline
from mixed_kernel import *
from shape_guard import *
from stable_refinement import *

ZERO=((0.,0.,0.),)*3

def plane(K=None):
    K=K or knots(10,3);n=len(K)-4;g=[sum(K[i+1:i+4])/3 for i in range(n)]
    return Patch([[(u,v,0.) for v in g] for u in g],3,K)

def boundaries_of(values,preferred=None):
    preferred=preferred or dict(bottom=0,right=2,top=0,left=2)
    out={}
    for side in SIDES:
        def f(t,side=side):
            u,v=side_uv(side,t); jet=values(u,v);n,H=frame(jet)
            return Support(jet[0],n,H,side,preferred[side])
        out[side]=f
    return out

def flat_values(u,v): return ((u,v,0.),(1.,0.,0.),(0.,1.,0.),(0.,0.,0.),(0.,0.,0.),(0.,0.,0.))

def bump(u,v,a=.6):
    return ((u,v,a*u*(1-u)*v*(1-v)),(1,0,a*(1-2*u)*v*(1-v)),(0,1,a*u*(1-u)*(1-2*v)),
            (0,0,-2*a*v*(1-v)),(0,0,a*(1-2*u)*(1-2*v)),(0,0,-2*a*u*(1-u)))

def stationary_bump(u,v):
    a=.8;f=u*u*(1-u)*(1-u); df=2*u-6*u*u+4*u**3; ddf=2-12*u+12*u*u
    return ((u,v,a*f*v*(1-v)),(1,0,a*df*v*(1-v)),(0,1,a*f*(1-2*v)),
            (0,0,a*ddf*v*(1-v)),(0,0,a*df*(1-2*v)),(0,0,-2*a*f))


def independent(p,u,v,du=0,dv=0):
    b=BSpline(p.K,np.eye(p.n),p.p)
    return np.einsum('i,ijk,j->k',b(u,nu=du),np.array(p.net),b(v,nu=dv))

def bval(net,u,v):
    n=len(net)-1;m=len(net[0])-1
    return sum(_bin(n,i)*u**i*(1-u)**(n-i)*_bin(m,j)*v**j*(1-v)**(m-j)*net[i][j]
               for i in range(n+1) for j in range(m+1))

def _bin(n,i): return math.comb(n,i)

class ShapeGuardTests(unittest.TestCase):
    def setUp(self): self.bounds=boundaries_of(flat_values)
    def test_plane_every_knot_cell_passes(self):
        p=plane();r=ShapePolicy(p,self.bounds,.01).inspect(p)
        self.assertTrue(r['ok'],r);self.assertEqual(r['cells'],49)
    def test_sparse_evaluator_matches_scipy(self):
        p=plane([0]*4+[.007,.021,.048,.2,.5,.7,.92,.985]+[1]*4)
        net=[[add(x,(0,0,.01*math.sin(i+j))) for j,x in enumerate(row)] for i,row in enumerate(p.net)]
        p=Patch(net,3,p.K); e=FastEvaluator(p)
        for u,v in ((.001,.012),(.024,.978),(.314,.62),(0,1)):
            for value,(du,dv) in zip(e.eval(u,v),((0,0),(1,0),(0,1),(2,0),(1,1),(0,2))):
                np.testing.assert_allclose(value,independent(p,u,v,du,dv),rtol=1e-10,atol=1e-9)
    def test_bezier_extraction_and_jacobian_against_independent_scipy(self):
        p=plane([0]*4+[.009,.032,.1,.33,.55,.94,.992]+[1]*4)
        net=[[add(x,(.01*math.sin(i+j),0,.008*math.cos(i-j))) for j,x in enumerate(row)] for i,row in enumerate(p.net)]
        p=Patch(net,3,p.K);ex=cell_extractors(p)
        for a,b,eu in ex:
            for c,d,ev in ex:
                B=bezier_cell(p,eu,ev); J=jacobian_coefficients(B,(0,0,1))
                for t,s in ((.137,.819),(.513,.271)):
                    u=a+(b-a)*t;v=c+(d-c)*s
                    bp=np.array([bval([[B[i][j][k] for j in range(4)] for i in range(4)],t,s) for k in range(3)])
                    np.testing.assert_allclose(bp,independent(p,u,v),rtol=1e-10,atol=1e-11)
                    au=[[mul(sub(B[i+1][j],B[i][j]),3.) for j in range(4)] for i in range(3)]
                    av=[[mul(sub(B[i][j+1],B[i][j]),3.) for j in range(3)] for i in range(4)]
                    scale=max(norm(x) for row in au for x in row)*max(norm(x) for row in av for x in row)
                    expect=np.cross(independent(p,u,v,1,0),independent(p,u,v,0,1))[2]*(b-a)*(d-c)/scale
                    self.assertAlmostEqual(bval(J,t,s),expect,places=10)
    def test_narrow_spike_missed_by_legacy_grid_is_rejected(self):
        # Synthetic, independent knot choices. CV(1,1) support is entirely below 1/16.
        p=plane([0]*4+[.006,.019,.045,.2,.4,.6,.8,.95,.99]+[1]*4)
        net=[list(row) for row in p.net];net[1][1]=add(net[1][1],(-200,0,50));bad=Patch(net,3,p.K)
        old=measure(bad,self.bounds);self.assertTrue(old['position_sampled_ok']);self.assertTrue(old['regularity_sampled_ok'])
        self.assertEqual(p.boundary_snapshot(),bad.boundary_snapshot())
        r=ShapePolicy(p,self.bounds,.01).inspect(bad)
        self.assertFalse(r['ok'],r)
        determinants=[np.cross(independent(bad,u,v,1,0),independent(bad,u,v,0,1))[2]
                      for u in np.linspace(.0001,.04,17) for v in np.linspace(.0001,.04,17)]
        self.assertLess(min(determinants),0)
    def test_interior_height_spike_cannot_pass_by_positive_jacobian(self):
        p=plane();net=[list(row) for row in p.net];net[4][4]=add(net[4][4],(0,0,10));bad=Patch(net,3,p.K)
        r=ShapePolicy(p,self.bounds,.01).inspect(bad)
        self.assertFalse(r['ok']);self.assertEqual(r['reason'],'BEZIER_ENVELOPE_UNRESOLVED')
    def test_negative_coefficients_are_not_alone_called_inversion(self):
        C=[[.251,.251,.251],[-.249,-.249,-.249],[.251,.251,.251]]
        r=positive_bernstein(C,max_depth=8)
        self.assertTrue(r['ok'],r);self.assertGreater(r['nodes'],1)
    def test_uncertain_budget_fails_closed(self):
        C=[[.251,.251,.251],[-.249,-.249,-.249],[.251,.251,.251]]
        r=positive_bernstein(C,max_depth=0)
        self.assertFalse(r['ok']);self.assertEqual(r['reason'],'PROJECTED_JACOBIAN_UNRESOLVED')
    def test_actual_negative_cell_value_detected(self):
        self.assertFalse(positive_bernstein([[1,1,1],[-2,-2,-2],[1,1,1]])['ok'])
    def test_every_span_contributes_to_boundary_samples(self):
        K=plane([0]*4+[.003,.007,.05,.4,.95,.999]+[1]*4).K
        ts=stable_sites(self.bounds['left'],K)
        for a,b in spans(K): self.assertTrue(any(a<t<b for t in ts))
    def test_harmonic_seed_preserves_boundary_and_rejects_no_point(self):
        p=plane();net=[list(row) for row in p.net];net[4][4]=(99,99,99);bad=Patch(net,3,p.K)
        fixed=harmonic_seed(bad)
        self.assertEqual(fixed.boundary_snapshot(),p.boundary_snapshot())
        self.assertTrue(ShapePolicy(p,self.bounds,.01).inspect(fixed)['ok'])
    def test_anchor_displacement_cannot_walk_away_over_many_steps(self):
        p=plane();net=[list(row) for row in p.net];net[4][4]=add(net[4][4],(0,0,.46));r=ShapePolicy(p,self.bounds,.01).inspect(Patch(net),p)
        self.assertFalse(r['ok']);self.assertEqual(r['reason'],'ANCHOR_DISPLACEMENT_LIMIT')
    def test_guard_rejects_unsupported_repeated_interior_knots(self):
        p=plane([0]*4+[.25,.25,.5,.75]+[1]*4)
        with self.assertRaisesRegex(ValueError,'SIMPLE_INTERIOR'): cell_extractors(p)
    def test_cancellation_is_not_swallowed(self):
        def stop(): raise RuntimeError('CANCELLED')
        with self.assertRaisesRegex(RuntimeError,'CANCELLED'):ShapePolicy(plane(),self.bounds,.01).inspect(plane(),checkpoint=stop)

class StabilizedSolverTests(unittest.TestCase):
    def test_real_bump_gets_G1_before_G2_with_frozen_boundary(self):
        bounds=boundaries_of(bump);p=plane();events=[];candidates=[]
        initial=stable_measure(p,bounds,ShapePolicy(p,bounds,.01))
        result,e=stable_solve(p,bounds,on_event=lambda k,d:events.append((k,d)),on_candidate=lambda l,p,e:candidates.append((l,p,e)),steps=8)
        self.assertIsNotNone(result);self.assertLess(e['normal_rms_deg'],initial['normal_rms_deg']*.8)
        self.assertTrue(e['g1_all'],e)
        for name,patch,ev in candidates:
            self.assertEqual(p.boundary_snapshot(),patch.boundary_snapshot());self.assertTrue(ev['shape']['ok'])
        for k,d in events:
            if k=='STABLE_STEP_START' and d['level']=='G2':self.assertTrue(d['g1_all'])
        for k,d in events:
            if k=='STABLE_TRIAL':self.assertLessEqual(d['actual_control_step'],d['step_limit']*(1+1e-10))
    def test_actual_G2_change_with_already_tangent_flat_seed(self):
        bounds=boundaries_of(stationary_bump);p=plane();initial=stable_measure(p,bounds,ShapePolicy(p,bounds,.01))
        self.assertTrue(initial['g1_all']);self.assertFalse(initial['desired_sampled_met'])
        result,e=stable_solve(p,bounds,steps=8)
        self.assertTrue(e['g1_all']);self.assertLess(e['curvature_rms_pct'],initial['curvature_rms_pct']*.5)
        # Worst-case grading remains strict even when interior curvature improves.
        if e['curvature_max_pct']>5:self.assertFalse(e['desired_sampled_met'])
        self.assertGreater(max(abs(pt[2]) for row in result.net for pt in row),1e-6)
    def test_impossible_tangent_assignment_never_enters_G2(self):
        bounds=boundaries_of(flat_values)
        for side in ('left','right'):
            def f(t,s=side):return Support(side_uv(s,t)+(0.,),(0,1,0),ZERO,s,2)
            bounds[side]=f
        events=[];p=plane();result,e=stable_solve(p,bounds,on_event=lambda k,d:events.append((k,d)),steps=2)
        self.assertIsNotNone(result);self.assertFalse(e['g1_all'])
        self.assertFalse(any(k=='STABLE_STEP_START' and d['level']=='G2' for k,d in events))
    def test_curvature_only_improvement_cannot_replace_failed_G1(self):
        bounds=boundaries_of(bump);p=plane();a=stable_measure(p,bounds,ShapePolicy(p,bounds,.01)); b=dict(a,curvature_max_pct=0.)
        self.assertFalse(a['g1_all']);self.assertFalse(prefer_evidence(b,a))
    def test_failed_step_retains_exact_previous_revision(self):
        p=plane();bounds=boundaries_of(flat_values);policy=ShapePolicy(p,bounds,.01);e=stable_measure(p,bounds,policy)
        bad=Patch([[add(pt,(0,0,999)) if 0<i<p.n-1 and 0<j<p.n-1 else pt for j,pt in enumerate(row)] for i,row in enumerate(p.net)])
        r,new,kept=bounded_step(p,bad,p,bounds,policy,e)
        self.assertFalse(kept);self.assertIs(r,p);self.assertIs(new,e)
    def test_missing_normals_never_become_G1(self):
        b=boundaries_of(flat_values);b['left']=lambda t:Support((0,t,0),None,None,'left',2)
        p=plane();r,e=stable_solve(p,b,steps=1)
        self.assertFalse(e['g1_all']);self.assertFalse(e['edges']['left']['frames'])
    def test_harmonic_fallback_is_constructive_not_only_a_rejection(self):
        p=plane();net=[list(row) for row in p.net];net[1][1]=(-100,0,30);bad=Patch(net,3,p.K)
        b=boundaries_of(flat_values);r,e=stable_solve(bad,b,steps=1)
        self.assertIsNotNone(r);self.assertTrue(e['shape']['ok'])
        self.assertLess(max(norm(pt) for row in r.net for pt in row),2.)

if __name__=='__main__': unittest.main(verbosity=2)
