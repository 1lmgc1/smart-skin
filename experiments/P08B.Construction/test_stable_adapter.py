"""P08B.3 source/IO tests; native Rhino calls and UI are NOT executed."""
import ast
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import rhino_prototype as old
import rhino_stable_adapter as new
from test_stability import plane, boundaries_of, flat_values, bump
from stable_refinement import *

ROOT=Path(__file__).parent

class StableAdapterTests(unittest.TestCase):
    def test_native_position_Join_conversion_and_cleanup_exactly_preserved(self):
        def methods(path):
            s=path.read_text(); cls=next(n for n in ast.parse(s).body if isinstance(n,ast.ClassDef) and n.name=='Experiment')
            return {n.name:ast.get_source_segment(s,n) for n in cls.body if isinstance(n,ast.FunctionDef)}
        a=methods(ROOT/'rhino_prototype.py');b=methods(ROOT/'rhino_stable_adapter.py')
        for name in ('make_brep','gap','native_evidence','close','capture','select','count'):
            self.assertEqual(a[name],b[name],name)
        self.assertIn("evidence.get('shape',{}).get('ok',False)",b['candidate'])
        self.assertIn('prefer_evidence',b['candidate'])
    def test_actual_Rhino_adapter_calls_new_solver_not_legacy_refine(self):
        s=(ROOT/'rhino_stable_adapter.py').read_text()
        cls=next(n for n in ast.parse(s).body if isinstance(n,ast.ClassDef) and n.name=='Experiment')
        run=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        code=ast.get_source_segment(s,run)
        self.assertIn('stable_solve(',code);self.assertNotIn('current,iterations=refine(',code)
    def test_original_compound_layout_metadata_is_unchanged(self):
        items=[dict(key=str(i),flip=False) for i in range(6)];features={'0','1','3','4'}
        self.assertEqual(new.four_side_layouts(items,features),old.four_side_layouts(items,features))
    def test_no_extra_dependency_or_document_geometry_write(self):
        for name in ('shape_guard.py','stable_refinement.py','rhino_stable_adapter.py'):
            s=(ROOT/name).read_text()
            for bad in ('Objects.Add','Objects.Delete','Objects.Replace','RunScript(','subprocess','import numpy','import scipy'):
                self.assertNotIn(bad,s,(name,bad))
    def test_large_binary_report_flush_and_integrity(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'отчёт.txt';r=new.Report(str(p),lambda x:None)
            for i in range(200):r.emit('DATA',index=i,payload='Форма'*400)
            # Read while still open: all records are present, not one buffered block behind.
            self.assertEqual(len(p.read_bytes().decode('utf-8-sig').splitlines()),200)
            before=r.digest.hexdigest();r.emit('REPORT_INTEGRITY',preceding_records=len(r.lines),preceding_sha256=before,footer=True);r.close()
            data=p.read_bytes();self.assertEqual(data.count(b'\xef\xbb\xbf'),1)
            body,footer=data[3:].rsplit(b'SMARTSKIN_P08B2_REPORT_INTEGRITY',1)
            self.assertEqual(hashlib.sha256(body).hexdigest(),before)
            self.assertIn(before.encode(),footer);self.assertIn(b'preceding_records=200',footer)
    def test_exact_net_snapshot_written_before_display(self):
        s=(ROOT/'rhino_stable_adapter.py').read_text();cls=next(n for n in ast.parse(s).body if isinstance(n,ast.ClassDef) and n.name=='Experiment')
        p=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='preview');text=ast.get_source_segment(s,p)
        self.assertLess(text.index("'NET_END'"),text.index('conduit.Enabled=True'))
        self.assertIn("'PREVIEW_BEGIN'",text)
    def test_python2_grammar_all_new_executable_sources(self):
        try:from lib2to3.refactor import RefactoringTool
        except ImportError:self.skipTest('Mandatory Python 3.11 CI check')
        for name in ('shape_guard.py','stable_refinement.py','rhino_stable_adapter.py'):
            RefactoringTool([]).refactor_string((ROOT/name).read_text(),name)
    def test_large_proposal_gets_real_clipped_backtracking(self):
        p=plane();b=boundaries_of(bump);policy=ShapePolicy(p,b,.01);e=stable_measure(p,b,policy)
        q,_=vector_proposal(p,p,b,policy)
        big=Patch([[add(a,mul(sub(z,a),1e5)) for a,z in zip(row,other)] for row,other in zip(p.net,q.net)],p.p,p.K)
        history=[];r,re,kept=bounded_step(p,big,p,b,policy,e,on_trial=history.append)
        self.assertTrue(history);self.assertLess(history[0]['alpha'],1.)
        self.assertTrue(all(h['actual_control_step']<=h['step_limit']*(1+1e-12) for h in history))
        self.assertEqual(r.boundary_snapshot(),p.boundary_snapshot())
    def test_G1_achievement_on_an_edge_cannot_be_sacrificed_for_other_score(self):
        p=plane();b=boundaries_of(flat_values);e=stable_measure(p,b,ShapePolicy(p,b,.01));other=dict(e)
        other['edges']={k:dict(v) for k,v in e['edges'].items()};other['edges']['left']['achieved']=0
        other['score']=(999,0,0,0)
        self.assertFalse(prefer_evidence(other,e))

if __name__=='__main__':unittest.main(verbosity=2)
