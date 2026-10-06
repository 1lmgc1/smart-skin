#! python 3
# requirements: numpy==1.26.4, scipy==1.13.1, mpmath==1.3.0
"""Rhino 8 CPython entry point for the experimental native FULLCYCLE builder.

This file is executed through Rhino's ScriptEditor command. It never starts an
external interpreter, downloads model data, or writes source geometry.
"""

import importlib.util
import importlib
import os
import sys


def _verify_dependency_versions(import_module=None):
    """Fail closed if Rhino's persistent interpreter cached another version."""
    import_module = import_module or importlib.import_module
    expected = (("numpy", "1.26.4"), ("scipy", "1.13.1"), ("mpmath", "1.3.0"))
    for name, required in expected:
        try:
            package = import_module(name)
        except ImportError:
            raise RuntimeError("Required Python package {0}=={1} is unavailable. "
                               "Let Rhino ScriptEditor finish resolving the pinned packages, then restart Rhino.".format(
                                   name, required)) from None
        actual = str(getattr(package, "__version__", "unknown"))
        if actual != required:
            raise RuntimeError("Rhino's Python session loaded {0} {1}; Smart Skin requires {2}. "
                               "Restart Rhino so ScriptEditor can load the pinned package versions.".format(
                                   name, actual, required))


def _load_local(name, module_name=None):
    """Load this installed bundle, never an old module cached by another build."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name + ".py")
    module_name = module_name or "_smartskin_p08e1_" + name
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("An installed Smart Skin Python asset is missing: " + name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    # The installed bundle is hash checked and immutable. Compile source
    # directly rather than letting SourceFileLoader create __pycache__ files;
    # do not change the user's process-wide bytecode preference.
    with open(path, "rb") as source:
        code = compile(source.read(), path, "exec")
    exec(code, module.__dict__)
    return module


def main():
    import Rhino
    import scriptcontext

    capture = None
    input_module = None
    escape_requested = [False]

    def on_escape(sender, event):
        escape_requested[0] = True

    def cancelled():
        Rhino.RhinoApp.Wait()
        return escape_requested[0]

    try:
        if sys.version_info < (3, 9):
            raise RuntimeError("Rhino 8 CPython 3.9 or newer is required.")
        doc = scriptcontext.doc
        if not isinstance(doc, Rhino.RhinoDoc):
            raise RuntimeError("Run SmartSurfaceBuild in a Rhino document.")
        _verify_dependency_versions()
        # Version-owned aliases avoid another script's generic module names.
        _load_local("native_boundary_evidence")
        _load_local("native_family")
        input_module = _load_local("native_input")
        _load_local("fan_shared_jets")
        _load_local("fan_rational_fields")
        _load_local("fan_geometry")
        _load_local("lower_corner_geometry")
        _load_local("upper_corner_geometry")
        _load_local("upper_corner_certificate")
        _load_local("constrained_uv")
        kernel = _load_local("skin_kernel")
        _load_local("repaired_validation")
        _load_local("atlas_separation")
        _load_local("native_owner_separation")
        preview = _load_local("preview")
        Rhino.RhinoApp.EscapeKeyPressed += on_escape
        try:
            capture = input_module.capture(doc, cancelled=cancelled)
        finally:
            Rhino.RhinoApp.EscapeKeyPressed -= on_escape
        return preview.run(doc, capture, kernel)
    except Exception as error:
        if escape_requested[0] or (input_module is not None and isinstance(error, input_module.InputCancelled)):
            Rhino.RhinoApp.WriteLine("SMARTSKIN_P08E1 CANCELLED | added=0 | sources=unchanged")
            return False
        # Do not serialize the model, selected IDs, private coordinates, paths,
        # or a traceback to logs. Domain errors supply a bounded safe diagnosis.
        reason = str(error) if isinstance(error, (ValueError, RuntimeError)) else type(error).__name__
        Rhino.RhinoApp.WriteLine("SMARTSKIN_P08E1 BLOCKED | " + reason)
        return False
    finally:
        if capture is not None:
            try:
                capture.dispose()
            except Exception:
                Rhino.RhinoApp.WriteLine("SMARTSKIN_P08E1 CLEANUP_WARNING | native input references could not all be released")


if __name__ == "__main__":
    main()
