"""Private callable local fan constructor. No source data or file I/O.

Inputs are an authoritative polynomial old Bezier cell, normalized source-derived
layout, and immutable native lower-owner jets/outward co-normal. This candidate
is not production acceptance. Every call rebuilds exact rational fields.
"""
from fractions import Fraction as F
import time
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

def value2(poly,x,y):return fj.value(fj.value(poly,x),y)
def derivative2(poly,i,j):return np.moveaxis(fj.derivative(np.moveaxis(fj.derivative(poly,i),1,0),j),0,1)
def compose1(a,lo,hi):
    out=fj._zeros((1,)+a.shape[1:])
    for c in a[::-1]:
        out=fj.multiply_scalar([lo,hi-lo],out);out[0]+=c
    # The initial zero multiplication can retain one harmless leading zero.
    while len(out)>1 and not any(x!=0 for x in np.asarray(out[-1]).flat):out=out[:-1]
    return out

def fade(a,b):return np.asarray([a,0,0,10*(b-a),-15*(b-a),6*(b-a)],dtype=object)
def homogeneous(fields):
    out=[]
    for j,a in enumerate(fields):
        h=fj._zeros((len(a),4));h[:,:3]=a
        if j==0:h[0,3]=1
        out.append(h)
    return fr.RationalEdgeJet(tuple(out),np.asarray([F(1)]))

def cross(a,b):return np.array([a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],dtype=object)
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def solve2(a,b,target):
    candidates=[(abs(a[i]*b[j]-a[j]*b[i]),i,j) for i in range(len(a)) for j in range(i+1,len(a))]
    _,i,j=max(candidates)
    det=a[i]*b[j]-a[j]*b[i]
    if not det:raise ValueError('Singular exact tangent frame.')
    x=(target[i]*b[j]-target[j]*b[i])/det;y=(a[i]*target[j]-a[j]*target[i])/det
    if not np.array_equal(x*a+y*b,target):raise ValueError('Target tangent/acceleration is outside its exact declared frame.')
    return x,y

value=lambda c,t:fj.value(c,F(t))
jet=lambda c,t,d:fj.value(fj.derivative(c,d),F(t))
def check_corners(fields):
    left,right,bottom,top=fields
    for ui,vert in enumerate((left,right)):
        for vi,horiz in enumerate((bottom,top)):
            for i in range(3):
                for j in range(3):
                    assert np.array_equal(jet(vert[i],vi,j),jet(horiz[j],ui,i)),(ui,vi,i,j)

def coons_power(fields):
    L,R,B,T=[x[0] for x in fields];nu=max(2,len(B),len(T));nv=max(2,len(L),len(R));out=fj._zeros((nu,nv,3))
    out[0,:len(L)]+=L;out[1,:len(L)]-=L;out[1,:len(R)]+=R
    out[:len(B),0]+=B;out[:len(B),1]-=B;out[:len(T),1]+=T
    p00=value(B,0);p10=value(B,1);p01=value(T,0);p11=value(T,1)
    out[0,0]-=p00;out[1,0]-=p10-p00;out[0,1]-=p01-p00;out[1,1]-=p11-p10-p01+p00
    return out

def tensor_grid(cp,x):
    sk=_runtime_module('skin_kernel')
    pu,pv=cp.shape[0]-1,cp.shape[1]-1
    BU=sk.BSpline([0.]*(pu+1)+[1.]*(pu+1),np.eye(pu+1),pu)
    BV=sk.BSpline([0.]*(pv+1)+[1.]*(pv+1),np.eye(pv+1),pv)
    U,V=BU(x),BV(x);Ud,Vd=BU(x,nu=1),BV(x,nu=1)
    return tuple(np.einsum('ia,jb,abc->ijc',a,b,cp,optimize=True) for a,b in ((U,V),(Ud,V),(U,Vd)))

def mul_tensor_u(a,t):
    out=fj._zeros((len(a)+len(t)-1,t.shape[1],3))
    for i,k in enumerate(a):out[i:i+len(t)]+=k*t
    return out

