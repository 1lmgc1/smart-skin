"""Runs compiled OpenNURBS via rhino3dm, NOT RhinoCommon MatchSrf/Join.
Convert actual constructed nets to Breps, evaluate native points/normals, write/read 3dm.
"""
from pathlib import Path
import json
import os
import math
import rhino3dm as rg
from mixed_kernel import *
from synthetic_cases import boundaries,curved_boundaries
out=Path(os.environ.get('ARTIFACT_DIR','construction-artifact'));out.mkdir(exist_ok=True,parents=True)
model=rg.File3dm(); model.ApplicationName='Smart Skin P08B.2 synthetic construction experiment'
model.StartSectionComments='Synthetic fixtures only. No private user model. OpenNURBS verification is not Rhino Join/field acceptance.'
report={'scope':'ACTUAL_CONSTRUCTION_AND_OPENNURBS;NOT_RHINOCOMMON_JOIN','rhino3dm':rg.__version__,'cases':[]}
expected=[]
for name,f in [('mixed_4G2_2G0',boundaries(sharp_top=True,split=True)),('curved_all_G2',curved_boundaries())]:
    pool=solve(f,n=8,steps=4); label,patch,e=pool.best
    assert e['desired_sampled_met'],(name,e)
    s=rg.NurbsSurface.Create(3,False,patch.p+1,patch.p+1,patch.n,patch.n)
    assert s is not None
    for i,value in enumerate(patch.K[1:-1]): s.KnotsU[i]=value;s.KnotsV[i]=value
    for i in range(patch.n):
        for j in range(patch.n):
            x,y,z=patch.net[i][j];s.Points[i,j]=rg.Point4d(x,y,z,1)
    assert s.IsValid
    brep=rg.Brep.CreateFromSurface(s);assert brep is not None and brep.IsValid
    assert len(brep.Faces)==1 and len(brep.Edges)==4
    max_p=0.;max_angle=0.
    for i in range(25):
        for j in range(25):
            u=(i+.137)/25;v=(j+.273)/25
            p=s.PointAt(u,v);n=s.NormalAt(u,v); vals=patch.eval(u,v);kn=frame(vals)[0]
            max_p=max(max_p,norm(sub((p.X,p.Y,p.Z),vals[0])))
            max_angle=max(max_angle,math.degrees(math.acos(min(1,abs(dot(unit((n.X,n.Y,n.Z)),kn))))))
    assert max_p<1e-10,(name,max_p)
    assert max_angle<1e-4,(name,max_angle)
    attrs=rg.ObjectAttributes();attrs.Name=name
    model.Objects.AddBrep(brep,attrs);expected.append((name,patch))
    report['cases'].append({'case':name,'result':'PASS','candidate':label,'native_brep_valid':True,'native_faces':len(brep.Faces),'native_edges':len(brep.Edges),'native_point_max_error':max_p,'native_normal_max_degrees':max_angle,'sampled_boundary':e,'all_iterations':[{'label':a,'eligible_sampled':b,'retained':c,'evidence':d} for a,b,c,d in pool.history]})
path=out/'P08B2_synthetic_results.3dm';assert model.Write(str(path),8)
loaded=rg.File3dm.Read(str(path));assert loaded is not None and len(loaded.Objects)==len(expected)
for item,(name,patch) in zip(loaded.Objects,expected):
    b=item.Geometry;assert b.IsValid
    for u,v in ((.1,.2),(.4,.6),(.99,.7)):
        p=b.Faces[0].PointAt(u,v);assert norm(sub((p.X,p.Y,p.Z),patch.eval(u,v)[0]))<1e-10
report['roundtrip_3dm']='PASS';report['rhino_join']='NOT_RUN';report['private_hole']='NOT_VERIFIED'
(out/'opennurbs-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
for row in report['cases']:print('P08B2_OPENNURBS PASS | '+row['case']+' | native_position_error='+str(row['native_point_max_error'])+' | native_brep_valid=True')
print('P08B2_3DM_ROUNDTRIP PASS | objects='+str(len(expected))+' | actual_native_Join=NOT_RUN')
