"""Private exact-algebra C2 fan building blocks; polynomial fields only.

C,D,A are position, first cross derivative, and second cross derivative.
All parameter directions are signed positive chart directions, not implicit
inward normals. Canonical-to-patch transports are fixed scalar coefficients.
Rational outer fields must be retained algebraically and denominator-cleared
by the integration layer; this module never samples/fits a rational boundary.
"""
from fractions import Fraction as F
from functools import lru_cache
from math import comb, factorial
import numpy as np


# Private bounded exact-arithmetic execution. One budget spans nested calls.
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from time import monotonic
from math import isfinite, prod


class FanGuardError(ValueError):
    """Fail-closed diagnostic; callers may report code, phase, limit, observed."""
    def __init__(self, code, phase, observed=None, limit=None):
        self.code,self.phase,self.observed,self.limit=code,phase,observed,limit
        detail='' if limit is None else ' (observed %s, limit %s)'%(observed,limit)
        super().__init__('%s: %s%s'%(code,phase,detail))


class ExactWorkBudget:
    """Cooperative bounds for one rebuild, including nested exact helpers.

    Work units conservatively count scalar arithmetic and inspected numeric
    values, not elapsed CPU instructions. A checkpoint occurs at least every
    bounded arithmetic/conversion row; no worker-thread abort is attempted.
    A single Python bigint operation is not preemptible, so inputs and each
    arithmetic stage are bit-bounded before reuse. A caller can share this
    object across all fan cells and native-span preparation in one rebuild.
    """
    def __init__(self, *, max_work=20_000_000, max_bits=8192,
                 max_seconds=60.0, max_elements=32768,
                 cancelled=None, deadline=None, cancel_poll_seconds=.02, _clock=monotonic):
        limits=((max_work,1,100_000_000),(max_bits,1,32768),(max_elements,1,32768))
        if any(isinstance(x,bool) or not isinstance(x,int) or not lo<=x<=hi for x,lo,hi in limits):
            raise FanGuardError('fan.invalid_budget','Integer work, bit or allocation budget is outside its hard bound.')
        if not isfinite(max_seconds) or not 0<max_seconds<=600:
            raise FanGuardError('fan.invalid_budget','Elapsed-time budget must be in (0,600] seconds.')
        if not isfinite(cancel_poll_seconds) or not 0<=cancel_poll_seconds<=.25:
            raise FanGuardError('fan.invalid_budget','Cancellation poll interval must be in [0,.25] seconds.')
        self.cancel_poll_seconds=cancel_poll_seconds;self.next_cancel_poll=float('-inf')
        if cancelled is not None and not callable(cancelled):
            raise FanGuardError('fan.invalid_budget','Cancellation must be a callback.')
        self.max_work,self.max_bits,self.max_elements=max_work,max_bits,max_elements
        self.cancelled,self.clock=cancelled,_clock
        self.started=_clock();self.deadline=self.started+max_seconds
        if deadline is not None:
            if not isfinite(deadline):raise FanGuardError('fan.invalid_budget','Deadline must be finite monotonic time.')
            self.deadline=min(self.deadline,deadline)
        self.work=0;self.peak_bits=0;self.peak_elements=0;self.checkpoints=0

    def checkpoint(self, phase, work=0, force_cancel=False):
        self.checkpoints+=1
        self.last_phase=phase
        now=self.clock()
        if self.cancelled is not None and (force_cancel or now>=self.next_cancel_poll):
            self.next_cancel_poll=now+self.cancel_poll_seconds
            if self.cancelled():raise FanGuardError('fan.cancelled',phase)
        if now>=self.deadline:
            raise FanGuardError('fan.elapsed_limit',phase,now-self.started,self.deadline-self.started)
        if work<0:raise FanGuardError('fan.invalid_budget','Work charges must not be negative.')
        if self.work+work>self.max_work:
            raise FanGuardError('fan.work_limit',phase,self.work+work,self.max_work)
        self.work+=work

    def allocation(self, shape, phase):
        if any(isinstance(n,bool) or int(n)!=n or n<0 for n in shape):
            raise FanGuardError('fan.invalid_shape',phase)
        count=prod(int(n) for n in shape)
        self.checkpoint(phase)
        if count>self.max_elements:
            raise FanGuardError('fan.allocation_limit',phase,count,self.max_elements)
        self.peak_elements=max(self.peak_elements,count)

    def inspect(self, value, phase):
        """Check all numeric leaves, with bounded traversal and periodic Esc."""
        seen=0
        def walk(x,depth=0):
            nonlocal seen
            if depth>12:raise FanGuardError('fan.invalid_shape',phase)
            if isinstance(x,np.ndarray):
                self.allocation(x.shape,phase)
                for item in x.flat:walk(item,depth+1)
            elif isinstance(x,(tuple,list)):
                if len(x)>self.max_elements:raise FanGuardError('fan.allocation_limit',phase,len(x),self.max_elements)
                for item in x:walk(item,depth+1)
            elif isinstance(x,dict):
                if len(x)>self.max_elements:raise FanGuardError('fan.allocation_limit',phase,len(x),self.max_elements)
                for item in x.values():walk(item,depth+1)
            elif isinstance(x,(F,int,np.integer,float,np.floating)):
                seen+=1
                if seen%64==1:self.checkpoint(phase)
                if isinstance(x,F):bits=max(abs(x.numerator).bit_length(),x.denominator.bit_length())
                elif isinstance(x,(int,np.integer)):bits=abs(int(x)).bit_length()
                else:
                    if not isfinite(float(x)):raise FanGuardError('fan.nonfinite_coefficient',phase)
                    n,d=float(x).as_integer_ratio();bits=max(abs(n).bit_length(),d.bit_length())
                self.peak_bits=max(self.peak_bits,bits)
                if bits>self.max_bits:raise FanGuardError('fan.fraction_bit_limit',phase,bits,self.max_bits)
                if self.work+1>self.max_work:raise FanGuardError('fan.work_limit',phase,self.work+1,self.max_work)
                self.work+=1
            elif hasattr(x,'fields') and hasattr(x,'weight_certificate'):
                walk(x.fields,depth+1);walk(x.weight_certificate,depth+1)
        walk(value)
        self.checkpoint(phase)

    def report(self):
        return dict(work_units=self.work,peak_fraction_bits=self.peak_bits,
                    peak_array_elements=self.peak_elements,checkpoints=self.checkpoints,
                    elapsed_seconds=self.clock()-self.started)


