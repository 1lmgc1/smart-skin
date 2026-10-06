"""Bounded source-preserving lower-corner construction and integration."""
from fractions import Fraction as F
from math import comb,factorial
import numpy as np
def _runtime_module(name):
    import importlib
    alias='_smartskin_p08e1_'+name
    try:return importlib.import_module(alias)
    except ModuleNotFoundError as error:
        if error.name!=alias:raise
        return importlib.import_module(name)

fj=_runtime_module('fan_shared_jets')
fr=_runtime_module('fan_rational_fields')


def dot(a,b):return sum(x*y for x,y in zip(a,b))

def solve_frame(a,b,target):
    aa,ab,bb=dot(a,a),dot(a,b),dot(b,b);at,bt=dot(a,target),dot(b,target);det=aa*bb-ab*ab
    if not det:raise ValueError('Native source endpoint frame is singular.')
    return (bb*at-ab*bt)/det,(aa*bt-ab*at)/det


def compose(a,lo,hi):
    out=fj._zeros((1,)+a.shape[1:])
    for c in a[::-1]:out=fj.multiply_scalar([lo,hi-lo],out);out[0]+=c
    while len(out)>1 and not any(x!=0 for x in np.asarray(out[-1]).flat):out=out[:-1]
    return out


def native_source_fields(record,v_interval,u_end=0):
    """Exact native endpoint-U derivatives, with the complete polynomial V trace."""
    pu,pv=int(record['degree_u']),int(record['degree_v']);kv=record['knots_v']
    if len(set(kv))!=2 or len(record['homogeneous_cp'][0])!=pv+1:
        raise ValueError('Bounded source reconciliation requires one native V Bezier span.')
    raw=np.asarray(record['homogeneous_cp'],float)
    if raw.ndim!=3 or raw.shape[2]!=4 or raw.shape[0]*raw.shape[1]>16384 or max(pu,pv)>40 or min(pu,pv)<1 or not np.isfinite(raw).all():raise ValueError('Native source degree/control budget exceeded.')
    w=F(float(raw[0,0,3]))
    if w<=0 or not np.all(raw[:,:,3]==float(w)):raise ValueError('Native source must remain genuinely positive-weight nonrational.')
    if u_end not in (0,1):raise ValueError('Native cross endpoint must be0 or1.')
    selected=raw[:pu+1,:,:3] if u_end==0 else raw[-pu-1:,:,:3]
    cp=np.vectorize(lambda x:F(float(x)),otypes=[object])(selected)/w
    allknots=[F(float(x)) for x in record['knots_u']]
    knots=allknots[:2*pu+2] if u_end==0 else allknots[-2*pu-2:];degree=pu;out=[]
    vlow,vhigh=[F(float(x)) for x in v_interval];v0,v1=F(float(kv[0])),F(float(kv[-1]))
    lo=(vhigh-v0)/(v1-v0);hi=(vlow-v0)/(v1-v0)
    for r in range(5):
        if r<=pu:
            out.append(compose(fr.bernstein_to_power(cp[0 if u_end==0 else -1]),lo,hi))
            if r<pu:
                cp=np.asarray([degree*(cp[i+1]-cp[i])/(knots[i+degree+1]-knots[i+1]) for i in range(len(cp)-1)],dtype=object)
                knots=knots[1:-1];degree-=1
        else:out.append(fj._zeros((1,3)))
    return out


def reconcile_shared_start(native,start,source_curve,alpha,beta,gamma,delta):
    """Joint O mixed jets; original position curves are never replaced."""
    C,D,A=start;O,C1,C2=C[:3];B,R11=D[:2];B2=A[0]
    S1=fj.value(fj.derivative(source_curve),F(0));S2=fj.value(fj.derivative(source_curve,2),F(0))
    E0=fj.value(native[1],F(0));T0=fj.value(fj.derivative(native[0]),F(0))
    ac,bc=[F(float(x)) for x in solve_frame(E0,T0,C1)]
    physical={(i,j):fj.value(fj.derivative(native[i],j),F(0)) for i in range(5) for j in range(5-i)}
    # Source-chart Taylor pullback controls only NEW shared seam/mixed data.
    # The exact original source curve keeps its own unrestricted derivatives.
    J={(i,j):fj.directional_jet(physical,(F(0),F(1)),(ac,bc),i,j) for i in range(5) for j in range(5-i)}
    J[0,0]=O;J[1,0]=S1;J[2,0]=S2;J[0,1]=C1;J[0,2]=C2;J[1,1]=alpha*R11+beta*C2
    # Invert the existing source-vs-lower second-order seam map at O.
    a,b=1/alpha,-beta/alpha
    g,d=-gamma/alpha**3,gamma*beta/alpha**3-delta/alpha**2
    newC=np.asarray([J[0,k] for k in range(5)],dtype=object)
    newD=np.asarray([a*J[1,k]+b*J[0,k+1] for k in range(4)],dtype=object)
    newA=np.asarray([a*a*J[2,k]+2*a*b*J[1,k+1]+b*b*J[0,k+2]+g*J[1,k]+d*J[0,k+1] for k in range(3)],dtype=object)
    # These are free newly designed higher jets, encoded once at native
    # double precision. Shared authoritative low-order jets remain untouched.
    encode=np.vectorize(lambda x:F(float(x)),otypes=[object])
    newC[3:]=encode(newC[3:]);newD[2:]=encode(newD[2:]);newA[1:]=encode(newA[1:])
    assert np.array_equal(newD[0],B) and np.array_equal(newD[1],R11) and np.array_equal(newA[0],B2)
    return newC,newD,newA


