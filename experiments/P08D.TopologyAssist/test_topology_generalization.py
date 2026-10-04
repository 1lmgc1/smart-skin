import unittest, pathlib
import numpy as np
from topology_generalization import *

def cycle(roles):
    n=len(roles)
    return BoundaryCycle([BoundarySegment('e%d'%i,'v%d'%i,'v%d'%((i+1)%n),'p%d'%(i%4),r) for i,r in enumerate(roles)])

class TopologyTests(unittest.TestCase):
    def test_case_a_six_segments(self):
        r=infer_two_support_strip_route(cycle(['FEATURE','FEATURE','G2','FEATURE','FEATURE','G2']))
        self.assertEqual(r.segment_count,6)
        self.assertEqual(sorted(len(r.chains[i].segments) for i in r.feature_indices),[2,2])
        self.assertEqual(sorted(len(r.chains[i].segments) for i in r.support_indices),[1,1])
        self.assertEqual(len(route_summary(r)['source_coverage']),6)

    def test_case_b_eight_segments_not_forced_to_2211(self):
        r=infer_two_support_strip_route(cycle(['FEATURE','FEATURE','G2','FEATURE','FEATURE','FEATURE','FEATURE','G2']))
        self.assertEqual(r.segment_count,8)
        self.assertEqual(sorted(len(r.chains[i].segments) for i in r.feature_indices),[2,4])
        self.assertEqual(sorted(len(r.chains[i].segments) for i in r.support_indices),[1,1])

    def test_rotation_and_reverse_keep_counts(self):
        c=cycle(['FEATURE','FEATURE','G2','FEATURE','FEATURE','FEATURE','FEATURE','G2'])
        for k in range(8):
            for q in (c.rotated(k),c.rotated(k).reversed()):
                r=infer_two_support_strip_route(q)
                self.assertEqual(sorted(r.side_edge_counts),[1,1,2,4])
                self.assertEqual(set(route_summary(r)['source_coverage']),set(c.source_keys()))

    def test_not_two_support_topology_is_named_stop(self):
        with self.assertRaisesRegex(ValueError,'NOT_TWO_SUPPORT_STRIP_TOPOLOGY'):
            infer_two_support_strip_route(cycle(['G2','FEATURE','G2','FEATURE','G2','FEATURE']))

    def test_cycle_rejects_gap(self):
        s=[BoundarySegment('a','0','1','p'),BoundarySegment('b','2','3','p'),
           BoundarySegment('c','3','4','p'),BoundarySegment('d','4','0','p')]
        with self.assertRaisesRegex(ValueError,'ORDERED_SINGLE_CYCLE_REQUIRED'):
            BoundaryCycle(s)

class AssistTests(unittest.TestCase):
    def test_defaults_validate(self):
        SemanticAssist().validate()

    def test_axis_normalized(self):
        self.assertTrue(np.allclose(SemanticAssist(preferred_axis=(2,0,0)).normalized_axis(),(1,0,0)))

    def test_product_controls_hide_nurbs_internals(self):
        d=SemanticAssist().semantic_controls()
        for bad in ('degree','degrees','cv','cv_count','knots','multiplicity','iterations','solver_weight'):
            self.assertNotIn(bad,d)

    def test_relief_and_normalized_bounds(self):
        with self.assertRaises(ValueError):SemanticAssist(corner_freedom=1.01).validate()
        with self.assertRaises(ValueError):SemanticAssist(contour_relief_budget_mm=.051).validate()

    def test_continuity_override(self):
        d=SemanticAssist(continuity_overrides={'support-left':'G2'}).semantic_controls()
        self.assertEqual(d['continuity_overrides']['support-left'],'G2')

class DistributedAttachmentTests(unittest.TestCase):
    def setUp(self):
        rng=np.random.default_rng(4);n=41
        A=np.tile([1.1,.1,.2],(n,1));T=np.tile([.2,1.3,-.15],(n,1))
        B=rng.normal(scale=.2,size=(n,3));M=rng.normal(scale=.2,size=(n,3));F=rng.normal(scale=.2,size=(n,3))
        self.jets=(A,T,B,M,F);self.v=np.linspace(0,1,n)

    def test_schedule_hits_anchors_and_zero_anchor_slopes(self):
        s=QuinticSchedule([0,.2,.8,1],[1,.8,1.2,1])
        y,d=s.eval(np.array([0,.2,.8,1.]))
        self.assertTrue(np.allclose(y,[1,.8,1.2,1]))
        self.assertTrue(np.allclose(d,0,atol=1e-12))

    def test_variable_speed_shear_preserves_world_shape(self):
        c=DistributedChart.from_anchors([0,.2,.5,.8,1],
            [[1,0,0,0],[.82,.16,.01,.02],[.9,-.1,-.02,.01],[1.12,.12,.01,-.01],[1,0,0,0]])
        j=transform_distributed_jet(*self.jets,c,self.v)
        N0,K0=world_shape(*self.jets);N1,K1=world_shape(*j)
        self.assertLess(float(np.max(np.linalg.norm(N0-N1,axis=1))),1e-12)
        self.assertLess(float(np.max(np.abs(K0-K1))),1e-11)

    def test_variable_chart_mixed_jet_contains_derivative_terms(self):
        c=DistributedChart.from_anchors([0,.5,1],[[1,0,0,0],[.8,.2,0,0],[1,0,0,0]])
        j=transform_distributed_jet(*self.jets,c,self.v)
        a,b,cc,d,ap,bp=c.eval(self.v)
        plain=a[:,None]*self.jets[3]+b[:,None]*self.jets[4]
        self.assertGreater(float(np.max(np.linalg.norm(j[3]-plain,axis=1))),1e-3)

    def test_constant_chart_reduces_to_old_formula(self):
        q=[.83,.14,.01,.02];c=DistributedChart.from_anchors([0,1],[q,q])
        j=transform_distributed_jet(*self.jets,c,self.v)
        A,T,B,M,F=self.jets;a,b,cc,d=q
        old=(a*A+b*T,T,a*a*B+2*a*b*M+b*b*F+cc*A+d*T,a*M+b*F,F)
        for x,y in zip(j,old):self.assertTrue(np.allclose(x,y,atol=1e-13))

    def test_orientation_must_stay_positive(self):
        with self.assertRaises(ValueError):
            DistributedChart.from_anchors([0,1],[[1,0,0,0],[0,0,0,0]])

class SourceGuardTests(unittest.TestCase):
    def test_no_rhino_or_document_write_api(self):
        src=pathlib.Path(__file__).with_name('topology_generalization.py').read_text(encoding='utf8')
        for bad in ('RhinoDoc','doc.Objects.Add','doc.Objects.Delete','doc.Objects.Replace','JoinBreps'):
            self.assertNotIn(bad,src)

if __name__=='__main__':unittest.main()
