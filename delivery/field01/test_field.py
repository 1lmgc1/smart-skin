# Developer tests. Never ship this file as a Rhino user entry point.
import ast, copy, hashlib, json, os, pathlib, tempfile, unittest, uuid
from field_core import PACKAGE, Report, validate_manifest, interval_coverage, safe_child, sha256_file
ROOT=pathlib.Path(__file__).parent

def fixture():
    sources=[dict(object_id=str(uuid.uuid5(uuid.NAMESPACE_DNS,'source'+str(i))),edge=i,face=0) for i in range(6)]
    return dict(schema=1,package=PACKAGE,maximum_doc_tolerance=.01,default_case='X',source_edges=sources,
                cases=[dict(id='X',layer='FIELD_X',form_status='REJECTED_RESEARCH_ONLY',geometry_commit=False,relief_bound_mm=.002,
                            caps=[dict(object_id=str(uuid.uuid4()),exterior_sides=['top','bottom','left','right'])])])
class ManifestTests(unittest.TestCase):
    def test_valid(self): self.assertTrue(validate_manifest(fixture()))
    def test_no_promotion(self):
        x=fixture();x['cases'][0]['form_status']='PASS'
        with self.assertRaises(ValueError): validate_manifest(x)
    def test_no_commit(self):
        x=fixture();x['cases'][0]['geometry_commit']=True
        with self.assertRaises(ValueError): validate_manifest(x)
    def test_relief_not_reset(self):
        x=fixture();x['cases'][0]['relief_bound_mm']=.003
        with self.assertRaises(ValueError): validate_manifest(x)
    def test_nonfinite_relief(self):
        x=fixture();x['cases'][0]['relief_bound_mm']=float('nan')
        with self.assertRaises(ValueError): validate_manifest(x)
    def test_missing_source(self):
        x=fixture();x['source_edges'].pop()
        with self.assertRaises(ValueError): validate_manifest(x)
    def test_duplicate_source(self):
        x=fixture();x['source_edges'][2]=x['source_edges'][1]
        with self.assertRaises(ValueError): validate_manifest(x)
    def test_source_cap_collision(self):
        x=fixture();x['cases'][0]['caps'][0]['object_id']=x['source_edges'][0]['object_id']
        with self.assertRaises(ValueError): validate_manifest(x)
    def test_duplicate_case(self):
        x=fixture();x['cases'].append(copy.deepcopy(x['cases'][0]))
        with self.assertRaises(ValueError): validate_manifest(x)
    def test_unknown_side(self):
        x=fixture();x['cases'][0]['caps'][0]['exterior_sides']=['bad']
        with self.assertRaises(ValueError): validate_manifest(x)
class IntegrityTests(unittest.TestCase):
    def test_utf8_integrity(self):
        with tempfile.TemporaryDirectory() as root:
            r=Report(root);r.emit('TEST',message='Проверка отчёта αβ');r.finish()
            b=pathlib.Path(r.path).read_bytes();lines=b[3:].splitlines(keepends=True)
            self.assertTrue(b.startswith(b'\xef\xbb\xbf'));self.assertIn(hashlib.sha256(b''.join(lines[:-1])).hexdigest().encode(),lines[-1])
    def test_finish_idempotent(self):
        with tempfile.TemporaryDirectory() as root:
            r=Report(root);r.emit('TEST');r.finish();a=sha256_file(r.path);r.finish();self.assertEqual(a,sha256_file(r.path))
    def test_after_close_not_written(self):
        with tempfile.TemporaryDirectory() as root:
            r=Report(root);r.finish()
            with self.assertRaises(ValueError):r.emit('BAD')
    def test_distinct_paths(self):
        with tempfile.TemporaryDirectory() as root:
            a=Report(root);b=Report(root);a.finish();b.finish();self.assertNotEqual(a.path,b.path)
    def test_write_failure_not_saved(self):
        with tempfile.TemporaryDirectory() as root:
            messages=[];r=Report(root,messages.append);r.handle.close()
            with self.assertRaises(ValueError): r.emit('BAD')
            self.assertEqual(messages,[])
    def test_path_traversal(self):
        for bad in ('../a','/a','a/../b','C:/a','a\\b','a//b'):
            with self.assertRaises(ValueError):safe_child('/tmp/root',bad)
    def test_safe_path(self):self.assertTrue(safe_child('/tmp/root','a/b').endswith(os.path.join('a','b')))
    def test_nonfinite_report_refused(self):
        with tempfile.TemporaryDirectory() as root:
            r=Report(root)
            with self.assertRaises(ValueError):r.emit('BAD',x={'gap':float('nan')})
            r.finish()
class CoverageTests(unittest.TestCase):
    def test_complete_extra_splits(self):self.assertTrue(interval_coverage([(0,.2),(.2,.4),(.4,1)]))
    def test_missing(self):self.assertFalse(interval_coverage([(0,.2),(.3,1)]))
    def test_duplicate(self):self.assertFalse(interval_coverage([(0,.5),(.3,1)]))
    def test_reverse(self):self.assertTrue(interval_coverage([(.4,0),(1,.4)]))
    def test_nonfinite(self):self.assertFalse(interval_coverage([(0,float('nan'))]))
class SourceTests(unittest.TestCase):
    def test_python_parses(self):
        for name in ('field_core.py','field_runtime.py','native_check.py'):ast.parse((ROOT/name).read_text(encoding='utf8'))
    def test_no_geometry_writes(self):
        for name in ('field_runtime.py','native_check.py'):
            s=(ROOT/name).read_text(encoding='utf8')
            for forbidden in ('Objects.Add','Objects.Delete','Objects.Replace','Objects.Transform','JoinEdge','SetDotNetRuntime','SaveFileName'):
                self.assertNotIn(forbidden,s)
    def test_native_trim_path_present(self):
        s=(ROOT/'native_check.py').read_text(encoding='utf8')
        self.assertIn('tr.GetTrimParameter(t)',s);self.assertIn('tr.Face.PointAt',s);self.assertIn('image_to_image_mm',s)
    def test_no_solver_import_in_rhino(self):
        for name in ('field_core.py','field_runtime.py','native_check.py'):
            tree=ast.parse((ROOT/name).read_text(encoding='utf8'))
            for n in ast.walk(tree):
                if isinstance(n,ast.Import):self.assertFalse(any(a.name in ('numpy','scipy') for a in n.names))
    def test_runtime_object_id_is_rhinocommon(self):
        s=(ROOT/'field_runtime.py').read_text(encoding='utf8');self.assertIn('Attributes.ObjectId',s);self.assertNotIn('Attributes.Id',s)
if __name__=='__main__':unittest.main()