def attach_native_source(native,target_fields,return_context=False):
    """Native full fields plus exact, reported endpoint-compatibility residuals.

    All residuals remain subject to the original finite native G2 gates; this
    function grants no failing source interval or relaxed tolerance.
    """
    Cnative,E,Aparent=native[:3];Ctarget,Dtarget,Atarget=target_fields
    jet=lambda p,t,k:fj.value(fj.derivative(p,k),F(t))
    map_end=[];endpoint_reports=[]
    for end in (0,1):
        C=[jet(Cnative,end,k) for k in range(5)];Ej=[jet(E,end,k) for k in range(4)];Aj=[jet(Aparent,end,k) for k in range(3)]
        Dj=[jet(Dtarget,end,k) for k in range(3)];Tj=[jet(Atarget,end,k) for k in range(3)]
        alpha=[];beta=[]
        for k in range(3):
            rhs=Dj[k].copy()
            for j in range(k):rhs-=comb(k,j)*(alpha[j]*Ej[k-j]+beta[j]*C[k-j+1])
            a,b=[F(float(x)) for x in solve_frame(Ej[0],C[1],rhs)];alpha.append(a);beta.append(b)
        # Local Taylor polynomials of the first map, then its geometric two-jet.
        ap=np.asarray([alpha[k]/factorial(k) for k in range(3)],dtype=object);bp=np.asarray([beta[k]/factorial(k) for k in range(3)],dtype=object)
        ep=np.asarray([Ej[k+1]/factorial(k) for k in range(3)],dtype=object);cp=np.asarray([C[k+2]/factorial(k) for k in range(3)],dtype=object);fp=np.asarray([Aj[k]/factorial(k) for k in range(3)],dtype=object)
        Q=fj.add(fj.add(fj.multiply_scalar(fj.multiply_scalar(ap,ap),fp),2*fj.multiply_scalar(fj.multiply_scalar(ap,bp),ep)),fj.multiply_scalar(fj.multiply_scalar(bp,bp),cp))
        gamma=[];delta=[]
        for k in range(3):
            rhs=Tj[k]-Q[k]*factorial(k)
            for j in range(k):rhs-=comb(k,j)*(gamma[j]*Ej[k-j]+delta[j]*C[k-j+1])
            g,d=[F(float(x)) for x in solve_frame(Ej[0],C[1],rhs)];gamma.append(g);delta.append(d)
        map_end.append((alpha,beta,gamma,delta))
    maps=[fj.hermite_endpoint_jets(map_end[0][i],map_end[1][i]) for i in range(4)]
    transported=fj.transport_fields((Cnative,E,Aparent),*maps)
    output=[Ctarget]
    for order,target in ((1,Dtarget),(2,Atarget)):
        residual_jets=[[jet(target,end,k)-jet(transported[order],end,k) for k in range(3)] for end in (0,1)]
        residual=fj.hermite_endpoint_jets(*residual_jets)
        output.append(fj.add(transported[order],residual))
        endpoint_reports.append({'field':'D' if order==1 else 'A','endpoint_residual_norms':[[float(np.linalg.norm(np.asarray(x,float))) for x in js] for js in residual_jets]})
    report={'endpoint_residuals':endpoint_reports,'native_field_degrees':[len(x)-1 for x in output],'map_encoding':'native tangent fits rounded once to binary64; exact endpoint residuals retained','policy':'every finite source station remains subject to original native G2 gates'}
    if return_context:return tuple(output),report,transported,maps
    return tuple(output),report


def piecewise_native_fields(native,target_fields,rho):
    """C2 plateau-transition residual, with exact endpoint jets and no exclusion."""
    rleft,rright=tuple(map(F,rho)) if isinstance(rho,(tuple,list)) else (F(rho),F(rho))
    if not 0<rleft<F(1,2) or not 0<rright<F(1,2):raise ValueError('Residual supports must lie in (0,1/2).')
    fields,report,transported,maps=attach_native_source(native,target_fields,return_context=True)
    alpha=maps[0];cuts=[F(0),rleft,1-rright,F(1)];m=1/(1-(rleft+rright)/2)
    C1=np.asarray([F(0),F(1),F(0),F(-6),F(8),F(-3)],dtype=object)
    C2=np.asarray([F(0),F(0),F(1,2),F(-3,2),F(3,2),F(-1,2)],dtype=object)
    C4=np.asarray([F(0),F(0),F(0),F(-4),F(7),F(-3)],dtype=object)
    C5=np.asarray([F(0),F(0),F(0),F(1,2),F(-1),F(1,2)],dtype=object)
    residual_data=[]
    for order in (1,2):
        weight=alpha if order==1 else fj.multiply_scalar(alpha,alpha)
        residual=fj.add(target_fields[order],-transported[order]);ends=[]
        for t in (F(0),F(1)):
            w=[fj.value(fj.derivative(weight,k),t) for k in range(3)];r=[fj.value(fj.derivative(residual,k),t) for k in range(3)]
            if w[0]==0:raise ValueError('Zero native transverse speed at residual endpoint.')
            y0=r[0]/w[0];y1=(r[1]-w[1]*y0)/w[0];y2=(r[2]-2*w[1]*y1-w[2]*y0)/w[0]
            ends.append((y0,y1,y2))
        residual_data.append((weight,ends))
    pieces=[]
    for index,(a,b) in enumerate(zip(cuts[:-1],cuts[1:])):
        rho=rleft if index==0 else rright
        if index==0:q=np.asarray([F(1),F(0),F(0),-m*rho,m*rho/2],dtype=object)
        elif index==1:q=np.asarray([1-m*(a-rleft/2),-m*(b-a)],dtype=object)
        else:q=compose(np.asarray([F(0),F(0),F(0),m*rho,-m*rho/2],dtype=object),F(1),F(0))
        out=[compose(target_fields[0],a,b)]
        for order,(weight,ends) in enumerate(residual_data,1):
            y0,y1=ends;profile=q[:,None]*(y0[0]-y1[0])[None,:];profile[0]+=y1[0]
            if index==0:
                profile=fj.add(profile,C1[:,None]*(rho*y0[1])[None,:]);profile=fj.add(profile,C2[:,None]*(rho*rho*y0[2])[None,:])
            if index==2:
                profile=fj.add(profile,C4[:,None]*(rho*y1[1])[None,:]);profile=fj.add(profile,C5[:,None]*(rho*rho*y1[2])[None,:])
            r=fj.multiply_scalar(compose(weight,a,b),profile)
            out.append(fj.add(compose(transported[order],a,b),r))
        pieces.append((a,b,tuple(out)))
    # Whole polynomial field joins, not just sampled values.
    for left,right in zip(pieces[:-1],pieces[1:]):
        la,lb,lf=left;ra,rb,rf=right
        for order in range(3):
            for k in range(3):
                x=fj.value(fj.derivative(lf[order],k),F(1))/(lb-la)**k;y=fj.value(fj.derivative(rf[order],k),F(0))/(rb-ra)**k
                assert np.array_equal(x,y),(order,k)
    report.update(piecewise_residual_support=[float(rleft),float(rright)],residual_policy='C2 endpoint ramps and bounded linear transition; all finite attachment gates remain active')
    return fields,pieces,report


