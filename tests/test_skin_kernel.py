"""Synthetic, redistributable fixtures only. No Rhino installation required."""
import copy
import importlib.util
import pathlib
import unittest
import numpy as np

MODULE=pathlib.Path(__file__).parents[1]/'src'/'SmartSkin.Rhino8'/'Python'/'skin_kernel.py'
spec=importlib.util.spec_from_file_location('skin_kernel',MODULE)
sk=importlib.util.module_from_spec(spec);spec.loader.exec_module(sk)


def fixture(rational=True,reverse=False):
    sides=[]
    for sign in (-1,1):
        cp=[]
        # S(u,v)=(sign*(3+u),-2v,0.12*u^2*v*(1-v)).
        for i in range(3):
            row=[]
            for j in range(3):
                z=.06 if i==2 and j==1 else 0
                row.append([sign*(3+i/2),-j,z,1])
            cp.append(row)
        sides.append(dict(degree_u=2,degree_v=2,knots_u=[0]*3+[1]*3,knots_v=[0]*3+[1]*3,homogeneous_cp=cp))
    profiles=[dict(p0=[x,0,0],p1=[x,-2,0],t0=[0,-1,0],t1=[0,-1,0],k0=[0,0,0],k1=[0,0,0],speed0=2,speed1=2) for x in (-2,-1,0,1,2)]
    upper=[]
    for sign in (-1,1):
        path=[]
        for a,b in ((0,.1),(.1,.2),(.2,1)):
            weights=np.array([1,np.nextafter(1.,2),np.nextafter(1.,0),1]) if rational else np.ones(4)
            xyz=np.array([[sign*(3-a-(b-a)*t),0,0] for t in np.linspace(0,1,4)])
            h=np.c_[xyz*weights[:,None],weights]
            if reverse:h=h[::-1]
            path.append(dict(curve=dict(degree=3,knots=[0]*4+[1]*4,homogeneous_cp=h.tolist()),u_interval=[a,b],reverse=reverse))
        upper.append(path)
    return dict(side_surfaces=sides,profiles=profiles,upper_paths=upper,upper_plane_normal=[0,0,1],transverse_direction=[1,0,0],row_t=[.12,.2,.2+.7/6,.2+2*.7/6,.55,.2+4*.7/6,.2+5*.7/6,.9,.95],tolerance=1e-6)


class AlgebraTests(unittest.TestCase):
    def test_bernstein_roundtrip(self):
        rng=np.random.default_rng(12)
        cp=rng.normal(size=(12,16,3))
        with sk.mp.workdps(60):
            p=sk.bernstein_to_power(sk.bernstein_to_power(cp,0),1)
            back=sk.power_to_bernstein(sk.power_to_bernstein(p,axis=0),axis=1)
        np.testing.assert_allclose(np.asarray(back,float),cp,atol=2e-13)

    def test_rational_curve_jet(self):
        c=dict(degree=2,knots=[0]*3+[1]*3,homogeneous_cp=[[1,0,0,1],[1,1,0,1],[0,2,0,2]])
        np.testing.assert_allclose(sk.evaluate_curve(c,0),[1,0,0])
        np.testing.assert_allclose(sk.evaluate_curve(c,1),[0,1,0])
        t=.37;eps=1e-5
        fd=(sk.evaluate_curve(c,t+eps)-sk.evaluate_curve(c,t-eps))/(2*eps)
        np.testing.assert_allclose(sk.evaluate_curve(c,t,1),fd,atol=1e-9)


    def test_rational_native_knot_and_restricted_reverse(self):
        h=np.array([[0,0,0,1],[1.2,.4,0,.8],[2,1,0,1],[4,0,0,1]])
        original=sk.BSpline([2]*4+[6]*4,h,3).insert_knot(3.4)
        record=dict(degree=3,knots=original.t.tolist(),homogeneous_cp=original.c.tolist(),domain=[2.5,5.5])
        pieces=sk._upper_pieces([dict(curve=record,u_interval=[0,1],reverse=True)])
        self.assertEqual(len(pieces),2)
        self.assertAlmostEqual(pieces[0]['ub'],(5.5-3.4)/3)
        for piece in pieces:
            for t in np.linspace(0,1,9):
                u=piece['ua']+(piece['ub']-piece['ua'])*t
                cp=sk._val(piece['top'],sk.mp.mpf(t))
                np.testing.assert_allclose(np.asarray(cp[:3]/cp[3],float),sk.evaluate_curve(record,5.5-3*u),atol=2e-12)

    def test_preallocation_control_point_budgets(self):
        model=sk.SkinModel.__new__(sk.SkinModel);model._encoded_control_points=0
        huge={'p':np.zeros((41,41,3)),'w':np.ones(1)}
        with self.assertRaisesRegex(sk.UnsupportedFamily,'16,384'):
            model._encode_strip([huge]*64,'collar',0,0)
        model._encoded_control_points=65530
        small={'p':np.zeros((6,16,3)),'w':np.ones(1)}
        with self.assertRaisesRegex(sk.UnsupportedFamily,'65,536'):
            model._encode_strip([small],'collar',0,0)

    def test_nonfinite_geometry_never_passes(self):
        jets=np.zeros((6,3));jets[1,0]=float('nan')
        geometry,sine=sk._geometry(jets)
        self.assertIsNone(geometry);self.assertEqual(sine,0)


class ConstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model=sk.build_model(fixture())
        cls.result=cls.model.evaluate(1,validate=False)

    def test_topology_and_native_weights(self):
        surfaces=self.result['surfaces']
        self.assertEqual(len(surfaces),10)
        self.assertEqual(self.result['network']['profile_count'],5)
        self.assertEqual(self.result['network']['row_count'],9)
        self.assertTrue(any(np.any(np.asarray(s['weights'])!=1) for s in surfaces[:6]))
        for s in surfaces:
            cp=np.asarray(s['homogeneous_cp'])
            self.assertEqual(len(s['knots_u']),cp.shape[0]+s['degree_u']+1)
            self.assertEqual(len(s['knots_v']),cp.shape[1]+s['degree_v']+1)

    def test_exact_upper_source_locus(self):
        source=fixture()
        for s in self.result['surfaces']:
            if s['kind']!='collar':continue
            segment=source['upper_paths'][s['side']][s['piece']]
            a,b=s['domain'][0]
            for t in np.linspace(0,1,17):
                np.testing.assert_allclose(sk.evaluate_surface(s,a+(b-a)*t,0),sk.evaluate_curve(segment['curve'],t),atol=2e-12)

    def test_handle_changes_shape_not_network(self):
        low=self.model.evaluate(.65,validate=False);high=self.model.evaluate(1.35,validate=False)
        self.assertEqual(low['network'],high['network'])
        left=low['surfaces'][0];right=high['surfaces'][0]
        delta=np.linalg.norm(sk.evaluate_surface(left,.045,.55)-sk.evaluate_surface(right,.045,.55))
        self.assertGreater(delta,1e-4)
        for a,b in zip(low['guides'][:5],high['guides'][:5]):self.assertEqual(a,b)

    def test_source_handle_scaling(self):
        low=self.model.evaluate(.7,validate=False);high=self.model.evaluate(1.4,validate=False)
        a,b=low['surfaces'][0],high['surfaces'][0]
        np.testing.assert_allclose(sk.evaluate_surface(b,0,.55,1,0),2*sk.evaluate_surface(a,0,.55,1,0),atol=5e-10)
        np.testing.assert_allclose(sk.evaluate_surface(b,0,.55,2,0),4*sk.evaluate_surface(a,0,.55,2,0),atol=5e-9)

    def test_seam_physical_two_jet_transport(self):
        surfaces=self.result['surfaces']
        for side in range(2):
            group=[s for s in surfaces if s['kind']=='collar' and s['side']==side]
            for k,(left,right) in enumerate(zip(group[:-1],group[1:])):
                u=right['domain'][0][0]
                alpha,beta,gamma,delta=self.model._maps[side][k]
                for v in (.0,.03,.075,.12,.55,.95,1):
                    t=min(v/self.model.vs[1],1)
                    fade=float(sk._val(sk._C0,sk.mp.mpf(t)))
                    A=1+(alpha-1)*fade;B=beta*fade;G=gamma*fade;D=delta*fade
                    L=lambda du,dv:sk.evaluate_surface(left,u,v,du,dv)
                    R=lambda du,dv:sk.evaluate_surface(right,u,v,du,dv)
                    np.testing.assert_allclose(R(0,0),L(0,0),atol=2e-10)
                    np.testing.assert_allclose(R(1,0),A*L(1,0)+B*L(0,1),atol=1e-8)
                    np.testing.assert_allclose(R(2,0),A*A*L(2,0)+2*A*B*L(1,1)+B*B*L(0,2)+G*L(1,0)+D*L(0,1),atol=5e-7)

    def test_rigid_scale_and_reversed_source_curves(self):
        original=fixture(reverse=True)
        theta=.67;axis=np.array([1.,2.,-1.]);axis/=np.linalg.norm(axis)
        cross=np.array([[0,-axis[2],axis[1]],[axis[2],0,-axis[0]],[-axis[1],axis[0],0]])
        rotation=np.eye(3)*np.cos(theta)+(1-np.cos(theta))*np.outer(axis,axis)+np.sin(theta)*cross
        scale=3.7;offset=np.array([9.,-12.,5.])
        def point(p):return (scale*(rotation@np.asarray(p))+offset).tolist()
        def vector(p,factor=1):return (factor*(rotation@np.asarray(p))).tolist()
        for side in original['side_surfaces']:
            h=np.asarray(side['homogeneous_cp']);xyz=h[:,:,:3]/h[:,:,3,None]
            h[:,:,:3]=(scale*(xyz@rotation.T)+offset)*h[:,:,3,None]
            side['homogeneous_cp']=h.tolist()
        for path in original['upper_paths']:
            for segment in path:
                h=np.asarray(segment['curve']['homogeneous_cp']);xyz=h[:,:3]/h[:,3,None]
                h[:,:3]=(scale*(xyz@rotation.T)+offset)*h[:,3,None]
                segment['curve']['homogeneous_cp']=h.tolist()
        for section in original['profiles']:
            for key in ('p0','p1'):section[key]=point(section[key])
            for key in ('t0','t1'):section[key]=vector(section[key])
            for key in ('k0','k1'):section[key]=vector(section[key],1/scale)
            for key in ('speed0','speed1'):section[key]*=scale
        original['upper_plane_normal']=vector(original['upper_plane_normal'])
        original['transverse_direction']=vector(original['transverse_direction'])
        original['tolerance']*=scale
        transformed=sk.build_model(original).evaluate(1,validate=False)
        for left,right in zip(self.result['surfaces'],transformed['surfaces']):
            a,b=left['domain'][0]
            for u,v in ((a,.0),((a+b)/2,.037),(b,.55),((a+b)/2,.973)):
                np.testing.assert_allclose(sk.evaluate_surface(right,u,v),point(sk.evaluate_surface(left,u,v)),atol=2e-8)

    def test_sampled_validation_and_regular_failure(self):
        good=self.model.evaluate(1)
        self.assertTrue(good['geometry_valid'],good['reason'])
        self.assertGreater(good['report']['sample_count'],1000)
        self.assertGreater(good['report']['minimum_sampled_sine'],1e-5)
        bad=copy.copy(self.model);bad.cache=[]
        for zero,first,second in self.model.cache:
            zero=dict(zero);zero['cp']=zero['cp'].copy();zero['cp'][:,:,:3]=0
            first=first.copy();first[:,:,:3]=0
            second=second.copy();second[:,:,:3]=0
            bad.cache.append((zero,first,second))
        result=bad.evaluate(1)
        self.assertTrue(result['fatal'])
        self.assertFalse(result['experimental_commit_allowed'])
        self.assertIn('singular',result['reason'])

    def test_unsupported_rational_side_is_rejected(self):
        source=fixture();source['side_surfaces'][0]['homogeneous_cp'][1][1][3]=np.nextafter(1.,2)
        with self.assertRaises(sk.UnsupportedFamily):sk.build_model(source)

    def test_cancelled(self):
        with self.assertRaises(sk.Cancelled):self.model.evaluate(1,cancelled=lambda:True)
        with self.assertRaises(sk.Cancelled):sk.build_model(fixture(),cancelled=lambda:True)

    def test_fixed_production_baseline_retains_h1_only(self):
        fixed=sk.SkinModel(fixture(),_fixed_h1=True)
        a=self.model.evaluate(1,validate=False);b=fixed.evaluate(1,validate=False)
        self.assertEqual(fixed.network['production_baseline_h'],1.)
        for left,right in zip(a['surfaces'],b['surfaces']):
            np.testing.assert_allclose(left['homogeneous_cp'],right['homogeneous_cp'],rtol=0,atol=2e-12)
        for h in (.5,1.5):
            with self.assertRaisesRegex(ValueError,'select a generated U/V handle'):fixed.evaluate(h,validate=False)
        self.assertEqual(self.model.evaluate(.5,validate=False)['h'],.5)

    def test_invalid_factor(self):
        for h in (.4,1.6,float('nan')):
            with self.assertRaises(ValueError):self.model.evaluate(h)


if __name__=='__main__':unittest.main()
