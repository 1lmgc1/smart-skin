"""Adapter source, I/O and topology-helper checks, NOT a Rhino UI/Join run."""
import ast
import codecs
import importlib
from pathlib import Path
import tempfile
import unittest
from mixed_kernel import *
from rhino_prototype import Report, four_side_layouts, flip_items

class AdapterTests(unittest.TestCase):
    def test_one_BOM_full_UTF8_long_report_and_flush(self):
        with tempfile.TemporaryDirectory() as d:
            p=str(Path(d)/'отчёт.txt'); console=[]; r=Report(p,console.append)
            r.emit('EDGE',detail='данные'*20000)
            r.emit('END',state='COMPLETE')
            b=Path(p).read_bytes(); self.assertEqual(b.count(codecs.BOM_UTF8),1)
            self.assertIn(('данные'*20000).encode('utf-8'),b); self.assertTrue(b.endswith(b'\r\n'))
            r.close(); self.assertLess(len(''.join(console)),100)
    def test_four_side_layout_covers_every_original_once(self):
        edges=[{'key':str(i),'flip':False} for i in range(6)]; features={'3','4'}
        layouts=four_side_layouts(edges,features)
        self.assertEqual(len(layouts),3)
        for layout in layouts:
            keys=[x['key'] for s in SIDES for x in layout[s]]
            self.assertEqual(set(keys),set(str(i) for i in range(6)));self.assertEqual(len(keys),6)
            self.assertEqual({x['key'] for x in layout['bottom']},features)
    def test_layout_roles_ignore_pick_order_start(self):
        base=[{'key':str(i),'flip':False} for i in range(6)]; features={'3','4'}
        expected=four_side_layouts(base,features)
        for shift in range(6): self.assertEqual(expected,four_side_layouts(base[shift:]+base[:shift],features))
    def test_fragmented_feature_chain_is_explicitly_unsupported(self):
        with self.assertRaises(ValueError): four_side_layouts([{'key':str(i),'flip':False} for i in range(6)],{'1','4'})
    def test_reversal_does_not_mutate_source_items(self):
        a=[{'key':'a','flip':False},{'key':'b','flip':True}];b=flip_items(a)
        self.assertEqual(a,[{'key':'a','flip':False},{'key':'b','flip':True}]);self.assertEqual(b[0]['key'],'b'); self.assertFalse(b[0]['flip'])
    def test_source_contains_no_document_writes_or_unapproved_runtime(self):
        s=Path(__file__).with_name('rhino_prototype.py').read_text(encoding='utf-8')
        for forbidden in ('Objects.Add','Objects.Replace','Objects.Delete','RunScript(', 'CreatePatch(', 'pip install', 'SetDotNetRuntime','ModelAbsoluteTolerance='):
            self.assertNotIn(forbidden,s)
        self.assertIn('commit_allowed=False',s); self.assertIn('Brep.JoinBreps(extra,self.tol,self.angle)',s)
    def test_kernel_has_no_Rhino_dependency_or_private_model_ids(self):
        s=Path(__file__).with_name('mixed_kernel.py').read_text(encoding='utf-8')
        for word in ('import Rhino','import numpy','import scipy','error_shape'):
            self.assertNotIn(word,s)
    def test_python2_grammar_for_executable_sources(self):
        try:
            from lib2to3.refactor import RefactoringTool
        except ImportError:
            self.skipTest('CI Python3.11 requires grammar check')
        for name in ('mixed_kernel.py','rhino_prototype.py'):
            p=Path(__file__).with_name(name); RefactoringTool([]).refactor_string(p.read_text(encoding='utf-8'),str(p))

if __name__=='__main__':unittest.main(verbosity=2)