def assemble_native_fan(quads,native_source,native_lower,side,coons_power,mul_tensor,descriptor,lower_regularization=None):
    """Polynomial native attachments, C2 piecewise residuals, fixed bubbles."""
    C1=np.asarray([F(0),F(1),F(0),F(-6),F(8),F(-3)],dtype=object)
    C2=np.asarray([F(0),F(0),F(1,2),F(-3,2),F(3,2),F(-1,2)],dtype=object)
    B6=np.asarray([F(x) for x in (0,0,0,64,-192,192,-64)],dtype=object)
    B12=fj.add(2*B6,-fj.multiply_scalar(B6,B6))
    reports=[];surfaces=[]
    f_normal=np.cross(np.asarray(fj.value(fj.derivative(quads[0][1][3][0]),F(0)),float),np.asarray(fj.value(fj.derivative(quads[0][1][0][0]),F(1)),float));f_normal/=np.linalg.norm(f_normal)
    for index,(name,original) in enumerate(quads):
        fields=list(original)
        if index==0:
            fields[2],pieces,report=piecewise_native_fields(native_source,fields[2],F(1,10));axis=0;bubble=B12;reports.append({'attachment':'source',**report})
        elif index==2:
            fields[0],pieces,report=piecewise_native_fields(native_lower,fields[0],(F(1,25),F(1,5)));axis=1;bubble=B12;reports.append({'attachment':'lower',**report})
        else:
            power=fj.tensor_c2_boolean_sum(*fields);net=fj.power_to_bernstein_tensor(power);hom=fj._zeros(net.shape[:2]+(4,));hom[:,:,:3]=net;hom[:,:,3]=1
            du,dv=hom.shape[0]-1,hom.shape[1]-1
            encoded,encoding=encode_normal_coupled(hom,du,dv,[0.]*(du+1)+[1.]*(du+1),[0.]*(dv+1)+[1.]*(dv+1),('u0','v0'),(0,0),f_normal)
            item=descriptor(encoded,side,name);item['encoding_report']=encoding;surfaces.append(item);continue
        base=fj.tensor_c2_boolean_sum(*fields);coons=coons_power(fields)
        if index==2:
            sk=_runtime_module('skin_kernel')
            n=np.cross(np.asarray(fj.value(fj.derivative(quads[0][1][2][0]),F(0)),float),np.asarray(fj.value(fj.derivative(quads[0][1][0][0]),F(0)),float));n/=np.linalg.norm(n)
            rawpieces=[]
            for a,b,target in pieces:
                raw=np.moveaxis(compose(np.moveaxis(base,1,0),a,b),0,1);oldfield=fields[0]
                d=fj.add(target[1],-compose(oldfield[1],a,b));dd=fj.add(target[2],-compose(oldfield[2],a,b))
                delta=fj.add(C1[:,None,None]*d[None,:,:],C2[:,None,None]*dd[None,:,:]);raw=fj.add(raw,delta)
                goal=np.moveaxis(compose(np.moveaxis(coons,1,0),a,b),0,1)
                rawpieces.append((a,b,raw,goal))
            def gridjets(cp):
                u=np.linspace(0,1,25);pu,pv=cp.shape[0]-1,cp.shape[1]-1
                bu=sk.BSpline([0.]*(pu+1)+[1.]*(pu+1),np.eye(pu+1),pu);bv=sk.BSpline([0.]*(pv+1)+[1.]*(pv+1),np.eye(pv+1),pv)
                return tuple(np.einsum('ia,jb,abc->ijc',A,B,cp,optimize=True) for A,B in ((bu(u,nu=1),bv(u)),(bu(u),bv(u,nu=1))))
            choices=[];candidate_data={}
            orders=(int(lower_regularization['basis_order']),) if lower_regularization else (2,3)
            for order in orders:
                one_minus=fj.add(np.asarray([F(1)],dtype=object),-B6);power=np.asarray([F(1)],dtype=object)
                for _ in range(order):power=fj.multiply_scalar(power,one_minus)
                trialbubble=fj.add(np.asarray([F(1)],dtype=object),-power);data=[]
                du=max(raw.shape[0]-1 for _,_,raw,_ in rawpieces)+len(trialbubble)-1;dv=max(raw.shape[1]-1 for _,_,raw,_ in rawpieces)+len(trialbubble)-1
                for a,b,raw,goal in rawpieces:
                    q=mul_tensor(trialbubble,compose(trialbubble,a,b),fj.add(goal,-raw));cp0=fj.power_to_bernstein_tensor(raw,du,dv);cpq=fj.power_to_bernstein_tensor(q,du,dv)
                    j0=gridjets(np.asarray(cp0,float));jq=gridjets(np.asarray(cpq,float));data.append((a,b,cp0,cpq,j0,jq))
                scalars=(F(str(lower_regularization['scale'])),) if lower_regularization else (F(1,2),F(1),F(3,2),F(2))
                for scalar in scalars:
                    minimum=min(float(np.min(np.einsum('ijk,k->ij',np.cross(j0[0]+float(scalar)*jq[0],j0[1]+float(scalar)*jq[1]),n)))/float(b-a) for a,b,_,_,j0,jq in data)
                    choices.append((minimum,order,scalar));candidate_data[order]=data
            best=max(choices,key=lambda item:item[0]);minimum,order,scalar=best
            if minimum<=0:raise ValueError('Bounded native lower interior regularization failed projected-Jacobian screen: '+str([(x[0],x[1],float(x[2])) for x in choices]))
            nets=[];breaks=[candidate_data[order][0][0]]
            for a,b,cp0,cpq,_,_ in candidate_data[order]:
                xyz=cp0+scalar*cpq;hom=fj._zeros(xyz.shape[:2]+(4,));hom[:,:,:3]=xyz;hom[:,:,3]=1;nets.append(hom);breaks.append(b)
            assembled=fr.assemble_c2_bernstein_spans(nets,breaks,axis=1);du,dv=assembled['degree_u'],assembled['degree_v']
            net,encoding=encode_normal_coupled(assembled['homogeneous_cp'],du,dv,[0.]*(du+1)+[1.]*(du+1),assembled['knots'],('v0','u1'),(1,0),f_normal)
            surfaces.append(dict(degree_u=du,degree_v=dv,knots_u=[0.]*(du+1)+[1.]*(du+1),knots_v=list(map(float,assembled['knots'])),homogeneous_cp=net.tolist(),domain=[[0.,1.],[0.,1.]],kind='fan_prototype',side=side,piece=name,exact_homogeneous_C2_span_joins=True,native_attachment_mode='whole native parent fields plus bounded endpoint reconciliation',lower_regularization=dict(basis_order=order,scale=float(scalar),minimum_screened_jacobian=minimum)))
            surfaces[-1]['encoding_report']=encoding
            reports[-1]['lower_regularization']=surfaces[-1]['lower_regularization']
            continue
        beta=F(2)

        base=fj.add(base,beta*mul_tensor(bubble,bubble,fj.add(coons,-base)))
        powers=[];breaks=[pieces[0][0]]
        for a,b,target in pieces:
            restricted=np.moveaxis(compose(np.moveaxis(base,axis,0),a,b),0,axis)
            original_field=fields[2 if axis==0 else 0]
            d=fj.add(target[1],-compose(original_field[1],a,b));dd=fj.add(target[2],-compose(original_field[2],a,b))
            if axis==0:
                correction=fj.add(d[:,None,:]*C1[None,:,None],dd[:,None,:]*C2[None,:,None]);weighted=mul_tensor(compose(bubble,a,b),bubble,correction)
            else:
                correction=fj.add(C1[:,None,None]*d[None,:,:],C2[:,None,None]*dd[None,:,:]);weighted=mul_tensor(bubble,compose(bubble,a,b),correction)
            powers.append(fj.add(restricted,fj.add(correction,-beta*weighted)));breaks.append(b)
        du=max(p.shape[0]-1 for p in powers);dv=max(p.shape[1]-1 for p in powers);nets=[]
        for p in powers:
            xyz=fj.power_to_bernstein_tensor(p,du,dv);hom=fj._zeros(xyz.shape[:2]+(4,));hom[:,:,:3]=xyz;hom[:,:,3]=1;nets.append(hom)
        assembled=fr.assemble_c2_bernstein_spans(nets,breaks,axis=axis)
        net=np.asarray(assembled['homogeneous_cp'],float);ku=[0.]*(du+1)+[1.]*(du+1);kv=[0.]*(dv+1)+[1.]*(dv+1)
        if axis==0:ku=list(map(float,assembled['knots']))
        else:kv=list(map(float,assembled['knots']))
        net,encoding=encode_normal_coupled(assembled['homogeneous_cp'],du,dv,ku,kv,('u0','v1'),(0,1),f_normal)
        surfaces.append(dict(degree_u=du,degree_v=dv,knots_u=ku,knots_v=kv,homogeneous_cp=net.tolist(),domain=[[0.,1.],[0.,1.]],kind='fan_prototype',side=side,piece=name,exact_homogeneous_C2_span_joins=True,native_attachment_mode='whole native parent fields plus bounded endpoint reconciliation',encoding_report=encoding))
    return surfaces,reports


