"""Redistributable regression for translated native endpoint-jet fairing."""
import copy
from contextlib import ExitStack
import itertools
import pathlib
import sys
import types
import unittest
from unittest import mock

import numpy as np
from scipy.interpolate import BPoly

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'src'/'SmartSkin.Rhino8'/'Python'))
import native_family as nf
from test_native_family import compound_upper_edges,transform


def transformed_jet_inputs():
    # This is the existing public compound-edge fixture, never user geometry.
    _,joined=compound_upper_edges(True)
    for edge in joined:
        c=edge['curve'];total=c['knots'][0]+c['knots'][-1]
        c['homogeneous_cp']=c['homogeneous_cp'][::-1];c['knots']=[total-k for k in c['knots'][::-1]]
    theta=.51;rotation=np.array([[np.cos(theta),0,np.sin(theta)],[0,1,0],[-np.sin(theta),0,np.cos(theta)]])
    inputs=[]
    def capture(*args):
        inputs.append(copy.deepcopy(args));return np.array([1.,1.,0.,0.])
    with mock.patch.object(nf,'_fair_handles',side_effect=capture):
        nf.build_spec(transform(joined,rotation,np.array([7.,-11.,13.]),2.7),2.7e-5)
    args=list(inputs[0]);args[0][2]+=1e-13;args[1][2]+=1e-13
    return args


class FairingRetryTests(unittest.TestCase):
    def test_actual_public_fixture_tiny_translation_regression(self):
        args=transformed_jet_inputs();handles=nf._fair_handles(*args)
        p0,p1,t0,t1,k0,k1,normal,depth,_=args;length=np.linalg.norm(p1-p0)
        points=nf._quintic(p0,p1,t0,t1,k0,k1,*handles)
        constraints=np.r_[np.diff(points,axis=0)@normal,np.diff(points,axis=0)@depth]/length
        self.assertGreaterEqual(float(np.min(constraints)),-1e-8)
        self.assertTrue(np.all(np.isfinite(handles)))
        self.assertTrue(.05*length<=handles[0]<=3*length and .05*length<=handles[1]<=3*length)

    def test_interval_bound_and_analytic_derivatives(self):
        args=transformed_jet_inputs();length=np.linalg.norm(args[1]-args[0])
        fun,jac,con,cjac,bound=nf._centered_fairing_problem(*args[:-1],length,args[-1])
        omitted=bound>=-1e-8
        self.assertTrue(omitted[9])  # Tiny negative native arrival projection.
        for corner in itertools.product(*[(.05,3.),(.05,3.),(-10.,10.),(-10.,10.)]):
            values=con(np.asarray(corner));self.assertTrue(np.all(values>=bound-1e-13));self.assertTrue(np.all(values[omitted]>=-1e-8))
        rng=np.random.default_rng(57)
        for _ in range(40):
            x=rng.uniform([.05,.05,-10.,-10.],[3.,3.,10.,10.]);self.assertTrue(np.all(con(x)>=bound-1e-13))
        x=np.array([.9,1.1,.2,-.3]);eps=1e-6;steps=np.eye(4)*eps
        numeric=np.array([(fun(x+h)-fun(x-h))/(2*eps) for h in steps])
        np.testing.assert_allclose(jac(x),numeric,rtol=2e-6,atol=1e-6)
        numeric_constraints=np.column_stack([(con(x+h)-con(x-h))/(2*eps) for h in steps])
        np.testing.assert_allclose(cjac(x),numeric_constraints,rtol=2e-6,atol=1e-9)
        points=nf._quintic(*args[:6],*(x*length));nodes,weights=np.polynomial.legendre.leggauss(3)
        jerk=BPoly(points[:,None,:],[0.,1.]).derivative(3)((nodes+1)/2)
        original=np.einsum('i,ij,ij->',weights/2,jerk,jerk)/(length*length)
        self.assertAlmostEqual(fun(x),original,places=10)

    def test_successful_primary_path_never_calls_retry(self):
        p0=np.zeros(3);p1=np.array([1.,0.,1.]);t=p1/np.linalg.norm(p1);x=np.array([1.,1.,0.,0.])
        with mock.patch.object(nf,'minimize',return_value=types.SimpleNamespace(success=True,x=x.copy())) as minimize, \
             mock.patch.object(nf,'_centered_fairing_problem',side_effect=AssertionError('Successful primary output must remain unchanged')):
            result=nf._fair_handles(p0,p1,t,t,np.zeros(3),np.zeros(3),np.array([1.,0.,0.]),np.array([0.,0.,1.]),None)
        np.testing.assert_array_equal(result,x*np.linalg.norm(p1));self.assertEqual(minimize.call_count,3)
        self.assertTrue(all('jac' not in call.kwargs for call in minimize.call_args_list))

    def test_impossible_monotone_arrival_still_rejected(self):
        p0=np.zeros(3);p1=np.array([1.,0.,1.]);t=p1/np.linalg.norm(p1)
        with self.assertRaisesRegex(nf.UnsupportedFamily,'CENTER_GUIDE_FAIRING'):
            nf._fair_handles(p0,p1,t,-t,np.zeros(3),np.zeros(3),np.array([1.,0.,0.]),np.array([0.,0.,1.]),None)

    def test_success_flag_cannot_bypass_original_acceptance(self):
        p0=np.zeros(3);p1=np.array([1.,0.,1.]);t=p1/np.linalg.norm(p1)
        args=(p0,p1,t,t,np.zeros(3),np.zeros(3),np.array([1.,0.,0.]),np.array([0.,0.,1.]),None)
        for kind,x in (('outside_box',[3.01,1.,0.,0.]),('original_feasibility',[3.,3.,10.,10.]),
                       ('nonfinite_x',[np.nan,1.,0.,0.]),('nonfinite_constraints',[1.,1.,0.,0.]),
                       ('nonfinite_objective',[1.,1.,0.,0.])):
            with self.subTest(kind=kind),ExitStack() as stack:
                def fake(fun,start,*a,**kw):
                    return types.SimpleNamespace(success='jac' in kw,x=np.asarray(x,float))
                stack.enter_context(mock.patch.object(nf,'minimize',side_effect=fake))
                if kind=='nonfinite_constraints':stack.enter_context(mock.patch.object(nf,'_quintic',return_value=np.full((6,3),np.nan)))
                if kind=='nonfinite_objective':
                    poly=stack.enter_context(mock.patch.object(nf,'BPoly'))
                    poly.return_value.derivative.return_value.return_value=np.full((3,3),np.inf)
                with self.assertRaisesRegex(nf.UnsupportedFamily,'CENTER_GUIDE_FAIRING'):nf._fair_handles(*args)

    def test_retry_observes_cancellation(self):
        args=transformed_jet_inputs();args[-1]=lambda:True;real=nf.minimize
        def fail_primary(fun,x,*a,**kw):
            if 'jac' not in kw:return types.SimpleNamespace(success=False,x=np.asarray(x,float))
            return real(fun,x,*a,**kw)
        with mock.patch.object(nf,'minimize',side_effect=fail_primary):
            with self.assertRaisesRegex(nf.UnsupportedFamily,'CANCELLED'):nf._fair_handles(*args)

if __name__=='__main__':unittest.main()