def mul_tensor(a,b,t):return np.moveaxis(mul_tensor_u(b,np.moveaxis(mul_tensor_u(a,t),1,0)),0,1)



def descriptor(cp,side,piece,knots_v=None):
    cp=np.asarray(cp,float);pu,pv=cp.shape[0]-1,cp.shape[1]-1
    if knots_v is not None:pv=len(knots_v)-cp.shape[1]-1
    if max(pu,pv)>40 or cp.shape[0]*cp.shape[1]>16384:raise ValueError('Fan control budget exceeded.')
    if not np.isfinite(cp).all() or np.min(cp[:,:,3])<=0:raise ValueError('Invalid fan weights/control points.')
    return dict(degree_u=pu,degree_v=pv,knots_u=[0.]*(pu+1)+[1.]*(pu+1),knots_v=knots_v or [0.]*(pv+1)+[1.]*(pv+1),homogeneous_cp=cp.tolist(),domain=[[0.,1.],[0.,1.]],kind='fan_prototype',side=side,piece=piece)


@fj.bounded_exact
def build_corner(cell_cp,layout,native_normal,native_operator,outward,side=0,h=1.,cancelled=None,native_source_record=None,native_source_v_interval=None,native_lower_record=None,native_lower_v_interval=None,native_lower_u_end=1,native_lower_uv_endpoints=None):
    """Rebuild three quads from supplied native-derived records.

    layout contains fixed normalized cell-coordinate rays and radial_speed.
    The caller owns native trim evidence and complete role-based validation.
    """
    START=time.monotonic()
    def check():
        if cancelled is not None and cancelled():raise InterruptedError('Fan construction cancelled.')
    check()
    cp=np.asarray(cell_cp,float)
    if cp.ndim!=3 or cp.shape[2]!=4 or not np.all(cp[:,:,3]==1):raise ValueError('This bounded corner route requires an exact unit-weight old cell.')
    exact=np.vectorize(lambda x:F(float(x)),otypes=[object])(cp[:,:,:3])
    p=fr.bernstein_to_power(exact)
    p=np.moveaxis(fr.bernstein_to_power(np.moveaxis(p,1,0)),0,1)
    derivatives={(i,j):derivative2(p,i,j) for i in range(5) for j in range(5-i)}
    def taylor(xy):return {(i,j):value2(q,*xy) for (i,j),q in derivatives.items()}

    def trace_along_u(v,a,b,cross):
        fields=[]
        for j in range(3):
            coeff=fj.value(np.moveaxis(derivative2(p,0,j),1,0),v)*cross**j
            fields.append(compose1(coeff,a,b))
        return tuple(fields)
    def trace_along_v(u,a,b,cross):
        return tuple(compose1(fj.value(derivative2(p,j,0),u),a,b)*cross**j for j in range(3))
    
    
    rays={k:np.array([(x if isinstance(x,F) else F(float(x))) for x in v],dtype=object) for k,v in layout["normalized_rays"].items()}
    M=(F(1,2),F(0));Q=(F(1),F(0));N=(F(1),F(1,2));FF=tuple(F(str(x)) for x in layout.get("reference_fraction",[.65,.5]))
    TM,TN,TF=taylor(M),taylor(N),taylor(FF)
    if layout.get('free_f_speed_scale'):
        speed=F(float(layout['free_f_speed_scale']))
        if not F(1)<=speed<=F(3):raise ValueError('Free F speed scale outside bounded construction range.')
        for ij in TF:
            if sum(ij):TF[ij]*=speed**sum(ij)
    if layout.get('conditioned_free_f'):
        J=np.column_stack([np.asarray(TF[1,0],float),np.asarray(TF[0,1],float)])
        q,s,vt=np.linalg.svd(J,full_matrices=False)
        if s[-1]<=0:raise ValueError('Free F tangent reference is singular.')
        s[-1]=max(s[-1],s[0]/3.)
        repaired=(q*s)@vt
        TF[1,0]=np.asarray([F(float(x)) for x in repaired[:,0]],dtype=object)
        TF[0,1]=np.asarray([F(float(x)) for x in repaired[:,1]],dtype=object)
        for ij in TF:
            if sum(ij)>=2:TF[ij]=fj._zeros((3,))
    MF=fj.shared_fields(TM,TF,rays['MF'],np.array([F(1,2),F(0)]),end_tangent=-rays['FM'],end_cross=rays['FN'])
    NF=fj.shared_fields(TN,TF,rays['NF'],np.array([F(0),F(-1,2)]),end_tangent=-rays['FN'],end_cross=rays['FM'])
    bottom=tuple(fj.reverse_parameter(x) for x in MF)
    left=tuple(fj.reverse_parameter(x) for x in NF)
    row=trace_along_u(F(0),F(1,2),F(1),F(-1,2))
    right=fj.transport_fields(row,fade(2*rays['MF'][1],F(1)),fade(-2*rays['MF'][0],F(0)))
    vertical=trace_along_v(F(1),F(0),F(1,2),F(1,2))
    top=fj.transport_fields(vertical,fade(F(1),-2*rays['NF'][0]),fade(F(0),-2*rays['NF'][1]),reverse=True)
    
    check()
    traceU=trace_along_u;traceV=trace_along_v;hom=homogeneous
    zero=np.array([F(0)]*3,dtype=object)
    # Exact unchanged old-cell source and lower position curves.
    Cs=traceV(F(0),F(1),F(0),F(1))[0] # O -> P
    Cb=traceU(F(1),F(0),F(1),F(1))[0] # O -> R
    O=value(Cs,0);B=jet(Cb,0,1);B2=jet(Cb,0,2);S1=jet(Cs,0,1);S2=jet(Cs,0,2)
    assert np.array_equal(O,value(Cb,0))
    
    native_n=np.asarray(native_normal,float);native_w=np.asarray(native_operator,float)
    outward=np.asarray(outward,float)
    desired=outward*layout['radial_speed']
    a,b=np.linalg.lstsq(np.column_stack([np.asarray(B,float),np.asarray(S1,float)]),desired,rcond=None)[0]
    a,b=F(float(a)),F(float(b));C1=a*B+b*S1
    alpha0,beta0=-a/b,1/b
    assert np.array_equal(alpha0*B+beta0*C1,S1)
    N=cross(B,C1);N2=dot(N,N)
    v=np.asarray(C1,float);native_acc=native_n*float(v@native_w@v)
    acc=np.array([F(float(x)) for x in native_acc],dtype=object)
    C2=N*dot(N,acc)/N2
    R11=N*dot(N,S2-alpha0*alpha0*B2-beta0*beta0*C2)/(2*alpha0*beta0*N2)
    residual=S2-alpha0*alpha0*B2-2*alpha0*beta0*R11-beta0*beta0*C2
    gamma0,delta0=solve2(B,C1,residual)
    start=(np.array([O,C1,C2,zero,zero]),np.array([B,R11,zero,zero]),np.array([B2,zero,zero]))
    source_report=None
    if native_source_record is not None:
        source_reconcile=_runtime_module('lower_corner_geometry')
        native_source_fields=source_reconcile.native_source_fields(native_source_record,native_source_v_interval)
        start=source_reconcile.reconcile_shared_start(native_source_fields,start,Cs,alpha0,beta0,gamma0,delta0)
    end=fj.endpoint_fields(TF,-rays['FO'],rays['FN'])
    OFfields=tuple(fj.hermite_endpoint_jets(x,y) for x,y in zip(start,end))
    alphaF,betaF=solve2(rays['FN'],-rays['FO'],rays['FM'])
    left1=fj.transport_fields(OFfields,fade(alpha0,alphaF),fade(beta0,betaF),fade(gamma0,F(0)),fade(delta0,F(0)))
    
    # Outer row P -> M stays on the original old-cell 2-jet.
    rowPM=traceU(F(0),F(0),F(1,2),F(-1,2))
    right1=fj.transport_fields(rowPM,fade(F(2),2*rays['MF'][1]),fade(F(0),-2*rays['MF'][0]))
    aF,bF=solve2(rays['FN'],-rays['FM'],-rays['FO'])
    top1=fj.transport_fields(MF,fade(F(1),aF),fade(F(0),bF),reverse=True)
    # Original source position is exact. Native whole-field reconciliation
    # below enforces the same finite attachment gates throughout the support.
    def horizontal_from_vertical(C,left,right):
        fields=[C]
        for j in (1,2):
            fields.append(fj.hermite_endpoint_jets([jet(left[i],0,j) for i in range(3)], [jet(right[i],0,j) for i in range(3)]))
        return tuple(fields)
    bottom1=horizontal_from_vertical(Cs,left1,right1)
    if native_source_record is not None:
        bottom1,source_report=source_reconcile.attach_native_source(native_source_fields,bottom1)
    
    # Lower quad inherits its other two sides from authoritative existing traces.
    aF,bF=solve2(rays['FM'],-rays['FN'],-rays['FO'])
    right3=fj.transport_fields(NF,fade(F(1),aF),fade(F(0),bF),reverse=True)
    oldNR=traceV(F(1),F(1,2),F(1),F(1,2))
    top3=fj.transport_fields(oldNR,fade(-2*rays['NF'][0],F(2)),fade(-2*rays['NF'][1],F(0)),reverse=True)
    bottom3=OFfields
    
    def vertical_from_horizontal(C,bottom,top):
        fields=[C]
        for i in (1,2):
            fields.append(fj.hermite_endpoint_jets([jet(bottom[j],0,i) for j in range(3)], [jet(top[j],0,i) for j in range(3)]))
        return tuple(fields)
    left3=vertical_from_horizontal(Cb,bottom3,top3)
    quads=[('O-P-M-F',(left1,right1,bottom1,top1)),('F-M-Q-N',(left,right,bottom,top)),('O-F-N-R',(left3,right3,bottom3,top3))]
    
    for _,fields in quads:check_corners(fields)
    check()
    if native_source_record is not None and native_lower_record is not None:
        native_lower_fields=(source_reconcile.native_linear_chart_fields(native_lower_record,*native_lower_uv_endpoints) if native_lower_uv_endpoints is not None else source_reconcile.native_source_fields(native_lower_record,native_lower_v_interval,native_lower_u_end))
        surfaces,attachment_reports=source_reconcile.assemble_native_fan(quads,native_source_fields,native_lower_fields,side,coons_power,mul_tensor,descriptor,layout.get('lower_regularization'))
        if not (layout.get("conditioned_free_f") or layout.get("free_f_speed_scale")):
            raise ValueError("A bounded common free-F conditioning policy is required.")
        f_encoding_report={"joint_free_f_construction":True,"post_encoding_point_correction":False}
        return dict(surfaces=surfaces,h=h,side=side,accepted=False,native_source_reconciliation=source_report,native_attachment_reports=attachment_reports,f_encoding_report=f_encoding_report,construction_seconds=time.monotonic()-START,exact_corner_jets=108,exact_homogeneous_C2_span_joins=True)
    NN=np.array([F(float(x)) for x in native_n],dtype=object)
    WW=np.array([[F(float(x)) for x in row] for row in native_w],dtype=object)
    C,Dlower,Alower=left3
    normalA=np.array([dot(NN,row) for row in Alower],dtype=object)
    q=fj._zeros((2*len(Dlower)-1,))
    for i in range(3):
        for j in range(3):q+=WW[i,j]*fj.multiply_scalar(Dlower[:,i],Dlower[:,j])
    delta=fj.add(normalA,-q)
    taxis=np.array([F(float(x)) for x in outward],dtype=object)
    speed=np.array([dot(taxis,row) for row in Dlower],dtype=object)
    speed_squared=fj.multiply_scalar(speed,speed)
    def normalized_residual(endpoint):
        g=[jet(speed_squared,endpoint,j) for j in range(3)]
        e=[jet(delta,endpoint,j) for j in range(3)]
        r0=e[0]/g[0];r1=(e[1]-g[1]*r0)/g[0];r2=(e[2]-2*g[1]*r1-g[2]*r0)/g[0]
        return [r0,r1,r2]
    epsilon=fj.hermite_endpoint_jets(normalized_residual(0),normalized_residual(1))
    residual=fj.multiply_scalar(speed_squared,epsilon)
    correction=fj.add(fj.add(q,residual),-normalA)
    Alower=fj.add(Alower,correction[:,None]*NN[None]/dot(NN,NN))
    left3=(C,Dlower,Alower)
    quads[2]=(quads[2][0],(left3,right3,bottom3,top3))
    
    
    B6=np.array([F(x) for x in (0,0,0,64,-192,192,-64)],dtype=object)
    B12=fj.add(2*B6,-fj.multiply_scalar(B6,B6))
    surfaces=[]
    for index in (0,1):
        name,fields=quads[index]
        assembled=fr.rational_tensor_c2_patch(*(hom(x) for x in fields))
        power=assembled['power'][:,:,:3]
        if index==0:power=fj.add(power,2*mul_tensor(B12,B12,fj.add(coons_power(fields),-power)))
        net=np.asarray(fj.power_to_bernstein_tensor(power),float)
        net=np.concatenate([net,np.ones(net.shape[:2]+(1,))],axis=2)
        surfaces.append(descriptor(net,side,name))
        check()
    C,Dlower,Alower=left3
    Cp=fj.derivative(C)
    def product(a,b):return fj.multiply_scalar(a,b)
    def poly_cross(a,b):
        return np.column_stack([product(a[:,1],b[:,2])-product(a[:,2],b[:,1]),product(a[:,2],b[:,0])-product(a[:,0],b[:,2]),product(a[:,0],b[:,1])-product(a[:,1],b[:,0])])
    def poly_dot(a,b):
        out=fj._zeros((len(a)+len(b)-1,))
        for i in range(3):out+=product(a[:,i],b[:,i])
        return out
    Bchord=jet(C,1,0)-jet(C,0,0)
    Nraw=poly_cross(Bchord[None,:],Dlower)
    W=np.array([dot(row,NN) for row in Nraw],dtype=object)
    if jet(W,0,0)<0:Nraw=-Nraw;W=-W
    P=poly_dot(Nraw,Alower)
    shear=np.array([dot(row,Bchord)/dot(Bchord,Bchord) for row in Dlower],dtype=object)
    transverse=Dlower-shear[:,None]*Bchord[None,:]
    q=fj._zeros((2*len(transverse)-1,))
    for i in range(3):
        for j in range(3):q+=WW[i,j]*product(transverse[:,i],transverse[:,j])
    g=poly_dot(transverse,transverse)
    mixed=poly_dot(Nraw,fj.derivative(Dlower))
    width_second=poly_dot(Nraw,fj.derivative(C,2))
    target_base=fj.add(fj.add(product(W,q),2*product(shear,mixed)),-product(product(shear,shear),width_second))
    resnum=fj.add(P,-target_base);resden=product(W,g)
    def ratio_jet(t):
        a=[jet(resnum,t,j) for j in range(3)];b=[jet(resden,t,j) for j in range(3)]
        v0=a[0]/b[0];v1=(a[1]-b[1]*v0)/b[0];v2=(a[2]-2*b[1]*v1-b[2]*v0)/b[0]
        return [v0,v1,v2]
    eps=fj.hermite_endpoint_jets(ratio_jet(0),ratio_jet(1))
    
    target_numerator=fj.add(target_base,product(product(W,g),eps))
    H0_xyz=product(W,C);H1_xyz=product(W,Dlower)
    H2_xyz=fj.add(product(W,Alower),fj.add(target_numerator,-P)[:,None]*NN[None])
    def hfield(x,weight=None):
        size=max(len(x),len(weight) if weight is not None else 1);h=fj._zeros((size,4));h[:len(x),:3]=x
        if weight is not None:h[:len(weight),3]=weight
        return h
    certificate=fr.power_to_bernstein(W,40)
    left_rational=fr.RationalEdgeJet((hfield(H0_xyz,W),hfield(H1_xyz),hfield(H2_xyz)),certificate)
    fields=quads[2][1]
    r=fr.rational_tensor_c2_patch(left_rational,hom(fields[1]),hom(fields[2]),hom(fields[3]))
    Pbase=r['power'][:,:,:3];weight=r['weight_power']
    # Original G0 boundary positions are unchanged; homogenize that regular
    # layout with the authoritative positive W, never blend weights by Coons.
    C0=coons_power(fields)
    # This native proof has W=W(v); assert rather than assume the general case.
    assert weight.shape[0]==1
    coonsH=np.moveaxis(mul_tensor_u(weight[0],np.moveaxis(C0,1,0)),0,1)
    change=fj.add(coonsH,-Pbase)
    B6=np.array([F(x) for x in (0,0,0,64,-192,192,-64)],dtype=object)
    Pfinal=fj.add(Pbase,F(2)*mul_tensor(B6,B6,change))
    H=fj._zeros(Pfinal.shape[:2]+(4,));H[:,:,:3]=Pfinal;H[:weight.shape[0],:weight.shape[1],3]=weight
    
    check()
    BASE=H;du,dv=BASE.shape[0]-1,BASE.shape[1]-1
    rho=F(1,4);breaks=[F(0),rho,1-rho,F(1)]
    leftjets=ratio_jet(0);rightjets=ratio_jet(1)
    compact=[fj.hermite_endpoint_jets([leftjets[k]*rho**k for k in range(3)],[F(0)]*3),np.array([F(0)],dtype=object),fj.hermite_endpoint_jets([F(0)]*3,[rightjets[k]*rho**k for k in range(3)])]
    Hcard=np.array([F(0),F(0),F(1,2),F(-3,2),F(3,2),F(-1,2)],dtype=object)
    B6=np.array([F(x) for x in (0,0,0,64,-192,192,-64)],dtype=object)
    Ppieces=[];CPpieces=[]
    for a,b,compact_eps in zip(breaks[:-1],breaks[1:],compact):
        restricted=np.moveaxis(compose1(np.moveaxis(BASE,1,0),a,b),0,1)
        deltaeps=fj.add(compact_eps,-compose1(eps,a,b))
        deltaA=product(compose1(g,a,b),deltaeps)[:,None]*NN[None]
        nativeW=compose1(weight[0],a,b)
        numerator=product(nativeW,deltaA)
        correction=Hcard[:,None,None]*numerator[None,:,:]
        bubble_correction=product(B6,Hcard)[:,None,None]*product(compose1(B6,a,b),numerator)[None,:,:]
        extra=fj.add(correction,-2*bubble_correction)
        deltaH=fj._zeros(extra.shape[:2]+(4,));deltaH[:,:,:3]=extra
        piece=fj.add(restricted,deltaH);Ppieces.append(piece)
        cp_exact=fj.power_to_bernstein_tensor(piece,du,dv);CPpieces.append(cp_exact)
    # C2 is checked exactly in homogeneous physical-V jets along the whole U edge.
    for i in range(2):
        for k in range(3):
            a=np.moveaxis(Ppieces[i],1,0);b=np.moveaxis(Ppieces[i+1],1,0)
            va=fj.value(fj.derivative(a,k),F(1))/(breaks[i+1]-breaks[i])**k
            vb=fj.value(fj.derivative(b,k),F(0))/(breaks[i+2]-breaks[i+1])**k
            # Coefficient arrays may have trailing exact zero degree elevations.
            assert all(x==0 for x in fj.add(va,-vb).flat),(i,k)
    
    joined_result=fr.assemble_c2_bernstein_spans(CPpieces,breaks,axis=1)
    joined=joined_result["homogeneous_cp"]
    kv=[float(x) for x in joined_result["knots"]]
    last=descriptor(joined,side,'O-F-N-R',kv)
    last.update(residual_support=float(rho),exact_homogeneous_C2_span_joins=True,intrinsic_C2_knots=True,exact_knot_reinsertion_verified=joined_result["exact_reinsertion_verified"])
    surfaces.append(last)
    check()
    return dict(surfaces=surfaces,h=h,side=side,accepted=False,native_source_reconciliation=source_report,construction_seconds=time.monotonic()-START,exact_corner_jets=108,exact_homogeneous_C2_span_joins=True)