def native_linear_chart_fields(record,uv_start,uv_end):
    """Exact source-surface fields along an affine native parameter trace.

    Both endpoints must lie in one original U and V knot span. The actual
    target trim trace stays authoritative; callers must check correspondence.
    """
    pu,pv=int(record['degree_u']),int(record['degree_v']);raw=np.asarray(record['homogeneous_cp'],float)
    if raw.ndim!=3 or raw.shape[2]!=4 or raw.shape[0]*raw.shape[1]>16384 or max(pu,pv)>40 or min(pu,pv)<1 or not np.isfinite(raw).all() or np.min(raw[:,:,3])<=0:raise ValueError('Native lower degree/control/weight budget exceeded.')
    if not np.all(raw[:,:,3]==raw[0,0,3]):raise ValueError('Nonrational native parent required.')
    cp=np.vectorize(lambda x:F(float(x)),otypes=[object])(raw);ku=[F(float(x)) for x in record['knots_u']];kv=[F(float(x)) for x in record['knots_v']]
    p0,p1=[[F(float(x)) for x in uv] for uv in (uv_start,uv_end)]
    def select_span(knots,a,b):
        unique=sorted(set(knots));hits=[(x,y) for x,y in zip(unique[:-1],unique[1:]) if x<=min(a,b) and max(a,b)<=y]
        if len(hits)!=1:raise ValueError('Native reference crosses an original knot; explicit splitting required.')
        return hits[0]
    ua,ub=select_span(ku,p0[0],p1[0]);va,vb=select_span(kv,p0[1],p1[1])
    for axis,degree,knots,ends in ((0,pu,ku,(ua,ub)),(1,pv,kv,(va,vb))):
        for t in ends:
            while knots.count(t)<degree:
                cp,knots=fr._insert_exact_knot(cp,knots,t,degree,axis)
        if axis==0:ku=knots
        else:kv=knots
    iu=max(i for i,t in enumerate(ku) if t<(ua+ub)/2);iv=max(i for i,t in enumerate(kv) if t<(va+vb)/2)
    bcp=cp[iu-pu:iu+1,iv-pv:iv+1,:3]/cp[0,0,3]
    power=fr.bernstein_to_power(bcp);power=np.moveaxis(fr.bernstein_to_power(np.moveaxis(power,1,0)),0,1)
    U=np.array([(p0[0]-ua)/(ub-ua),(p1[0]-p0[0])/(ub-ua)],dtype=object);V=np.array([(p0[1]-va)/(vb-va),(p1[1]-p0[1])/(vb-va)],dtype=object)
    def restrict(poly):
        up=[np.asarray([F(1)],dtype=object)];vp=[up[0]]
        for _ in range(poly.shape[0]-1):up.append(fj.multiply_scalar(up[-1],U))
        for _ in range(poly.shape[1]-1):vp.append(fj.multiply_scalar(vp[-1],V))
        out=fj._zeros((1,3))
        for i in range(poly.shape[0]):
            for j in range(poly.shape[1]):out=fj.add(out,fj.multiply_scalar(up[i],vp[j])[:,None]*poly[i,j][None,:])
        return out
    return [restrict(fj.derivative(power,r))/(ub-ua)**r for r in range(3)]


