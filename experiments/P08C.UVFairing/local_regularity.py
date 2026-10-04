"""Cell-wise 3D regularity screening. NOT global injectivity or collision proof.
No Rhino APIs. Explicit bounded recursion and truthful missing-bound reporting.
"""
import math
import numpy as np
from scipy.interpolate import BSpline
from scipy.signal import convolve2d
from scipy.optimize import linprog
from uv_basis_fairing import bernstein_matrix


def extract(knots,degree):
    t=(1-np.cos(np.linspace(0,np.pi,degree+1)))/2
    B=bernstein_matrix(degree,t);sp=BSpline(knots,np.eye(len(knots)-degree-1),degree)
    distinct=np.unique(knots)
    return [(a,b,np.linalg.solve(B,sp(a+(b-a)*t))) for a,b in zip(distinct[:-1],distinct[1:])]


def bernstein_cross(A,B):
    p,q=np.array(A.shape[:2])-1;r,s=np.array(B.shape[:2])-1
    wa=np.outer([math.comb(int(p),i) for i in range(p+1)],[math.comb(int(q),j) for j in range(q+1)])
    wb=np.outer([math.comb(int(r),i) for i in range(r+1)],[math.comb(int(s),j) for j in range(s+1)])
    denom=np.outer([math.comb(int(p+r),i) for i in range(p+r+1)], [math.comb(int(q+s),j) for j in range(q+s+1)])
    a=A*wa[:,:,None];b=B*wb[:,:,None]
    return np.stack([(convolve2d(a[:,:,i],b[:,:,j])-convolve2d(a[:,:,j],b[:,:,i]))/denom
                     for i,j in ((1,2),(2,0),(0,1))],axis=2)


def bisect(coeff,axis):
    c=np.moveaxis(coeff,axis,0).copy();left=[c[0]];right=[c[-1]]
    while len(c)>1:
        c=(c[:-1]+c[1:])/2;left.append(c[0]);right.append(c[-1])
    return np.moveaxis(np.array(left),0,axis),np.moveaxis(np.array(right[::-1]),0,axis)


def inspect(tensor,max_depth=5,max_nodes=2048,checkpoint=None):
    if not 0<=max_depth<=7 or not 1<=max_nodes<=8192:
        raise ValueError('BOUNDED_SUBDIVISION_REQUIRED')
    U=extract(tensor.ku,tensor.p);V=extract(tensor.kv,tensor.q)
    if len(U)*len(V)>256:return {'ok':False,'reason':'CELL_BUDGET','cells':len(U)*len(V),'min_positive_margin':None}
    state={'nodes':0,'min_positive_margin':None,'reason':None};events=[]
    def recurse(C,depth):
        if checkpoint is not None:checkpoint()
        state['nodes']+=1
        if state['nodes']>max_nodes:state['reason']='NODE_BUDGET';return False
        A=C.reshape(-1,3);scale=float(np.linalg.norm(A,axis=1).max())
        if not np.isfinite(A).all() or scale<=1e-18:state['reason']='DEGENERATE_CROSS_PRODUCT';return False
        A=A/scale;n=A.mean(axis=0);n=n/max(np.linalg.norm(n),1e-30);margin=float((A@n).min())
        if margin<=1e-9:
            lp=linprog([0.,0.,0.,-1.],A_ub=np.c_[-A,np.ones(len(A))],b_ub=np.zeros(len(A)),bounds=[(-1.,1.)]*3+[(None,None)],method='highs')
            if lp.success and np.linalg.norm(lp.x[:3])>1e-20:
                n=lp.x[:3]/np.linalg.norm(lp.x[:3]);margin=float((A@n).min())
        if margin>1e-9:
            prev=state['min_positive_margin'];state['min_positive_margin']=margin if prev is None else min(prev,margin)
            return True
        if depth>=max_depth:state['reason']='LOCAL_REGULARITY_NOT_PROVEN';return False
        for half in bisect(C,0):
            for quarter in bisect(half,1):
                if not recurse(quarter,depth+1):return False
        return True
    for a,b,E in U:
        for c,d,F in V:
            net=np.einsum('ai,bj,ijc->abc',E,F,tensor.net,optimize=True)
            coeff=bernstein_cross(tensor.p*np.diff(net,axis=0),tensor.q*np.diff(net,axis=1))
            ok=recurse(coeff,0);events.append({'cell':[float(a),float(b),float(c),float(d)],'ok':ok})
            if not ok:return dict(state,ok=False,cells=len(U)*len(V),tested_cells=len(events),events=events,scope='LOCAL_NUMERICAL_NONZERO_CROSS_PRODUCT;NOT_GLOBAL_OR_PARENT_COLLISION_PROOF')
    return dict(state,ok=True,cells=len(U)*len(V),tested_cells=len(events),events=events,scope='LOCAL_NUMERICAL_NONZERO_CROSS_PRODUCT;NOT_GLOBAL_OR_PARENT_COLLISION_PROOF')
