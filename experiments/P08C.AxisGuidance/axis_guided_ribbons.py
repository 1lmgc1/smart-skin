# -*- coding: utf-8 -*-
"""P08C.1 constructive kernel: axis-guided core and finite end-match zones.

Pure Python. No Rhino, document, file or network calls. This does not infer G2
from a requested grade, repair source contours, or authorize a CAD commit.
Callbacks must preserve the supplied curve pieces and surface jet parameters.
The adapter must validate surface-parameter mapping and all returned evidence.
"""
from __future__ import division
import math


def add(a,b): return tuple(x+y for x,y in zip(a,b))
def sub(a,b): return tuple(x-y for x,y in zip(a,b))
def mul(a,t): return tuple(x*t for x in a)
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def norm(a): return math.sqrt(dot(a,a))
def cross(a,b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def finite(x): return not (math.isnan(x) or math.isinf(x))
def vector(a):
    a=tuple(float(x) for x in a)
    if len(a)!=3 or not all(finite(x) for x in a): raise ValueError('INVALID_VECTOR')
    return a

def unit(a):
    a=vector(a);n=norm(a)
    if n<=1e-14: raise ValueError('DEGENERATE_DIRECTION')
    return mul(a,1/n)

def smooth5(x):
    x=max(0.,min(1.,x));return x*x*x*(10+x*(-15+6*x))


def hermite5(t,conditions):
    """Position/first/second jet at each endpoint; derivatives use local t."""
    t2=t*t;t3=t2*t;t4=t3*t;t5=t4*t
    weights=(1-10*t3+15*t4-6*t5,
             t-6*t3+8*t4-3*t5,
             .5*(t2-3*t3+3*t4-t5),
             10*t3-15*t4+6*t5,
             -4*t3+7*t4-3*t5,
             .5*(t3-2*t4+t5))
    if len(conditions)!=6:raise ValueError('SIX_HERMITE_JETS_REQUIRED')
    values=[vector(v) for v in conditions]
    return tuple(sum(w*v[k] for w,v in zip(weights,values)) for k in range(3))


class DesignFrame(object):
    """A design frame is not the shape-check projection and not an inferred axis line.
    Origin must be chosen explicitly. Axis sign and transverse sign are meaningful.
    """
    def __init__(self,origin,longitudinal,transverse):
        self.origin=vector(origin);self.axis=unit(longitudinal)
        self.transverse=unit(sub(vector(transverse),mul(self.axis,dot(self.axis,transverse))))
        self.lift=unit(cross(self.axis,self.transverse))


class CoreProfile(object):
    """Cubic axial profile plus an optional quartic axial bulge. Endpoints fixed."""
    def __init__(self,start,end,frame,start_handle=.7,end_handle=.7,bulge=0.):
        self.start=vector(start);self.end=vector(end);self.frame=frame
        numbers=(float(start_handle),float(end_handle),float(bulge))
        if not all(finite(x) for x in numbers) or min(numbers[:2])<=0:raise ValueError('INVALID_PROFILE_CONTROL')
        d=sub(self.end,self.start);axial=dot(d,frame.axis);rise=dot(d,frame.lift)
        if axial<=0 or rise<=0:raise ValueError('PROFILE_FRAME_MUST_ORIENT_TOWARDS_END')
        self.control=(self.start,add(self.start,mul(frame.axis,numbers[0]*axial)),
                      sub(self.end,mul(frame.lift,numbers[1]*rise)),self.end)
        self.bulge=numbers[2]
    def __call__(self,v):
        w=((1-v)**3,3*v*(1-v)**2,3*v*v*(1-v),v**3)
        p=tuple(sum(x*y[k] for x,y in zip(w,self.control)) for k in range(3))
        return add(p,mul(self.frame.axis,self.bulge*16*v*v*(1-v)*(1-v)))


class AxisRibbons(object):
    """Construct a core + left/right quintic ribbons, then restore top/bottom.

    left/right(v) -> (boundary point, parent surface dq, parent surface dqq).
    The caller has verified that q is transverse to the selected boundary and
    that v maps to its original parent parameter without dropping a source piece.
    Tangency/curvature follow from surface reparameterization jets only on the
    active interval. Finite correction zones are FULLY reported, not ignored.

    widths are parameter fractions; callers expose physical dimensions after
    a documented conversion. pulls are signed parent-parameter increments over
    each local ribbon. They are NOT a tolerance or a claimed radius.
    """
    def __init__(self,left,right,bottom,top,profile,transverse,
                 left_width=.16,right_width=.16,left_pull=.7,right_pull=-.7,
                 start_cut=.08,end_cut=.8,corner_tolerance=1e-8):
        self.left,self.right,self.bottom,self.top=left,right,bottom,top
        self.profile=profile;self.transverse=unit(transverse)
        nums=tuple(float(x) for x in (left_width,right_width,left_pull,right_pull,start_cut,end_cut,corner_tolerance))
        if not all(finite(x) for x in nums):raise ValueError('NONFINITE_CONTROLS')
        self.lw,self.rw,self.lp,self.rp,self.start_cut,self.end_cut,tol=nums
        if min(self.lw,self.rw)<=0 or self.lw+self.rw>=1:raise ValueError('CORE_MUST_HAVE_POSITIVE_WIDTH')
        if self.lp==0 or self.rp==0:raise ValueError('ZERO_TRANSVERSE_JET_IS_NOT_A_MATCH')
        if not 0<self.start_cut<self.end_cut<1:raise ValueError('EMPTY_ACTIVE_MATCH_INTERVAL')
        if tol<=0:raise ValueError('INVALID_CORNER_TOLERANCE')
        for a,b in ((bottom(0),left(0)[0]),(bottom(1),right(0)[0]),(top(0),left(1)[0]),(top(1),right(1)[0])):
            if norm(sub(vector(a),vector(b)))>tol:raise ValueError('SOURCE_CORNERS_DO_NOT_CLOSE')
        if norm(sub(profile(0),bottom(.5)))>tol or norm(sub(profile(1),top(.5)))>tol:
            raise ValueError('GUIDE_ENDPOINTS_MUST_RESPECT_COMPOUND_JUNCTIONS')
        self.commit_allowed=False

    def core(self,u,v):
        width=dot(sub(self.right(v)[0],self.left(v)[0]),self.transverse)
        if not finite(width) or width<=1e-12:raise ValueError('NONPOSITIVE_CROSS_SPAN')
        d=mul(self.transverse,width)
        return add(self.profile(v),mul(d,u-.5)),d,(0.,0.,0.)

    def raw(self,u,v):
        if self.lw<=u<=1-self.rw:return self.core(u,v)[0]
        left=u<self.lw
        point,dq,dqq=(self.left if left else self.right)(v)
        point,dq,dqq=vector(point),vector(dq),vector(dqq)
        if norm(dq)<=1e-14:raise ValueError('MISSING_OR_DEGENERATE_PARENT_JET')
        w,pull=(self.lw,self.lp) if left else (self.rw,self.rp)
        core,dc,ac=self.core(w if left else 1-w,v)
        endpoint=(point,mul(dq,pull),mul(dqq,pull*pull))
        inner=(core,mul(dc,w),mul(ac,w*w))
        return hermite5(u/w if left else (u-1+w)/w,endpoint+inner if left else inner+endpoint)

    def point(self,u,v):
        u=float(u);v=float(v)
        if not finite(u) or not finite(v) or not 0<=u<=1 or not 0<=v<=1:raise ValueError('PARAMETER_OUTSIDE_UNIT_DOMAIN')
        r=self.raw(u,v)
        if v<self.start_cut:
            r=add(r,mul(sub(self.bottom(u),self.raw(u,0)),1-smooth5(v/self.start_cut)))
        if v>self.end_cut:
            r=add(r,mul(sub(self.top(u),self.raw(u,1)),smooth5((v-self.end_cut)/(1-self.end_cut))))
        return r

    def contract(self):
        return {'core_u':[self.lw,1-self.rw],
                'active_parent_match_v':[self.start_cut,self.end_cut],
                'finite_correction_zones_v':[[0.,self.start_cut],[self.end_cut,1.]],
                'outside_active_grade':'NOT_ASSIGNED_G2;POSITION_ONLY_UNTIL_MEASURED',
                'boundary':'ALL_ORIGINAL_PIECES_AND_JUNCTIONS_RETAINED',
                'source_edit':False,'commit_allowed':False,
                'certification':'NONE;VALIDATE_NATIVE_SHAPE_SEAMS_AND_JOIN'}