def encode_normal_coupled(cp_exact,pu,pv,ku,kv,internal_edges,f_corner,f_normal):
    """Round generated interior rows coherently; every boundary position stays bitwise fixed."""
    sk=_runtime_module('skin_kernel')
    cp_exact=np.asarray(cp_exact,dtype=object);encoded=np.asarray(cp_exact,float);initial=encoded.copy()
    if not np.all(encoded[:,:,3]==1):raise ValueError('Normal-coupled encoding currently requires unit weights.')
    record=dict(degree_u=pu,degree_v=pv,knots_u=list(map(float,ku)),knots_v=list(map(float,kv)),homogeneous_cp=encoded.tolist())
    ev=sk._Evaluator(record);nu,nv=encoded.shape[:2];limit=256*np.finfo(float).eps*max(1.,float(np.max(abs(encoded[:,:,:3]))))
    external=set(('u0','u1','v0','v1'))-set(internal_edges)
    def fixed(i,j):
        return (i in (0,nu-1) or j in (0,nv-1) or ('u0' in external and i<3) or ('u1' in external and i>=nu-3) or ('v0' in external and j<3) or ('v1' in external and j>=nv-3))
    def xyz(i,j):return np.array([F(float(x)) for x in encoded[i,j,:3]],dtype=object)
    def normal_at(u,v):
        jets=ev.jets(float(u),float(v));n=np.cross(jets[1],jets[2]);return n/np.linalg.norm(n)
    def round_normal(target,n,old):
        normal=np.asarray([F(float(x)) for x in n],dtype=object);nearest=np.asarray(target,float);best=nearest.copy()
        def residual(q):return abs(sum(normal[k]*(target[k]-F(float(q[k]))) for k in range(3)))
        score=residual(best)
        r=sum(normal[k]*(target[k]-F(float(nearest[k]))) for k in range(3))
        for k in range(3):
            if abs(float(normal[k]))<1e-8:continue
            candidate=nearest.copy();candidate[k]=float(F(float(nearest[k]))+r/normal[k])
            if np.max(abs(candidate-old))>limit:continue
            newscore=residual(candidate)
            if newscore<score:best,score=candidate,newscore
        if np.max(abs(best-old))>limit:return old
        return best
    for iteration in range(2):
        for edge in internal_edges:
            fj.guard_checkpoint('normal-coupled seam encoding')
            axis=0 if edge[0]=='u' else 1;at_end=edge[1]=='1';cross_count=nu if axis==0 else nv;count=nv if axis==0 else nu
            indices=[cross_count-1-i if at_end else i for i in range(3)];knots=kv if axis==0 else ku;degree=pv if axis==0 else pu
            for t in range(1,count-1):
                if t%8==0:fj.guard_checkpoint('normal-coupled seam row',work=24)
                parameter=sum(float(x) for x in knots[t+1:t+degree+1])/degree
                u,v=(float(at_end),parameter) if axis==0 else (parameter,float(at_end));n=normal_at(u,v)
                ij=lambda k:(indices[k],t) if axis==0 else (t,indices[k])
                i0,j0=ij(0);i1,j1=ij(1);i2,j2=ij(2)
                d0=xyz(i0,j0)-cp_exact[i0,j0,:3]
                target1=cp_exact[i1,j1,:3]+d0
                if not fixed(i1,j1):encoded[i1,j1,:3]=round_normal(target1,n,initial[i1,j1,:3])
                d1=xyz(i1,j1)-cp_exact[i1,j1,:3]
                target2=cp_exact[i2,j2,:3]+2*d1-d0
                if not fixed(i2,j2):encoded[i2,j2,:3]=round_normal(target2,n,initial[i2,j2,:3])
        # One common mixed-jet reference at every vertex; F is shared by all3 charts.
        for ue,ve in ((0,0),(0,1),(1,0),(1,1)):
            iu=0 if ue==0 else nu-1;jv=0 if ve==0 else nv-1;su=1 if ue==0 else -1;sv=1 if ve==0 else -1
            n=np.asarray(f_normal,float) if (ue,ve)==tuple(f_corner) else normal_at(ue,ve)
            origin_error=xyz(iu,jv)-cp_exact[iu,jv,:3]
            for a in (1,2):
                for b in (1,2):
                    i,j=iu+su*a,jv+sv*b
                    target=cp_exact[i,j,:3]+(xyz(i,jv)-cp_exact[i,jv,:3])+(xyz(iu,j)-cp_exact[iu,j,:3])-origin_error
                    if not fixed(i,j):encoded[i,j,:3]=round_normal(target,n,initial[i,j,:3])
    assert np.array_equal(encoded[0],initial[0]) and np.array_equal(encoded[-1],initial[-1]) and np.array_equal(encoded[:,0],initial[:,0]) and np.array_equal(encoded[:,-1],initial[:,-1])
    for edge in external:
        A,B=(encoded[:3],initial[:3]) if edge=='u0' else (encoded[-3:],initial[-3:]) if edge=='u1' else (encoded[:,:3],initial[:,:3]) if edge=='v0' else (encoded[:,-3:],initial[:,-3:])
        assert np.array_equal(A,B)
    return encoded,{'all_boundary_position_controls_bit_identical':True,'native_and_outer_twojet_strips_bit_identical':True,'protected_edges':sorted(external),'maximum_generated_interior_control_change':float(np.max(abs(encoded-initial))),'rounding_policy':'shared-reference normal first/second rows and additive mixed corner block; native/source positions unchanged'}


# Generated-neighbor support propagation.
from copy import deepcopy
_GEOMETRY_ALIASES=('homogeneousCP','control_points','weights')


def _descriptor_copy(record):
    """Keep one authoritative geometry representation in generated output."""
    result=deepcopy(record)
    for name in _GEOMETRY_ALIASES:result.pop(name,None)
    return result


def split_existing_v(record, support_start):
    """Split C0-or-better concatenated Bezier spans without parameter changes.

    This is deliberately bounded to this generated-strip representation. No
    fitting, knot deletion, source editing, or global assembly is performed.
    Both outputs retain their original U knots and every V knot within their
    domains. The shared V knot receives endpoint clamping, not reparameterizing.
    """
    cp=np.asarray(record['homogeneous_cp'],float);p=int(record['degree_v'])
    knots=list(record['knots_v']);breaks=sorted(set(knots));start=float(support_start)
    if start not in breaks[1:-1]:raise ValueError('Split must be an existing interior generated V knot.')
    if len(knots)!=cp.shape[1]+p+1:raise ValueError('Invalid generated V knot/control count.')
    if (knots.count(breaks[0])!=p+1 or knots.count(breaks[-1])!=p+1 or
            any(knots.count(x)!=p for x in breaks[1:-1]) or
            cp.shape[1]!=1+(len(breaks)-1)*p):
        raise ValueError('Split requires concatenated generated Bezier spans.')
    if list(record['domain'][1])!=[breaks[0],breaks[-1]]:
        raise ValueError('Generated V domain does not match its knot range.')
    cut=breaks.index(start)*p
    retained=_descriptor_copy(record);bridge=_descriptor_copy(record)
    retained['homogeneous_cp']=cp[:,:cut+1].tolist()
    retained['knots_v']=[x for x in knots if x<start]+[start]*(p+1)
    retained['domain'][1]=[breaks[0],start]
    bridge['homogeneous_cp']=cp[:,cut:].tolist()
    bridge['knots_v']=[start]*(p+1)+[x for x in knots if x>start]
    bridge['domain'][1]=[start,breaks[-1]]
    for item,role in ((retained,'retained'),(bridge,'lower_bridge')):
        item['bounded_split_role']=role
        item['bounded_split_parameter_map']='identity in original generated U,V parameters'
        if len(item['knots_v'])!=len(item['homogeneous_cp'][0])+p+1:
            raise AssertionError('Invalid split control count.')
    return retained,bridge


def propagate_neighbor_split(neighbor,bridge,support_start,cancelled=None):
    """Callable finite-support propagation plus two standalone descriptors."""
    propagated,report=propagate_neighbor(neighbor,bridge,support_start,cancelled=cancelled)
    retained,lower_bridge=split_existing_v(propagated,support_start)
    original_retained,_=split_existing_v(neighbor,support_start)
    report['retained_controls_bit_identical']=bool(np.array_equal(
        retained['homogeneous_cp'],original_retained['homogeneous_cp']))
    report['retained_knots_unchanged']=retained['knots_v']==original_retained['knots_v']
    report['parameter_maps_unchanged']=True
    if not report['retained_controls_bit_identical']:
        raise ValueError('Lower propagation escaped the declared generated support.')
    return {'retained':retained,'lower_bridge':lower_bridge},report


