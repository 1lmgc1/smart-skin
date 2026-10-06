"""PRIVATE PROTOTYPE: exact rational boundary 2-jets for one bounded fan cell.

Not a generic rational spline library and not production Rhino code. Inputs are
single-span homogeneous power polynomials (Qx,Qy,Qz,w), with signed, positive
chart-axis transverse derivatives. Native rational edge positions are never
sampled or fitted. Cartesian first/second derivatives are preserved by exact
homogeneous product rules, not by treating Q derivatives as X derivatives.

The positive denominator is selected explicitly as W(u,v)=A(u)B(v). Each
factor contains the smallest exactly certified power (one, two, or three) of
each distinct normalized native position weight on its opposite edge pair.
A cube clears the worst case; zero or divisible transverse weight derivatives
need less. Positive native Bernstein weights certify the factor construction. Only XYZ numerator jets are Boolean-sum interpolated;
W is appended independently, because quintic Hermite blending loses genuine
interior weight bubbles when both factors have degree greater than five.
"""
from dataclasses import dataclass
from fractions import Fraction as F
from math import comb
import numpy as np
try:
    import _smartskin_p08e1_fan_shared_jets as fj
except ModuleNotFoundError as exc:
    if exc.name != '_smartskin_p08e1_fan_shared_jets':
        raise
    import fan_shared_jets as fj


MAX_DEGREE = 40
MAX_CONTROLS = 1681


def _exact(a):
    a = np.asarray(a, dtype=object)
    if any(not isinstance(x,(F,int,np.integer,float,np.floating)) for x in a.flat):
        raise ValueError('Finite rational numeric coefficients are required; textual coefficients are not accepted.')
    fj.guard_checkpoint('exact numeric conversion',a.size)
    try:
        return np.asarray([x if isinstance(x, F) else F(x) for x in a.flat], dtype=object).reshape(a.shape)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('Finite rational numeric coefficients are required.') from exc


def _trim(a):
    a = np.asarray(a, dtype=object)
    end = len(a)
    while end > 1 and not any(x != 0 for x in np.asarray(a[end-1]).flat):
        fj.guard_checkpoint('trailing coefficient inspection',np.size(a[end-1]))
        end -= 1
    return a[:end].copy()


def _zero(a):
    return not any(x != 0 for x in np.asarray(a).flat)


def _equal(a, b):
    return _zero(fj.add(a, -np.asarray(b, dtype=object)))


def polynomial_product(a, b):
    """One scalar polynomial times a scalar or vector polynomial."""
    a, b = np.asarray(a, dtype=object), np.asarray(b, dtype=object)
    if a.ndim != 1:
        if b.ndim != 1:
            raise ValueError('One polynomial factor must be scalar.')
        return polynomial_product(b, a)
    if len(a)+len(b)-2>120:
        raise fj.FanGuardError('fan.degree_limit','Intermediate polynomial multiplication',len(a)+len(b)-2,120)
    fj.guard_checkpoint('polynomial multiplication estimate',2*len(a)*b.size)
    z = fj._zeros((len(a)+len(b)-1,)+b.shape[1:])
    for i, x in enumerate(a):
        fj.guard_checkpoint('polynomial multiplication row',2*b.size,values=z[i:i+len(b)])
        z[i:i+len(b)] += x*b
        fj.guard_checkpoint('polynomial multiplication row',values=z[i:i+len(b)])
    return _trim(z)


