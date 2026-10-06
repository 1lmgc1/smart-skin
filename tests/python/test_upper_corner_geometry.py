"""Redistributable synthetic tests for the bounded upper hard-corner algebra."""
import unittest
import sys
import functools
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"src"/"SmartSkin.Rhino8"/"Python"))
from fractions import Fraction as F
import numpy as np
import mpmath as mp
import upper_corner_geometry as uc
import fan_shared_jets as fj
def basis(knots,p,t,d):
    U=tuple(mp.mpf(float(x)) for x in knots);t=mp.mpf(float(t))
    @functools.lru_cache(None)
    def N(i,q,k):
        if i<0 or i+q+1>=len(U):return mp.mpf(0)
        if k:
            if q==0:return mp.mpf(0)
            a=q/(U[i+q]-U[i])*N(i,q-1,k-1) if U[i+q]!=U[i] else 0
            b=q/(U[i+q+1]-U[i+1])*N(i+1,q-1,k-1) if U[i+q+1]!=U[i+1] else 0
            return a-b
        if q==0:return mp.mpf(int(U[i]<=t<U[i+1] or (t==U[-1] and U[i]<t==U[i+1])))
        a=(t-U[i])/(U[i+q]-U[i])*N(i,q-1,0) if U[i+q]!=U[i] else 0
        b=(U[i+q+1]-t)/(U[i+q+1]-U[i+1])*N(i+1,q-1,0) if U[i+q+1]!=U[i+1] else 0
        return a+b
    return [N(i,p,d) for i in range(len(U)-p-1)]

def jets(s,u,v):
    cp=np.asarray(s['homogeneous_cp'],float);U=[basis(s['knots_u'],s['degree_u'],u,k) for k in range(3)];V=[basis(s['knots_v'],s['degree_v'],v,k) for k in range(3)];H={}
    for a,b in ((0,0),(1,0),(0,1),(2,0),(1,1),(0,2)):
        H[a,b]=[mp.fsum(U[a][i]*V[b][j]*mp.mpf(float(cp[i,j,c])) for i in range(len(U[a])) if U[a][i] for j in range(len(V[b])) if V[b][j]) for c in range(4)]
    X={};w=H[0,0][3]
    for a,b in ((0,0),(1,0),(0,1),(2,0),(1,1),(0,2)):
        x=mp.matrix(H[a,b][:3])
        for i in range(a+1):
            for j in range(b+1):
                if i+j:x-=mp.binomial(a,i)*mp.binomial(b,j)*H[i,j][3]*X[a-i,b-j]
        X[a,b]=x/w
    return [X[a,b] for a,b in ((0,0),(1,0),(0,1),(2,0),(1,1),(0,2))]

def cross(a,b):return mp.matrix([a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]])
def geo(j):
    _,u,v,uu,uv,vv=j;n=cross(u,v);n/=mp.norm(n);J=mp.matrix([[u[k],v[k]] for k in range(3)]);I=J.T*J;II=mp.matrix([[mp.fdot(n,uu),mp.fdot(n,uv)],[mp.fdot(n,uv),mp.fdot(n,vv)]]);return n,J*I**-1*II*I**-1*J.T

def compare(a,b):
    na,wa=geo(a);nb,wb=geo(b)
    if mp.fdot(na,nb)<0:nb=-nb;wb=-wb
    delta=wa-wb;delta=(delta+delta.T)/2
    return dict(angle_degrees=float(mp.atan2(mp.norm(cross(na,nb)),mp.fdot(na,nb))*180/mp.pi),operator=float(max(abs(x) for x in mp.eigsy(delta,eigvals_only=True))),position=float(mp.norm(a[0]-b[0])))




def fixture(h=1.,rational=False):
    base=fj._zeros((2,2,3));base[1,0,2]=F(h);base[0,1,1]=1
    regular=base.copy();delta=fj._zeros((2,6,3));delta[1,:,0]=uc.obj([1,0,0,-10,15,-6]);delta[1,:,2]=-F(h)*uc.obj([1,0,0,-10,15,-6]);regular=fj.add(regular,delta)
    w=uc.obj([1,F(1,10)]) if rational else uc.obj([1])
    return base,uc.mul_u(w,regular),w,uc.obj([0,0,1])

def transformed(data,rotation,scale,translation):
    base,p,w,n=data
    b=np.einsum('ijc,dc->ijd',base,uc.obj(rotation))*F(scale);b[0,0]+=uc.obj(translation)
    q=np.einsum('ijc,dc->ijd',p,uc.obj(rotation))*F(scale);q[:len(w),0]+=w[:,None]*uc.obj(translation)[None,:]
    normal=uc.obj(rotation)@n
    return b,q,w,normal

