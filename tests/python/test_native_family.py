"""Synthetic, redistributable family and exact-root regression tests."""
import copy
import hashlib
import json
import pathlib
import sys
import unittest
import numpy as np
from scipy.interpolate import BPoly

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'src/SmartSkin.Rhino8/Python'))
from native_family import build_spec, ordered_cycle, _all_roots, UnsupportedFamily


def curve(points,weights=None):
    p=np.array(points,float);n=len(p);w=np.ones(n) if weights is None else np.array(weights,float)
    return dict(degree=n-1,knots=[0.]*n+[1.]*n,homogeneous_cp=np.column_stack([p*w[:,None],w]).tolist(),domain=[0.,1.])


def surface(points):
    p=np.asarray(points,float);nu,nv=p.shape[:2]
    return dict(degree_u=nu-1,degree_v=nv-1,knots_u=[0.]*nu+[1.]*nu,knots_v=[0.]*nv+[1.]*nv,homogeneous_cp=np.concatenate([p,np.ones(p.shape[:2]+(1,))],axis=2).tolist())


def synthetic_edges():
    # A rational curved upper end, polynomial mirrored sides, ruled lower end.
    topplane=dict(origin=[0,0,0],normal=[1,0,0])
    upper=surface([[[0,-8,-8],[0,8,-8]],[[0,-8,8],[0,8,8]]])
    side=np.array([[0,-5,-1],[0,-5,-1.5],[1,-4.7,-2.5],[2,-4.5,-3.]])
    left=surface([side,side+np.array([0,-3,0])])
    right=copy.deepcopy(left)
    for row in right['homogeneous_cp']:
        for p in row:p[1]*=-1
    bottom=surface([[[2,-8,-3],[2,8,-3]],[[2.5,-8,-3],[2.5,8,-3]],[[3,-8,-2.9],[3,8,-2.9]]])
    roundleft=curve([[0,-5,-1],[0,-5,-.3],[0,-4.5,0],[0,-4,0]],[1,.9,.9,1])
    roundright=copy.deepcopy(roundleft)
    for p in roundright['homogeneous_cp']:p[1]*=-1
    return [dict(key='top-left',curve=roundleft,surface=upper,plane=topplane),
            dict(key='top-line',curve=curve([[0,-4,0],[0,4,0]]),surface=upper,plane=topplane),
            dict(key='top-right',curve=roundright,surface=upper,plane=topplane),
            dict(key='side-left',curve=curve(side),surface=left,plane=None),
            dict(key='side-right',curve=curve(side*np.array([1,-1,1])),surface=right,plane=None),
            dict(key='bottom',curve=curve([[2,-4.5,-3],[2,4.5,-3]]),surface=bottom,plane=None)]


def transform(edges,rotation,translation,scale=1):
    out=[copy.deepcopy(e) for e in edges]
    for e in out:
        for r in [e['curve'],e['surface']]:
            cp=np.asarray(r['homogeneous_cp']);xyz=cp[...,:3]/cp[...,3,None]
            cp[...,:3]=(scale*np.einsum('ij,...j->...i',rotation,xyz)+translation)*cp[...,3,None]
            r['homogeneous_cp']=cp.tolist()
        if e['plane']:
            e['plane']['origin']=(scale*rotation@np.array(e['plane']['origin'])+translation).tolist()
            e['plane']['normal']=(rotation@np.array(e['plane']['normal'])).tolist()
    return out


class NativeFamilyTests(unittest.TestCase):
    def test_generic_selection_builds_without_private_data(self):
        edges=synthetic_edges();before=json.dumps(edges,sort_keys=True)
        spec=build_spec(edges,1e-5)
        self.assertEqual(len(spec['profiles']),5)
        self.assertTrue(spec['extraction_report']['exact_rational_upper'])
        self.assertEqual(before,json.dumps(edges,sort_keys=True))
        self.assertTrue(any(any(abs(p[3]-1)>1e-3 for p in segment['curve']['homogeneous_cp']) for segment in spec['upper_paths'][0]))

    def test_reordered_selection_same_output(self):
        a=build_spec(synthetic_edges(),1e-5)
        b=build_spec(list(reversed(synthetic_edges())),1e-5)
        self.assertEqual(a,b)

    def test_rigid_transform_and_scale(self):
        theta=.63;R=np.array([[np.cos(theta),-np.sin(theta),0],[np.sin(theta),np.cos(theta),0],[0,0,1.]])
        a=build_spec(synthetic_edges(),1e-5)
        b=build_spec(transform(synthetic_edges(),R,np.array([17.,-9.,4.]),2.3),2.3e-5)
        for pa,pb in zip(a['profiles'],b['profiles']):
            np.testing.assert_allclose(pb['p0'],2.3*R@pa['p0']+np.array([17.,-9.,4.]),atol=1e-7)
            np.testing.assert_allclose(pb['p1'],2.3*R@pa['p1']+np.array([17.,-9.,4.]),atol=1e-7)
            np.testing.assert_allclose(pb['t1'],R@pa['t1'],atol=1e-7)

    def test_reverse_every_curve(self):
        edges=synthetic_edges()
        for e in edges:
            c=e['curve'];c['homogeneous_cp']=c['homogeneous_cp'][::-1];c['knots']=[1-k for k in c['knots'][::-1]]
        spec=build_spec(edges,1e-5)
        self.assertEqual(len(spec['profiles']),5)

    def test_asymmetric_upper_rejected(self):
        edges=synthetic_edges();edges[2]['curve']['homogeneous_cp'][1][2]+=.2
        with self.assertRaises(UnsupportedFamily):build_spec(edges,1e-5)

    def test_rational_side_rejected(self):
        edges=synthetic_edges();edges[3]['surface']['homogeneous_cp'][1][1][3]=.9
        with self.assertRaises(UnsupportedFamily):build_spec(edges,1e-5)

    def test_three_roots_not_false_unique(self):
        # Exact cubic with two roots inside one old 1/32 sampling cell.
        polynomial=np.polynomial.Polynomial.fromroots([.30,.31,.70])
        power=np.column_stack([polynomial.coef,[0,1,0,0],np.zeros(4)])
        # Power-to-Bernstein coefficients.
        from math import comb
        cp=np.array([sum((power[k]*comb(i,k)/comb(3,k) for k in range(i+1)),np.zeros(3)) for i in range(4)])
        edge=dict(key='roots',curve=curve(cp))
        with self.assertRaises(UnsupportedFamily):_all_roots([(edge,False)],np.zeros(3),np.array([1,0,0]),0.,1e-7,None)

    def test_flat_section_overlap_rejected(self):
        edge=dict(key='flat',curve=curve([[0,0,0],[0,1,0]]))
        with self.assertRaises(UnsupportedFamily):_all_roots([(edge,False)],np.zeros(3),np.array([1,0,0]),0.,1e-7,None)

    def test_duplicate_and_disconnected_edges_rejected(self):
        edges=synthetic_edges()
        with self.assertRaises(UnsupportedFamily):ordered_cycle(edges+[edges[0]],1e-5)
        edges[-1]['curve']['homogeneous_cp'][0][0]+=2
        with self.assertRaises(UnsupportedFamily):ordered_cycle(edges,1e-5)

    def test_cancellation_and_nonfinite_rejected(self):
        with self.assertRaises(UnsupportedFamily):build_spec(synthetic_edges(),1e-5,cancelled=lambda:True)
        with self.assertRaises(UnsupportedFamily):build_spec(synthetic_edges(),float('nan'))

if __name__=='__main__':unittest.main()
