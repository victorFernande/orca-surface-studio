"""Planning samples inside the copied solid; never a collision certificate."""
from __future__ import annotations
import math
import numpy as np
from .contracts import WaveError


def material_samples(mesh,spacing=1.2,*,cancelled=lambda:False):
    boundary=np.asarray([p for face in mesh.faces for p in face.points])
    extra=[]
    # Include long vertical walls and large sparse STL faces, whose vertices
    # alone can all lie above a low material gap near the base.
    for i,face in enumerate(mesh.faces):
        if i%4096==0 and cancelled():raise WaveError('Geração cancelada.')
        triangle=np.asarray(face.points);extra.append(triangle.mean(axis=0))
        for a,b in zip(triangle,np.roll(triangle,-1,axis=0)):
            count=math.ceil(float(np.linalg.norm(b-a))/spacing)
            if count>1:extra.extend(a+(b-a)*t/count for t in range(1,count))
    for x in np.arange(mesh.bounds[0][0]+spacing*.371,mesh.bounds[1][0],spacing):
        if cancelled():raise WaveError('Geração cancelada.')
        for y in np.arange(mesh.bounds[0][1]+spacing*.613,mesh.bounds[1][1],spacing):
            hits=[]
            for index in mesh.grid.get((math.floor(x/mesh.cell),math.floor(y/mesh.cell)),()):
                face=mesh.faces[index]
                if not face.nz or not face.ymin<=y<face.ymax:continue
                span=face.span(y)
                if span and span[0]<=x<span[1]:hits.append(face.height(x,y))
            unique=[]
            for z in sorted(hits):
                if not unique or z-unique[-1]>1e-7:unique.append(z)
            if len(unique)%2:
                raise WaveError('SPLINE_MATERIAL: uma coluna do sólido tem interseções ambíguas.')
            for lo,hi in zip(unique[::2],unique[1::2]):
                levels=np.arange(lo+spacing/2,hi,spacing)
                if not len(levels):levels=[(lo+hi)/2]
                extra.extend((x,y,float(z)) for z in levels)
    extra=np.asarray(extra)
    _,chosen=np.unique(np.floor(extra/(spacing/2)),axis=0,return_index=True)
    return np.unique(np.vstack((boundary,extra[chosen])),axis=0)
