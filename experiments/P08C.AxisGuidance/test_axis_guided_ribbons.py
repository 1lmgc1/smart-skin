"""Independent numerical tests; no private model, no Rhino UI/Join execution."""
from pathlib import Path
import tempfile, unittest
import numpy as np
from numpy.polynomial import Polynomial
from scipy.interpolate import BSpline
import axis_guided_ribbons as k


def fixture(**changes):
    frame=k.DesignFrame((0,0,0),(1,0,0),(0,1,0))
    def left(v):return ((v,-1.,.2*v*v),(1.,.1,.1*v),(0.,.02,.3))
    def right(v):return ((v,1.,.2*v*v),(1.,-.1,.1*v),(0.,-.02,.3))
    def bottom(u):return (0.,2*u-1,0.)
    def top(u):return (1.,2*u-1,.2+.02*(.5-abs(u-.5)))
    controls=dict(left_width=.2,right_width=.2,left_pull=.12,right_pull=-.12,start_cut=.15,end_cut=.8)
    controls.update(changes)
    p=k.CoreProfile(bottom(.5),top(.5),frame)
    return k.AxisRibbons(left,right,bottom,top,p,frame.transverse,**controls)


def endpoint_derivatives(fn,span,right=False):
    t=np.linspace(0,1,7)
    vals=np.array([fn((1-span)+span*x if right else span*x) for x in t])
    p=[Polynomial.fit(t,vals[:,j],5,domain=[0,1]).convert() for j in range(3)]
    at=1. if right else 0.
    return np.array([[s.deriv(d)(at)/span**d for s in p] for d in range(3)])


