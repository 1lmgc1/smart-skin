"""Bounded homogeneous hard-corner construction, source-derived inputs.

The isolated corner is covered by two collapsed-edge tensor charts. For every
positive physical radius the boundary two-jets obey the supplied native-side
base and corrected upper plane. The angular blend has two flat U-jets at the
unchanged artificial U=1 interface. This module contains no native model data.
"""
from fractions import Fraction as F
import math
import numpy as np
try:
    import _smartskin_p08e1_fan_shared_jets as fj
except ModuleNotFoundError as exc:
    if exc.name != "_smartskin_p08e1_fan_shared_jets":
        raise
    import fan_shared_jets as fj


@fj.bounded_exact
def obj(a):
    a=np.asarray(a,dtype=object)
    return np.vectorize(lambda x:x if isinstance(x,F) else F(str(x)),otypes=[object])(a)

@fj.bounded_exact
def mul_u(a,p):
    out=fj._zeros((len(a)+len(p)-1,)+p.shape[1:])
    for i,k in enumerate(a):
        fj.guard_checkpoint("upper polynomial multiplication",p.size,values=out)
        out[i:i+len(p)]+=k*p
    return out

@fj.bounded_exact
def mul_v(a,p):return np.moveaxis(mul_u(a,np.moveaxis(p,1,0)),0,1)

@fj.bounded_exact
def mul_tensor(a,b):
    a,b=np.asarray(a,dtype=object),np.asarray(b,dtype=object)
    out=fj._zeros((a.shape[0]+b.shape[0]-1,a.shape[1]+b.shape[1]-1)+b.shape[2:])
    for i in range(a.shape[0]):
        fj.guard_checkpoint("upper tensor multiplication",a.shape[1]*b.size,values=out)
        for j in range(a.shape[1]):
            if a[i,j]:out[i:i+b.shape[0],j:j+b.shape[1]]+=a[i,j]*b
    return out

@fj.bounded_exact
def pullback(p,kind):
    nu,nv=p.shape[:2];na=nu if kind==0 else nv
    out=fj._zeros((na,nu+nv-1)+p.shape[2:])
    for i in range(nu):
        fj.guard_checkpoint("upper triangular pullback",nv,values=out)
        for j in range(nv):out[i if kind==0 else j,i+j]+=p[i,j]
    return out

def native_exact_row(point,weights):
    """Encode a common physical vertex, recording binary64 quotient roundoff.

    Exact quotient matching is attempted; unrepresentable quotients retain the nearest product.
    Homogeneous binary64 products can still have sub-ULP projective residuals;
    report them rather than claiming an exact rational coefficient factor.
    """
    out=np.empty((len(weights),4),float)
    for i,w in enumerate(weights):
        out[i,3]=w
        for k,p in enumerate(point):
            x=float(p*w)
            for _ in range(4):
                q=x/w
                if q==p:break
                x=np.nextafter(x,math.inf if q<p else -math.inf)
            if x/w!=p:x=float(p*w) # Explicit native-tolerance collapse; measured after readback.
            out[i,k]=x
    return out


