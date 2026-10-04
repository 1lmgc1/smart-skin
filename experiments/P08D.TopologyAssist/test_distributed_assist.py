import pathlib,sys,unittest
import numpy as np
HERE=pathlib.Path(__file__).parent
sys.path.insert(0,str(HERE))
from topology_generalization import *
from distributed_assist import *

def make_cycle(roles):
    n=len(roles)
    return BoundaryCycle([BoundarySegment('e%d'%i,'v%d'%i,'v%d'%((i+1)%n),'p%d'%(i%5),r) for i,r in enumerate(roles)])

class FieldPlanTests(unittest.TestCase):
    def test_same_contract_six_and_eight(self):
        a=infer_two_support_strip_route(make_cycle(['FEATURE','FEATURE','G2','FEATURE','FEATURE','G2']))
        b=infer_two_support_strip_route(make_cycle(['FEATURE']*4+['G2']+['FEATURE']*2+['G2']))
        s=SemanticAssist()
        A=common_case_contract(a,s);B=common_case_contract(b,s)
        self.assertEqual(A['solver_family'],B['solver_family'])
        self.assertFalse(A['case_specific_solver_branch']);self.assertFalse(B['case_specific_solver_branch'])
        self.assertEqual(A['source_segments'],6);self.assertEqual(B['source_segments'],8)

    def test_assist_changes_field_not_endpoint_identity(self):
        p=semantic_field_plan(SemanticAssist(corner_freedom=.8,fairness_strength=.3,seam_bias=.2),.25)
        L=np.asarray(p.left)
        self.assertTrue(np.allclose(L[0],IDENTITY));self.assertTrue(np.allclose(L[-1],IDENTITY))
        self.assertGreater(np.linalg.norm(L[2]-IDENTITY),.01)

    def test_symmetric_field_is_mirrored(self):
        p=semantic_field_plan(SemanticAssist(),.2)
        L=np.asarray(p.left);R=np.asarray(p.right)
        self.assertTrue(np.allclose(R,L*np.array([1,-1,-1,1])))

    def test_independent_right_supported(self):
        p=semantic_field_plan(SemanticAssist(symmetry_coupling=0),.2,-.1)
        self.assertFalse(p.linked)
        self.assertFalse(np.allclose(np.asarray(p.right),np.asarray(p.left)*np.array([1,-1,-1,1])))

    def test_retraction_returns_identity(self):
        p=semantic_field_plan(SemanticAssist(corner_freedom=.9,seam_bias=.3),.3)
        q=retract_plan(p,0)
        self.assertTrue(np.allclose(q.left,np.tile(IDENTITY,(5,1))))
        self.assertTrue(np.allclose(q.right,np.tile(IDENTITY,(5,1))))

    def test_retraction_is_parameter_not_net_blend(self):
        src=pathlib.Path(__file__).with_name('distributed_assist.py').read_text(encoding='utf8')
        self.assertNotIn('trial.control',src)
        self.assertIn("IDENTITY+alpha*(np.asarray(plan.left)-IDENTITY)",src)

    def test_variable_field_preserves_geometric_attachment(self):
        n=101;v=np.linspace(0,1,n);rng=np.random.default_rng(12)
        A=np.tile([1.1,.12,.1],(n,1));T=np.tile([.15,1.2,-.2],(n,1))
        B=rng.normal(scale=.15,size=(n,3));M=rng.normal(scale=.15,size=(n,3));F=rng.normal(scale=.15,size=(n,3))
        p=semantic_field_plan(SemanticAssist(corner_freedom=.8,fairness_strength=.4,seam_bias=.15),.25)
        L,_=charts_from_plan(p);e=attachment_evidence((A,T,B,M,F),v,L)
        self.assertTrue(e['finite']);self.assertLess(e['normal_deg'],1e-9);self.assertLess(e['shape_relative'],1e-10)

    def test_transition_overlap_rejected(self):
        with self.assertRaises(ValueError):
            semantic_field_plan(SemanticAssist(transition_length_start=.48,transition_length_end=.48))

if __name__=='__main__':unittest.main()
