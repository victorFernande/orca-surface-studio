"""Invertible, compact surface coordinates for continuous logical layers.

The input mesh is flattened and sliced once, with native ContourZ disabled.
Only the private slicing copy changes. The inverse field restores the solid,
including holes, with a bound on the complete triangles and emitted chords.
"""
from __future__ import annotations

import copy
import math
from bisect import bisect_right
from functools import lru_cache
from itertools import pairwise

import numpy as np

from .bending import _clip, _refine, roof_patches
from .contracts import WaveError
from .geometry import transform_point
from .mesh_normalization import normalize_snapshot
from .printer_profile import number
from .regional_shell import RegionalShellSettings, _local_z_direction
from .surface import SurfaceMesh, SurfaceSettings


class HeightField:
    """Area-weighted plane or quadratic graph, with continuous XY extension."""
    def __init__(self, points, weights, extension_mm=.8):
        p=np.asarray(points,dtype=float);w=np.asarray(weights,dtype=float)
        self.extension_mm=float(extension_mm)
        self.bounds=tuple((float(p[:,k].min()),float(p[:,k].max())) for k in (0,1))
        self.origin=tuple((a+b)/2 for a,b in self.bounds)
        self.scale=tuple(max(1e-6,(b-a)/2) for a,b in self.bounds)
        u=(p[:,0]-self.origin[0])/self.scale[0];v=(p[:,1]-self.origin[1])/self.scale[1]
        columns=np.column_stack((np.ones(len(p)),u,v,u*u,u*v,v*v))
        candidates=[]
        for terms in ((0,1),(0,2),(0,1,2),(0,1,3),(0,2,5),(0,1,2,3,4,5)):
            c=np.linalg.lstsq(columns[:,terms]*w[:,None],p[:,2]*w,rcond=None)[0]
            residual=columns[:,terms]@c-p[:,2]
            rms=float(np.sqrt(np.average(residual*residual,weights=w*w)))
            candidates.append((rms,terms,c,residual))
        best=min(row[0] for row in candidates)
        # Preserve a simple extrusion-invariant graph when a second axis does
        # not materially improve the area-weighted fit. Bevel residual remains
        # in the sliced solid, rather than being erased from the source shape.
        good=[r for r in candidates if r[0]<=max(.01,best*1.1)]
        rms,terms,c,residual=min(good,key=lambda r:(len(r[1]),r[0]))
        self.coefficients=[0.]*6
        for i,value in zip(terms,c):self.coefficients[i]=float(value)
        self.rms=rms;self.max_residual=float(abs(residual).max())
        self.low,self.high=self._range()
        self.hessian=((2*self.coefficients[3]/self.scale[0]**2,
                       self.coefficients[4]/(self.scale[0]*self.scale[1])),
                      (self.coefficients[4]/(self.scale[0]*self.scale[1]),
                       2*self.coefficients[5]/self.scale[1]**2))

    def _coordinate(self,q,k):
        a,b=self.bounds[k];w=self.extension_mm
        if q<a-w:return a-w/2,0.
        if q<a:
            t=q-a;return a+t+t*t/(2*w),1+t/w
        if q<=b:return q,1.
        if q<b+w:
            t=q-b;return b+t-t*t/(2*w),1-t/w
        return b+w/2,0.

    def _uv(self,x,y):
        return tuple((self._coordinate(q,k)[0]-o)/s for k,(q,o,s) in enumerate(zip((x,y),self.origin,self.scale)))

    def height(self,x,y):
        u,v=self._uv(x,y);a,b,c,d,e,f=self.coefficients
        return a+b*u+c*v+d*u*u+e*u*v+f*v*v

    def gradient(self,x,y):
        u,v=self._uv(x,y);_,b,c,d,e,f=self.coefficients
        return ((b+2*d*u+e*v)/self.scale[0]*self._coordinate(x,0)[1],
                (c+e*u+2*f*v)/self.scale[1]*self._coordinate(y,1)[1])

    def cuts(self,k):
        c=self.coefficients
        if not any(c[i] for i in ((1,3,4) if k==0 else (2,4,5))):return ()
        a,b=self.bounds[k];w=self.extension_mm
        return a-w,a,b,b+w

    def differential_bounds(self,points):
        """Bounds for |gradient H| and each Hessian entry on the XY box."""
        uv=[self._uv(*p[:2]) for p in points];ranges=[(min(p[k] for p in uv),max(p[k] for p in uv)) for k in (0,1)]
        _,b,c,d,e,f=self.coefficients
        gradients=(max(abs(b+2*d*u+e*v) for u in ranges[0] for v in ranges[1])/self.scale[0],
                   max(abs(c+e*u+2*f*v) for u in ranges[0] for v in ranges[1])/self.scale[1])
        active=[];second=[]
        for k,(a,z) in enumerate(self.bounds):
            lo=min(p[k] for p in points);hi=max(p[k] for p in points);w=self.extension_mm
            active.append(hi>a-w and lo<z+w)
            second.append(1/w if (lo<a and hi>a-w) or (lo<z+w and hi>z) else 0.)
        gx,gy=(g*on for g,on in zip(gradients,active));h=self.hessian
        hxx=abs(h[0][0])*active[0]+gradients[0]*second[0]
        hyy=abs(h[1][1])*active[1]+gradients[1]*second[1]
        hxy=abs(h[0][1])*active[0]*active[1]
        return gx,gy,hxx,hxy,hyy

    def chord_polynomial(self,a,b):
        """Exact H along a chord contained in one coordinate shoulder cell."""
        polys=[]
        for k,(lo,hi) in enumerate(self.bounds):
            x=np.array([a[k],b[k]-a[k],0.]);mid=(a[k]+b[k])/2;w=self.extension_mm
            if mid<=lo-w:poly=np.array([lo-w/2,0.,0.])
            elif mid<lo:
                t=x.copy();t[0]-=lo;poly=x+np.convolve(t[:2],t[:2])/(2*w)
            elif mid<=hi:poly=x
            elif mid<hi+w:
                t=x.copy();t[0]-=hi;poly=x-np.convolve(t[:2],t[:2])/(2*w)
            else:poly=np.array([hi+w/2,0.,0.])
            poly[0]-=self.origin[k];polys.append(poly/self.scale[k])
        u,v=polys;c=self.coefficients;result=np.zeros(5);result[0]=c[0]
        result[:3]+=c[1]*u+c[2]*v
        result+=c[3]*np.convolve(u,u)+c[4]*np.convolve(u,v)+c[5]*np.convolve(v,v)
        return result

    def _range(self):
        w=self.extension_mm/2
        us=tuple((q-self.origin[0])/self.scale[0] for q in (self.bounds[0][0]-w,self.bounds[0][1]+w))
        vs=tuple((q-self.origin[1])/self.scale[1] for q in (self.bounds[1][0]-w,self.bounds[1][1]+w))
        return self._range_uv(us,vs)

    def range_on(self,points):
        uv=[self._uv(*p[:2]) for p in points]
        return self._range_uv((min(p[0] for p in uv),max(p[0] for p in uv)),
                              (min(p[1] for p in uv),max(p[1] for p in uv)))

    def _range_uv(self,us,vs):
        a,b,c,d,e,f=self.coefficients
        points=[(u,v) for u in us for v in vs]
        for v in vs:
            if d and us[0]<=(u:=-(b+e*v)/(2*d))<=us[1]:points.append((u,v))
        for u in us:
            if f and vs[0]<=(v:=-(c+e*u)/(2*f))<=vs[1]:points.append((u,v))
        det=4*d*f-e*e
        if abs(det)>1e-14:
            u=(e*c-2*f*b)/det;v=(e*b-2*d*c)/det
            if us[0]<=u<=us[1] and vs[0]<=v<=vs[1]:points.append((u,v))
        values=[a+b*u+c*v+d*u*u+e*u*v+f*v*v for u,v in points]
        return min(values)-1e-9,max(values)+1e-9

    def variation_on(self,points):
        values=[self.height(*p[:2]) for p in points]
        return max(values)-min(values)


