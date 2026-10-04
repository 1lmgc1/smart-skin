"""P08D.2C: generic exact-boundary U-basis for differently segmented feature chains.

Pure CPython research helper. No Rhino/document/network/file writes.
The key rule is that source segmentation is NOT the logical-side topology:
bottom and top may contain different numbers of source intervals. Their
arc-length-proportional partitions and internal source breaks are merged into
one common tensor-product basis without deleting any source interval.
"""
from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class SegmentSpec:
    key:str
    length:float
    internal_fractions:tuple=()
    def validate(self):
        if not isinstance(self.key,str) or not self.key: raise ValueError('NAMED_SEGMENT_REQUIRED')
        if not np.isfinite(self.length) or self.length<=0: raise ValueError('POSITIVE_SEGMENT_LENGTH_REQUIRED')
        z=np.asarray(self.internal_fractions,float)
        if z.ndim!=1 or not np.isfinite(z).all() or np.any((z<=0)|(z>=1)) or (len(z)>1 and np.any(np.diff(z)<=0)):
            raise ValueError('ORDERED_INTERNAL_FRACTIONS_REQUIRED')
        return self

def chain_partition(segments):
    segs=tuple(segments)
    if not segs: raise ValueError('NONEMPTY_CHAIN_REQUIRED')
    for s in segs:s.validate()
    lengths=np.array([s.length for s in segs],float); total=float(lengths.sum())
    ends=np.r_[0.,np.cumsum(lengths)/total]
    out=[]
    for i,s in enumerate(segs):
        a=float(ends[i]);b=float(ends[i+1])
        breaks=tuple(a+(b-a)*float(x) for x in s.internal_fractions)
        out.append(dict(key=s.key,start=a,end=b,internal=breaks))
    return tuple(out)

def common_clamped_knots(chains,degree=3):
    if type(degree) is not int or not 2<=degree<=9:raise ValueError('BOUNDED_DEGREE_REQUIRED')
    allbreaks=[]
    partitions=[]
    for chain in chains:
        p=chain_partition(chain);partitions.append(p)
        for rec in p[:-1]:allbreaks.append(rec['end'])
        for rec in p:allbreaks.extend(rec['internal'])
    vals=sorted(set(round(float(x),14) for x in allbreaks if 1e-14<x<1-1e-14))
    K=[0.]*(degree+1)
    for x in vals:K += [float(x)]*degree
    K += [1.]*(degree+1)
    return np.asarray(K,float),tuple(partitions)

def greville(knots,degree):
    K=np.asarray(knots,float)
    n=len(K)-degree-1
    if n<=degree:raise ValueError('INSUFFICIENT_BASIS')
    return np.array([np.mean(K[i+1:i+degree+1]) for i in range(n)])

def locate_segment(partition,t):
    if not np.isfinite(t) or not 0<=t<=1:raise ValueError('UNIT_CHAIN_PARAMETER_REQUIRED')
    for i,r in enumerate(partition):
        if t<=r['end']+1e-14:
            den=r['end']-r['start']
            return i,min(1.,max(0.,(float(t)-r['start'])/den))
    return len(partition)-1,1.

def coverage_keys(partition):
    return tuple(x['key'] for x in partition)