class RibbonsTests(unittest.TestCase):
    def test_hermite_endpoint_jets_against_polynomial_fit(self):
        goals=np.array([[1,2,3],[2,-1,.4],[.2,.3,-.4],[3,4,-2],[.1,1,2],[3,.7,-1]])
        fn=lambda t:k.hermite5(t,goals)
        left=endpoint_derivatives(fn,1);right=endpoint_derivatives(fn,1,True)
        np.testing.assert_allclose(left,goals[:3],atol=2e-11)
        np.testing.assert_allclose(right,goals[3:],atol=2e-11)
    def test_complete_boundary_and_compound_junctions_preserved(self):
        p=fixture()
        for t in np.unique(np.r_[np.linspace(0,1,213),.5]):
            for a,b in [(p.point(t,0),p.bottom(t)),(p.point(t,1),p.top(t)),(p.point(0,t),p.left(t)[0]),(p.point(1,t),p.right(t)[0])]:
                np.testing.assert_allclose(a,b,atol=3e-14)
    def test_actual_parent_second_jet_match_both_sides(self):
        p=fixture()
        for v in [.2,.37,.6,.77]:
            for right,width,pull,target in [(False,p.lw,p.lp,p.left),(True,p.rw,p.rp,p.right)]:
                jets=endpoint_derivatives(lambda u:p.point(u,v),width,right)
                src=target(v);scale=pull/width
                np.testing.assert_allclose(jets,np.array([src[0],np.array(src[1])*scale,np.array(src[2])*scale*scale]),atol=2e-10)
    def test_core_not_merely_a_single_pinned_point(self):
        p=fixture()
        for u in [.22,.4,.5,.65,.78]:
            for v in [.22,.43,.66,.77]:
                np.testing.assert_allclose(p.point(u,v),p.core(u,v)[0],atol=1e-14)
    def test_guide_through_entire_domain_and_fixed_ends(self):
        p=fixture()
        for v in np.linspace(0,1,71):np.testing.assert_allclose(p.point(.5,v),p.profile(v),atol=2e-14)
    def test_local_corrections_really_change_geometry_not_just_a_flag(self):
        a=fixture(start_cut=.1,end_cut=.9);b=fixture(start_cut=.3,end_cut=.65)
        self.assertGreater(k.norm(k.sub(a.point(.07,.8),b.point(.07,.8))),1e-4)
        np.testing.assert_allclose(a.point(.07,.5),b.point(.07,.5),atol=2e-14)
    def test_tension_changes_end_zone_without_moving_boundaries_or_core(self):
        a=fixture(left_pull=.1);b=fixture(left_pull=.2)
        self.assertGreater(k.norm(k.sub(a.point(.1,.5),b.point(.1,.5))),1e-3)
        for u in [0,.5,1]:np.testing.assert_allclose(a.point(u,.5),b.point(u,.5),atol=1e-14)
    def test_core_to_ribbon_C2_jets(self):
        p=fixture()
        for right,w in [(False,p.lw),(True,p.rw)]:
            for v in [.23,.55,.75]:
                jets=endpoint_derivatives(lambda u:p.raw(u,v),w,right)
                if not right:
                    join=endpoint_derivatives(lambda t:p.raw(w-t,v),w)
                    join[1]*=-1
                else:
                    join=endpoint_derivatives(lambda t:p.raw(1-w+t,v),w)
                np.testing.assert_allclose(join,np.array(p.core(1-w if right else w,v)),atol=5e-10)
    def test_fade_has_zero_first_second_derivatives_at_release(self):
        h=Polynomial([0,0,0,10,-15,6])
        for d in [1,2]:
            self.assertEqual(h.deriv(d)(0),0);self.assertEqual(h.deriv(d)(1),0)
    def test_frame_rotation_translation_covariance(self):
        a=fixture();theta=.79;R=np.array([[np.cos(theta),0,np.sin(theta)],[0,1,0],[-np.sin(theta),0,np.cos(theta)]]);T=np.array([2,4,7])
        pt=lambda x:tuple(R@np.array(x)+T);vec=lambda x:tuple(R@np.array(x))
        def tr(fn):
            def call(v):
                p,d,a=fn(v);return pt(p),vec(d),vec(a)
            return call
        b=k.AxisRibbons(tr(a.left),tr(a.right),lambda t:pt(a.bottom(t)),lambda t:pt(a.top(t)),lambda t:pt(a.profile(t)),vec(a.transverse),a.lw,a.rw,a.lp,a.rp,a.start_cut,a.end_cut)
        for u in [.01,.2,.51,.9]:
            for v in [.02,.3,.91]:np.testing.assert_allclose(b.point(u,v),pt(a.point(u,v)),atol=2e-14)
    def test_profile_controls_move_middle_not_endpoints(self):
        F=k.DesignFrame((0,0,0),(1,0,0),(0,1,0));a=k.CoreProfile((0,0,0),(1,0,1),F);b=k.CoreProfile((0,0,0),(1,0,1),F,.9,.4,.05)
        self.assertGreater(k.norm(k.sub(a(.5),b(.5))),.02)
        for t in [0,1]:self.assertEqual(a(t),b(t))
    def test_nonfinite_and_empty_active_zones_rejected(self):
        for cfg in [dict(start_cut=.9,end_cut=.8),dict(start_cut=0),dict(end_cut=1),dict(left_pull=float('nan')),dict(right_pull=0),dict(left_width=.8,right_width=.4)]:
            with self.assertRaises(ValueError):fixture(**cfg)
    def test_invalid_frame_rejected(self):
        for a,b in [((0,0,0),(0,1,0)),((1,0,0),(2,0,0))]:
            with self.assertRaises(ValueError):k.DesignFrame((0,0,0),a,b)
    def test_model_does_not_silently_close_open_corner(self):
        a=fixture()
        with self.assertRaisesRegex(ValueError,'SOURCE_CORNERS'):
            k.AxisRibbons(a.left,a.right,lambda u:(0,2*u-1,.1),a.top,a.profile,a.transverse)
    def test_no_hidden_commit_or_G2_outside_active_interval(self):
        c=fixture().contract()
        self.assertFalse(c['commit_allowed']);self.assertFalse(c['source_edit'])
        self.assertIn('NOT_ASSIGNED_G2',c['outside_active_grade'])
        self.assertEqual(c['active_parent_match_v'],[.15,.8])
    def test_domains_and_degenerate_parent_jet(self):
        p=fixture()
        for u,v in [(-.1,.5),(.5,1.1),(float('nan'),0)]:
            with self.assertRaises(ValueError):p.point(u,v)
        p.left=lambda v:((v,-1,.2*v*v),(0,0,0),(0,0,0))
        with self.assertRaises(ValueError):p.point(.1,.5)
    def test_source_has_no_host_writes_or_IO(self):
        src=Path(k.__file__).read_text()
        for word in ['Objects.Add','Objects.Replace','Objects.Delete','open(', 'subprocess','requests.', 'os.']:
            self.assertNotIn(word,src)
    def test_true_openNURBS_conversion_and_roundtrip(self):
        import rhino3dm as rg
        p=fixture();xs=sorted(set([0.,p.lw,.5,1-p.rw,1.]));ys=[0.,p.start_cut,p.end_cut,1.]
        K=np.r_[[0.]*6,np.repeat(xs[1:-1],5),[1.]*6];L=np.r_[[0.]*6,np.repeat(ys[1:-1],5),[1.]*6]
        n,m=len(K)-6,len(L)-6;u=np.array([np.mean(K[i+1:i+6]) for i in range(n)]);v=np.array([np.mean(L[i+1:i+6]) for i in range(m)])
        Bu=BSpline(K,np.eye(n),5);Bv=BSpline(L,np.eye(m),5)
        Y=np.array([[p.point(float(s),float(t)) for t in v] for s in u]);C=np.linalg.solve(Bu(u),Y.reshape(n,-1)).reshape(n,m,3)
        C=np.linalg.solve(Bv(v),C.transpose(1,0,2).reshape(m,-1)).reshape(m,n,3).transpose(1,0,2)
        sf=rg.NurbsSurface.Create(3,False,6,6,n,m)
        for i,x in enumerate(K[1:-1]):sf.KnotsU[i]=float(x)
        for j,x in enumerate(L[1:-1]):sf.KnotsV[j]=float(x)
        for i in range(n):
            for j in range(m):sf.Points[i,j]=rg.Point4d(*C[i,j],1)
        b=rg.Brep.CreateFromSurface(sf);self.assertTrue(b.IsValid)
        for s,t in [(.03,.1),(.67,.3),(.5,.9),(.99,.53)]:
            q=sf.PointAt(s,t);np.testing.assert_allclose([q.X,q.Y,q.Z],p.point(s,t),atol=2e-12)
        with tempfile.TemporaryDirectory() as d:
            f=rg.File3dm();f.Objects.AddBrep(b,rg.ObjectAttributes());path=str(Path(d)/'synthetic.3dm');self.assertTrue(f.Write(path,8));r=rg.File3dm.Read(path);self.assertEqual(len(r.Objects),1);self.assertTrue(r.Objects[0].Geometry.IsValid)

if __name__=='__main__': unittest.main(verbosity=2)
