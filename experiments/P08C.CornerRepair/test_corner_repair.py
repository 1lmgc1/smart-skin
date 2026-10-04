"""Synthetic numerical/I/O tests. Not execution of Rhino UI or RhinoCommon Join."""
import ast,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
import numpy as np
from scipy.interpolate import BSpline
from corner_repair import *


def fixture():
    ku=np.r_[np.zeros(6),np.repeat(.2,3),np.repeat(.5,5),np.repeat(.8,3),np.ones(6)]
    kv=np.r_[np.zeros(6),np.repeat(.1,3),np.repeat(.8,3),np.ones(6)]
    gu=np.array([ku[i+1:i+6].mean() for i in range(len(ku)-6)])
    gv=np.array([kv[i+1:i+6].mean() for i in range(len(kv)-6)])
    Bu=BSpline(ku,np.eye(len(gu)),5)(gu);Bv=BSpline(kv,np.eye(len(gv)),5)(gv)
    xyz=np.array([[(v*v-.004*v,10*(u-.5),.5*v+.05*(u-.5)**2*v*v) for v in gv] for u in gu])
    c=np.linalg.solve(Bu,xyz.reshape(len(gu),-1)).reshape(xyz.shape)
    net=np.linalg.solve(Bv,c.transpose(1,0,2).reshape(len(gv),-1)).reshape(len(gv),len(gu),3).transpose(1,0,2)
    return Tensor(net,ku,kv,5,5)

class CornerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=fixture();cls.snapshot=cls.base.net.copy()
        cls.new,cls.info=corner_strip(cls.base,(.2,.8),(.1,.8),(1,0,0),.0025,True)
    def test_explicit_relief_policy_required(self):
        with self.assertRaisesRegex(ValueError,'EXPLICIT_POLICY'):corner_strip(self.base,(.2,.8),(.1,.8),(1,0,0),.0025)
    def test_no_source_mutation(self):np.testing.assert_array_equal(self.base.net,self.snapshot)
    def test_actual_axial_backtrack_is_removed(self):
        for side in (0,1):
            self.assertLess(curve_axis_minimum(self.base,side,np.array([1,0,0]),.1),0)
            self.assertGreater(curve_axis_minimum(self.new,side,np.array([1,0,0]),.1),0)
    def test_boundary_position_coefficient_bound(self):
        self.assertLess(max(self.info['boundary_coefficient_position_bounds']),.0025)
        for u in (0.,1.):
            gap=np.linalg.norm(self.new.grid([u],np.linspace(0,1,2001))-self.base.grid([u],np.linspace(0,1,2001)),axis=-1).max()
            self.assertLessEqual(gap,max(self.info['boundary_coefficient_position_bounds'])+1e-12)
    def test_tight_boundary_budget_rejects(self):
        with self.assertRaisesRegex(ValueError,'RELIEF_EXCEEDS_BUDGET'):corner_strip(self.base,(.2,.8),(.1,.8),(1,0,0),1e-10,True)
    def test_both_compound_sides_and_junctions_exact(self):
        for v in (0.,1.):np.testing.assert_allclose(self.new.grid(np.linspace(0,1,257),[v]),self.base.grid(np.linspace(0,1,257),[v]),atol=1e-12)
    def test_whole_core_and_active_two_jets_retained(self):
        np.testing.assert_allclose(self.new.grid(np.linspace(.2,.8,17),np.linspace(0,1,31)),self.base.grid(np.linspace(.2,.8,17),np.linspace(0,1,31)),atol=1e-11)
        for order in (0,1,2):
            np.testing.assert_allclose(self.new.grid([0,1],np.linspace(.1,.8,51),order,0),self.base.grid([0,1],np.linspace(.1,.8,51),order,0),atol=1e-9)
    def test_relief_is_not_reported_exact(self):
        self.assertEqual(self.info['mode'],'CAP_EDGE_RELIEF');self.assertFalse(self.info['geometry_commit']);self.assertFalse(self.info['sources_edited'])
    def test_bad_inputs_rejected(self):
        for axis,budget in [((0,0,0),.001),((1,np.nan,0),.001),((1,0,0),0),((1,0,0),np.nan)]:
            with self.assertRaises(ValueError):corner_strip(self.base,(.2,.8),(.1,.8),axis,budget,True)
    def test_zone_needs_existing_quintic_support(self):
        with self.assertRaises(ValueError):local_jet_basis(self.base,1,.3,1)
    def test_corner_control_step_is_bounded(self):
        with self.assertRaisesRegex(ValueError,'STEP_EXCEEDS'):corner_strip(self.base,(.2,.8),(.1,.8),(1,0,0),.0025,True,max_control_step=1e-8)
    def test_report_does_not_claim_native_join(self):self.assertIn('NATIVE_VALIDATION',self.info['status'])
    def test_native_roundtrip(self):
        import rhino3dm as rg
        t=self.new;s=rg.NurbsSurface.Create(3,False,6,6,t.nu,t.nv)
        for i,x in enumerate(t.ku[1:-1]):s.KnotsU[i]=float(x)
        for j,x in enumerate(t.kv[1:-1]):s.KnotsV[j]=float(x)
        for i in range(t.nu):
            for j in range(t.nv):s.Points[i,j]=rg.Point4d(*t.net[i,j],1.)
        cap=rg.Brep.CreateFromSurface(s);self.assertTrue(cap.IsValid)
        with tempfile.TemporaryDirectory() as tmp:
            f=rg.File3dm();f.Objects.AddBrep(cap,rg.ObjectAttributes());path=str(Path(tmp)/'synthetic.3dm');self.assertTrue(f.Write(path,8))
            saved=rg.File3dm.Read(path);self.assertTrue(saved.Objects[0].Geometry.IsValid)