_ACTIVE_BUDGET=ContextVar('private_fan_exact_budget',default=None)


@contextmanager
def exact_work_scope(budget=None, *, cancelled=None, deadline=None):
    active=_ACTIVE_BUDGET.get()
    if active is not None:
        if (budget is not None and budget is not active) or cancelled is not None or deadline is not None:
            raise FanGuardError('fan.invalid_budget','Nested calls must share the active rebuild budget.')
        yield active
        return
    if budget is None:budget=ExactWorkBudget(cancelled=cancelled,deadline=deadline)
    elif not isinstance(budget,ExactWorkBudget) or cancelled is not None or deadline is not None:
        raise FanGuardError('fan.invalid_budget','Configure cancellation/deadline on the explicit shared budget.')
    token=_ACTIVE_BUDGET.set(budget)
    try:
        budget.checkpoint('exact rebuild entry',force_cancel=True)
        yield budget
        budget.checkpoint('exact rebuild completion',force_cancel=True)
    finally:_ACTIVE_BUDGET.reset(token)


def guard_checkpoint(phase, work=0, values=None):
    budget=_ACTIVE_BUDGET.get()
    if budget is None:raise RuntimeError('Internal exact operation requires a budget scope.')
    budget.checkpoint(phase,work)
    if values is not None:budget.inspect(values,phase)


def bounded_exact(fn):
    """Preserve positional API; add optional budget/cancelled/deadline keywords."""
    @wraps(fn)
    def guarded(*args,budget=None,cancelled=None,deadline=None,**kwargs):
        with exact_work_scope(budget,cancelled=cancelled,deadline=deadline) as work:
            work.inspect((args,kwargs),fn.__name__+' inputs')
            result=fn(*args,**kwargs)
            work.inspect(result,fn.__name__+' result')
            return result
    return guarded