def derive_layout(cell_cp,outward,cancelled=None):
    """Choose a bounded dimensionless fan layout from the h=1 native cell.

    This is a layout screen only. Full field/Jacobian/attachment validation
    remains mandatory for each evaluated h. Fixed maps belong to this baseline.
    """
    sk=_runtime_module('skin_kernel')
    def _inside(points,polygon):
        points=np.asarray(points,float);polygon=np.asarray(polygon,float);x,y=points[:,0],points[:,1];inside=np.zeros(len(points),bool)
        for a,b in zip(polygon,np.roll(polygon,-1,axis=0)):
            if a[1]==b[1]:continue
            inside^=((a[1]>y)!=(b[1]>y)) & (x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0])
        return inside
    E=sk._Evaluator(descriptor(cell_cp,0,'layout_reference'))
    uv={'O':np.array([0.,1.]),'P':np.array([0.,0.]),'Q':np.array([1.,0.]),'R':np.array([1.,1.]),'M':np.array([.5,0.]),'N':np.array([1.,.5])}
    pts={k:E.jets(*v)[0] for k,v in uv.items()};B=sk._unit(pts['R']-pts['O']);C=sk._unit(np.asarray(outward,float));origin=pts['O']
    project=lambda p:np.stack([(np.asarray(p)-origin)@B,(np.asarray(p)-origin)@C],axis=-1)
    cross2=lambda a,b:a[...,0]*b[...,1]-a[...,1]*b[...,0]
    polygon=np.asarray([project(E.jets(*(uv[a]+t*(uv[b]-uv[a])))[0]) for a,b in ('OP','PM','MQ','QN','NR','RO') for t in np.linspace(0,1,51,endpoint=False)])
    def convexity(p):
        sign=np.sign(np.sum(cross2(p,np.roll(p,-1,axis=0))))
        return min(sign*cross2(p[(i+1)%4]-p[i],p[(i+2)%4]-p[(i+1)%4]) for i in range(4))
    candidates=[]
    for fu in (.15,.25,.35,.5,.65,.75,.85):
        for fv in (.15,.25,.35,.5,.65,.75,.85):
            if cancelled is not None and cancelled():raise InterruptedError('Fan layout cancelled.')
            xy=np.array([fu,fv]);point=E.jets(*xy)[0]
            if not _inside([project(point)],polygon)[0]:continue
            pp=dict(pts,F=point)
            score=min(convexity(project(np.array([pp[k] for k in names]))) for names in (('O','P','M','F'),('F','M','Q','N'),('O','F','N','R')))
            if score<=1e-12:continue
            if not all(np.all(_inside(project(np.linspace(point,pts[k],49)[1:-1]),polygon)) for k in ('O','M','N')):continue
            candidates.append((score,xy,point))
    if not candidates:raise ValueError('No bounded visible three-sector fan layout.')
    candidates.sort(key=lambda x:x[0],reverse=True)
    _,xy,point=candidates[0];pp=dict(pts,F=point);uv2=dict(uv,F=xy);rays={}
    for a,b in ('FO','FM','FN','MF','NF'):
        j=E.jets(*uv2[a]);rays[a+b]=(.25*np.linalg.lstsq(np.column_stack([j[1],j[2]]),pp[b]-pp[a],rcond=None)[0]).tolist()
    speed=max(.5*float((point-origin)@C),.0001*np.linalg.norm(pts['Q']-origin))
    return dict(reference_fraction=xy.tolist(),normalized_rays=rays,radial_speed=speed,policy='bounded visible maximum-minimum projected convexity, fixed baseline maps, quarter chord tangent scale')
