"""Installed-source module contract; no Rhino host is started by these tests."""
import ast
import pathlib
import re
import subprocess
import tempfile
import shutil
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PYTHON = ROOT / 'src' / 'SmartSkin.Rhino8' / 'Python'
ASSETS = {
    'smart_skin.py', 'native_input.py', 'native_family.py', 'skin_kernel.py',
    'preview.py', 'native_boundary_evidence.py', 'fan_shared_jets.py',
    'fan_rational_fields.py', 'fan_geometry.py', 'lower_corner_geometry.py',
    'upper_corner_geometry.py', 'upper_corner_certificate.py', 'constrained_uv.py',
    'repaired_validation.py', 'native_owner_separation.py', 'atlas_separation.py',
}


class RuntimeAssetContract(unittest.TestCase):
    def test_all_runtime_modules_are_owned_and_mandatory(self):
        self.assertEqual({p.name for p in PYTHON.glob('*.py')}, ASSETS)
        for relative in ('scripts/Installer-Common.ps1', 'scripts/Installer-Lifecycle.ps1',
                         'scripts/Test-InstallerLifecycle.ps1'):
            source = (ROOT / relative).read_text(encoding='utf-8-sig')
            listed = set(re.findall(r"(?:Python/)?([A-Za-z_]+\.py)'", source))
            self.assertTrue(ASSETS <= listed, (relative, sorted(ASSETS - listed)))

    def test_real_loader_sequence_works_without_generic_runtime_imports(self):
        entry = PYTHON / 'smart_skin.py'
        tree = ast.parse(entry.read_text())
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        # All actual call sites in main, in source order. Loading is exercised
        # with a neutral cwd and without placing the runtime directory on sys.path.
        calls = sorted((n for n in ast.walk(main) if isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Name) and n.func.id == '_load_local'),
                       key=lambda n: n.lineno)
        names = [n.args[0].value for n in calls]
        self.assertEqual({n + '.py' for n in names}, ASSETS - {'smart_skin.py'})
        self.assertEqual(len(names), len(set(names)))
        code = '''import importlib.util, pathlib, sys
entry_path = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location('_smartskin_asset_test_entry', entry_path)
entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)
names = sys.argv[2:]
for name in names:
    entry._load_local(name)
for name in names:
    assert '_smartskin_p08e1_' + name in sys.modules, name
    assert name not in sys.modules, 'generic module polluted: ' + name
assert not (entry_path.parent / '__pycache__').exists(), 'loader wrote bytecode'
'''
        # A clean installed-like folder distinguishes loader-created bytecode
        # from unrelated caches left by earlier developer probes.
        with tempfile.TemporaryDirectory(prefix='smartskin runtime assets ') as folder:
            isolated = pathlib.Path(folder)
            for asset in ASSETS:
                shutil.copyfile(PYTHON / asset, isolated / asset)
            result = subprocess.run([sys.executable, '-B', '-c', code,
                                     str(isolated / 'smart_skin.py'), *names],
                                    cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_capture_imports_do_not_hide_a_missing_transitive_dependency(self):
        for name, alias, generic in (
            ('native_input', '_smartskin_p08e1_native_family', 'native_family'),
            ('native_family', '_smartskin_p08e1_native_boundary_evidence', 'native_boundary_evidence'),
        ):
            code = '''import builtins, pathlib, sys
path, alias, generic = sys.argv[1:]
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name == alias:
        raise ModuleNotFoundError('missing nested dependency', name='nested_test_dependency')
    if name == generic:
        raise AssertionError('attempted generic fallback after transitive failure')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
try:
    exec(compile(pathlib.Path(path).read_bytes(), path, 'exec'), {'__name__': '_asset_test'})
except ModuleNotFoundError as error:
    assert error.name == 'nested_test_dependency', error
else:
    raise AssertionError('missing dependency was hidden')
'''
            result = subprocess.run([sys.executable, '-B', '-c', code,
                                     str(PYTHON / (name + '.py')), alias, generic],
                                    cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