def _guard_tensor_contract(matrix,data,phase):
    """Small exact contraction, checking cancellation/bit growth per term."""
    matrix,data=np.asarray(matrix,dtype=object),np.asarray(data,dtype=object)
    if matrix.shape[1]!=data.shape[0]:raise ValueError('Tensor contraction dimensions differ.')
    out=_zeros((matrix.shape[0],)+data.shape[1:])
    for i in range(len(matrix)):
        for k in range(matrix.shape[1]):
            if matrix[i,k]==0:continue
            guard_checkpoint(phase,2*np.size(data[k]),values=matrix[i,k])
            out[i]+=matrix[i,k]*data[k]
            guard_checkpoint(phase,values=out[i])
    return out




def _zeros(shape):
    _ACTIVE_BUDGET.get().allocation(shape,'exact zero allocation')
    z=np.empty(shape,dtype=object);z.fill(F(0));return z


def derivative(a,k=1):
    a=np.asarray(a,dtype=object)
    if not isinstance(k,(int,np.integer)) or not 0<=k<=120:raise FanGuardError('fan.derivative_order_limit','Polynomial differentiation',k,120)
    for _ in range(k):
        guard_checkpoint('polynomial differentiation',a.size,values=a)
        a=np.asarray([a[i]*i for i in range(1,len(a))],dtype=object) if len(a)>1 else _zeros((1,)+a.shape[1:])
    return a


def value(a,s):
    out=_zeros(np.asarray(a).shape[1:])
    for x in a[::-1]:
        guard_checkpoint('polynomial Horner evaluation',2*np.size(out),values=out)
        out=out*s+x
    return out


def add(a,b):
    a,b=np.asarray(a,dtype=object),np.asarray(b,dtype=object)
    shape=tuple(max(x,y) for x,y in zip(a.shape,b.shape));z=_zeros(shape)
    guard_checkpoint('polynomial addition',a.size+b.size)
    z[tuple(slice(0,x) for x in a.shape)]+=a;z[tuple(slice(0,x) for x in b.shape)]+=b
    return z


@lru_cache(maxsize=8)
def _endpoint_inverse(m):
    n=2*m+1
    a=[[F(factorial(j),factorial(j-k)) for j in range(m+1,n+1)]+[F(int(k==r)) for r in range(m+1)] for k in range(m+1)]
    for k in range(m+1):
        pivot=next(i for i in range(k,m+1) if a[i][k]);a[k],a[pivot]=a[pivot],a[k]
        q=a[k][k];a[k]=[v/q for v in a[k]]
        for i in range(m+1):
            if i!=k:
                q=a[i][k];a[i]=[v-q*w for v,w in zip(a[i],a[k])]
    return np.asarray([r[m+1:] for r in a],dtype=object)


def hermite_endpoint_jets(left,right):
    """Exact power coefficients for normalized [0,1] endpoint derivatives."""
    left,right=np.asarray(left,dtype=object),np.asarray(right,dtype=object)
    if left.shape!=right.shape or not 1<=len(left)<=5:raise ValueError('Matching derivative orders zero through at most four are required.')
    m=len(left)-1;out=_zeros((2*m+2,)+left.shape[1:])
    for j in range(m+1):
        guard_checkpoint('endpoint Hermite initial coefficient',np.size(left[j]))
        out[j]=left[j]/factorial(j)
        guard_checkpoint('endpoint Hermite initial coefficient',values=out[j])
    rhs=right.copy()
    for k in range(m+1):
        for j in range(k,m+1):
            guard_checkpoint('endpoint Hermite right residual',2*np.size(rhs[k]))
            rhs[k]-=out[j]*F(factorial(j),factorial(j-k))
            guard_checkpoint('endpoint Hermite right residual',values=rhs[k])
    out[m+1:]=_guard_tensor_contract(_endpoint_inverse(m),rhs,'endpoint Hermite solve')
    return out


def directional_jet(taylor,a,b,i,j):
    """D_a^i D_b^j X from ordinary physical-coordinate derivatives at a point."""
    if i+j>4:raise ValueError('Taylor jet is bounded at total order four.')
    out=_zeros(np.asarray(taylor[0,0]).shape)
    for r in range(i+1):
        for s in range(j+1):
            guard_checkpoint('directional Taylor jet',8*np.size(out),values=out)
            out+=comb(i,r)*comb(j,s)*a[0]**r*a[1]**(i-r)*b[0]**s*b[1]**(j-s)*np.asarray(taylor[r+s,i+j-r-s],dtype=object)
    return out


