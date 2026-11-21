"""Vectorized equivalent of the scalar original-face certificate.

Only the initial face sweep is batched. Adaptive children keep the scalar
certificate, so performance does not depend on relaxing the geometry budget.
"""
import numpy as np


def _coordinates(field,points):
    result=[];w=field.extension_mm
    for k,(a,b) in enumerate(field.bounds):
        q=points[...,k];left=q-a;right=q-b
        result.append(np.where(q<a-w,a-w/2,np.where(q<a,q+left*left/(2*w),
                      np.where(q<=b,q,np.where(q<b+w,q-right*right/(2*w),b+w/2)))))
    return np.stack(result,axis=-1)


def _height(field,points):
    xy=_coordinates(field,points)
    u=(xy[...,0]-field.origin[0])/field.scale[0];v=(xy[...,1]-field.origin[1])/field.scale[1]
    a,b,c,d,e,f=field.coefficients
    return a+b*u+c*v+d*u*u+e*u*v+f*v*v


def _map(stage,points):
    output=points.copy();z=points[...,2]
    if hasattr(stage,'flat'):
        output[...,2]=np.where((z<=stage.flat[0])|(z>=stage.flat[-1]),z,np.interp(z,stage.flat,stage.physical))
        return output
    h=_height(stage.field,points);below=z<=stage.reference
    u=(z-stage.anchor)/(stage.reference-stage.anchor)
    v=(z-stage.reference)/(stage.cap-stage.reference)
    left=(stage.anchor+(h-stage.anchor)*(3*u*u-2*u*u*u)+
          (stage.reference-stage.anchor)*(u*u*u-2*u*u+u)+
          (stage.reference-stage.anchor)*stage.tangent*(u*u*u-u*u))
    right=(stage.cap+(h-stage.cap)*(2*v*v*v-3*v*v+1)+
           (stage.cap-stage.reference)*stage.tangent*(v*v*v-2*v*v+v)+
           (stage.cap-stage.reference)*(v*v*v-v*v))
    output[...,2]=np.where((z<=stage.anchor)|(z>=stage.cap),z,np.where(below,left,right))
    return output


def _bound(stage,points):
    low=points[...,2].min(axis=1);high=points[...,2].max(axis=1)
    if hasattr(stage,'flat'):
        lo=_map(stage,np.stack((low*0,low*0,low),axis=-1))[...,2]-low
        hi=_map(stage,np.stack((high*0,high*0,high),axis=-1))[...,2]-high
        minimum=np.minimum(lo,hi);maximum=np.maximum(lo,hi);cross=np.zeros(len(low),dtype=bool)
        for s,p in zip(stage.flat,stage.physical):
            active=(low<s)&(s<high);cross|=active
            minimum=np.where(active,np.minimum(minimum,p-s),minimum)
            maximum=np.where(active,np.maximum(maximum,p-s),maximum)
        return np.where(cross,maximum-minimum+1e-9,0.)
    other=np.roll(points,-1,axis=1);delta=other-points;dx,dy,ds=np.moveaxis(delta,-1,0)
    field=stage.field;xy=_coordinates(field,points)
    u=(xy[...,0]-field.origin[0])/field.scale[0];v=(xy[...,1]-field.origin[1])/field.scale[1]
    ur=(u.min(axis=1),u.max(axis=1));vr=(v.min(axis=1),v.max(axis=1));_,b,c,d,e,f=field.coefficients
    gx=np.maximum.reduce([abs(b+2*d*q+e*r) for q in ur for r in vr])/field.scale[0]
    gy=np.maximum.reduce([abs(c+e*q+2*f*r) for q in ur for r in vr])/field.scale[1]
    active=[];second=[];w=field.extension_mm
    for k,(a,z) in enumerate(field.bounds):
        lo=points[...,k].min(axis=1);hi=points[...,k].max(axis=1)
        active.append((hi>a-w)&(lo<z+w))
        second.append(((lo<a)&(hi>a-w))|((lo<z+w)&(hi>z)))
    h=field.hessian
    hxx=abs(h[0][0])*active[0]+gx*second[0]/w
    hyy=abs(h[1][1])*active[1]+gy*second[1]/w
    hxy=abs(h[0][1])*active[0]*active[1]
    dh=abs(dx)*(gx*active[0])[:,None]+abs(dy)*(gy*active[1])[:,None]
    error=(stage.second_bound*ds*ds+4/stage.width*abs(ds)*dh+hxx[:,None]*dx*dx+
           2*hxy[:,None]*abs(dx*dy)+hyy[:,None]*dy*dy).max(axis=1)/6+1e-9
    return np.where((high<=stage.anchor)|(low>=stage.cap),0.,error)


def original_face_bounds(stages,flat,original):
    """Same certificate as _normal_certificate, for N triangles at once."""
    flat=np.asarray(flat,dtype=float);original=np.asarray(original,dtype=float)
    normal=np.cross(original[:,1]-original[:,0],original[:,2]-original[:,0]);length=np.linalg.norm(normal,axis=1)
    if np.any(length<1e-20):
        from .contracts import WaveError
        raise WaveError('LAYERS_REFERENCE: face original degenerada durante o refinamento.')
    error=np.zeros(len(flat));mapped=flat
    for stage in reversed(stages):
        error=stage.jmax*error+_bound(stage,mapped);mapped=_map(stage,mapped)
    vertex=abs(((mapped-original[:,0,None,:])*normal[:,None,:]).sum(axis=-1)).max(axis=1)/length
    return np.where(abs(normal[:,2])<=1e-12*length,0.,vertex+abs(normal[:,2])/length*error+1e-9)