@fj.bounded_exact
def build_upper_corner(base_power,regular_numerator,upper_weight,upper_normal,side=0,position_tolerance=1e-8,numerical_scale=None):
    base=obj(base_power);regular=obj(regular_numerator);w=obj(upper_weight);normal=obj(upper_normal)
    if base.ndim!=3 or regular.ndim!=3 or base.shape[2]!=3 or regular.shape[2]!=3 or w.ndim!=1 or normal.shape!=(3,):
        raise ValueError('Invalid native hard-corner field dimensions.')
    estimated_u=max(base.shape[0]+len(w)-2,base.shape[1]-1,regular.shape[0]-1,regular.shape[1]-1)+5
    estimated_v=max(base.shape[0]+base.shape[1]+len(w)-3,regular.shape[0]+regular.shape[1]-2)+3
    if max(estimated_u,estimated_v)>40 or (estimated_u+1)*(estimated_v+1)>16384:
        raise ValueError('Hard-corner degree/control preflight exceeded.')
    norm=sum(x*x for x in normal)
    if not norm:raise ValueError('Missing native upper-plane normal.')
    # The same approved physical vertex must be common to both source curves.
    corner_gap=np.asarray(regular[0,0]/w[0]-base[0,0],float)
    canonical=base[0,0]
    if not math.isfinite(position_tolerance) or position_tolerance<=0:raise ValueError('A positive native tolerance is required.')
    magnitude=max(1.,float(np.max(abs(np.asarray(canonical,float)))))
    scale=float(numerical_scale) if numerical_scale is not None else max(1.,float(np.max(abs(np.asarray(base[1:],float)))))
    reconciliation_limit=min(position_tolerance*1e-6,max(scale*1e-12,64*np.finfo(float).eps*magnitude))
    if np.linalg.norm(corner_gap)>reconciliation_limit:raise ValueError('Native upper/source endpoints exceed numerical reconciliation bound.')
    regular=regular.copy();regular[0,0]=w[0]*canonical
    h1=obj([0,1,0,-6,8,-3]);h2=obj([0,0,F(1,2),F(-3,2),F(3,2),F(-1,2)])
    target=regular.copy()
    for order,card in ((1,h1),(2,h2)):
        derivative=regular[:,order]*math.factorial(order)
        projection=np.asarray([sum(row[k]*normal[k] for k in range(3))/norm for row in derivative],dtype=object)
        target=fj.add(target,-projection[:,None,None]*card[None,:,None]*normal[None,None,:])
    # Paired angular polynomials retain native W exactly. Their diagonal
    # transitions use alpha=-1, beta=r, gamma=2, delta=0.
    weighted_base=mul_u(w,base)
    change=fj.add(target,-weighted_base)
    # Polynomial angular blends have the exact required diagonal 2-jet
    # transport. They avoid angularly varying weights on the collapsed row.
    theta=obj([0,0,0,F(13,8),F(-3,2),F(3,8)])
    rho_right=-theta[:,None]*obj([1,-3,3,-1])[None,:]
    rho_right[0,0]+=1
    C=obj([F(1,2),F(3,2),F(-3,2),F(1,2)])
    dr=fj.derivative(C);drr=fj.derivative(C,2)
    D=fj.add(fj.multiply_scalar(obj([0,1]),dr),F(3,4)*obj([1,-3,3,-1]))
    A=fj.add(fj.add(F(3,4)*obj([1,-3,3,-1]),2*fj.multiply_scalar(obj([0,1]),fj.derivative(D))),-fj.add(fj.multiply_scalar(obj([0,0,1]),drr),2*D))
    rho_left=fj._zeros((6,4))
    for j in range(4):rho_left[:,j]=fj.hermite_endpoint_jets(obj([0,0,0]),obj([C[j],D[j],A[j]]))
    powers=[]
    for kind,rho in enumerate((rho_left,rho_right)):
        numerator=fj.add(pullback(weighted_base,kind),mul_tensor(rho,pullback(change,kind)))
        denominator=pullback(w[:,None],kind)
        H=fj._zeros((max(numerator.shape[0],denominator.shape[0]),max(numerator.shape[1],denominator.shape[1]),4))
        H[:numerator.shape[0],:numerator.shape[1],:3]=numerator
        H[:denominator.shape[0],:denominator.shape[1],3]=denominator
        powers.append(H)
    pu=max(H.shape[0]-1 for H in powers);pv=max(H.shape[1]-1 for H in powers)
    if max(pu,pv)>40 or (pu+1)*(pv+1)>16384:raise ValueError('Hard corner degree/control budget exceeded.')
    nets=[np.asarray(fj.power_to_bernstein_tensor(H,pu,pv),float) for H in powers]
    original=[cp.copy() for cp in nets]
    # Enforce the common physical point and the radial-first-order seam jet
    # identities on the actual binary64 coefficient rows, not only pre-encoding.
    origin=nets[0][0,0].copy()
    for cp in nets:cp[:,0]=origin
    for c in range(4):
        P=F(float(origin[c]));C1=F(float(nets[0][-1,1,c]));spacing=max(abs(np.spacing(float(P))),abs(np.spacing(float(C1))))
        step=F(float(spacing));integer=round((C1-P)/(pu*step));C1=P+integer*pu*step
        if F(float(C1))!=C1:raise ValueError('Pole shared radial coefficient not representable.')
        nets[0][-1,1,c]=nets[1][-1,1,c]=float(C1)
        L1=F(float(nets[0][-2,1,c]));L2=F(float(nets[0][-3,1,c]))
        Dleft=pu*(C1-L1);Dright=-Dleft+(C1-P)
        Eleft=pu*(pu-1)*(C1-2*L1+L2)
        R1=C1-Dright/pu;R2=Eleft/(pu*(pu-1))-C1+2*R1
        for index,x in ((-2,R1),(-3,R2)):
            if F(float(x))!=x:raise ValueError('Pole seam derivative control is not representable.')
            nets[1][index,1,c]=float(x)
        for cp in nets:
            q=2*F(float(cp[1,1,c]))-F(float(cp[0,1,c]))
            if F(float(q))!=q:raise ValueError('Source/upper pole angular second coefficient is not representable.')
            cp[2,1,c]=float(q)
    charts=[]
    for kind,cp in enumerate(nets):
        if np.min(cp[:,:,3])<=0:raise ValueError('Hard-corner Bernstein weights are not strictly positive.')
        charts.append(dict(kind='upper_hard_corner',side=side,piece=kind,degree_u=pu,degree_v=pv,knots_u=[0.]*(pu+1)+[1.]*(pu+1),knots_v=[0.]*(pv+1)+[1.]*(pv+1),domain=[[0.,1.],[0.,1.]],homogeneous_cp=cp.tolist(),orientation_reversed=bool(kind==1),physical_map='U=a*r,V=r' if kind==0 else 'U=r,V=a*r',collapsed_parameter_edge='v=0',approved_physical_corner_id='upper:side'+str(side),pole_binary64_jet_constraints=True,coefficient_rounding_adjustment=float(np.max(abs(original[kind]-cp)))))
    return dict(surfaces=charts,accepted=False,corner_endpoint_reconciliation=float(np.linalg.norm(corner_gap)),corner_reconciliation_limit=reconciliation_limit,minimum_weight=float(min(np.min(np.asarray(c['homogeneous_cp'])[:,:,3]) for c in charts)),policy='only approved upper source vertex is singular; every positive radius requires ordinary attachment/seam/regularity gates')