class SurfaceStage:
    """Hermite interpolation with C1 vertical joins at all three levels.

    Positive quadratic Bezier derivative controls certify invertibility. The
    field is affine in H, allowing bounds on curved mesh faces and path chords.
    """
    def __init__(self,field,anchor,cap):
        self.field=field;self.anchor=float(anchor);self.cap=float(cap)
        if not self.anchor<field.low<=field.high<self.cap:
            raise WaveError('LAYERS_ORDER: não há espaço para transições sem inverter as camadas.')
        choices=[]
        for t in np.linspace(field.low,field.high,81):
            lo=(field.low-self.anchor)/(t-self.anchor)
            hi=(self.cap-field.high)/(self.cap-t)
            minimum=min(lo,hi)
            if minimum<=1/3+1e-6:continue
            m=float(min(1.,minimum,.9*(3*minimum-1)))
            bounds=self._derivative_bounds(float(t),m)
            choices.append((bounds[1]/bounds[0],float(t),m,bounds))
        if not choices:raise WaveError('LAYERS_JACOBIAN: não há uma transição suave com espessura positiva.')
        best=min(r[0] for r in choices);mid=(field.low+field.high)/2
        _,self.reference,self.tangent,(self.jmin,self.jmax)=min(
            (r for r in choices if r[0]<=best*(1+1e-10)),key=lambda r:(abs(r[1]-mid),r[1]))
        if self.jmin<=1e-5:
            raise WaveError('LAYERS_JACOBIAN: a transição não mantém espessura positiva.')
        self.width=min(self.reference-self.anchor,self.cap-self.reference)
        self.second_bound=max(2*max(abs(3*j-2-self.tangent),abs(2*self.tangent+1-3*j))/width
            for h in (field.low,field.high) for j,width in
            (((h-self.anchor)/(self.reference-self.anchor),self.reference-self.anchor),
             ((self.cap-h)/(self.cap-self.reference),self.cap-self.reference)))
        self._inverse=lru_cache(maxsize=600000)(self._flatten_point)

    def _derivative_bounds(self,t,m):
        values=[1.]
        for h in (self.field.low,self.field.high):
            for j,reverse in (((h-self.anchor)/(t-self.anchor),False),((self.cap-h)/(self.cap-t),True)):
                # Match the identity's derivative at the outer vertical knots.
                c=[1.,3*j-1-m,m]
                if reverse:c.reverse()
                values.extend((c[0],c[2]))
                denominator=c[0]-2*c[1]+c[2]
                if denominator and 0<(u:=(c[0]-c[1])/denominator)<1:
                    values.append((1-u)**2*c[0]+2*u*(1-u)*c[1]+u*u*c[2])
        return min(values),max(values)

    def _basis(self,s):
        if s<=self.anchor or s>=self.cap:return 0.,0.,0.
        if s<=self.reference:
            width=self.reference-self.anchor;u=(s-self.anchor)/width
            b=3*u*u-2*u**3
            k=self.anchor*(1-b)+width*(u**3-2*u*u+u)+width*self.tangent*(u**3-u*u)
            return b,k,(6*u-6*u*u)/width
        width=self.cap-self.reference;u=(s-self.reference)/width
        b=2*u**3-3*u*u+1
        k=self.cap*(1-b)+width*self.tangent*(u**3-2*u*u+u)+width*(u**3-u*u)
        return b,k,(6*u*u-6*u)/width

    def map_point(self,p):
        x,y,s=p
        if s<=self.anchor or s>=self.cap:return tuple(p)
        b,k,_=self._basis(s)
        return x,y,k+b*self.field.height(x,y)

    def flatten_point(self,p):
        return self._inverse(tuple(p))

    def clear_inverse_cache(self):
        self._inverse.cache_clear()

    def _flatten_point(self,p):
        x,y,z=p
        if z<=self.anchor or z>=self.cap:return p
        h=self.field.height(x,y)
        lo,hi=(self.anchor,self.reference) if z<=h else (self.reference,self.cap)
        s=(self.anchor+(z-self.anchor)*(self.reference-self.anchor)/(h-self.anchor) if z<=h
           else self.reference+(z-h)*(self.cap-self.reference)/(self.cap-h))
        for _ in range(30):
            error=self.map_point((x,y,s))[2]-z
            if abs(error)<1e-10:return x,y,s
            if error<0:lo=s
            else:hi=s
            trial=s-error/self.local_scale(x,y,s)
            s=trial if lo<trial<hi else (lo+hi)/2
        raise WaveError('LAYERS_INVERSE: a inversão não atingiu a tolerância exigida.')

    def local_scale(self,x,y,s):
        if s<=self.anchor or s>=self.cap:return 1.
        h=self.field.height(x,y)
        if s<=self.reference:
            width=self.reference-self.anchor;u=(s-self.anchor)/width;j=(h-self.anchor)/width
            return (1-u)**2+2*(3*j-1-self.tangent)*u*(1-u)+self.tangent*u*u
        width=self.cap-self.reference;u=(s-self.reference)/width;j=(self.cap-h)/width
        return self.tangent*(1-u)**2+2*(3*j-1-self.tangent)*u*(1-u)+u*u

    def gradient(self,x,y,s):
        b,_,_=self._basis(s)
        return tuple(b*g for g in self.field.gradient(x,y))

    def vertical_lipschitz(self,points,error):
        """Jacobian supremum on the complete previous-error tube."""
        low=min(p[2] for p in points)-error;high=max(p[2] for p in points)+error
        if high<=self.anchor or low>=self.cap:return 1.
        values=[1.] if low<=self.anchor or high>=self.cap else []
        for h in self.field.range_on(points):
            for start,end,reverse in ((self.anchor,self.reference,False),(self.reference,self.cap,True)):
                left=max(low,start);right=min(high,end)
                if left>right:continue
                width=end-start;j=(self.cap-h)/width if reverse else (h-self.anchor)/width
                c=[1.,3*j-1-self.tangent,self.tangent]
                if reverse:c.reverse()
                u,v=(left-start)/width,(right-start)/width
                probes=[u,v];den=c[0]-2*c[1]+c[2]
                if den and u<(critical:=(c[0]-c[1])/den)<v:probes.append(critical)
                values.extend((1-t)**2*c[0]+2*t*(1-t)*c[1]+t*t*c[2] for t in probes)
        return min(self.jmax,max(values)+1e-8)

    def _cuts(self,a,b):
        cuts={0.,1.}
        for k,values in ((0,self.field.cuts(0)),(1,self.field.cuts(1)),
                         (2,(self.anchor,self.reference,self.cap))):
            d=b[k]-a[k]
            if d:cuts.update(t for q in values if 0<(t:=(q-a[k])/d)<1)
        return sorted(cuts)

    def clipping_planes(self):
        return [(k,value) for k,values in ((0,self.field.cuts(0)),(1,self.field.cuts(1)),
                                         (2,(self.anchor,self.cap))) for value in values]

    def chord_error_bound(self,a,b,pa,pb):
        if max(a[2],b[2])<=self.anchor or min(a[2],b[2])>=self.cap:
            return max(math.dist(a,pa),math.dist(b,pb))+1e-9
        endpoint=max(math.dist(self.map_point(a),pa),math.dist(self.map_point(b),pb))
        quick=self._edge_curvature(a,b,self.field.differential_bounds((a,b)))/8+endpoint+1e-8
        if quick<=1e-4:return quick
        bound=0.
        for left,right in pairwise(self._cuts(a,b)):
            q=tuple(x+left*(y-x) for x,y in zip(a,b));r=tuple(x+right*(y-x) for x,y in zip(a,b))
            s0=q[2];ds=r[2]-s0;mid=(q[2]+r[2])/2
            if mid<=self.anchor or mid>=self.cap:poly=np.array([s0,ds])
            else:
                h=self.field.chord_polynomial(q,r)
                lower=mid<=self.reference
                width=self.reference-self.anchor if lower else self.cap-self.reference
                start=self.anchor if lower else self.reference;u=np.array([(s0-start)/width,ds/width])
                u2=np.convolve(u,u);u3=np.convolve(u2,u)
                basis=np.zeros(4);constant=np.zeros(4)
                if lower:
                    basis[:3]+=3*u2;basis-=2*u3
                    constant[0]=self.anchor;constant-=self.anchor*basis
                    constant+=width*(u3-2*np.pad(u2,(0,1))+np.pad(u,(0,2)))
                    constant+=width*self.tangent*(u3-np.pad(u2,(0,1)))
                else:
                    basis[0]=1;basis[:3]-=3*u2;basis+=2*u3
                    constant[0]=self.cap;constant-=self.cap*basis
                    constant+=width*self.tangent*(u3-2*np.pad(u2,(0,1))+np.pad(u,(0,2)))
                    constant+=width*(u3-np.pad(u2,(0,1)))
                poly=np.convolve(h,basis);poly[:4]+=constant
            degree=max(1,len(poly)-1);poly=np.pad(poly,(0,max(0,2-len(poly))))
            poly[0]-=pa[2]+left*(pb[2]-pa[2]);poly[1]-=(right-left)*(pb[2]-pa[2])
            controls=[sum(poly[j]*math.comb(k,j)/math.comb(degree,j) for j in range(k+1)) for k in range(degree+1)]
            bound=max(bound,*(abs(v) for v in controls))
        return min(quick,math.hypot(max(math.dist(a[:2],pa[:2]),math.dist(b[:2],pb[:2])),bound)+1e-8)

    def triangle_error(self,physical):
        if max(p[2] for p in physical)<=self.anchor or min(p[2] for p in physical)>=self.cap:return 0.
        u=tuple(b-a for a,b in zip(physical[0],physical[1]));v=tuple(b-a for a,b in zip(physical[0],physical[2]))
        n=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        # A vertical planar face is invariant as a geometric set: XY is fixed,
        # its vertical edges are mapped monotonically, and shared nonvertical
        # boundaries receive the neighbouring face's subdivision. There is no
        # need to approximate a parametrization inside that unchanged plane.
        if abs(n[2])<=1e-12*max(1.,math.hypot(*n)):return 0.
        return self.mapped_triangle_error([self.flatten_point(tuple(p)) for p in physical])

    def _edge_curvature(self,a,b,differentials):
        dx,dy,ds=(v-u for u,v in zip(a,b));gx,gy,hxx,hxy,hyy=differentials
        dh=abs(dx)*gx+abs(dy)*gy
        return self.second_bound*ds*ds+4/self.width*abs(ds)*dh+hxx*dx*dx+2*hxy*abs(dx*dy)+hyy*dy*dy

    def mapped_triangle_error(self,flat):
        """C1-map interpolation certificate over the complete triangle."""
        if max(p[2] for p in flat)<=self.anchor or min(p[2] for p in flat)>=self.cap:return 0.
        differential=self.field.differential_bounds(flat)
        return max(self._edge_curvature(a,b,differential) for a,b in
                   ((flat[0],flat[1]),(flat[1],flat[2]),(flat[2],flat[0])))/6+1e-9

    def triangle_normal_error(self,physical):
        u=tuple(b-a for a,b in zip(physical[0],physical[1]));v=tuple(b-a for a,b in zip(physical[0],physical[2]))
        n=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        return self.triangle_error(physical)*abs(n[2])/max(1e-20,math.hypot(*n))

    def crease_error(self,a,b):
        if math.dist(a[:2],b[:2])<1e-10:return 0.
        if max(a[2],b[2])<=self.anchor or min(a[2],b[2])>=self.cap:return 0.
        u,v=self.flatten_point(tuple(a)),self.flatten_point(tuple(b))
        quick=self._edge_curvature(u,v,self.field.differential_bounds((u,v)))/8+1e-9
        if quick<=getattr(self,'mesh_tolerance',0.):return quick
        return min(quick,self.chord_error_bound(u,v,a,b))


