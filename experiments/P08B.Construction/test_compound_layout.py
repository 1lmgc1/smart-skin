"""Compound-side regressions. Native Rhino binding/Join are NOT executed here."""
import ast
import hashlib
from pathlib import Path
import unittest
from mixed_kernel import *
from rhino_prototype import boundary_role_runs,four_side_layouts,flip_items
from compound_fixture import ring_fixture,opposed_boundaries,reference_surface


def traversal(layout):
    return layout['bottom']+layout['right']+flip_items(layout['top'])+flip_items(layout['left'])


def endpoint(e,last=False):
    return e['uv1' if last!=e['flip'] else 'uv0']


class CompoundLayoutTests(unittest.TestCase):
    def assert_layout(self,items,features,layout):
        by_key={e['key']:e for e in items}
        flat=[e for s in SIDES for e in layout[s]]
        self.assertEqual(len(flat),len(items)); self.assertEqual(set(by_key),{e['key'] for e in flat})
        for side in SIDES:
            self.assertTrue(layout[side])
            self.assertEqual(len({e['key'] in features for e in layout[side]}),1)
        for e in flat:
            source=by_key[e['key']]
            self.assertIs(e['edge'],source['edge'])
            self.assertEqual(e['identity'],source['identity']); self.assertEqual(e['interval'],source['interval'])
        walk=traversal(layout)
        for a,b in zip(walk,walk[1:]+walk[:1]): self.assertEqual(endpoint(a,True),endpoint(b))
    def test_two_G0_pairs_become_two_opposed_logical_sides(self):
        items,features=ring_fixture(); layouts=four_side_layouts(items,features)
        self.assertEqual(len(layouts),1)
        self.assertEqual([len(layouts[0][s]) for s in SIDES],[2,1,2,1])
        self.assertEqual({e['key'] for s in ('bottom','top') for e in layouts[0][s]},features)
        self.assert_layout(items,features,layouts[0])
    def test_every_cyclic_start_produces_same_layout(self):
        items,features=ring_fixture(); expected=four_side_layouts(items,features)
        for shift in range(len(items)):
            rotated=items[shift:]+items[:shift]
            self.assertEqual(four_side_layouts(rotated,features),expected)
    def test_both_traversal_directions_preserve_corners_and_roles(self):
        items,features=ring_fixture()
        for ring in (items,flip_items(items)):
            for shift in range(len(ring)):
                rotated=ring[shift:]+ring[:shift]
                self.assert_layout(rotated,features,four_side_layouts(rotated,features)[0])
    def test_no_mutation_of_source_metadata_or_role_set(self):
        items,features=ring_fixture(); before=[dict(e) for e in items]; roles=set(features)
        result=four_side_layouts(items,features)
        self.assertEqual(items,before); self.assertEqual(features,roles)
        result[0]['bottom'][0]['flip']=True
        self.assertEqual(items,before)
    def test_two_separate_single_edge_features_supported_too(self):
        items,unused=ring_fixture(); features={'a1','c1'}
        layout=four_side_layouts(items,features)[0]
        self.assertEqual([len(layout[s]) for s in SIDES],[1,2,1,2])
        self.assert_layout(items,features,layout)
    def test_wraparound_pair_is_one_chain(self):
        items,features=ring_fixture(); rotated=items[1:]+items[:1]
        self.assertEqual([len(r) for r in boundary_role_runs(rotated,features)],[2,1,2,1])
    def test_three_disjoint_G0_chains_are_not_silently_merged(self):
        items,unused=ring_fixture()
        with self.assertRaisesRegex(ValueError,'LAYOUT_UNSUPPORTED_ROLE_RUNS'):
            four_side_layouts(items,{'a0','b','c1'})
    def test_duplicate_source_key_rejected(self):
        items,features=ring_fixture(); items[1]=dict(items[1],key=items[0]['key'])
        with self.assertRaisesRegex(ValueError,'DUPLICATE_SOURCE_KEY'): four_side_layouts(items,features)
    def test_missing_or_unknown_role_not_inferred(self):
        items,features=ring_fixture()
        for invalid in (set(),{e['key'] for e in items},features|{'missing'}):
            with self.assertRaises(ValueError): four_side_layouts(items,invalid)
    def test_one_chain_route_preserved_with_three_alternatives(self):
        items,unused=ring_fixture(); features={'c0','c1'}
        layouts=four_side_layouts(items,features); self.assertEqual(len(layouts),3)
        for layout in layouts: self.assert_layout(items,features,layout)
    def test_more_than_eight_source_edges_stays_bounded(self):
        items=[dict(key=str(i),flip=False) for i in range(9)]
        with self.assertRaisesRegex(ValueError,'FOUR_TO_EIGHT'): four_side_layouts(items,{'0','1'})
    def test_role_runs_with_unequal_fragment_counts_not_hardcoded(self):
        items=[dict(key=str(i),flip=False) for i in range(8)]
        layout=four_side_layouts(items,{'0','1','2','4','5'})[0]
        self.assertEqual([len(layout[s]) for s in SIDES],[3,1,2,2])
    def test_construct_surface_through_actual_two_chain_layout(self):
        sides=opposed_boundaries(); pool=solve(sides,n=8,steps=4)
        self.assertIsNotNone(pool.best)
        unused,patch,e=pool.best
        self.assertTrue(e['desired_sampled_met'],e)
        self.assertEqual(len(e['edges']),6)
        self.assertEqual(sum(v['preferred']==0 for v in e['edges'].values()),4)
        self.assertEqual(sum(v['preferred']==2 for v in e['edges'].values()),2)
        self.assertTrue(all(v['achieved']==2 for v in e['edges'].values() if v['preferred']==2))
        # An independent dense grid on the TWO CURVED boundaries, outside training sites.
        max_gap=0.; max_normal=0.; max_curvature=0.
        for side in ('left','right'):
            for k in range(129):
                t=(k+.314159)/129;u,v=side_uv(side,t)
                actual=patch.eval(u,v); target=reference_surface(u,v)
                max_gap=max(max_gap,norm(sub(actual[0],target[0])))
                n,H=frame(actual); m,J=frame(target); d=dot(n,m)
                max_normal=max(max_normal,math.degrees(math.acos(min(1,abs(d)))))
                max_curvature=max(max_curvature,tensor_error(H,J,d))
        self.assertLess(max_gap,.01); self.assertLess(max_normal,1); self.assertLess(max_curvature,5)
    def test_boundary_frozen_on_each_refinement_with_two_G0_chains(self):
        sides=opposed_boundaries(); p=construct_coons(sides,n=8)
        frozen={(i,j):p.net[i][j] for i in range(p.n) for j in range(p.n) if i in (0,p.n-1) or j in (0,p.n-1)}
        for index in range(4):
            p,unused=refine(p,sides,curvature=index>0)
            self.assertTrue(all(p.net[i][j]==point for (i,j),point in frozen.items()))
    def test_constructive_result_also_after_reversed_traversal(self):
        items,unused=ring_fixture(); sides=opposed_boundaries(flip_items(items));pool=solve(sides,n=8,steps=4)
        self.assertIsNotNone(pool.best);self.assertTrue(pool.best[2]['desired_sampled_met'],pool.best[2])
    def test_kernel_exactly_preserved(self):
        data=Path(__file__).with_name('mixed_kernel.py').read_bytes()
        digest=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        self.assertEqual(digest,'5aa42ba1500badfd96fdb4a8675bd214f57b33dd')
    def test_numeric_refinement_and_native_evidence_not_replaced_by_layout(self):
        text=Path(__file__).with_name('rhino_prototype.py').read_text()
        tree=ast.parse(text);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Experiment')
        names=('make_brep','gap','native_evidence','candidate','close')
        methods=[ast.get_source_segment(text,n) for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names]
        digest=hashlib.sha256('\n\n'.join(methods).encode()).hexdigest()
        self.assertEqual(digest,'f38db43871a39649271c1a6e47f2170100769dc70bb4afa6804ae88166fbfe5d')

if __name__=='__main__': unittest.main(verbosity=2)