class UpperCornerTests(unittest.TestCase):
    def setUp(self):
        self._old_dps=mp.mp.dps;mp.mp.dps=80
    def tearDown(self):
        mp.mp.dps=self._old_dps
    def build(self,data):return uc.build_upper_corner(*data,position_tolerance=1e-5,numerical_scale=4.)
    def test_point_collapse_and_logarithmic_native_attachment(self):
        for h in (.5,1.,1.5):
            result=self.build(fixture(h));a,b=result['surfaces']
            for s in (a,b):
                cp=np.array(s['homogeneous_cp']);self.assertTrue(np.all(cp[:,0]==cp[0,0]));self.assertTrue(np.min(cp[:,:,3])>0)
            for r in (1e-12,1e-6,.03,.4,1.):
                ns,ws=geo(jets(a,0,r));nt,wt=geo(jets(b,0,r))
                self.assertLess(float(mp.norm(ws)),1e-8);self.assertLess(float(mp.norm(wt)),1e-8)
                self.assertLess(float(mp.norm(cross(ns,mp.matrix([1,0,0])))),1e-8);self.assertLess(float(mp.norm(cross(nt,mp.matrix([0,0,1])))),1e-8)
                self.assertLess(compare(jets(a,1,r),jets(b,1,r))['operator'],1e-7)
    def test_rational_weight_is_preserved(self):
        result=self.build(fixture(rational=True));self.assertGreater(np.ptp(np.array(result['surfaces'][1]['homogeneous_cp'])[:,:,3]),.05)
        for r in (1e-8,.1,.7):
            self.assertLess(float(mp.norm(geo(jets(result['surfaces'][0],0,r))[1])),1e-7)
            self.assertLess(compare(jets(result['surfaces'][0],1,r),jets(result['surfaces'][1],1,r))['operator'],1e-7)
    def test_rigid_rotation_scaling_translation(self):
        theta=.73;R=np.array([[np.cos(theta),-np.sin(theta),0],[np.sin(theta),np.cos(theta),0],[0,0,1.]])
        reference=self.build(fixture())
        for scale,translation in ((.01,[0.,0.,0.]),(10.,[123.,-87.,41.])):
            changed=self.build(transformed(fixture(),R,scale,translation))
            for a,b in zip(reference['surfaces'],changed['surfaces']):
                for u,v in ((.2,.1),(.8,.7),(.5,1)):
                    x=np.array(jets(a,u,v)[0],float).ravel();y=np.array(jets(b,u,v)[0],float).ravel();self.assertLess(np.linalg.norm(y-(R@x*scale+translation)),1e-9)
    def test_inconsistent_corner_is_rejected(self):
        b,p,w,n=fixture();p=p.copy();p[0,0,0]=F(1,1000)
        with self.assertRaisesRegex(ValueError,'reconciliation'):self.build((b,p,w,n))
    def test_integration_removes_cells_and_stale_acceptance(self):
        body={'surfaces':[],'guides':[],'network':{'native_v':[.2,.8],'profile_count':5},'valid':True,'experimental_commit_allowed':True,'attachment_proof':{'checked':True}}
        for side in (0,1):
            cp=[[[i,j,0,1] for j in range(3)] for i in range(2)]
            body['surfaces'].append(dict(kind='collar',side=side,piece=0,degree_u=1,degree_v=1,knots_u=[0,0,1,1],knots_v=[0,0,.2,1,1],domain=[[0,1],[0,1]],homogeneous_cp=cp))
        for side in (0,1):
            cp=[[[i,j,0,1] for j in range(2)] for i in range(2)]
            body['surfaces'].append(dict(kind='collar',side=side,piece=1,degree_u=1,degree_v=1,knots_u=[1,1,2,2],knots_v=[0,0,1,1],domain=[[1,2],[0,1]],homogeneous_cp=cp))
        corners=[self.build(fixture()) for _ in range(2)]
        result=uc.integrate_upper_cells(body,corners)
        self.assertEqual(len(result['surfaces']),8);self.assertEqual(len(result['guides']),2)
        self.assertEqual(len(result['network']['repaired_boundary_roles']),8)
        self.assertTrue(all(len(g['coincident_bindings'])==1 for g in result['guides']))
        self.assertEqual(len(result['network']['collapsed_boundary_bindings']),4)
        self.assertTrue(all(g['binding']['schema']=='smartskin.guide-isocurve.v1' for g in result['guides']))
        self.assertFalse(result['valid']);self.assertFalse(result['experimental_commit_allowed']);self.assertNotIn('attachment_proof',result)
        for s in result['surfaces'][:2]:
            self.assertEqual(s['domain'][1],[.2,1]);self.assertEqual(s['knots_v'],[.2,.2,1,1]);self.assertEqual(len(s['homogeneous_cp'][0]),2)
        for s in result['surfaces'][4:]:
            self.assertEqual(s['boundary_roles']['bottom']['physical_dimension'],0)
            self.assertEqual(set(s['boundary_roles']),{'left','right','bottom','top'})
        self.assertTrue(body['valid']);self.assertEqual(body['surfaces'][0]['domain'][1],[0,1])

    def test_cancellation_is_observed(self):
        with self.assertRaises(fj.FanGuardError):uc.build_upper_corner(*fixture(),cancelled=lambda:True)

if __name__=='__main__':unittest.main()