@fj.bounded_exact
def propagate_neighbor(neighbor,bridge,support_start):
    cp=np.asarray(neighbor['homogeneous_cp'],float);bp=np.asarray(bridge['homogeneous_cp'],float)
    if not np.all(cp[:,:,3]==1) or not np.all(bp[:,:,3]==1):raise ValueError('Bounded bridge propagation requires unit-weight generated strips.')
    pu,pv=neighbor['degree_u'],neighbor['degree_v'];bdu,bdv=bridge['degree_u'],bridge['degree_v']
    if not np.isfinite(cp).all() or not np.isfinite(bp).all():raise ValueError('Generated controls must be finite.')
    if pu<5 or pv<bdv or bdu<2 or cp.shape[0]!=pu+1 or bp.shape[:2]!=(bdu+1,bdv+1):
        raise ValueError('Propagation requires one adequate U Bezier span and a single V bridge span.')
    if list(bridge['domain'][1])!=[float(support_start),float(neighbor['domain'][1][1])]:
        raise ValueError('Bridge V domain must be the declared unchanged support parameter interval.')
    for item in (neighbor,bridge):
        for axis in ('u','v'):
            degree=int(item['degree_'+axis]);knots=list(item['knots_'+axis]);index=0 if axis=='u' else 1
            if len(knots)!=np.asarray(item['homogeneous_cp']).shape[index]+degree+1:
                raise ValueError('Generated knot/control count does not match.')
            if knots!=sorted(knots) or [knots[0],knots[-1]]!=list(item['domain'][index]):
                raise ValueError('Generated knot parameter map does not match its declared domain.')
            if knots.count(knots[0])!=degree+1 or knots.count(knots[-1])!=degree+1:
                raise ValueError('Generated endpoint knots must be clamped.')
    breaks=sorted(set(neighbor['knots_v']))
    if (float(support_start) not in breaks[1:-1] or
            any(neighbor['knots_v'].count(x)!=pv for x in breaks[1:-1]) or
            cp.shape[1]!=1+(len(breaks)-1)*pv):
        raise ValueError('Propagation requires existing concatenated Bezier V spans and an interior support knot.')
    exact=np.vectorize(lambda x:F(float(x)),otypes=[object])(cp[:,:,:3]);bexact=np.vectorize(lambda x:F(float(x)),otypes=[object])(bp[:,:,:3])
    ua,ub=map(lambda x:F(float(x)),neighbor['domain'][0]);bua,bub=map(lambda x:F(float(x)),bridge['domain'][0]);start=F(float(support_start));end=F(float(neighbor['domain'][1][1]));bu=bub-bua;nu=ub-ua
    if ua!=bub:raise ValueError('Generated interfaces do not share their declared U parameter.')
    desired=[bexact[-1],bdu*(bexact[-1]-bexact[-2])/bu,bdu*(bdu-1)*(bexact[-1]-2*bexact[-2]+bexact[-3])/bu**2]
    desired=[fr.bernstein_to_power(x) for x in desired]
    cards=[np.array([F(x) for x in (1,0,0,-10,15,-6)],object),np.array([F(x) for x in (0,1,0,-6,8,-3)],object)*nu,np.array([F(0),F(0),F(1,2),F(-3,2),F(3,2),F(-1,2)],object)*nu**2]
    breaks=sorted(set(map(lambda x:F(float(x)),neighbor['knots_v'])));spans=[];changed=[]
    for k,(a,b) in enumerate(zip(breaks[:-1],breaks[1:])):
        original=exact[:,k*pv:k*pv+pv+1]
        if b<=start:spans.append(original);continue
        if a<start:raise ValueError('Support must begin at an existing generated knot.')
        power=fr.bernstein_to_power(original);power=np.moveaxis(fr.bernstein_to_power(np.moveaxis(power,1,0)),0,1)
        for order in range(3):
            old=fj.value(fj.derivative(power,order),F(0))/nu**order
            target=compose(desired[order],(a-start)/(end-start),(b-start)/(end-start))
            delta=fj.add(target,-old);power=fj.add(power,cards[order][:,None,None]*delta[None,:,:])
        updated=fj.power_to_bernstein_tensor(power,pu,pv)
        # Authoritative new left interface is checked as a polynomial, not sampled.
        check=fr.bernstein_to_power(updated)
        for order in range(3):
            left=fj.value(fj.derivative(check,order),F(0))/nu**order
            target=compose(desired[order],(a-start)/(end-start),(b-start)/(end-start))
            target=fr.power_to_bernstein(target,pv)
            assert not any(x!=0 for x in fj.add(left,-target).flat)
        assert np.array_equal(updated[-3:],original[-3:]),'Untouched profile two-jet changed.'
        spans.append(updated);changed.append([float(a),float(b)])
    combined=np.concatenate([spans[0]]+[x[:,1:] for x in spans[1:]],axis=1);xyz=np.asarray(combined,float);newcp=np.concatenate([xyz,np.ones(xyz.shape[:2]+(1,))],axis=2)
    result=_descriptor_copy(neighbor);result['homogeneous_cp']=newcp.tolist();result['generated_bridge_support']=[float(start),float(end)]
    report={'changed_v_spans':changed,'exact_pre_encoding_left_interface_twojet_identity':True,'identity_scope':'Exact rational polynomial construction before binary64 encoding and shared-row assembly; stored output still requires all finite gates.','profile_last_three_u_rows_bit_identical':bool(np.array_equal(newcp[-3:],cp[-3:])),'lower_last_three_v_rows_bit_identical':bool(np.array_equal(newcp[:,-3:],cp[:,-3:])),'upper_first_three_v_rows_bit_identical':bool(np.array_equal(newcp[:,:3],cp[:,:3]))}
    return result,report


