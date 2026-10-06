"""Redistributable synthetic lower repair/coverage tests; no native fixture data."""
import sys,unittest,copy
from fractions import Fraction as F
from types import SimpleNamespace
import numpy as np
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'/'SmartSkin.Rhino8'/'Python'))
import fan_rational_fields as fr
import lower_corner_geometry as lc


def plane_record(u0,u1,breaks=(0.,.9,.95,1.)):
    spans=[]
    for a,b in zip(breaks[:-1],breaks[1:]):
        cp=np.zeros((6,6,4));cp[:,:,3]=1
        for i in range(6):
            for j in range(6):cp[i,j,:3]=[u0+(u1-u0)*i/5,a+(b-a)*j/5,0.]
        spans.append(cp)
    cp=np.concatenate([spans[0]]+[x[:,1:] for x in spans[1:]],axis=1)
    return dict(kind='collar',side=0,piece=0,degree_u=5,degree_v=5,domain=[[u0,u1],[breaks[0],breaks[-1]]],knots_u=[u0]*6+[u1]*6,knots_v=[breaks[0]]*6+sum(([x]*5 for x in breaks[1:-1]),[])+[breaks[-1]]*6,homogeneous_cp=cp.tolist())

class LowerGeometry(unittest.TestCase):
    def test_source_bridge_exact_original_polynomial(self):
        old=plane_record(0,.2);native=plane_record(0,1,(0.,1.));original=copy.deepcopy(old)
        cp,bridge,report=lc.build_source_bridge(old,native,.9)
        self.assertTrue(report['original_source_whole_span_coefficient_identity']);self.assertEqual(old,original)
        self.assertLess(report['stored_source_uniform_position_bound'],1e-14)
        self.assertEqual(bridge['domain'],[[0,.2],[.9,1.]])
    def test_multiple_native_spans_fail_closed(self):
        with self.assertRaises(ValueError):lc.build_source_bridge(plane_record(0,.2),plane_record(0,1,(0.,.5,1.)),.9)
    def test_bound_guides_full_noncollapsed_edges(self):
        rec=plane_record(0,.2);before=copy.deepcopy(rec)
        for edge in ('left','right','bottom','top'):
            guide=lc._edge_guide(rec,4,edge,'test:'+edge)
            self.assertEqual(guide['binding']['surface_index'],4)
            self.assertEqual(len(guide['knots']),len(guide['homogeneous_cp'])+guide['degree']+1)
            self.assertGreater(np.linalg.norm(np.asarray(guide['homogeneous_cp'])[-1,:3]-np.asarray(guide['homogeneous_cp'])[0,:3]),0.)
        self.assertEqual(rec,before)
    def test_production_requires_owner_evidence(self):
        with self.assertRaises(Exception):lc.repair_lower(SimpleNamespace(spec={}),{},1.)
    def test_deduplicated_metadata_covers_every_repaired_edge(self):
        from scipy.interpolate import CubicSpline
        records=[];neighbors={};corners=[]
        for side in (0,1):
            for piece,(a,b) in enumerate(((0.,.2),(.2,1.))):
                rec=plane_record(a,b);rec.update(side=side,piece=piece);records.append(rec)
                if piece==1:
                    retained,bridge=lc.split_existing_v(rec,.9);neighbors[side]=dict(retained=retained,lower_bridge=bridge)
            charts=[]
            for name in ('O-P-M-F','F-M-Q-N','O-F-N-R'):
                rec=plane_record(0.,1.,(0.,1.));rec.update(side=side,piece=name);charts.append(rec)
            corners.append(dict(surfaces=charts,original_u_interval=[0.,.2],original_v_interval=[.9,1.],lower_source_key='synthetic',lower_uv_endpoints=[[0.,0.],[0.,1.]],layout=dict(reference_fraction=[.65,.5])))
        for piece in range(4):
            rec=plane_record(0.,1.);rec.update(kind='middle',side=None,piece=piece);records.append(rec)
        rows=[.12,.2,.3,.4,.5,.6,.7,.9,.95]
        original=dict(surfaces=records,guides=[],network=dict(native_v=rows,profile_parameters=rows,row_count=9))
        before=copy.deepcopy(original);model=SimpleNamespace(v1=1.,tmap=CubicSpline([0.,1.],[0.,1.],bc_type='natural'))
        out=lc.integrate_lower_corners(model,original,corners,neighbors,.9)
        self.assertEqual(original,before);self.assertEqual(len(out['guides']),75);self.assertEqual(len(out['network']['repaired_boundary_roles']),20)
        shared=[g for g in out['guides'] if g['kind']=='lower_corner_internal']
        self.assertEqual(len(shared),6);self.assertTrue(all(len(g['coincident_bindings'])==1 for g in shared));self.assertEqual(len(out['network']['profile_parameters']),8)
        self.assertFalse(out['valid']);self.assertFalse(out['full_boundary_pass'])
        coverage={}
        for x in out['network']['repaired_boundary_roles']:
            self.assertEqual(out['surfaces'][x['surface_index']]['boundary_roles'][x['edge']]['role'],x['role']);coverage.setdefault(x['surface_index'],set()).add(x['edge'])
        for g in shared:
            for b in [g['binding']]+g['coincident_bindings']:
                axis=b['varying_axis'];end=b['constant_parameter'];edge=('left' if end==0 else 'right') if axis=='v' else ('bottom' if end==0 else 'top');coverage.setdefault(b['surface_index'],set()).add(edge)
        self.assertEqual(len(coverage),8);self.assertTrue(all(edges=={'left','right','bottom','top'} for edges in coverage.values()))

    def test_bridge_cancelled_before_exact_work(self):
        with self.assertRaises(Exception):lc.build_source_bridge(plane_record(0,.2),plane_record(0,1,(0.,1.)),.9,cancelled=lambda:True)
    def test_source_bridge_rejects_nonunit_weights(self):
        old=plane_record(0,.2);old['homogeneous_cp'][0][0][3]=2.
        with self.assertRaises(ValueError):lc.build_source_bridge(old,plane_record(0,1,(0.,1.)),.9)

if __name__=='__main__':unittest.main()
