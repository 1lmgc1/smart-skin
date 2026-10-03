"""Native OpenNURBS conversion of an adaptive nonuniform net, NOT Rhino Join."""
from pathlib import Path
import json
import os
import rhino3dm as rg
from mixed_kernel import norm, sub
from adaptive_boundary import adaptive_coons
from adaptive_fixture import localized_boundaries

out = Path(os.environ.get('ARTIFACT_DIR', 'construction-artifact'))
out.mkdir(exist_ok=True, parents=True)
fit = adaptive_coons(localized_boundaries())
assert fit.evidence['target_sampled_met']
p = fit.patch
surface = rg.NurbsSurface.Create(3, False, p.p+1, p.p+1, p.n, p.n)
for i, value in enumerate(p.K[1:-1]):
    surface.KnotsU[i] = value
    surface.KnotsV[i] = value
for i in range(p.n):
    for j in range(p.n):
        x, y, z = p.net[i][j]
        surface.Points[i, j] = rg.Point4d(x, y, z, 1)
assert surface.IsValid
brep = rg.Brep.CreateFromSurface(surface)
assert brep is not None and brep.IsValid
maximum = 0.
for i in range(31):
    for j in range(27):
        u, v = (i+.171)/31, (j+.319)/27
        a = surface.PointAt(u, v)
        maximum = max(maximum, norm(sub((a.X, a.Y, a.Z), p.eval(u, v)[0])))
assert maximum < 1e-10
# Also evaluate the actual native boundary on a dense lattice not used to fit.
sides = localized_boundaries()
max_boundary = 0.
for i in range(2001):
    t = (i+.2718281828)/2001
    a = surface.PointAt(t, 1)
    max_boundary = max(max_boundary, norm(sub((a.X, a.Y, a.Z), sides['top'](t).point)))
assert max_boundary < .0025
model = rg.File3dm()
attrs = rg.ObjectAttributes(); attrs.Name = 'Synthetic localized detail, adaptive boundary only'
model.Objects.AddBrep(brep, attrs)
path = out/'P08B2F2_adaptive_synthetic.3dm'
assert model.Write(str(path), 8)
loaded = rg.File3dm.Read(str(path))
assert loaded is not None and len(loaded.Objects) == 1 and loaded.Objects[0].Geometry.IsValid
report = {'scope': 'ADAPTIVE_BOUNDARY_AND_OPENNURBS_NOT_RHINOCOMMON_JOIN',
          'controls': p.n, 'knots': p.K, 'sampled_gap': fit.evidence['gap'],
          'native_dense_boundary_gap': max_boundary,
          'native_evaluation_discrepancy': maximum,
          'roundtrip': 'PASS', 'private_hole': 'NOT_VERIFIED', 'g2': 'NOT_TESTED_BY_THIS_FIXTURE'}
(out/'adaptive-opennurbs.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('P08B2F2_ADAPTIVE_OPENNURBS PASS | controls='+str(p.n)+' | dense_boundary_gap='+str(max_boundary)
      +' | native_brep_valid=True | roundtrip=PASS | Rhino_Join=NOT_RUN')