def endpoint_fields(taylor,tangent,cross):
    return tuple(np.asarray([directional_jet(taylor,tangent,cross,k,j) for k in range(5-j)],dtype=object) for j in range(3))


def shared_fields(start_taylor,end_taylor,tangent,cross,end_tangent=None,end_cross=None):
    """Return polynomial C9,D7,A5 from compatible endpoint Taylor jets."""
    start=endpoint_fields(start_taylor,tangent,cross)
    end=endpoint_fields(end_taylor,tangent if end_tangent is None else end_tangent,cross if end_cross is None else end_cross)
    return tuple(hermite_endpoint_jets(a,b) for a,b in zip(start,end))


def reverse_parameter(p):
    if len(p)>121:raise FanGuardError('fan.degree_limit','Intermediate parameter reversal',len(p)-1,120)
    out=_zeros(p.shape)
    for i,x in enumerate(p):
        for k in range(i+1):
            guard_checkpoint('parameter reversal',3*np.size(x),values=out[k])
            out[k]+=x*comb(i,k)*(-1)**k
    return out


def multiply_scalar(a,p):
    a=np.asarray(a,dtype=object)
    if a.ndim==0:a=a.reshape(1)
    p=np.asarray(p,dtype=object)
    if p.ndim==0:p=p.reshape(1)
    if len(a)+len(p)-2>120:raise FanGuardError('fan.degree_limit','Intermediate scalar polynomial multiplication',len(a)+len(p)-2,120)
    guard_checkpoint('scalar polynomial multiplication estimate',2*len(a)*p.size)
    out=_zeros((len(a)+len(p)-1,)+p.shape[1:])
    for i,x in enumerate(a):
        guard_checkpoint('scalar polynomial multiplication',2*p.size,values=out[i:i+len(p)])
        out[i:i+len(p)]+=x*p
        guard_checkpoint('scalar polynomial multiplication',values=out[i:i+len(p)])
    return out


def transport_fields(fields,alpha,beta,gamma=F(0),delta=F(0),reverse=False):
    """r=alpha(s)*t+gamma(s)*t²/2, s_new=z+beta(s)*t+delta(s)*t²/2.

    Maps may be scalars or power-coefficient vectors. They must be fixed in h
    for the quadratic cache proof. For reverse=True canonical s=1-z on the
    seam; form all cross derivatives in canonical s, then compose with 1-z.
    Nonzero alpha throughout the edge is a separate required chart check.
    """
    C,D,A=fields
    d=add(multiply_scalar(alpha,D),multiply_scalar(beta,derivative(C)))
    a=add(add(multiply_scalar(multiply_scalar(alpha,alpha),A),
              2*multiply_scalar(multiply_scalar(alpha,beta),derivative(D))),
          multiply_scalar(multiply_scalar(beta,beta),derivative(C,2)))
    a=add(add(a,multiply_scalar(gamma,D)),multiply_scalar(delta,derivative(C)))
    result=(C,d,a)
    return tuple(reverse_parameter(p) for p in result) if reverse else result


def tensor_c2_boolean_sum(left,right,bottom,top):
    """Exact polynomial tensor patch with supplied compatible boundary 2-jets.

    left/right are functions of v with positive-u cross derivatives;
    bottom/top are functions of u with positive-v cross derivatives.
    Reject inconsistent 3x3 corner jets rather than averaging them.
    """
    sides=[tuple(np.asarray(p,dtype=object) for p in x) for x in (left,right,bottom,top)]
    left,right,bottom,top=sides
    if any(len(side)!=3 for side in sides):raise ValueError('Exactly three jets per boundary are required.')
    du=max(5,max(len(p)-1 for side in (bottom,top) for p in side));dv=max(5,max(len(p)-1 for side in (left,right) for p in side))
    if max(du,dv)>40:raise FanGuardError('fan.degree_limit','C2 tensor assembly',max(du,dv),40)
    if (du+1)*(dv+1)>1681:raise FanGuardError('fan.control_count_limit','C2 tensor assembly',(du+1)*(dv+1),1681)
    for uedge,vertical in enumerate((left,right)):
        for vedge,horizontal in enumerate((bottom,top)):
            for i in range(3):
                for j in range(3):
                    a=value(derivative(vertical[i],j),F(vedge));b=value(derivative(horizontal[j],i),F(uedge))
                    if not np.array_equal(a,b):raise ValueError('Incompatible tensor corner jet at (%d,%d), derivative (%d,%d).'%(uedge,vedge,i,j))
    def padded_fields(*fields):
        degree=max(len(p) for f in fields for p in f);shape=(degree,)+fields[0][0].shape[1:]
        return [np.asarray([add(p,_zeros(shape)) for p in f],dtype=object) for f in fields]
    L,R=padded_fields(left,right);B,T=padded_fields(bottom,top)
    hu=hermite_endpoint_jets(L,R)
    hv=np.moveaxis(hermite_endpoint_jets(B,T),0,1)
    endpoint=[]
    for vertical in (left,right):
        endpoint.append(np.asarray([hermite_endpoint_jets([value(derivative(p,j),F(0)) for j in range(3)], [value(derivative(p,j),F(1)) for j in range(3)]) for p in vertical],dtype=object))
    intersection=hermite_endpoint_jets(*endpoint)
    return add(add(hu,hv),-intersection)