def _creases(faces,world):
    previous={};result=set()
    for tri in faces:
        a,b,c=(world[i] for i in tri);u=tuple(v-w for v,w in zip(b,a));v=tuple(q-w for q,w in zip(c,a))
        n=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]);length=math.hypot(*n)
        n=tuple(q/length for q in n)
        for a,b in zip(tri,(*tri[1:],tri[0])):
            edge=tuple(sorted((a,b)))
            if edge in previous:
                if sum(x*y for x,y in zip(n,previous.pop(edge)))<math.cos(math.radians(1.)):result.add(edge)
            else:previous[edge]=n
    if previous:raise WaveError('LAYERS_TOPOLOGY: a cópia perdeu uma fronteira fechada.')
    return result


def _map_triangle(stages,points):
    error=0.
    for stage in reversed(stages):
        error=stage.jmax*error+stage.mapped_triangle_error(points)
        points=[stage.map_point(p) for p in points]
    return points,error


def _normal_certificate(stages,flat,original):
    u=tuple(b-a for a,b in zip(original[0],original[1]));v=tuple(b-a for a,b in zip(original[0],original[2]))
    n=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]);length=math.hypot(*n)
    if length<1e-20:raise WaveError('LAYERS_REFERENCE: face original degenerada durante o refinamento.')
    if abs(n[2])<=1e-12*length:return 0.
    mapped,error=_map_triangle(stages,list(flat))
    vertex=max(abs(sum(a*(b-c) for a,b,c in zip(n,p,original[0])))/length for p in mapped)
    return vertex+abs(n[2])/length*error+1e-9


