import unittest, numpy as np
from segmented_boundary_basis import *

class SegmentedBasisTests(unittest.TestCase):
    def test_case_a_two_by_two(self):
        a=[SegmentSpec('b0',7),SegmentSpec('b1',7)]
        t=[SegmentSpec('t0',9),SegmentSpec('t1',9)]
        K,P=common_clamped_knots((a,t),3)
        self.assertEqual([round(x['end'],9) for x in P[0]],[.5,1.])
        self.assertEqual([round(x['end'],9) for x in P[1]],[.5,1.])
        self.assertEqual(np.count_nonzero(K==.5),3)

    def test_case_b_two_vs_four_uses_length_not_count(self):
        b=[SegmentSpec('b0',14),SegmentSpec('b1',14)]
        t=[SegmentSpec('t0',1),SegmentSpec('t1',16),SegmentSpec('t2',16),SegmentSpec('t3',1)]
        K,P=common_clamped_knots((b,t),3)
        self.assertEqual(len(P[0]),2);self.assertEqual(len(P[1]),4)
        self.assertAlmostEqual(P[0][0]['end'],.5)
        self.assertNotAlmostEqual(P[1][0]['end'],.25)
        self.assertEqual(coverage_keys(P[1]),('t0','t1','t2','t3'))
        self.assertTrue(any(abs(x-1/34)<1e-12 for x in K))

    def test_internal_source_break_is_retained(self):
        K,P=common_clamped_knots(([SegmentSpec('a',2,(.25,.75))],[SegmentSpec('b',2)]),3)
        self.assertEqual(np.count_nonzero(np.isclose(K,.25)),3)
        self.assertEqual(np.count_nonzero(np.isclose(K,.75)),3)

    def test_locate_preserves_each_interval(self):
        p=chain_partition([SegmentSpec('a',1),SegmentSpec('b',3)])
        self.assertEqual(locate_segment(p,.125),(0,.5))
        i,f=locate_segment(p,.625);self.assertEqual(i,1);self.assertAlmostEqual(f,.5)

    def test_rotation_is_not_part_of_basis_contract(self):
        src=open(__file__.replace('test_segmented_boundary_basis.py','segmented_boundary_basis.py'),encoding='utf8').read()
        self.assertNotIn('2/1/2/1',src)
        self.assertNotIn('opposite_side',src)

if __name__=='__main__':unittest.main()
