"""Synthetic analytic input for layout/construction tests; no private model data.

The mock source intervals below are not a Rhino trim-extraction test. The actual
layout helper and numerical construction kernel are executed on these inputs.
"""
from mixed_kernel import *
from rhino_prototype import four_side_layouts


def reference_surface(u,v):
    # Two curved G2 sides (u=0,1), two straight G0 sides split in halves.
    a,b=0.2,0.3; q=a+b*u*(1-u); q1=b*(1-2*u); q2=-2*b
    r=v*(1-v); r1=1-2*v
    return ((u,v,q*r),(1,0,q1*r),(0,1,q*r1),
            (0,0,q2*r),(0,0,q1*r1),(0,0,-2*q))


def ring_fixture():
    definitions=[('a0',(0,0),(.5,0)),('a1',(.5,0),(1,0)),
                 ('b',(1,0),(1,1)),('c0',(1,1),(.5,1)),
                 ('c1',(.5,1),(0,1)),('d',(0,1),(0,0))]
    items=[dict(key=k,flip=False,uv0=p,uv1=q,edge=object(),
                identity=('synthetic',k),interval=(0.,1.)) for k,p,q in definitions]
    return items,{'a0','a1','c0','c1'}


class AnalyticChain:
    def __init__(self,items,features):
        self.items=items; self.features=features; self.entries=[]; self.parameters=[0.,1.]
        weights=[math.hypot(e['uv1'][0]-e['uv0'][0],e['uv1'][1]-e['uv0'][1]) for e in items]
        total=sum(weights); left=0.
        for e,w in zip(items,weights):
            right=left+w/total; self.entries.append((left,right,e,w))
            self.parameters.extend(left+(right-left)*a for a in (0,1e-5,.25,.5,.75,1-1e-5,1))
            left=right
    def __call__(self,t):
        entry=self.entries[-1]
        for item in self.entries:
            if t<=item[1]: entry=item; break
        start,end,e,w=entry; f=max(0,min(1,(t-start)/(end-start)))
        if e['flip']: f=1-f
        u=e['uv0'][0]+f*(e['uv1'][0]-e['uv0'][0])
        v=e['uv0'][1]+f*(e['uv1'][1]-e['uv0'][1])
        values=reference_surface(u,v); n,H=frame(values)
        grade=0 if e['key'] in self.features else 2
        if grade==0: n=(0,1,0); H=((0,0,0),)*3
        return Support(values[0],n,H,e['key'],grade,w)


def opposed_boundaries(items=None):
    original,features=ring_fixture()
    layout=four_side_layouts(original if items is None else items,features)[0]
    return {side:AnalyticChain(layout[side],features) for side in SIDES}