def _crease_certificate(stages,a,b,ra,rb,tolerance):
    if math.dist(ra[:2],rb[:2])<1e-10:return 0.
    points,quick=_map_triangle(stages,[a,b,a])
    endpoint=max(math.dist(points[0],ra),math.dist(points[1],rb))
    if endpoint+quick<=tolerance:return endpoint+quick
    error=0.;u,v=a,b
    for stage in reversed(stages):
        p,q=stage.map_point(u),stage.map_point(v)
        error=stage.jmax*error+stage.chord_error_bound(u,v,p,q);u,v=p,q
    return endpoint+min(quick,error)


class LayerGridStage:
    """Monotone Z-only reparametrization; surface cores share a slice band.

    It does not change a physical surface or apply contouring to existing
    G-code. The private model and its inverse use the same positive knot map.
    """
    def __init__(self,flat_levels,physical_levels):
        self.flat=tuple(map(float,flat_levels));self.physical=tuple(map(float,physical_levels))
        if (len(self.flat)!=len(self.physical) or len(self.flat)<2 or
            not all(math.isfinite(z) for values in (self.flat,self.physical) for z in values) or
            self.flat[0]!=self.physical[0] or self.flat[-1]!=self.physical[-1]):
            raise WaveError('LAYERS_GRID: referências inválidas para preservar os extremos.')
        if any(b<=a for values in (self.flat,self.physical) for a,b in pairwise(values)):
            raise WaveError('LAYERS_GRID: superfícies próximas não permitem uma ordem de camadas positiva.')
        knots=[]
        for point in zip(self.flat,self.physical):
            knots.append(point)
            while len(knots)>=3:
                a,b,c=knots[-3:]
                left=(b[1]-a[1])*(c[0]-a[0]);right=(c[1]-a[1])*(b[0]-a[0])
                if abs(left-right)>1e-11*max(abs(left),abs(right),1e-30):break
                knots.pop(-2)
        self.flat,self.physical=tuple(zip(*knots))
        self.slopes=tuple((b-a)/(d-c) for a,b,c,d in zip(self.physical,self.physical[1:],self.flat,self.flat[1:]))
        self.jmin=min(1.,*self.slopes);self.jmax=max(1.,*self.slopes)

    @staticmethod
    def _value(z,source,target):
        if z<=source[0] or z>=source[-1]:return z
        i=bisect_right(source,z)-1;t=(z-source[i])/(source[i+1]-source[i])
        return target[i]+t*(target[i+1]-target[i])

    def map_point(self,p):return p[0],p[1],self._value(p[2],self.flat,self.physical)
    def flatten_point(self,p):return p[0],p[1],self._value(p[2],self.physical,self.flat)
    def clear_inverse_cache(self):pass
    def local_scale(self,x,y,s):
        if s<=self.flat[0] or s>=self.flat[-1]:return 1.
        return self.slopes[bisect_right(self.flat,s)-1]
    def gradient(self,x,y,s):return 0.,0.
    def vertical_lipschitz(self,points,error):
        low=min(p[2] for p in points)-error;high=max(p[2] for p in points)+error
        values=[1.] if low<=self.flat[0] or high>=self.flat[-1] else []
        values.extend(j for i,j in enumerate(self.slopes) if self.flat[i]<=high and self.flat[i+1]>=low)
        return max(values,default=1.)
    def clipping_planes(self):return [(2,z) for z in self.physical]

    def chord_error_bound(self,a,b,pa,pb):
        cuts=[0.,1.];ds=b[2]-a[2]
        if ds:cuts += [(s-a[2])/ds for s in self.flat if 0<(s-a[2])/ds<1]
        return max(abs(self.map_point(tuple(x+t*(y-x) for x,y in zip(a,b)))[2]-
                       (pa[2]+t*(pb[2]-pa[2]))) for t in cuts)+1e-9

    def mapped_triangle_error(self,points):
        low=min(p[2] for p in points);high=max(p[2] for p in points)
        zs=[low,high]+[z for z in self.flat if low<z<high]
        if len(zs)==2:return 0.
        offsets=[self.map_point((0,0,z))[2]-z for z in zs]
        return max(offsets)-min(offsets)+1e-9