def power_to_bernstein_tensor(power,degree_u=None,degree_v=None):
    """Exact polynomial conversion/elevation, with bounded tensor dimensions."""
    p=np.asarray(power,dtype=object);nu,nv=p.shape[0]-1,p.shape[1]-1
    du=nu if degree_u is None else int(degree_u);dv=nv if degree_v is None else int(degree_v)
    if not nu<=du<=40 or not nv<=dv<=40 or (du+1)*(dv+1)>16384:
        raise FanGuardError('fan.degree_limit','Tensor Bernstein conversion degree budget exceeded; no truncation is allowed.',max(du,dv),40)
    bu=np.asarray([[F(comb(i,k),comb(du,k)) if k<=i else F(0) for k in range(nu+1)] for i in range(du+1)],dtype=object)
    bv=np.asarray([[F(comb(j,k),comb(dv,k)) if k<=j else F(0) for k in range(nv+1)] for j in range(dv+1)],dtype=object)
    guard_checkpoint('tensor Bernstein conversion estimate',2*((du+1)*(nu+1)*(nv+1)+(dv+1)*(nv+1)*(du+1))*prod(p.shape[2:]))
    first=_guard_tensor_contract(bu,p,'tensor Bernstein u conversion')
    second=_guard_tensor_contract(bv,np.moveaxis(first,1,0),'tensor Bernstein v conversion')
    return np.moveaxis(second,0,1)


def tensor_c2_homogeneous_patch(left,right,bottom,top,weight_power):
    """Assemble already-homogenized 2-jets and certify positive Bernstein W.

    This convenience wrapper excludes interior weight bubbles. General rational
    construction should interpolate XYZ and append separately verified W.
    Here the supplied weight polynomial must match
    the assembled fourth coordinate exactly. A positive Bernstein control net
    certifies W>0 on the whole patch. Failure is conservative; no weight is
    snapped, flattened, averaged, or replaced.
    """
    p=tensor_c2_boolean_sum(left,right,bottom,top)
    if p.shape[-1]!=4:raise ValueError('Four-dimensional homogeneous fields are required.')
    w=np.asarray(weight_power,dtype=object)
    residual=add(p[:,:,3],-w)
    if any(x!=0 for x in residual.flat):raise ValueError('Supplied W does not match homogeneous boundary-jet assembly.')
    cp=power_to_bernstein_tensor(p)
    minimum=min(cp[:,:,3].flat)
    if minimum<=0:raise ValueError('Positive-weight Bernstein certificate failed.')
    return {'power':p,'homogeneous_cp':cp,'degree_u':cp.shape[0]-1,'degree_v':cp.shape[1]-1,
            'minimum_weight':minimum,'positive_weight_certificate':'strictly_positive_Bernstein_coefficients'}


# All public and allocation primitives participate in one nested budget.
for _name in ('_zeros','derivative','value','add','_endpoint_inverse',
              'hermite_endpoint_jets','directional_jet','endpoint_fields',
              'shared_fields','reverse_parameter','multiply_scalar',
              'transport_fields','tensor_c2_boolean_sum',
              'power_to_bernstein_tensor','tensor_c2_homogeneous_patch'):
    globals()[_name]=bounded_exact(globals()[_name])
