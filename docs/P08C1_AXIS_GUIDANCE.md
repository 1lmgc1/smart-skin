# P08C.1 — axis-guided core with finite local matching zones

## Objective and current status

Replace an undirected whole-hole correction with a constructive design frame, an explicit central profile/band, and two local quintic ribbons. Preserve every original boundary piece and its compound-side junction. Handle incompatible corners through finite geometric correction zones, not by omitting failed endpoint samples.

This branch contains a pure numerical backend and synthetic tests. It does NOT replace the released P07F2 plugin, P08B.3, or its local logging fix. No Rhino-facing slider window, automated general axis extractor, native Join adapter, or contour-edit transaction is implemented in this commit. Constructor parameters are functional controls, not mock policy flags; two parameter sets have also been evaluated privately on a supplied model. Private models, coordinates, identifiers, control nets and logs must not enter this public branch or its CI.

## Geometric construction

A DesignFrame separates the longitudinal design direction, transverse span direction, profile origin and lift direction. It is not the projection used to check a surface for foldovers. A dominant component of a whole-parent point cloud is only an axis candidate: use supporting planar directions, matched section structure or symmetry evidence, then provide a manual override. Never use the largest hole dimension as an unqualified object axis, or infer a unique center line from a direction alone.

CoreProfile is a cubic profile with adjustable endpoint handle lengths and optional axial bulge. Endpoints remain tied to the compound boundary junctions. The central band follows this profile transversely. The side ribbons match full first and second parent-surface jets to the core through quintic Hermite interpolation. This avoids a global least-squares compromise between incompatible endpoint demands. Parent parameter orientation, transverse parameter meaning and consistency of the boundary-jet callbacks must be checked by a future host adapter.

A quintic smoothstep correction restores the complete bottom/top source curves only in finite lower/upper transition zones. Its value, first derivative and second derivative vanish at the active matching interval. On that interval, valid parent 2-jets are retained. Outside it, the output is explicitly NOT assigned G2; it must be measured as a local transition. The kernel validates closure and refuses degenerate or missing jets. It does not silently close a gap or shift a parent edge.

The point evaluator supports arbitrary finite callbacks. Exact piecewise-polynomial conversion in the current experiment applies only when callbacks belong to the supported polynomial representation; do not imply arbitrary rational surfaces become exact quintic patches. Structural Brep validity does not establish smoothness across all stored knot lines.

## Functional parameters and intended UI

- Frame: axis direction and sense, transverse direction, profile origin; automatic suggestion must be observable and overridable.
- Profile: start/end handles and axial bulge; these change the core without moving its endpoints.
- Left/right ribbon widths: independent parameter fractions; a UI can link them under confirmed symmetry. Any millimeter label must define a reference section or a true metric construction, not rename a parameter fraction.
- Left/right pulls: signed parent-parameter increments; a UI tension normalization requires an explicitly documented conversion.
- Lower/upper corner-zone lengths: the host must convert a requested physical arc length to original boundary parameters; parameter domain length is not curve arc length.
- Mode: FIXED_CONTOUR initially. HEAL_CONTOUR is a separate proposed operation, not a flag that loosens the positional tolerance.

The UI is intentionally not shipped before adapter mapping, cancellation, safe preview, reporting and native seam proofs are in place. Keep the accepted one-window interaction contract when it is integrated.

## Contour healing boundary

A new contour that differs from a parent Brep edge is not a filled, joined opening. A healing transaction must identify the exact affected parent faces/trim loops, preview changes separately, limit displacement in model units, rebuild shared trim/edge topology consistently and prove unchanged external seams plus the intended new seams. Parent geometry must stay untouched until explicit acceptance, with one reversible transaction. The current kernel has no source-edit or commit path.

## Verification levels

- Synthetic tests execute the construction, all source boundaries and junctions, both transverse second jets, central-band preservation, finite geometric correction, real parameter changes, intended core/ribbon derivative matching, rigid-transform covariance, invalid controls and OpenNURBS conversion/3dm roundtrip.
- Exact-commit CI is evidence only for the checks actually run there. It does not execute the Rhino UI or RhinoCommon Join.
- Private-model experiments and their native point/normal measurements are recorded privately. Local numerical regularity bounds and sampled nonadjacent triangle tests must not be called a global self-intersection certificate. Coplanar overlap, interactions with the parent body and robust solid topology require further checks.
- No output is a universally verified G2 cap. Distinguish the active measured G2 interval, finite local transition zones and positional seams. Failed local conditions must never be hidden by averaging.

## Background references, not implementation claims

XNURBS public materials describe internal constraints, symmetry workflows, tension controls and partial matching. They do not document a proprietary axis-recognition algorithm that this project can claim to reproduce:
https://www.xnurbs.com/whats-new/
https://www.xnurbs.com/tutorials/

Rhino Brep geometry separates 3D edge curves, 2D trim curves and supporting surfaces. Changing a shared contour requires consistent topology, not moving a detached curve:
https://developer.rhino3d.com/guides/grasshopper/csharp-essentials/3-rhinocommon-geometry/

## Reproducible synthetic test

```bash
python -m pip install numpy==2.2.6 scipy==1.15.3 rhino3dm==8.17.0
PYTHONPATH=experiments/P08C.AxisGuidance python -m unittest discover -s experiments/P08C.AxisGuidance -p 'test_*.py' -v
```

Python 3 is needed for the independent test dependencies. The kernel itself uses Python 2.7/3 compatible syntax, no third-party imports, no filesystem/network calls and no Rhino APIs. It is not a standalone _RunPythonScript command.