class ShapeGradientTests(unittest.TestCase):
    def test_analytic_gradient_all_five_derivatives(self):
        rng=np.random.default_rng(24);args=[rng.normal(size=(3,3)) for _ in range(5)];v,g=squared_shape_gradient(*args)
        for k in range(5):
            for c in range(3):
                a=[x.copy() for x in args];b=[x.copy() for x in args];a[k][1,c]+=1e-6;b[k][1,c]-=1e-6
                fd=(squared_shape_gradient(*a)[0][1]-squared_shape_gradient(*b)[0][1])/2e-6
                self.assertAlmostEqual(fd,g[k][1,c],delta=3e-5*max(1,abs(fd)))
    def test_plane_has_zero_shape_energy(self):
        a=np.array([[1.,0,0]]);b=np.array([[0.,1,0]]);z=np.zeros((1,3));v,_=squared_shape_gradient(a,b,z,z,z);self.assertEqual(v[0],0)
    def test_oblique_mixed_curvature_is_not_hidden(self):
        a=np.array([[1.,0,0]]);b=np.array([[0.,1,0]]);z=np.zeros((1,3));v,_=squared_shape_gradient(a,b,z,np.array([[0.,0,3.]]),z);self.assertAlmostEqual(v[0],18)
    def test_degenerate_and_nan_rejected(self):
        z=np.zeros((1,3));a=np.array([[1.,0,0]])
        with self.assertRaises(ValueError):squared_shape_gradient(a,a,z,z,z)
        with self.assertRaises(ValueError):squared_shape_gradient(a,np.array([[0,np.nan,0]]),z,z,z)
    def test_uniform_geometry_scaling(self):
        a=np.array([[1.,0,0]]);b=np.array([[0.,1,0]]);c=np.array([[0.,0,2]]);d=np.array([[0.,0,1]]);f=np.array([[0.,0,3]])
        v,_=squared_shape_gradient(a,b,c,d,f);w,_=squared_shape_gradient(3*a,3*b,3*c,3*d,3*f);np.testing.assert_allclose(w,v/9)
    def test_optimal_mixed_normal_reduces_fixed_corner_shape(self):
        jet=[np.zeros(3),np.array([1.,0,0]),np.array([.4,.8,0]),np.array([0,0,2.]),np.array([0,0,9.]),np.array([0,0,3.])]
        n,f=minimum_twist(jet);a=[x[None,:] for x in jet[1:]];before=squared_shape_gradient(*a)[0][0];a[3]=n[None,:]*f
        self.assertLess(squared_shape_gradient(*a)[0][0],before)