def exact_polynomial_quotient(a, b):
    """Exact scalar polynomial division. Nonzero remainders fail closed."""
    a, b = _trim(_exact(a)), _trim(_exact(b))
    if a.ndim != 1 or b.ndim != 1 or _zero(b):
        raise ValueError('Nonzero scalar divisor is required.')
    if len(a) < len(b):
        if _zero(a):
            return np.asarray([F(0)], dtype=object)
        raise ValueError('Native denominator does not divide chosen weight jet.')
    if max(len(a),len(b))>121:raise fj.FanGuardError('fan.degree_limit','Exact polynomial division',max(len(a),len(b))-1,120)
    fj.guard_checkpoint('exact polynomial division estimate',3*len(a)*len(b))
    remainder = a.copy()
    quotient = fj._zeros((len(a)-len(b)+1,))
    for k in range(len(quotient)-1, -1, -1):
        fj.guard_checkpoint('exact polynomial division row',3*len(b),values=remainder)
        quotient[k] = remainder[k+len(b)-1]/b[-1]
        fj.guard_checkpoint('exact polynomial quotient coefficient',values=quotient[k])
        remainder[k:k+len(b)] -= quotient[k]*b
        fj.guard_checkpoint('exact polynomial division row',values=remainder)
    if not _zero(remainder):
        raise ValueError('Native denominator does not divide chosen weight jet.')
    return _trim(quotient)