def integrate_upper_cells(body,corners):
    """Remove exactly the old first cells, retaining all original source records.

    Every new edge receives a physical boundary role and native parameter map.
    This function never creates an affirmative attachment proof.
    """
    import copy
    if len(corners)!=2:raise ValueError('Both source upper corners are required.')
    out=copy.deepcopy(body);surfaces=[];guides=copy.deepcopy(body['guides']);collapsed_bindings=[]
    first_row=float(body['network']['native_v'][0]);originals={}
    covered_roles=copy.deepcopy(body['network'].get('repaired_boundary_roles',[]))
    for source in body['surfaces']:
        if source.get('kind')!='collar' or source.get('piece')!=0:
            surfaces.append(copy.deepcopy(source));continue
        side=source['side'];originals[side]=source;p=source['degree_v']
        if not source['domain'][1][0]<first_row<source['domain'][1][1]:raise ValueError('Missing original first native V cell.')
        interior=sorted(set(source['knots_v']))
        if len(interior)<3 or interior[1]!=first_row:raise ValueError('The first source V cell is not the declared corner support.')
        trimmed=copy.deepcopy(source);cp=np.asarray(source['homogeneous_cp'],float)
        trimmed['homogeneous_cp']=cp[:,p:].tolist();trimmed['knots_v']=[first_row]+[k for k in source['knots_v'] if k>=first_row]
        trimmed['domain'][1][0]=first_row;trimmed['upper_corner_cell_removed']=True
        for key in ('homogeneousCP','control_points','weights'):trimmed.pop(key,None)
        if len(trimmed['knots_v'])!=len(trimmed['homogeneous_cp'][0])+p+1:raise ValueError('Corner removal knot/control mismatch.')
        surfaces.append(trimmed)
    if set(originals)!={0,1}:raise ValueError('Missing or duplicate original corner collars.')
    for side,corner in enumerate(corners):
        old=originals[side];ua,ub=old['domain'][0];v0=old['domain'][1][0]
        for chart,source in enumerate(corner['surfaces']):
            patch=copy.deepcopy(source);patch['surface_id']='upper:side%d:chart%d'%(side,chart)
            shared=dict(role='new_shared_2jet',seam_id='upper:side%d:diagonal'%side,parameter_interval=[0.,1.])
            collapsed=dict(role='approved_source_vertex',corner_id='upper:side%d'%side,physical_dimension=0)
            if chart==0:
                outer=dict(role='retained_body_2jet',kind='collar',side=side,piece=0,fixed_axis='v',fixed_parameter=first_row,parameter_interval=[ua,ub])
            else:
                neighbors=sorted([x for x in surfaces if x.get('kind')=='collar' and x.get('side')==side and x.get('piece',0)>0],key=lambda x:x['piece'])
                if neighbors:
                    neighbor=neighbors[0]
                    outer=dict(role='retained_body_2jet',kind='collar',side=side,piece=neighbor['piece'],fixed_axis='u',fixed_parameter=neighbor['domain'][0][0],parameter_interval=[v0,first_row])
                else:
                    bands=[x for x in surfaces if x.get('kind')=='middle']
                    if bands:
                        index=0 if side==0 else 3
                        outer=dict(role='retained_body_2jet',kind='middle',side=None,piece=index,fixed_axis='u',fixed_parameter=0. if side==0 else 1.,parameter_interval=[v0,first_row])
                    else:
                        raise ValueError('No retained neighbor for the hard-corner artificial U seam.')

            native=dict(role='native_source_side' if chart==0 else 'native_upper',side=side,parameter_interval=[v0,first_row] if chart==0 else [ua,ub])
            patch['boundary_roles']=dict(left=native,right=shared,bottom=collapsed,top=outer)
            patch['native_parameter_map']=dict(kind='triangular_pullback',chart=chart,u_interval=[ua,ub],v_interval=[v0,first_row],angular_axis='u',radial_axis='v')
            surface_index=len(surfaces)
            surfaces.append(patch)
            cp=np.asarray(patch['homogeneous_cp'],float)
            for edge in ('left','top'):
                covered_roles.append(dict(surface_index=surface_index,edge=edge,role=patch['boundary_roles'][edge]['role']))
            binding=dict(schema='smartskin.guide-isocurve.v1',surface_index=surface_index,varying_axis='v',constant_parameter=1.)
            if chart==0:
                guides.append(dict(degree=patch['degree_v'],knots=list(patch['knots_v']),homogeneous_cp=cp[-1].tolist(),domain=[0.,1.],kind='upper_corner_internal',side=side,piece='right',guide_id='upper:side%d:diagonal'%side,varying_axis='v',binding=binding,coincident_bindings=[]))
            else:
                guides[-1]['coincident_bindings'].append(binding)
            collapsed_bindings.append(dict(surface_index=surface_index,edge='bottom',corner_id='upper:side%d'%side))
        a,b=corner['surfaces'];ca=np.asarray(a['homogeneous_cp']);cb=np.asarray(b['homogeneous_cp'])
        if a['degree_v']!=b['degree_v'] or not np.array_equal(ca[-1],cb[-1]):raise ValueError('Upper diagonal position controls are not identical.')

    out['network']['density_policy']='%d complete native-V rows, %d profiles, and explicit shared corner guides; selected U/V modes preserve native attachments.'%(len(out['network']['native_v']),out['network']['profile_count'])
    out['upper_corner_reports']=[{k:v for k,v in corner.items() if k!='surfaces'} for corner in corners]
    out['network']['repaired_boundary_roles']=covered_roles
    out['network']['collapsed_boundary_bindings']=list(out['network'].get('collapsed_boundary_bindings',[]))+collapsed_bindings
    out.update(surfaces=surfaces,patches=surfaces,guides=guides,valid=False,geometry_valid=False,fatal=True,full_boundary_pass=False,continuity_pass=False,experimental_commit_allowed=False)
    out['report']={'checked':False,'fatal':True,'full_boundary_pass':False,'reason':'Reconstructed corner geometry requires complete per-value attachment validation.'}
    out['metrics']=out['report']
    out.pop('attachment_proof',None)
    return out