class SolveTests(unittest.TestCase):
    def test_bounded_real_nonlinear_solve_keeps_locks(self):
        base=fixture();t,_=corner_strip(base,(.2,.8),(.1,.8),(1,0,0),.0025,True)
        new,r=refine_shape(t,(.2,.8),(.1,.8),limits=CornerLimits(max_control_step=.001,iterations=5,evaluations=40))
        self.assertTrue(r['locks']['ok']);self.assertLessEqual(r['final_step'],.001+1e-12);self.assertFalse(r['geometry_commit']);self.assertEqual(r['native_join'],'NOT_RUN')
    def test_cancellation_is_not_acceptance(self):
        def stop():raise RuntimeError('USER_CANCEL')
        with self.assertRaisesRegex(RuntimeError,'USER_CANCEL'):refine_shape(fixture(),(.2,.8),(.1,.8),checkpoint=stop)
    def test_limits_reject_invalid_budgets(self):
        for n in (0,701,1.5):
            with self.assertRaises(ValueError):CornerLimits(iterations=n).validate()
        for n in (0,-1,float('nan')):
            with self.assertRaises(ValueError):CornerLimits(seconds=n).validate()

HELPER=Path(__file__).with_name('SmartSkin_P08C4_JoinCheck.py')
if not HELPER.exists():HELPER=Path(__file__).parents[2]/'scripts/field/SmartSkin_P08C4_JoinCheck.py'
spec=importlib.util.spec_from_file_location('field',HELPER);field=importlib.util.module_from_spec(spec);spec.loader.exec_module(field)
class FieldHelperTests(unittest.TestCase):
    def test_unicode_report_integrity_and_readback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/'отчёт.txt');console=[];r=field.Report(path,console.append);r.emit('BEGIN',value='данные'*10000);r.emit('SAFETY',added=0);r.finish()
            raw=Path(path).read_bytes();self.assertTrue(raw.startswith(b'\xef\xbb\xbf'));self.assertEqual(raw,b'\xef\xbb\xbf'+b''.join(r.lines));self.assertIsNone(r.failed);self.assertIn('SAVED',console[-1])
    def test_write_failure_is_not_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            console=[];r=field.Report(str(Path(tmp)/'x.txt'),console.append);r.handle.close();r.emit('STOP',error='test');r.finish();self.assertIsNotNone(r.failed);self.assertIn('REPORT_STOP',console[-1])
    def test_bom_failure_closes_handle(self):
        handle=Mock();handle.write.side_effect=OSError('disk error')
        with patch('builtins.open',return_value=handle):
            with self.assertRaises(OSError):field.Report('x.txt',lambda x:None)
        handle.close.assert_called_once()
    def test_no_document_mutations(self):
        text=HELPER.read_text()
        for forbidden in ('Objects.Add','Objects.Delete','Objects.Replace','RunScript(', 'SetTolerances','JoinEdge'):
            self.assertNotIn(forbidden,text)
        self.assertIn('Brep.JoinBreps',text);self.assertIn('BrepBrep',text)
    def test_single_save_dialog_and_no_retry_loop(self):
        tree=ast.parse(HELPER.read_text());self.assertFalse(any(isinstance(n,ast.While) for n in ast.walk(tree)))
        self.assertEqual(HELPER.read_text().count('rs.SaveFileName('),1)
    def test_native_measurement_failure_is_not_zero(self):
        r=Mock();r.Geometry.Curve.GetDistancesBetweenCurves.return_value=(False,0.)
        with self.assertRaises(ValueError):field.native_gap(r,None,None,.01)
    def test_legacy_python_grammar(self):
        try:from lib2to3.refactor import RefactoringTool
        except ImportError:self.skipTest('Python3.11 CI requires this checker')
        RefactoringTool([]).refactor_string(HELPER.read_text(),str(HELPER))

if __name__=='__main__':unittest.main(verbosity=2)