def bernstein_to_power(cp):
    """Exact conversion of one scalar/vector Bernstein span on [0,1]."""
    cp = _exact(cp)
    if cp.ndim < 1 or len(cp) < 1:
        raise ValueError('At least one Bernstein control is required.')
    n = len(cp)-1
    if n>MAX_DEGREE:raise fj.FanGuardError('fan.degree_limit','Univariate Bernstein span',n,MAX_DEGREE)
    fj.guard_checkpoint('Bernstein to power conversion estimate',3*(n+1)*(n+2)*max(1,cp.size//len(cp))//2)
    out = fj._zeros(cp.shape)
    for i, c in enumerate(cp):
        for k in range(i, n+1):
            fj.guard_checkpoint('Bernstein to power conversion term',4*np.size(c),values=out[k])
            out[k] += c*comb(n,i)*comb(n-i,k-i)*(-1)**(k-i)
            fj.guard_checkpoint('Bernstein to power conversion term',values=out[k])
    return out


def power_to_bernstein(power, degree=None):
    p = _exact(power)
    n = len(p)-1 if degree is None else int(degree)
    if n < len(_trim(p))-1 or n > MAX_DEGREE:
        raise fj.FanGuardError('fan.degree_limit','Univariate Bernstein degree budget exceeded.',n,MAX_DEGREE)
    p = _trim(p)
    out = fj._zeros((n+1,)+p.shape[1:])
    for i in range(n+1):
        for k in range(min(i,len(p)-1)+1):
            fj.guard_checkpoint('Power to Bernstein conversion term',3*np.size(p[k]),values=out[i])
            out[i] += p[k]*F(comb(i,k),comb(n,k))
            fj.guard_checkpoint('Power to Bernstein conversion term',values=out[i])
    return out


@dataclass(frozen=True)
class RationalEdgeJet:
    """Homogeneous native edge jets and a positive position-weight proof.

    Fields are functions of the edge parameter, with transverse derivatives
    in increasing patch u for left/right and increasing patch v for bottom/top.
    A supplied weight_certificate is a Bernstein representation of H0[:,3];
    it is checked exactly, never trusted as an unrelated claim of positivity.
    """
    fields: tuple
    weight_certificate: object = None

    def __post_init__(self):
        if len(self.fields) != 3:
            raise ValueError('Exactly position, first and second homogeneous jets are required.')
        fields = tuple(_exact(p) for p in self.fields)
        if any(p.ndim != 2 or p.shape[1] != 4 or not 1 <= len(p) <= MAX_DEGREE+1 for p in fields):
            raise ValueError('Each homogeneous jet must be a bounded nonempty [power,4] array.')
        w = fields[0][:,3]
        if self.weight_certificate is None:
            cp = power_to_bernstein(w, len(w)-1)
        else:
            cp = _exact(self.weight_certificate)
            if cp.ndim != 1 or not 1 <= len(cp) <= MAX_DEGREE+1 or not _equal(bernstein_to_power(cp), w):
                raise ValueError('Native Bernstein weight certificate does not match H0.')
        if min(cp) <= 0:
            raise ValueError('Strictly positive native Bernstein weights are required.')
        # Find the cheapest positive certificate without assuming that a
        # minimal-degree representation has positive Bernstein coefficients.
        for n in range(len(_trim(w))-1, len(cp)):
            candidate = power_to_bernstein(w, n)
            if min(candidate) > 0:
                cp = candidate
                break
        object.__setattr__(self, 'fields', fields)
        object.__setattr__(self, 'weight_certificate', cp)

    @property
    def weight_power(self):
        return _trim(self.fields[0][:,3])


def edge_from_bernstein(fields):
    """Construct from homogeneous Bernstein curves, already transverse jets."""
    if len(fields) != 3:
        raise ValueError('Three Bernstein jet curves are required.')
    fields = tuple(_exact(p) for p in fields)
    return RationalEdgeJet(tuple(bernstein_to_power(p) for p in fields), fields[0][:,3])


def edges_from_bernstein_tensor(homogeneous_cp):
    """Exact normalized edge 2-jets from one native Bernstein tensor span.

    Derivative controls are formed from exact native control differences
    before power conversion, so repeated transverse weight rows prove zero
    weight derivatives. This accepts one full Bezier span only; no knots,
    trimming, physical parameter scaling, or multi-span extraction is done.
    The returned order is left, right, bottom, top with positive-axis jets.
    """
    cp = _exact(homogeneous_cp)
    if cp.ndim != 3 or cp.shape[2] != 4 or not all(1 <= n <= MAX_DEGREE+1 for n in cp.shape[:2]):
        raise ValueError('A bounded homogeneous Bernstein tensor span is required.')
    if cp.shape[0]*cp.shape[1] > MAX_CONTROLS or min(cp[:,:,3].flat) <= 0:
        raise ValueError('A bounded positive-weight native Bernstein tensor span is required.')
    result=[]
    for q in (cp,np.moveaxis(cp,1,0)):
        degree=len(q)-1
        for end in (0,1):
            h0=q[0 if end==0 else -1].copy()
            h1=degree*(q[1]-q[0] if end==0 else q[-1]-q[-2]) if degree>=1 else fj._zeros(h0.shape)
            h2=degree*(degree-1)*(q[2]-2*q[1]+q[0] if end==0 else q[-1]-2*q[-2]+q[-3]) if degree>=2 else fj._zeros(h0.shape)
            result.append(edge_from_bernstein((h0,h1,h2)))
    return tuple(result)


def transport_edge(edge, alpha, beta, gamma=F(0), delta=F(0), reverse=False):
    """Apply the shared signed/sheared chart transport in homogeneous space."""
    edge = _as_edge(edge)
    transformed = fj.transport_fields(edge.fields, alpha, beta, gamma, delta, reverse)
    certificate = edge.weight_certificate[::-1].copy() if reverse else edge.weight_certificate.copy()
    return RationalEdgeJet(transformed, certificate)


def _as_edge(edge):
    return edge if isinstance(edge, RationalEdgeJet) else RationalEdgeJet(tuple(edge))


def _divides(a, b):
    """Whether scalar polynomial b divides a, with exact arithmetic only."""
    try:
        exact_polynomial_quotient(a, b)
        return True
    except fj.FanGuardError:
        raise
    except ValueError:
        return False


def minimal_weight_exponent(edge):
    """Minimal whole power of w needed for arbitrary separable W weight jets.

    With F=w^m, product-rule gauge coefficients require F/w,
    F*w1/w^2, and F*(2*w1^2-w*w2)/w^3 to be polynomials. For m=1 this
    is equivalent to w dividing both w1 and w2. For m=2 it is equivalent
    to w dividing w1^2. Otherwise m=3. These exact divisibility conditions
    include zero transverse weights and repeated factors; no tolerance or
    approximate degree cancellation is used. The claim is minimal among
    whole powers for the homogeneous gauge, not arbitrary rational gcds or
    geometry-specific numerator cancellations.
    """
    edge = _as_edge(edge)
    w, w1, w2 = (p[:,3] for p in edge.fields)
    if _divides(w1, w) and _divides(w2, w):
        return 1
    if _divides(polynomial_product(w1,w1), w):
        return 2
    return 3


def _weight_factor(edges, max_degree):
    factor = np.asarray([F(1)], dtype=object)
    certified_degree = 0
    distinct = {}
    for edge in edges:
        w = edge.weight_power / edge.weight_power[0]
        if len(w) == 1:
            continue
        key = tuple(w)
        exponent = minimal_weight_exponent(edge)
        certificate_degree = len(edge.weight_certificate)-1
        if key in distinct:
            old_exponent,old_degree = distinct[key]
            # One normalized denominator may carry different cross-weight
            # jets on its two edges. Retain the greater required exponent.
            distinct[key] = (max(exponent,old_exponent),min(certificate_degree,old_degree))
        else:
            distinct[key] = (exponent,certificate_degree)
    for key,(exponent,certificate_degree) in distinct.items():
        certified_degree += exponent*certificate_degree
        if certified_degree > max_degree:
            raise fj.FanGuardError('fan.degree_limit','Denominator-clearing degree budget exceeded before assembly.',certified_degree,max_degree)
        for _ in range(exponent):
            factor = polynomial_product(factor,np.asarray(key,dtype=object))
    return factor, certified_degree


def weight_boundary_jets(a, b):
    """Boundary homogeneous weight jets of the authoritative W=A(u)B(v)."""
    return tuple(tuple(fj.value(fj.derivative(a,k),F(end))*b for k in range(3)) for end in (0,1)) + tuple(tuple(fj.value(fj.derivative(b,k),F(end))*a for k in range(3)) for end in (0,1))


def homogenize_edge(edge, weight_jets):
    """Re-gauge a native rational edge so all three jets use supplied W jets.

    Solve W=R*w through second transverse order, then N=R*Q. The second
    product rules include both mixed terms. Exact divisibility is mandatory.
    """
    edge = _as_edge(edge)
    if len(weight_jets) != 3:
        raise ValueError('Three chosen weight jets are required.')
    h = edge.fields
    w = tuple(p[:,3] for p in h)
    chosen = tuple(_trim(_exact(p)) for p in weight_jets)
    if any(p.ndim != 1 for p in chosen):
        raise ValueError('Chosen weight jets must be scalar polynomials.')
    r = [exact_polynomial_quotient(chosen[0],w[0])]
    r.append(exact_polynomial_quotient(fj.add(chosen[1],-polynomial_product(w[1],r[0])),w[0]))
    r.append(exact_polynomial_quotient(fj.add(fj.add(chosen[2],-polynomial_product(w[2],r[0])),-2*polynomial_product(w[1],r[1])),w[0]))
    result=[]
    for k in range(3):
        n = fj._zeros((1,3))
        for j in range(k+1):
            n = fj.add(n,comb(k,j)*polynomial_product(r[j],h[k-j][:,:3]))
        out = fj._zeros((max(len(n),len(chosen[k])),4))
        out[:len(n),:3]=n
        out[:len(chosen[k]),3]=chosen[k]
        result.append(_trim(out))
    if not equivalent_rational_edge_jets(tuple(result),edge.fields):
        raise ArithmeticError('Exact native rational boundary preservation failed.')
    return tuple(result)


def equivalent_rational_edge_jets(a, b):
    """Polynomial identity certificate for a.xyz/a.w == b.xyz/b.w to order2."""
    for k in range(3):
        residual = fj._zeros((1,3))
        for j in range(k+1):
            residual = fj.add(residual, comb(k,j)*polynomial_product(b[j][:,3],a[k-j][:,:3]))
            residual = fj.add(residual,-comb(k,j)*polynomial_product(a[j][:,3],b[k-j][:,:3]))
        if not _zero(residual):
            return False
    return True


def patch_boundary_jets(power):
    """Extract exact [left,right,bottom,top] transverse 2-jets."""
    p = _exact(power)
    sides = []
    for q in (p,np.moveaxis(p,1,0)):
        for end in (F(0),F(1)):
            sides.append(tuple(fj.value(fj.derivative(q,k),end) for k in range(3)))
    return tuple(sides)


def rational_tensor_c2_patch(left,right,bottom,top, *, max_degree=MAX_DEGREE, max_controls=MAX_CONTROLS):
    """Build and exactly verify one bounded positive-weight rational fan cell.

    Corner mismatches are rejected by tensor_c2_boolean_sum. No snapping or
    averaging, source modification, point sampling, or fitted replacement is
    performed. Degree/control budgets fail before the tensor allocation.
    """
    if not 5 <= max_degree <= MAX_DEGREE or not 1 <= max_controls <= MAX_CONTROLS:
        raise ValueError('Unsupported degree/control budget.')
    edges=tuple(_as_edge(edge) for edge in (left,right,bottom,top))
    a, a_degree = _weight_factor(edges[2:],max_degree)
    b, b_degree = _weight_factor(edges[:2],max_degree)
    weight_jets = weight_boundary_jets(a,b)
    homogeneous = tuple(homogenize_edge(edge,w) for edge,w in zip(edges,weight_jets))
    du=max(5,a_degree,max(len(p)-1 for side in homogeneous[2:] for p in side))
    dv=max(5,b_degree,max(len(p)-1 for side in homogeneous[:2] for p in side))
    if max(du,dv)>max_degree:
        raise fj.FanGuardError('fan.degree_limit','Rational fan degree budget exceeded before assembly.',max(du,dv),max_degree)
    if (du+1)*(dv+1)>max_controls:
        raise fj.FanGuardError('fan.control_count_limit','Rational fan control-count budget exceeded before assembly.',(du+1)*(dv+1),max_controls)
    numerator=fj.tensor_c2_boolean_sum(*(tuple(p[:,:3] for p in side) for side in homogeneous))
    weight=fj._zeros((len(a),len(b)))
    for i,x in enumerate(a):
        fj.guard_checkpoint('authoritative weight product',len(b))
        weight[i]=x*b
        fj.guard_checkpoint('authoritative weight product',values=weight[i])
    power=fj._zeros((max(len(weight),len(numerator)),max(weight.shape[1],numerator.shape[1]),4))
    power[:numerator.shape[0],:numerator.shape[1],:3]=numerator
    power[:weight.shape[0],:weight.shape[1],3]=weight
    # Enforce actual W and all boundary jets after appending it. This also
    # checks mixed tangential derivatives algebraically, not at sample points.
    actual=patch_boundary_jets(power)
    for side_index,(got,want,native) in enumerate(zip(actual,homogeneous,edges)):
        if any(not _equal(g,w) for g,w in zip(got,want)):
            raise ArithmeticError('Exact homogeneous boundary verification failed on side %d.'%side_index)
        if not equivalent_rational_edge_jets(got,native.fields):
            raise ArithmeticError('Exact native rational boundary verification failed on side %d.'%side_index)
    cp=fj.power_to_bernstein_tensor(power,du,dv)
    minimum=min(cp[:,:,3].flat)
    if minimum<=0:
        raise ValueError('Authoritative W positive Bernstein certificate failed.')
    return {'power':power,'homogeneous_cp':cp,'degree_u':du,'degree_v':dv,
            'weight_power':weight,'weight_factors':(a,b),'weight_exponents':tuple(minimal_weight_exponent(edge) for edge in edges),'minimum_weight':minimum,
            'positive_weight_certificate':'strictly_positive_Bernstein_coefficients',
            'exact_boundary_jets':True,'homogeneous_boundary_jets':homogeneous}


# Existing calls get a bounded default; callers may pass budget= or share
# fj.exact_work_scope(...) across one complete multi-cell fan rebuild.
RationalEdgeJet.__post_init__=fj.bounded_exact(RationalEdgeJet.__post_init__)
for _name in ('_exact','_trim','_zero','_equal','polynomial_product',
              'exact_polynomial_quotient','bernstein_to_power','power_to_bernstein',
              'edge_from_bernstein','edges_from_bernstein_tensor','transport_edge',
              '_as_edge','_divides','minimal_weight_exponent','_weight_factor',
              'weight_boundary_jets','homogenize_edge','equivalent_rational_edge_jets',
              'patch_boundary_jets','rational_tensor_c2_patch'):
    globals()[_name]=fj.bounded_exact(globals()[_name])


@fj.bounded_exact
def _insert_exact_knot(cp, knots, knot, degree, axis=1):
    """One exact Boehm insertion, used only to verify bounded inverse steps."""
    q=np.moveaxis(_exact(cp),axis,0);u=list(knots);t=F(knot)
    k=max(i for i,x in enumerate(u) if x<=t)
    s=u.count(t)
    if not u[degree]<t<u[-degree-1] or s>=degree:
        raise ValueError('Only bounded interior knot insertion is supported.')
    out=fj._zeros((len(q)+1,)+q.shape[1:])
    out[:k-degree+1]=q[:k-degree+1]
    out[k-s+1:]=q[k-s:]
    for i in range(k-degree+1,k-s+1):
        alpha=(t-u[i])/(u[i+degree]-u[i])
        fj.guard_checkpoint('exact knot reinsertion row',5*np.size(q[i]),values=alpha)
        out[i]=alpha*q[i]+(1-alpha)*q[i-1]
        fj.guard_checkpoint('exact knot reinsertion row',values=out[i])
    u.insert(k+1,t)
    return np.moveaxis(out,0,axis),u


@fj.bounded_exact
def _remove_exact_knot(cp, knots, knot, degree, axis=1):
    """Inverse Boehm insertion with exact endpoint and reinsertion checks."""
    q=np.moveaxis(_exact(cp),axis,0);u=list(knots);t=F(knot)
    if t not in u:raise ValueError('The interior knot to remove is absent.')
    u.remove(t)
    k=max(i for i,x in enumerate(u) if x<=t);s=u.count(t)
    p=fj._zeros((len(q)-1,)+q.shape[1:])
    p[:k-degree+1]=q[:k-degree+1]
    p[k-s:]=q[k-s+1:]
    for i in range(k-degree+1,k-s+1):
        alpha=(t-u[i])/(u[i+degree]-u[i])
        if alpha<=0 or alpha>=1:
            raise fj.FanGuardError('fan.invalid_knot_removal','Inverse insertion has no bounded interior blend.')
        fj.guard_checkpoint('exact inverse knot insertion row',5*np.size(q[i]),values=alpha)
        candidate=(q[i]-(1-alpha)*p[i-1])/alpha
        fj.guard_checkpoint('exact inverse knot insertion row',values=candidate)
        if i==k-s and not np.array_equal(candidate,p[i]):
            raise fj.FanGuardError('fan.incompatible_c2','Exact inverse knot insertion endpoint mismatch.')
        p[i]=candidate
    out=np.moveaxis(p,0,axis)
    restored,restored_knots=_insert_exact_knot(out,u,t,degree,axis)
    if restored_knots!=list(knots) or not np.array_equal(restored,cp):
        raise fj.FanGuardError('fan.exact_reinsertion_failed','Removed knot does not reproduce every source coefficient.')
    return out,u


@fj.bounded_exact
def assemble_c2_bernstein_spans(spans, breaks, axis=1, *, max_controls=16384):
    """Assemble <=4 exact positive-weight spans with intrinsic homogeneous C2.

    Removes two copies of every internal C0 Bezier knot by inverse Boehm
    insertion; exact reinsertion must recover every coefficient at each step.
    No least-squares solve, tolerance, approximation, or source adjustment is
    used. A resulting interior multiplicity p-2 preserves C2 after storage as
    binary64, provided downstream construction preserves this knot vector.
    """
    if axis not in (0,1):raise ValueError('The assembly axis must be zero or one.')
    if not 1<=len(spans)<=4:raise fj.FanGuardError('fan.span_count_limit','Exact C2 span assembly',len(spans),4)
    if not isinstance(max_controls,int) or not 1<=max_controls<=16384:
        raise fj.FanGuardError('fan.invalid_budget','Composite control budget must be in [1,16384].')
    spans=tuple(_exact(cp) for cp in spans)
    shape=spans[0].shape
    if len(shape)!=3 or shape[-1]!=4 or any(cp.shape!=shape for cp in spans):
        raise ValueError('Identically shaped homogeneous tensor Bernstein spans are required.')
    degree=shape[axis]-1
    if not 2<=degree<=MAX_DEGREE or not 0<=shape[1-axis]-1<=MAX_DEGREE:
        raise fj.FanGuardError('fan.degree_limit','Exact C2 span assembly requires joined degree 2..40.',max(shape[:2])-1,MAX_DEGREE)
    break_values=_exact(breaks)
    if break_values.ndim!=1:raise ValueError('Span breaks must be a scalar sequence.')
    b=tuple(break_values)
    if len(b)!=len(spans)+1 or any(x>=y for x,y in zip(b,b[1:])):
        raise ValueError('One strictly increasing exact interval per span is required.')
    if any(min(cp[:,:,3].flat)<=0 for cp in spans):
        raise ValueError('Strictly positive native span weights are required.')
    initial_count=shape[1-axis]*(len(spans)*degree+1)
    final_count=shape[1-axis]*(len(spans)*degree+1-2*(len(spans)-1))
    if initial_count>max_controls:
        raise fj.FanGuardError('fan.control_count_limit','Exact C2 span assembly before allocation',initial_count,max_controls)
    # Prove C2 using the supplied nonuniform parameter intervals. These are
    # homogeneous identities, hence preserve the rational Euclidean 2-jets.
    for j in range(len(spans)-1):
        left=np.moveaxis(spans[j],axis,0);right=np.moveaxis(spans[j+1],axis,0)
        wl,wr=b[j+1]-b[j],b[j+2]-b[j+1]
        pairs=((left[-1],right[0]),
               (degree*(left[-1]-left[-2])/wl,degree*(right[1]-right[0])/wr),
               (degree*(degree-1)*(left[-1]-2*left[-2]+left[-3])/(wl*wl),
                degree*(degree-1)*(right[2]-2*right[1]+right[0])/(wr*wr)))
        for order,(a,c) in enumerate(pairs):
            fj.guard_checkpoint('exact span C2 compatibility',8*np.size(a),values=(a,c))
            if not np.array_equal(a,c):
                raise fj.FanGuardError('fan.incompatible_c2','Span join %d homogeneous derivative %d differs.'%(j,order))
    initial_shape=list(shape);initial_shape[axis]=len(spans)*degree+1
    fj._ACTIVE_BUDGET.get().allocation(initial_shape,'exact C0 concatenation')
    cuts=[spans[0]]
    for cp in spans[1:]:
        sl=[slice(None)]*3;sl[axis]=slice(1,None);cuts.append(cp[tuple(sl)])
    cp=np.concatenate(cuts,axis=axis)
    knots=[b[0]]*(degree+1)
    for knot in b[1:-1]:knots.extend([knot]*degree)
    knots.extend([b[-1]]*(degree+1))
    for knot in b[1:-1]:
        for _ in range(2):
            fj.guard_checkpoint('exact C2 knot assembly')
            cp,knots=_remove_exact_knot(cp,knots,knot,degree,axis)
    if min(cp[:,:,3].flat)<=0:
        raise fj.FanGuardError('fan.nonpositive_weight','Exact knot removal produced a nonpositive stored weight.')
    if cp.shape[0]*cp.shape[1]!=final_count:
        raise ArithmeticError('Exact C2 assembly control count is inconsistent.')
    return dict(homogeneous_cp=cp,knots=knots,degree_u=shape[0]-1,degree_v=shape[1]-1,
                assembly_axis=axis,join_multiplicity=degree-2,removed_knots=2*(len(spans)-1),
                exact_reinsertion_verified=True,exact_homogeneous_c2=True,
                minimum_weight=min(cp[:,:,3].flat))