def _core_interval(row):
    zs=np.asarray([p[2] for p in row['points']]);order=np.argsort(zs);weights=row['weights']**2
    cumulative=np.cumsum(weights[order]);cumulative/=cumulative[-1]
    return np.interp([.05,.95],cumulative,zs[order])


class ContinuousLayerWarp:
    def __init__(self,snapshot,object_id,settings=None,progress=lambda message:None,cancelled=lambda:False,initial_layer_mm=None):
        self.object_id=str(object_id);self.source_revision=snapshot.revision
        self.settings=settings or RegionalShellSettings(retain_native_short_edges=True)
        clean,normalization=normalize_snapshot(snapshot,self.object_id)
        if len(clean.objects)!=1:raise WaveError('LAYERS_OBJECT: deixe uma peça nesta placa para o estudo contínuo.')
        obj=clean.objects[0];vol=obj['volumes'][0];inst=next(i for i in obj['instances_data'] if i.get('printable',True))
        mesh=SurfaceMesh(obj,SurfaceSettings());threshold=max(4.,.02*math.prod(mesh.bounds[1][k]-mesh.bounds[0][k] for k in (0,1)))
        candidates=[];flat_caps=[]
        for ids in roof_patches(mesh,vol['triangles'],self.settings.max_slope_deg):
            fs=[mesh.faces[i] for i in ids];area=sum(abs(f.nz)/2 for f in fs)
            if area<4:continue
            points=[p for f in fs for p in f.points];weights=np.repeat(np.sqrt([abs(f.nz)/6 for f in fs]),3)
            field=HeightField(points,weights,4*self.settings.step_mm)
            if field.high-field.low<self.settings.nominal_layer_height_mm*.75:
                flat_caps.append(min(p[2] for p in points))
            if area<threshold:continue
            center=[(a+b)/2 for a,b in field.bounds]
            candidates.append({'points':points,'weights':weights,'area':area,'original_z':[min(p[2] for p in points),max(p[2] for p in points)],
                'original_bounds':field.bounds,'original_gradient':field.gradient(*center),
                'original_plane':max(abs(c) for c in field.coefficients[3:])<.01})
        candidates.sort(key=lambda r:r['original_z'][1])
        inclined=[r for r in candidates if HeightField(r['points'],r['weights'],4*self.settings.step_mm).high-HeightField(r['points'],r['weights'],4*self.settings.step_mm).low>=self.settings.nominal_layer_height_mm*.75]
        if not inclined:raise WaveError('LAYERS_SURFACE: não há uma superfície inclinada extensa para alinhar as camadas.')
        highest=inclined[-1]
        if len(candidates)>12:raise WaveError('LAYERS_COMPLEXITY: mais de doze superfícies extensas exigem decomposição adicional.')
        first_layer=initial_layer_mm if initial_layer_mm is not None else number(snapshot.settings,'initial_layer_print_height',self.settings.nominal_layer_height_mm)
        self.anchor_z=max(mesh.bounds[0][2]+max(first_layer,self.settings.nominal_layer_height_mm*2),.5)
        top_cap=min((z-.1 for z in flat_caps if z>highest['original_z'][1]+.2),
                    default=mesh.bounds[1][2]+max(1.,self.settings.nominal_layer_height_mm*3))
        roof_cap=highest['original_z'][0]-.2
        self.stages=[];done=[];self.details=[];total_bound=0.
        direction=_local_z_direction(inst['matrix'],vol['matrix'])
        world=[tuple(transform_point(p,inst['matrix'],vol['matrix'])) for p in vol['vertices']]
        reference_world=list(world)
        self.original_world_vertices=tuple(world);vertices=copy.deepcopy(vol['vertices']);faces=[tuple(f) for f in vol['triangles']]
        self.exact_vertex_count=len(world)
        def apply_stage(stage,metadata):
            nonlocal vertices,faces,world,total_bound
            if isinstance(stage,LayerGridStage):
                # Each clipped cell has an affine grid inverse. It therefore
                # restores the *entire preceding triangle*, not only vertices,
                # and inherits its already certified face/crease bound exactly.
                for k,value in stage.clipping_planes():
                    if cancelled():raise WaveError('Geração cancelada.')
                    plane=[0.,0.,0.,-value];plane[k]=1.
                    faces=_clip(vertices,faces,world,plane,reference_world=reference_world)
                    if len(faces)>3000000:raise WaveError('BEND_COMPLEXITY: grade supera 3000000 faces.')
                flat=[stage.flatten_point(tuple(p)) for p in world]
                vertices=[[v+d*(q[2]-p[2]) for v,d in zip(local,direction)] for local,p,q in zip(vertices,world,flat)]
                world=list(flat)
                for record in candidates:record['points']=[stage.flatten_point(tuple(p)) for p in record['points']]
                self.stages.append(stage)
                self.details.append(dict(metadata,minimum_vertical_jacobian=stage.jmin,
                    maximum_vertical_jacobian=stage.jmax,mesh_normal_and_crease_bound_mm=total_bound,
                    certificate='exact_affine_cells_preserve_preceding_mesh'))
                progress(f'Grade contínua: {len(faces)} faces, formato anterior preservado por células afins.')
                return
            # New subdivision points must come from the original source face,
            # rather than accumulating the preceding approximation's residual.
            known={tuple(ref):tuple(p) for ref,p in zip(reference_world,world)}
            @lru_cache(maxsize=600000)
            def previous_flat(reference):
                if reference in known:return known[reference]
                point=reference
                for before in self.stages:point=before.flatten_point(tuple(point))
                return point
            def exact_flat(reference):return stage.flatten_point(previous_flat(tuple(reference)))
            for k,value in stage.clipping_planes():
                plane=[0.,0.,0.,-value];plane[k]=1.
                faces=_clip(vertices,faces,world,plane,reference_world=reference_world)
            tolerance=self.settings.tolerance_mm
            creases=_creases(faces,reference_world);stages=(*self.stages,stage);calls=0
            def checked_bound(points,reference):
                nonlocal calls
                calls+=1
                if calls%1024==0 and cancelled():raise WaveError('Geração cancelada.')
                return _normal_certificate(stages,[exact_flat(p) for p in reference],reference)
            def checked_edge(a,b,ra,rb):
                left,right=sorted(((tuple(a),tuple(ra)),(tuple(b),tuple(rb))))
                return cached_edge(left,right)
            @lru_cache(maxsize=300000)
            def cached_edge(left,right):
                a,ra=left;b,rb=right
                return _crease_certificate(stages,exact_flat(ra),exact_flat(rb),ra,rb,tolerance)
            def checked_batch(points,triangles,reference):
                from .continuous_certificates import original_face_bounds
                flat=[]
                for i,p in enumerate(reference):
                    if i%8192==0 and cancelled():raise WaveError('Geração cancelada.')
                    flat.append(exact_flat(p))
                flat=np.asarray(flat);ref=np.asarray(reference)
                result=[]
                for offset in range(0,len(triangles),20000):
                    if cancelled():raise WaveError('Geração cancelada.')
                    ids=np.asarray(triangles[offset:offset+20000])
                    result.extend(original_face_bounds(stages,flat[ids],ref[ids]))
                return result
            try:
                faces,error=_refine(vertices,faces,world,checked_bound,tolerance,max_faces=3000000,
                                    crease_edges=creases,edge_bound=checked_edge,reference_world=reference_world,batch_bound=checked_batch)
                flat=[exact_flat(p) for p in reference_world]
                vertices=[[v+d*(q[2]-p[2]) for v,d in zip(local,direction)] for local,p,q in zip(vertices,world,flat)]
                world=list(flat)
                self.exact_vertex_count=len(world)
                for record in candidates:record['points']=[stage.flatten_point(tuple(p)) for p in record['points']]
                error=float(error)
                self.stages.append(stage);total_bound=error
                self.details.append(dict(metadata,minimum_vertical_jacobian=stage.jmin,
                    maximum_vertical_jacobian=stage.jmax,mesh_normal_and_crease_bound_mm=error))
                progress(f'Geometria contínua: {len(faces)} faces, desvio normal/quinas até {error:.4f} mm.')
            finally:
                stage.clear_inverse_cache()
                for before in self.stages:before.clear_inverse_cache()
        for index,row in enumerate(candidates):
            if cancelled():raise WaveError('Geração cancelada.')
            progress(f'Planejando superfície contínua {index+1} de {len(candidates)}…')
            field=HeightField(row['points'],row['weights'],4*self.settings.step_mm);anchor=self.anchor_z
            if field.high-field.low<self.settings.nominal_layer_height_mm*.75:
                done.append(row);continue
            # Parallel skins belong to the same coordinate family. Extend the
            # lower skin's field over both footprints so a clamp cannot cut
            # through the higher rim and reintroduce a change of slope there.
            if row['original_plane'] and math.hypot(*row['original_gradient'])>.01:
                family=[r for r in candidates if r['original_plane'] and
                        math.dist(r['original_gradient'],row['original_gradient'])<.005]
                if len(family)>1:
                    field.bounds=tuple((min(r['original_bounds'][k][0] for r in family),
                                        max(r['original_bounds'][k][1] for r in family)) for k in (0,1))
                    field.low,field.high=field._range()
            # Previously flattened patches remain untouched, unless the new
            # field is constant over them (then their constant level stays flat).
            for record in done:
                points=record['points']
                if field.variation_on(points)>1e-5:anchor=max(anchor,max(p[2] for p in points)+.15)
            cap=top_cap if row is highest else roof_cap
            if field.low<=anchor+.02 or field.high>=cap-.02:
                raise WaveError('LAYERS_TRANSITION: regiões próximas não permitem preservar todas as camadas alinhadas.')
            stage=SurfaceStage(field,anchor,cap)
            apply_stage(stage,{'kind':'surface','area_mm2':row['area'],'original_z_range_mm':row['original_z'],
                'anchor_mm':anchor,'reference_mm':stage.reference,'cap_mm':cap,
                'tangent_vertical_scale':float(stage.tangent),
                'field_range_mm':[field.low,field.high],'fit_rms_mm':field.rms,'fit_max_residual_mm':field.max_residual,
                'coefficients':field.coefficients,
                'field_extension_mm':field.extension_mm,'field_bounds_xy':field.bounds,'field_origin_xy':field.origin,'field_scale_xy':field.scale})
            done.append(row)
        # Align the broad surface cores jointly to actual native slice bands.
        # A narrow residual fit alone is insufficient if it straddles a band.
        height=self.settings.nominal_layer_height_mm
        origin=first_layer
        groups=[]
        for low,high in sorted((_core_interval(r) for r in candidates),key=lambda q:q[0]):
            if high-low>=height*.8:
                raise WaveError('LAYERS_FIT: uma superfície ainda atravessa várias camadas; o formato foi preservado e a geração interrompida.')
            if groups and (low-groups[-1][1]<height*.25 or high-groups[-1][0]<height*.8):groups[-1][1]=max(high,groups[-1][1])
            else:groups.append([float(low),float(high)])
        if any(high-low>height*1.5 for low,high in groups):
            raise WaveError('LAYERS_GRID: referências próximas demais exigem outra distribuição de camadas.')
        physical=[self.anchor_z];flat=[self.anchor_z]
        for low,high in groups:
            level=(low+high)/2
            if level<=self.anchor_z:continue
            target=origin+round((level-origin)/height)*height
            if target-height*.4<=flat[-1]+1e-8:target=origin+math.ceil((flat[-1]+height*.4-origin)/height)*height
            if high-low>1e-7:
                radius=min((high-low)/2,height*.4)
                physical.extend([low,level,high]);flat.extend([target-radius,target,target+radius])
            else:physical.append(level);flat.append(target)
        top=max(p[2] for p in world)
        if top>physical[-1]+1e-5:
            physical.append(top);flat.append(max(flat[-1]+height,origin+round((top-origin)/height)*height))
        cap=max(top,flat[-1])+1.
        physical.append(cap);flat.append(cap)
        apply_stage(LayerGridStage(flat,physical),{'kind':'layer_grid','flat_levels_mm':flat,'physical_levels_mm':physical})
        if total_bound>self.settings.tolerance_mm+1e-8:
            raise WaveError('LAYERS_SHAPE: a composição excede a tolerância do formato original.')
        self.flattened_snapshot=copy.deepcopy(clean);target=self.flattened_snapshot.objects[0]['volumes'][0]
        target['vertices']=vertices;target['triangles']=[list(f) for f in faces]
        self.reference_world_vertices=tuple(reference_world)
        self.summary={'study_type':'continuous_surface_coordinates','transition_kernel':'hermite_c1_xyz_v2','stages':self.details,
            'source_revision':snapshot.revision,'normalization':normalization,'source_mesh_unchanged':True,
            'mesh_normal_and_crease_error_budget_mm':total_bound,'flattened_faces':len(faces),'flattened_vertices':len(vertices),
            'vertex_reference':'original_source_faces_before_grid','output_face_limit':3000000,
            'grid_shape_transform':'exact_piecewise_affine',
            'xy_preserved':True,'base_unchanged':True,'holes_preserved':True,'positive_jacobian':True,
            'physical_validation':False,'print_allowed':False}
        alignment=[]
        for row in candidates:
            zs=np.asarray([p[2] for p in row['points']]);order=np.argsort(zs);weights=row['weights']**2
            cumulative=np.cumsum(weights[order]);cumulative/=cumulative[-1]
            q=np.interp([.05,.95],cumulative,zs[order])
            alignment.append({'original_z_range_mm':row['original_z'],'area_mm2':row['area'],
                'final_flat_z_range_mm':[float(zs.min()),float(zs.max())],
                'central_90_percent_z_span_mm':float(q[1]-q[0]),
                'core_in_one_native_band':int(math.floor((q[0]-origin)/height+.5))==int(math.floor((q[1]-origin)/height+.5))})
        self.summary['reference_alignment']=alignment
        if not all(r['core_in_one_native_band'] for r in alignment):
            raise WaveError('LAYERS_ALIGNMENT: uma referência ainda cruza a faixa de corte; a geração foi interrompida.')

    def map_point(self,p):
        for stage in reversed(self.stages):p=stage.map_point(p)
        return tuple(p)

    def flatten_point(self,p):
        for stage in self.stages:p=stage.flatten_point(tuple(p))
        return tuple(p)

    def local_scale(self,x,y,s):
        scale=1.;p=(x,y,s)
        for stage in reversed(self.stages):scale*=stage.local_scale(*p);p=stage.map_point(p)
        return scale

    def gradient(self,x,y,s):
        gradient=(0.,0.);p=(x,y,s)
        for stage in reversed(self.stages):
            j=stage.local_scale(*p);g=stage.gradient(*p)
            gradient=tuple(v+j*u for u,v in zip(gradient,g));p=stage.map_point(p)
        return gradient

    def volume_scale(self,x,y,s,h):
        return (self.map_point((x,y,s))[2]-self.map_point((x,y,s-h))[2])/h

    def normal_gap(self,x,y,s,h):
        return h*self.volume_scale(x,y,s,h)/math.hypot(1.,*self.gradient(x,y,s))

    def chord_error_bound(self,a,b,pa,pb):
        error=0.;u,v=tuple(a),tuple(b)
        for stage in reversed(self.stages):
            p,q=stage.map_point(u),stage.map_point(v)
            error=stage.vertical_lipschitz((u,v),error)*error+stage.chord_error_bound(u,v,p,q);u,v=p,q
        return error+max(math.dist(u,pa),math.dist(v,pb))+1e-9

    def surface_heights(self,x,y):
        # There is no single "highest roof plane" in this multi-surface field.
        return None