@fj.bounded_exact
def build_source_bridge(old_record,source_record,start):
    """Exact quintic source and generated endpoint two-jets on one native span."""
    import copy
    cp=np.asarray(old_record['homogeneous_cp'],float);pu,pv=old_record['degree_u'],old_record['degree_v']
    if cp.ndim!=3 or cp.shape[2]!=4 or cp.shape[0]*cp.shape[1]>16384 or max(pu,pv)>40 or min(pu,pv)<2 or not np.isfinite(cp).all():raise ValueError('Lower bridge degree/control budget exceeded.')
    if not np.all(cp[:,:,3]==1):raise ValueError('Lower bridge requires unit-weight generated strips.')
    breaks=sorted(set(old_record['knots_v']));end=old_record['domain'][1][1]
    if start not in breaks[1:-1] or breaks[-1]!=end:raise ValueError('Support must start at an existing interior generated row.')
    if any(old_record['knots_v'].count(t)!=pv for t in breaks[1:-1]):raise ValueError('Generated bridge needs complete original Bezier spans.')
    i=breaks.index(start);j=len(breaks)-2;exact=np.vectorize(lambda x:F(float(x)),otypes=[object])(cp[:,:,:3])
    left=exact[:,i*pv:i*pv+pv+1];right=exact[:,j*pv:j*pv+pv+1]
    length=F(float(end))-F(float(start));ll=F(float(breaks[i+1]))-F(float(start));rl=F(float(end))-F(float(breaks[-2]))
    p0,p1=left[:,0],right[:,-1];d0=pv*(left[:,1]-left[:,0])/ll;dd0=pv*(pv-1)*(left[:,2]-2*left[:,1]+left[:,0])/ll**2
    d1=pv*(right[:,-1]-right[:,-2])/rl;dd1=pv*(pv-1)*(right[:,-1]-2*right[:,-2]+right[:,-3])/rl**2
    net=np.stack([p0,p0+length*d0/5,p0+2*length*d0/5+length**2*dd0/20,p1-2*length*d1/5+length**2*dd1/20,p1-length*d1/5,p1],axis=1)
    native=native_source_fields(source_record,(start,end))[0]
    if len(native)>6:raise ValueError('Original source trace is not exactly quintic on this entire support.')
    source_cp=fr.power_to_bernstein(native,5)[::-1];net[0]=source_cp
    if not np.array_equal(fr.bernstein_to_power(net[0][::-1]),native):
        if any(x!=0 for x in fj.add(fr.bernstein_to_power(net[0][::-1]),-native).flat):raise ValueError('Original source coefficient identity failed.')
    xyz=np.asarray(net,float);hom=np.concatenate([xyz,np.ones(xyz.shape[:2]+(1,))],axis=2)
    out=_descriptor_copy(old_record);out.update(degree_v=5,knots_v=[float(start)]*6+[float(end)]*6,homogeneous_cp=hom.tolist(),domain=[list(old_record['domain'][0]),[float(start),float(end)]])
    residual=np.asarray(net[0],dtype=object)-np.vectorize(lambda x:F(float(x)),otypes=[object])(hom[0,:,:3])
    bound=max(float(sum(abs(x) for x in row)) for row in residual)
    return hom,out,dict(original_source_whole_span_coefficient_identity=True,stored_source_uniform_position_bound=bound,native_knots_preserved=True)


def _edge_guide(surface,index,edge,guide_id):
    cp=np.asarray(surface['homogeneous_cp'],float)
    if edge in ('left','right'):
        axis='v';constant=surface['domain'][0][0 if edge=='left' else 1];points=cp[0 if edge=='left' else -1];degree=surface['degree_v'];knots=surface['knots_v'];domain=surface['domain'][1]
    else:
        axis='u';constant=surface['domain'][1][0 if edge=='bottom' else 1];points=cp[:,0 if edge=='bottom' else -1];degree=surface['degree_u'];knots=surface['knots_u'];domain=surface['domain'][0]
    return dict(degree=degree,knots=list(knots),homogeneous_cp=points.tolist(),domain=list(domain),kind='lower_repair_boundary',side=surface.get('side'),piece=edge,guide_id=guide_id,varying_axis=axis,binding=dict(schema='smartskin.guide-isocurve.v1',surface_index=index,varying_axis=axis,constant_parameter=float(constant)))


def integrate_lower_corners(model,original,corners,neighbors,support):
    """Assemble retained strips and the lower charts without issuing acceptance."""
    import copy
    sk=_runtime_module('skin_kernel')
    out=copy.deepcopy(original);surfaces=[]
    for rec in original['surfaces']:
        if rec.get('kind')=='collar' and rec.get('piece')==0:
            retained,_=split_existing_v(rec,support);retained['lower_corner_support_removed']=True;surfaces.append(retained)
        elif rec.get('kind')=='collar' and rec.get('piece')==1:
            pieces=neighbors[rec['side']];surfaces.append(pieces['retained']);bridge=copy.deepcopy(pieces['lower_bridge']);bridge['kind']='lower_bridge'
            side=rec['side'];corner=corners[side];end=corner['original_v_interval'][1];mid=(support+end)/2
            bridge['boundary_roles']=dict(
                left=dict(role='retained_body_2jet',generated_body_propagation=True,counterparts=[dict(surface_id='lower:side%d:chart1'%side,edge='top',native_v_interval=[mid,support]),dict(surface_id='lower:side%d:chart2'%side,edge='top',native_v_interval=[end,mid])]),
                right=dict(role='retained_body_2jet',kind='middle',piece=0 if side==0 else 3,fixed_axis='u',fixed_parameter=0. if side==0 else 1.,parameter_interval=[support,end]),
                bottom=dict(role='retained_body_2jet',kind='collar',side=side,piece=rec['piece'],fixed_axis='v',fixed_parameter=support,parameter_interval=list(rec['domain'][0])),
                top=dict(role='native_lower',side=side,source_key=corner.get('lower_source_key')))
            surfaces.append(bridge)
        else:surfaces.append(copy.deepcopy(rec))
    for side,corner in enumerate(corners):
        for index,record in enumerate(corner['surfaces']):
            rec=copy.deepcopy(record);rec['kind']='lower_chart';rec['surface_id']='lower:side%d:chart%d'%(side,index)
            shared=lambda name:dict(role='new_shared_2jet',seam_id='lower:side%d:%s'%(side,name),parameter_interval=[0.,1.])
            retained=lambda edge,interval:dict(role='retained_body_2jet',kind='collar' if edge in ('PM','MQ') else 'lower_bridge',side=side,piece=0 if edge in ('PM','MQ') else 1,fixed_axis='v' if edge in ('PM','MQ') else 'u',fixed_parameter=support if edge in ('PM','MQ') else corner['original_u_interval'][1],parameter_interval=list(interval))
            ua,ub=corner['original_u_interval'];mid=(ua+ub)/2;end=corner['original_v_interval'][1];vmid=(support+end)/2
            roles=[dict(left=shared('OF'),right=retained('PM',(ua,mid)),bottom=dict(role='native_source_side',side=side,parameter_interval=[end,support]),top=shared('MF')),
                   dict(left=shared('NF'),right=retained('MQ',(mid,ub)),bottom=shared('MF'),top=retained('QN',(vmid,support))),
                   dict(left=dict(role='native_lower',side=side,source_key=corner.get('lower_source_key'),native_uv_endpoints=corner['lower_uv_endpoints']),right=shared('NF'),bottom=shared('OF'),top=retained('NR',(end,vmid)))][index]
            rec['boundary_roles']=roles;rec['native_parameter_map']=dict(kind='lower_three_sector_fan',chart=index,u_interval=[ua,ub],v_interval=[support,end],reference_fraction=corner['layout']['reference_fraction'])
            surfaces.append(rec)
    rows=[float(v) for v in original['network']['native_v'] if float(v)<=support];guides=[]
    for j in range(5):
        rec=next(s for s in surfaces if s.get('kind')=='middle' and s.get('piece')==min(j,3));cp=np.asarray(rec['homogeneous_cp'],float);points=cp[-1 if j==4 else 0]
        guides.append(dict(degree=rec['degree_v'],knots=list(rec['knots_v']),homogeneous_cp=points.tolist(),domain=list(rec['domain'][1]),kind='profile',piece=j))
    for row,v in enumerate(rows):
        for rec in surfaces:
            if rec.get('kind') not in ('collar','middle') or not rec['domain'][1][0]<=v<=rec['domain'][1][1]:continue
            cp=np.asarray(rec['homogeneous_cp'],float);basis=sk.BSpline(rec['knots_v'],np.eye(cp.shape[1]),rec['degree_v'])(v);points=np.einsum('j,ijc->ic',basis,cp)
            guides.append(dict(degree=rec['degree_u'],knots=list(rec['knots_u']),homogeneous_cp=points.tolist(),domain=list(rec['domain'][0]),kind='row_'+rec['kind'],row=row,native_v=v,side=rec.get('side'),piece=rec.get('piece')))
    repaired_roles=[]
    for index,rec in enumerate(surfaces):
        if rec.get('kind') in ('lower_chart','lower_bridge'):
            for edge,role in rec['boundary_roles'].items():
                if role['role']!='new_shared_2jet':repaired_roles.append(dict(surface_index=index,edge=edge,role=role['role']))
    for side in (0,1):
        chart_indices=[i for i,r in enumerate(surfaces) if r.get('kind')=='lower_chart' and r.get('side')==side]
        if len(chart_indices)!=3:raise ValueError('Incomplete lower chart guide ownership.')
        for name,a,ae,b,be in (('OF',0,'left',2,'bottom'),('MF',0,'top',1,'bottom'),('NF',1,'left',2,'right')):
            ia,ib=chart_indices[a],chart_indices[b];guide=_edge_guide(surfaces[ia],ia,ae,'lower:side%d:%s'%(side,name))
            guide['kind']='lower_corner_internal';guide['coincident_bindings']=[_edge_guide(surfaces[ib],ib,be,'unused')['binding']];guides.append(guide)
    out['network']['repaired_boundary_roles']=repaired_roles
    out['network']['parameter_map']=dict(kind='original_natural_cubic',native_v=[float(x) for x in model.tmap.x],power_coefficients=np.asarray(model.tmap.c,float).tolist(),removed_visible_rows=[float(x) for x in original['network']['native_v'] if x>support])
    out['network']['native_v']=rows;out['network']['profile_parameters']=[float(model.tmap(v)) for v in rows];out['network']['row_count']=len(rows);out['network']['density_policy']='Retained complete native-V rows plus bound local lower fan traces';out['network']['lower_corner_support']=[float(support),float(model.v1)]
    out.update(surfaces=surfaces,patches=surfaces,guides=guides,valid=False,geometry_valid=False,continuity_pass=False,experimental_commit_allowed=False,fatal=True,full_boundary_pass=False)
    out['lower_corner_reports']=[{k:v for k,v in c.items() if k!='surfaces'} for c in corners]
    out['report']=dict(checked=False,fatal=True,full_boundary_pass=False,source_modifications=0,reason='Complete repaired boundary and per-edit acceptance remain mandatory.');out['metrics']=out['report'];out.pop('attachment_proof',None)
    return out


