"""A small fold must be caught by the Jacobian guard, not merely the envelope."""
import unittest
import numpy as np
from test_stability import plane, boundaries_of, flat_values, independent
from mixed_kernel import Patch, add, measure
from shape_guard import ShapePolicy


class SmallSpanFoldTests(unittest.TestCase):
    def test_small_in_envelope_fold_is_not_hidden_by_position_or_step_limits(self):
        base=plane([0]*4+[.006,.019,.045,.2,.4,.6,.8,.95,.99]+[1]*4)
        sides=boundaries_of(flat_values)
        net=[list(row) for row in base.net]
        net[1][1]=add(net[1][1],(-.005,0.,0.))
        bad=Patch(net,3,base.K)
        old=measure(bad,sides)
        self.assertTrue(old['position_sampled_ok'])
        self.assertTrue(old['regularity_sampled_ok'])
        self.assertEqual(bad.boundary_snapshot(),base.boundary_snapshot())
        policy=ShapePolicy(base,sides,.01)
        self.assertLess(.005,policy.step_limit)
        result=policy.inspect(bad,base)
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'],'NONPOSITIVE_PROJECTED_JACOBIAN_SAMPLE')
        self.assertGreater(result['subdivision_nodes'],0)
        # Independent SciPy derivatives verify an actual negative value while
        # every point remains close to the original flat unit-square envelope.
        determinants=[]
        for u in np.linspace(0,.006,17):
            for v in np.linspace(0,.006,17):
                a=independent(bad,u,v,1,0);b=independent(bad,u,v,0,1)
                determinants.append(np.cross(a,b)[2])
        self.assertLess(min(determinants),0.)


if __name__=='__main__':unittest.main(verbosity=2)
