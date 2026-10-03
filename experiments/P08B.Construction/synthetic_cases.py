from __future__ import division
from mixed_kernel import *

def surface(u,v,amp=0.25):
    z=amp*u*(1-u)*v*(1-v)
    return ((u,v,z),(1,0,amp*(1-2*u)*v*(1-v)),(0,1,amp*u*(1-u)*(1-2*v)),
            (0,0,-2*amp*v*(1-v)),(0,0,amp*(1-2*u)*(1-2*v)),(0,0,-2*amp*u*(1-u)))

def boundaries(amp=0.25,sharp_top=False,conflicting_top=False,split=False):
    result={}
    for side in SIDES:
        def f(t,side=side):
            u,v=side_uv(side,t); values=surface(u,v,amp); n,H=frame(values)
            desired=2
            if side=='top' and (sharp_top or conflicting_top):
                n=(0,1,0); H=((0,0,0),)*3; desired=0 if sharp_top else 2
            key=side + ('_a' if t<=0.5 else '_b') if split and side in ('bottom','top') else side
            return Support(values[0],n,H,key,desired,0.5 if split and side in ('bottom','top') else 1.0)
        result[side]=f
    return result

def curved_boundaries():
    result={}
    for side in SIDES:
        def f(t,side=side):
            u,v=side_uv(side,t); vals=list(surface(u,v,.2))
            vals[0]=add(vals[0],(0,0,.12*u*u+.08*v*v))
            vals[1]=add(vals[1],(0,0,.24*u)); vals[2]=add(vals[2],(0,0,.16*v))
            vals[3]=add(vals[3],(0,0,.24)); vals[5]=add(vals[5],(0,0,.16))
            n,H=frame(vals)
            return Support(vals[0],n,H,side,2)
        result[side]=f
    return result