def repair_lower_numeric(model,original,lower_records,outward_directions,h=1.,cancelled=None,f_mode='speed3'):
    """Pure numerical core. It does not establish native trim provenance."""
    sk=_runtime_module('skin_kernel')
    nf=_runtime_module('native_family')
    fg=_runtime_module('fan_geometry')
    if h!=1.:raise ValueError('The lower production baseline is fixed at h=1.')
    rows=list(original['network']['native_v'])
    if len(rows)<2:raise ValueError('Missing bounded lower support rows.')
    support=float(rows[-2]);corners=[];neighbors={}
    for side in (0,1):
        sk._check(cancelled)
        old=next(s for s in original['surfaces'] if s.get('kind')=='collar' and s.get('side')==side and s.get('piece')==0)
        neighbor=next(s for s in original['surfaces'] if s.get('kind')=='collar' and s.get('side')==side and s.get('piece')==1)
        cell,bridge,identity=build_source_bridge(old,model.spec['side_surfaces'][side],support,cancelled=cancelled);O,R=cell[0,-1,:3],cell[-1,-1,:3];lower=lower_records[side]
        native,uvO=nf._surface_uv(lower,O,model.tolerance);_,uvR=nf._surface_uv(lower,R,model.tolerance);normal,operator=nf._physical_shape_operator(native)
        layout=fg.derive_layout(cell,outward_directions[side],cancelled);layout['lower_regularization']=dict(basis_order=3,scale=.5)
        if f_mode=='conditioned':layout['conditioned_free_f']=True
        elif f_mode in ('speed2','speed3'):layout['free_f_speed_scale']=int(f_mode[-1])
        else:raise ValueError('Unsupported bounded free-F construction.')
        corner=fg.build_corner(cell,layout,normal,operator,outward_directions[side],side=side,h=h,cancelled=cancelled,native_source_record=model.spec['side_surfaces'][side],native_source_v_interval=(support,model.v1),native_lower_record=lower['surface'],native_lower_uv_endpoints=(uvO,uvR))
        corner.update(layout=layout,source_coefficient_certificate=identity,original_u_interval=old['domain'][0],original_v_interval=[support,model.v1],lower_source_key=lower.get('source_key',lower.get('key')),lower_uv_endpoints=[list(uvO),list(uvR)])
        pieces,propagation=propagate_neighbor_split(neighbor,bridge,support,cancelled=cancelled);neighbors[side]=pieces;corner['neighbor_propagation']=propagation;corners.append(corner)
    return integrate_lower_corners(model,original,corners,neighbors,support)


def repair_lower(model,original_result,h=1.,cancelled=None):
    """Require authentic native owner evidence before any production repair."""
    nf=_runtime_module('native_family')
    sk=_runtime_module('skin_kernel')
    nf.require_native_provenance(model.spec,cancelled)
    roles=model.spec['source_boundaries']['roles'];records=[];outward=[]
    for side in (0,1):
        source=roles['side%d'%side][0];end=source['traversal_domain'][1];corner=min(source['reference_corners'],key=lambda c:abs(c['edge_parameter']-end));point=np.asarray(corner['point'],float)
        hits=[(record,c) for record in roles['lower'] for c in record['reference_corners'] if np.linalg.norm(np.asarray(c['point'],float)-point)<=model.tolerance]
        if len(hits)!=1:raise ValueError('Lower native owner at the source corner is ambiguous.')
        record,ref=hits[0];witness=record['owner_side']['corners'][ref['edge_end']];inward=np.asarray(witness['inward_conormal'],float)
        records.append(record);outward.append(-sk._unit(inward))
    return repair_lower_numeric(model,original_result,records,outward,h,cancelled)
