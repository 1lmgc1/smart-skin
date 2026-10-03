# -*- coding: utf-8 -*-
"""P08B.2 boundary-fixed constructive experiment (Python 2.7/3 compatible).
No Rhino, numpy, filesystem, UI or document access. Produces actual B-spline nets.
Evidence is sampled, never a commit permission. Inputs are immutable sampled jets.
"""
from __future__ import division
import math

EXPERIMENT = 'P08B.2'
SIDES = ('bottom', 'right', 'top', 'left')

def dot(a,b): return sum(x*y for x,y in zip(a,b))
def add(a,b): return tuple(x+y for x,y in zip(a,b))
def sub(a,b): return tuple(x-y for x,y in zip(a,b))
def mul(a,s): return tuple(x*s for x in a)
def norm(a): return math.sqrt(max(0.0,dot(a,a)))
def cross(a,b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def finite(x): return not (math.isnan(float(x)) or math.isinf(float(x)))
def unit(a):
    d=norm(a)
    if not finite(d) or d<1e-14: raise ValueError('DEGENERATE_VECTOR')
    return mul(a,1.0/d)

def knots(n,p):
    if p<2 or n<p+1: raise ValueError('INVALID_SPLINE_SIZE')
    return [0.0]*(p+1)+[i/(n-p) for i in range(1,n-p)]+[1.0]*(p+1)

def basis(n,p,t,K=None):
    """Full value/first/second derivative vectors, including clamped endpoints."""
    K=K or knots(n,p)
    if not finite(t) or t<0 or t>1: raise ValueError('PARAMETER_OUTSIDE_UNIT_INTERVAL')
    cache={}
    def B(i,d,k):
        key=(i,d,k)
        if key in cache: return cache[key]
        if i<0 or i+d+1>=len(K): return 0.0
        if k>d: return 0.0
        if d==0:
            v=1.0 if (K[i]<=t<K[i+1] or (t==1.0 and K[i]<K[i+1]==1.0)) else 0.0
        elif k==0:
            a=K[i+d]-K[i]; b=K[i+d+1]-K[i+1]
            v=((t-K[i])*B(i,d-1,0)/a if a else 0)+( (K[i+d+1]-t)*B(i+1,d-1,0)/b if b else 0)
        else:
            a=K[i+d]-K[i]; b=K[i+d+1]-K[i+1]
            v=(d*B(i,d-1,k-1)/a if a else 0)-(d*B(i+1,d-1,k-1)/b if b else 0)
        cache[key]=v
        return v
    return [[B(i,p,k) for i in range(n)] for k in range(3)]

def qr_fit(A,Y):
    """Householder least squares; no normal equations for positional curve fitting."""
    m=len(A); n=len(A[0]); q=len(Y[0]); R=[list(a)+list(y) for a,y in zip(A,Y)]
    if m<n: raise ValueError('UNDERDETERMINED_FIT')
    for k in range(n):
        size=math.sqrt(sum(R[i][k]**2 for i in range(k,m)))
        if not finite(size) or size<1e-13: raise ValueError('RANK_DEFICIENT_FIT')
        alpha=-math.copysign(size,R[k][k]); v=[R[i][k] for i in range(k,m)]; v[0]-=alpha
        beta=2.0/sum(x*x for x in v)
        for j in range(k,n+q):
            s=beta*sum(v[i-k]*R[i][j] for i in range(k,m))
            for i in range(k,m): R[i][j]-=s*v[i-k]
    X=[[0.0]*q for _ in range(n)]
    for i in reversed(range(n)):
        for c in range(q): X[i][c]=(R[i][n+c]-sum(R[i][j]*X[j][c] for j in range(i+1,n)))/R[i][i]
    if not all(finite(x) for row in X for x in row): raise ValueError('NONFINITE_FIT')
    return [tuple(x) for x in X]

class Support(object):
    """A boundary sample at its true parent face, with world-space shape operator.
    H is a symmetric 3x3 tensor extended by zero in the face-normal direction.
    Its sign is coupled to normal. key identifies the original edge/interval.
    """
    def __init__(self,point,normal,H,key,preferred=2,weight=1.0):
        self.point=tuple(point); self.normal=unit(normal) if normal is not None else None
        self.H=tuple(tuple(row) for row in H) if H is not None else None
        self.key=str(key); self.preferred=int(preferred); self.weight=float(weight)
        if self.preferred not in (0,1,2) or self.weight<=0: raise ValueError('INVALID_CONTRACT')
        if not all(finite(x) for x in self.point): raise ValueError('INVALID_POINT')
        if self.H is not None and not all(finite(x) for row in self.H for x in row): raise ValueError('INVALID_CURVATURE')
    def second(self,d):
        if self.H is None: return None
        return sum(d[i]*self.H[i][j]*d[j] for i in range(3) for j in range(3))

class Patch(object):
    def __init__(self,net,p=3,K=None):
        self.n=len(net); self.p=p; self.K=list(K or knots(self.n,p))
        if any(len(row)!=self.n for row in net): raise ValueError('NONSQUARE_NET')
        self.net=tuple(tuple(tuple(pt) for pt in row) for row in net)
        if not all(finite(x) for row in self.net for pt in row for x in pt): raise ValueError('NONFINITE_NET')
    def eval(self,u,v):
        bu=basis(self.n,self.p,u,self.K); bv=basis(self.n,self.p,v,self.K)
        out=[]
        for du,dv in ((0,0),(1,0),(0,1),(2,0),(1,1),(0,2)):
            data=[0.0,0.0,0.0]
            for i in range(self.n):
                if not bu[du][i]: continue
                for j in range(self.n):
                    c=bu[du][i]*bv[dv][j]
                    if c:
                        pt=self.net[i][j]
                        for k in range(3): data[k]+=c*pt[k]
            out.append(tuple(data))
        return tuple(out)
    def boundary_snapshot(self):
        n=self.n
        return tuple(self.net[i][j] for i in range(n) for j in range(n) if i in (0,n-1) or j in (0,n-1))

def side_uv(side,t):
    return {'bottom':(t,0.0),'top':(t,1.0),'left':(0.0,t),'right':(1.0,t)}[side]

def sample_parameters(func,count):
    points=set(i/(count-1) for i in range(count))
    points.update(getattr(func,'parameters',()))
    return sorted(t for t in points if 0<=t<=1)

def fit_boundary(func,n,p,first,last,sample_count=97):
    A=[]; Y=[]
    for t in sample_parameters(func,sample_count):
        b=basis(n,p,t)[0]; pt=func(t).point
        A.append(b[1:-1]); Y.append(sub(sub(pt,mul(first,b[0])),mul(last,b[-1])))
    return [first]+qr_fit(A,Y)+[last]

def construct_coons(boundaries,n=10,p=3,corner_tolerance=0.01):
    """Fit four chains without losing their support callbacks, then make a Coons net.
    Boundary CPs are fixed by all subsequent refinement. G0 still needs verification.
    """
    b,r,t,l=[boundaries[s] for s in SIDES]
    pairs=((b(0).point,l(0).point),(b(1).point,r(0).point),(t(0).point,l(1).point),(t(1).point,r(1).point))
    if any(norm(sub(a,z))>corner_tolerance for a,z in pairs): raise ValueError('OPEN_BOUNDARY_CORNER')
    p00,p10,p01,p11=[mul(add(a,z),0.5) for a,z in pairs]
    sides={'bottom':fit_boundary(b,n,p,p00,p10),'top':fit_boundary(t,n,p,p01,p11),
           'left':fit_boundary(l,n,p,p00,p01),'right':fit_boundary(r,n,p,p10,p11)}
    K=knots(n,p); g=[sum(K[i+1:i+p+1])/p for i in range(n)]; net=[]
    for i,u in enumerate(g):
        row=[]
        for j,v in enumerate(g):
            a=add(mul(sides['bottom'][i],1-v),mul(sides['top'][i],v))
            a=add(a,add(mul(sides['left'][j],1-u),mul(sides['right'][j],u)))
            bil=add(add(mul(p00,(1-u)*(1-v)),mul(p10,u*(1-v))),add(mul(p01,(1-u)*v),mul(p11,u*v)))
            row.append(sub(a,bil))
        net.append(row)
    # Exact shared row values (avoid accumulating corner cancellation roundoff).
    for i in range(n): net[i][0]=sides['bottom'][i]; net[i][-1]=sides['top'][i]
    for j in range(n): net[0][j]=sides['left'][j]; net[-1][j]=sides['right'][j]
    return Patch(net,p,K)

def pcg(rows,rhs,initial,ridge=1e-10,limit=600,checkpoint=None):
    """Matrix-free diagonal-preconditioned least squares of sparse rows.
    Solves for a displacement from initial, regularizing unconstrained modes to zero.
    This is an approximate solve: actual geometry must always be measured afterward.
    """
    n=len(initial); b=[0.0]*n; diag=[ridge]*n
    for row,y in zip(rows,rhs):
        residual=y-sum(c*initial[i] for i,c in row)
        for i,c in row: b[i]+=c*residual; diag[i]+=c*c
    def apply(x):
        out=[ridge*v for v in x]
        for row in rows:
            val=sum(c*x[i] for i,c in row)
            for i,c in row: out[i]+=c*val
        return out
    x=[0.0]*n; r=list(b); z=[r[i]/diag[i] for i in range(n)]; d=list(z); rz=dot(r,z)
    initial_norm=norm(b); iterations=0
    if initial_norm<1e-13: return list(initial),0
    for iteration in range(limit):
        if checkpoint is not None and iteration%10==0: checkpoint()
        ad=apply(d); denom=dot(d,ad)
        if denom<=0 or not finite(denom): break
        a=rz/denom
        x=[x[i]+a*d[i] for i in range(n)]; r=[r[i]-a*ad[i] for i in range(n)]
        iterations=iteration+1
        if norm(r)<max(1e-12,initial_norm*1e-9): break
        z=[r[i]/diag[i] for i in range(n)]; new=dot(r,z)
        d=[z[i]+(new/rz)*d[i] for i in range(n)]; rz=new
    out=[initial[i]+x[i] for i in range(n)]
    if not all(finite(v) for v in out): raise ValueError('NONFINITE_SOLVE')
    return out,iterations

def refine(patch,boundaries,curvature=False,sample_count=41,checkpoint=None):
    """One global boundary-jet step. Every selected smooth side participates together.
    Position rows stay fixed, unlike sequential MatchSrf. No source surface is edited.
    """
    n=patch.n; p=patch.p; K=patch.K
    ids={(i,j,k):((i-1)*(n-2)+(j-1))*3+k for i in range(1,n-1) for j in range(1,n-1) for k in range(3)}
    initial=[x for i in range(1,n-1) for j in range(1,n-1) for x in patch.net[i][j]]
    rows=[]; rhs=[]
    def equation(u,v,du,dv,normal,y,weight):
        bu=basis(n,p,u,K)[du]; bv=basis(n,p,v,K)[dv]; row=[]; fixed=0.0
        for i in range(n):
            for j in range(n):
                c=bu[i]*bv[j]
                if not c: continue
                if i in (0,n-1) or j in (0,n-1): fixed+=c*dot(normal,patch.net[i][j])
                else:
                    for k in range(3):
                        if abs(c*normal[k])>1e-15: row.append((ids[i,j,k],c*normal[k]))
        length=math.sqrt(sum(c*c for _,c in row))
        if length>1e-14:
            scale=weight/length; rows.append([(i,c*scale) for i,c in row]); rhs.append((y-fixed)*scale)
    for side in SIDES:
        for t in sample_parameters(boundaries[side],sample_count):
            if checkpoint is not None: checkpoint()
            support=boundaries[side](t)
            if support.preferred==0 or support.normal is None: continue
            u,v=side_uv(side,t); du,dv=(0,1) if side in ('bottom','top') else (1,0)
            equation(u,v,du,dv,support.normal,0.0,1.0)
            if curvature and support.preferred>=2 and support.H is not None:
                values=patch.eval(u,v); d=values[2 if dv else 1]
                # Remove current normal residual before evaluating the target II.
                tangent=sub(d,mul(support.normal,dot(d,support.normal)))
                equation(u,v,2*du,2*dv,support.normal,support.second(tangent),1.0)
    solved,it=pcg(rows,rhs,initial,checkpoint=checkpoint)
    net=[[list(pt) for pt in row] for row in patch.net]
    for i in range(1,n-1):
        for j in range(1,n-1):
            net[i][j]=solved[ids[i,j,0]:ids[i,j,0]+3]
    result=Patch(net,p,K)
    if result.boundary_snapshot()!=patch.boundary_snapshot(): raise AssertionError('POSITION_ROWS_CHANGED')
    return result,it

def frame(values):
    pt,su,sv,suu,suv,svv=values; nu=unit(cross(su,sv)); e=dot(su,su); f=dot(su,sv); g=dot(sv,sv)
    det=e*g-f*f
    if det<=max(e*g*1e-14,1e-24): raise ValueError('SINGULAR_FRAME')
    a=unit(su); b=unit(cross(nu,a))
    def coeff(d): return ((g*dot(d,su)-f*dot(d,sv))/det,(e*dot(d,sv)-f*dot(d,su))/det)
    ia,ib=coeff(a),coeff(b)
    def ii(x,y): return dot(nu,add(add(mul(suu,x[0]*y[0]),mul(suv,x[0]*y[1]+x[1]*y[0])),mul(svv,x[1]*y[1])))
    h00,h01,h11=ii(ia,ia),ii(ia,ib),ii(ib,ib)
    H=tuple(tuple(h00*a[i]*a[j]+h01*(a[i]*b[j]+b[i]*a[j])+h11*b[i]*b[j] for j in range(3)) for i in range(3))
    return nu,H

def tensor_error(a,b,normal_dot=1.0):
    # Frobenius relative shape-operator difference in one world frame; stricter
    # than checking a single normal curvature. Zero-flat numerical floor is 1e-9.
    sign=1 if normal_dot>=0 else -1
    aa=math.sqrt(sum(x*x for row in a for x in row)); bb=math.sqrt(sum(x*x for row in b for x in row))
    err=math.sqrt(sum((sign*a[i][j]-b[i][j])**2 for i in range(3) for j in range(3)))
    if aa<1e-9 and bb<1e-9: return 0.0
    return 100*err/max(aa,bb,1e-9)

def measure(patch,boundaries,tolerance=0.01,angle_deg=1.0,curvature_pct=5.0,samples=65,checkpoint=None):
    """All samples describe this single patch revision. No cached cross-candidate grades.
    Position uses explicit known side correspondence (sampled upper-bound distance).
    G1/G2 checks include endpoints; missing frames yield UNKNOWN, not a successful zero.
    """
    edges={}; weighted=0.0; total=0.0
    for side in SIDES:
        for t in sample_parameters(boundaries[side],samples):
            if checkpoint is not None: checkpoint()
            s=boundaries[side](t); u,v=side_uv(side,t); values=patch.eval(u,v)
            key=s.key
            if key not in edges: edges[key]={'gap':0.0,'normal_deg':0.0,'curvature_pct':0.0,'frames':True,'curvatures':True,'count':0,'preferred':s.preferred,'weight':0.0}
            e=edges[key]; e['count']+=1; e['weight']=s.weight; e['gap']=max(e['gap'],norm(sub(values[0],s.point)))
            try:
                normal,H=frame(values)
                if s.normal is None: raise ValueError('NO_SUPPORT_NORMAL')
                d=max(-1,min(1,dot(normal,s.normal))); a=math.degrees(math.acos(abs(d)))
                e['normal_deg']=max(e['normal_deg'],a)
                if s.H is None: e['curvatures']=False
                else: e['curvature_pct']=max(e['curvature_pct'],tensor_error(H,s.H,d))
            except ValueError: e['frames']=False; e['curvatures']=False
    position_ok=True
    for e in edges.values():
        grade=0 if e['gap']<=tolerance else -1
        if grade>=0 and e['frames'] and e['normal_deg']<=angle_deg:
            grade=1
            if e['curvatures'] and e['curvature_pct']<=curvature_pct: grade=2
        e['achieved']=grade
        if grade<0: position_ok=False
        # Full-edge classification is conservative. Quality credit is physical
        # sampled length, capped at desired grade; no credit for a split itself.
        weighted+=e['weight']*min(max(grade,0),e['preferred']); total+=e['weight']
    origin=patch.eval(0.5,0.5); regular=True; min_ratio=1.0
    try:
        ref=unit(cross(origin[1],origin[2]))
        for i in range(1,16):
            if checkpoint is not None: checkpoint()
            for j in range(1,16):
                values=patch.eval(i/16,j/16); jac=cross(values[1],values[2]); den=norm(values[1])*norm(values[2])
                ratio=dot(jac,ref)/max(den,1e-30); min_ratio=min(min_ratio,ratio)
                if ratio<=1e-6 or not finite(ratio): regular=False
    except ValueError: regular=False; min_ratio=0.0
    worst_normal=max((e['normal_deg'] if e['frames'] else 90) for e in edges.values() if e['preferred']>0) if any(e['preferred']>0 for e in edges.values()) else 0
    worst_curve=max((e['curvature_pct'] if e['curvatures'] else 200) for e in edges.values() if e['preferred']>1) if any(e['preferred']>1 for e in edges.values()) else 0
    gap=max(e['gap'] for e in edges.values())
    desired=all(e['achieved']>=e['preferred'] for e in edges.values())
    return {'edges':edges,'position_sampled_ok':position_ok,'regularity_sampled_ok':regular,'min_projection_ratio':min_ratio,
            'desired_sampled_met':desired,'gap_sampled':gap,'score':(weighted/max(total,1e-30),-worst_normal,-worst_curve),
            'scope':'SAMPLED_ONLY;NOT_JOIN_PROOF;NOT_SELF_INTERSECTION_CERTIFICATE','commit_allowed':False}

class CandidatePool(object):
    def __init__(self): self.best=None; self.history=[]
    def offer(self,label,patch,evidence):
        valid=evidence['position_sampled_ok'] and evidence['regularity_sampled_ok']
        kept=valid and (self.best is None or evidence['score']>self.best[2]['score'])
        if kept: self.best=(label,patch,evidence)
        self.history.append((label,valid,kept,evidence))
        return kept

def solve(boundaries,n=10,p=3,tolerance=0.01,steps=4,checkpoint=None,on_candidate=None):
    pool=CandidatePool(); base=construct_coons(boundaries,n,p,tolerance)
    def offer(label,patch):
        e=measure(patch,boundaries,tolerance,checkpoint=checkpoint); kept=pool.offer(label,patch,e)
        if on_candidate: on_candidate(label,patch,e,kept)
    offer('COONS_FIXED_G0',base)
    current=base
    for step in range(steps):
        current,it=refine(current,boundaries,curvature=(step>0),checkpoint=checkpoint)
        offer(('G1_JET' if step==0 else 'G2_JET')+'_'+str(step),current)
    return pool

def seam_measure(first,side_a,second,side_b,reverse=False,samples=65):
    gap=0.0; angle=0.0; curvature=0.0; frames=True
    for i in range(samples):
        t=i/(samples-1); a=first.eval(*side_uv(side_a,t)); b=second.eval(*side_uv(side_b,1-t if reverse else t)); gap=max(gap,norm(sub(a[0],b[0])))
        try:
            na,ha=frame(a); nb,hb=frame(b); d=dot(na,nb)
            angle=max(angle,math.degrees(math.acos(min(1,abs(d))))); curvature=max(curvature,tensor_error(ha,hb,d))
        except ValueError: frames=False
    return {'gap_sampled':gap,'normal_deg':angle if frames else None,'curvature_pct':curvature if frames else None,'frames':frames,'scope':'SAMPLED_KNOWN_SEAM_CORRESPONDENCE'}
