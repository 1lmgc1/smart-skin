"""P08B.3: actual stabilized synthetic nets through native OpenNURBS/3dm.
Does not run Rhino UI, RhinoCommon Join or the private hole. G1 is not called G2.
"""
from pathlib import Path
import json
import os
import math
import rhino3dm as rg
from mixed_kernel import *
from shape_guard import *
from stable_refinement import *
from test_stability import plane,boundaries_of,bump,flat_values
out=Path(os.environ.get('ARTIFACT_DIR','construction-artifact'));out.mkdir(exist_ok=True,parents=True)
model=rg.File3dm();model.ApplicationName='Smart Skin P08B.3 synthetic stabilization'
model.StartSectionComments='Synthetic only. No private geometry. Native Join and UI NOT RUN.'
report={'scope':'STABILIZED_SYNTHETIC_GEOMETRY_AND_OPENNURBS','cases':[]}
functions=boundaries_of(bump)
for side in ('bottom','top'):
    original=functions[side]
    def fragment(t,source=original,side=side):
        s=source(t);return Support(s.point,s.normal,s.H,side+('_a' if t<=.5 else '_b'),0,.5)
    fragment.parameters=[0,.49999,.5,.50001,1];functions[side]=fragment
bad=plane([0]*4+[.006,.019,.045,.2,.4,.6,.8,.95,.99]+[1]*4)
net=[list(row) for row in bad.net];net[1][1]=add(net[1][1],(-200,0,50));bad=Patch(net,3,bad.K)
expected=[]
for name,start,boundary in [('six_segment_stable_G1',plane(),functions),('spike_replaced_by_harmonic_seed',bad,boundaries_of(flat_values))]:
    events=[];p,e=stable_solve(start,boundary,on_event=lambda k,d:events.append((k,d)),steps=8)
    assert p is not None and e['shape']['ok'] and e['g1_all'],(name,e)
    if name=='six_segment_stable_G1':
        assert len(e['edges'])==6 and sum(x['preferred']==0 for x in e['edges'].values())==4
    s=rg.NurbsSurface.Create(3,False,p.p+1,p.p+1,p.n,p.n)
    for i,value in enumerate(p.K[1:-1]):s.KnotsU[i]=value;s.KnotsV[i]=value
    for i in range(p.n):
        for j in range(p.n):s.Points[i,j]=rg.Point4d(*(p.net[i][j]+(1,)))
    assert s.IsValid
    brep=rg.Brep.CreateFromSurface(s);assert brep is not None and brep.IsValid
    point_error=0.;normal_error=0.;boundary_angle=0.
    for i in range(21):
        for j in range(21):
            u=(i+.173)/21;v=(j+.417)/21;actual=s.PointAt(u,v);normal=s.NormalAt(u,v);values=p.eval(u,v)
            point_error=max(point_error,norm(sub((actual.X,actual.Y,actual.Z),values[0])))
            normal_error=max(normal_error,math.degrees(math.acos(min(1.,abs(dot(unit((normal.X,normal.Y,normal.Z)),frame(values)[0]))))))
    for side in ('left','right'):
        for i in range(257):
            t=(i+.271828)/257;u,v=side_uv(side,t);normal=s.NormalAt(u,v);target=boundary[side](t).normal
            boundary_angle=max(boundary_angle,math.degrees(math.acos(min(1.,abs(dot(unit((normal.X,normal.Y,normal.Z)),target))))))
    assert point_error<1e-10 and normal_error<1e-4 and boundary_angle<=1.,(name,point_error,normal_error,boundary_angle)
    attrs=rg.ObjectAttributes();attrs.Name=name;model.Objects.AddBrep(brep,attrs);expected.append(p)
    report['cases'].append(dict(name=name,brep_valid=True,native_point_error=point_error,
        native_conversion_normal_error_deg=normal_error,independent_boundary_normal_max_deg=boundary_angle,
        g1_sampled=e['g1_all'],requested_G2_met=e['desired_sampled_met'],evidence=e,events=events))
    print('P08B3_OPENNURBS PASS | '+name+' | G1='+str(e['g1_all'])+' | requested_G2='+str(e['desired_sampled_met']))
p=out/'P08B3_stable_synthetic.3dm';assert model.Write(str(p),8)
read=rg.File3dm.Read(str(p));assert read is not None and len(read.Objects)==len(expected)
for item,patch in zip(read.Objects,expected):
    assert item.Geometry.IsValid
    for u,v in ((.1,.2),(.013,.007),(.977,.93)):
        a=item.Geometry.Faces[0].PointAt(u,v)
        assert norm(sub((a.X,a.Y,a.Z),patch.eval(u,v)[0]))<1e-10
report.update(roundtrip='PASS',rhino_join='NOT_RUN',rhino_UI='NOT_RUN',private_hole='NOT_VERIFIED',committable=False)
(out/'stability-opennurbs.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('P08B3_ROUNDTRIP PASS | objects='+str(len(expected))+' | native_Rhino_Join=NOT_RUN')
