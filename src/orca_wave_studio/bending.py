"""Invertible roof-aligned coordinates for complete solids, including holes.

Unlike the rectangular paired-skin pilot this transforms coordinates, not a
filled XY footprint. Every face/opening belongs to the same homeomorphism.
The reference is a fitted plane of a connected roof patch; residual curvature
is retained in the sliced solid, not advertised as an exactly flattened skin.
"""
from __future__ import annotations

import copy
import heapq
import math
from collections import defaultdict
import numpy as np

from .contracts import WaveError
from .geometry import transform_point
from .mesh_normalization import normalize_snapshot
from .regional_shell import RegionalShellWarp,RegionalShellSettings,_local_z_direction,_plane,_same_plane
from .surface import SurfaceMesh,SurfaceSettings


def roof_patches(mesh,triangles,limit):
    edges={};adj=defaultdict(list);eligible=[]
    for i,(f,tri) in enumerate(zip(mesh.faces,triangles)):
        if f.nz*mesh.orientation<=1e-10 or f.gradient>math.tan(math.radians(limit))+1e-8:continue
        eligible.append(i)
        for a,b in zip(tri,(*tri[1:],tri[0])):
            edge=tuple(sorted((a,b)))
            if edge in edges:
                j=edges[edge];adj[i].append(j);adj[j].append(i)
            else:edges[edge]=i
    unseen=set(eligible);patches=[]
    while unseen:
        seed=min(unseen);unseen.remove(seed);ids={seed};queue=[seed]
        while queue:
            for j in adj[queue.pop()]:
                if j in unseen:unseen.remove(j);ids.add(j);queue.append(j)
        patches.append(ids)
    return patches


def _clip(vertices,faces,world,plane,*,reference_world=None):
    """Split both sides of a linear plane, sharing intersection vertices."""
    if not faces:return []
    p=np.asarray(world,dtype=float)
    values=((p[:,0]*plane[0]+p[:,1]*plane[1])+p[:,2]*plane[2])+plane[3]
    # Keep face order and the original crossing routine. Only the broad phase
    # is vectorized: non-crossing faces never need Python polygon construction.
    points=values[np.asarray(faces,dtype=np.int64)]
    candidates=np.flatnonzero((points.min(axis=1)<-1e-10)&(points.max(axis=1)>1e-10))
    if not len(candidates):return list(faces)
    values=values.tolist()
    intersections={};result=[]
    def crossing(a,b):
        if abs(values[a])<1e-10:return a
        if abs(values[b])<1e-10:return b
        edge=tuple(sorted((a,b)))
        if edge not in intersections:
            a,b=edge;t=values[a]/(values[a]-values[b]);index=len(vertices)
            vertices.append([u+t*(v-u) for u,v in zip(vertices[a],vertices[b])])
            world.append(tuple(u+t*(v-u) for u,v in zip(world[a],world[b])))
            if reference_world is not None:
                reference_world.append(tuple(u+t*(v-u) for u,v in zip(reference_world[a],reference_world[b])))
            values.append(0.);intersections[edge]=index
        return intersections[edge]
    previous=0
    for index in candidates:
        result.extend(faces[previous:index]);previous=index+1;tri=faces[index]
        for side in (-1,1):
            poly=[];a=tri[-1]
            for b in tri:
                ia=side*values[a]>=-1e-10;ib=side*values[b]>=-1e-10
                if ia!=ib:poly.append(crossing(a,b))
                if ib:poly.append(b)
                a=b
            poly=list(dict.fromkeys(poly))
            result.extend((poly[0],poly[j],poly[j+1]) for j in range(1,len(poly)-1))
    result.extend(faces[previous:])
    return result


def _refine(vertices,faces,world,bound,tolerance,max_faces=250000,*,crease_edges=None,edge_bound=None,reference_world=None,batch_bound=None):
    if len(faces)>max_faces:raise WaveError(f'BEND_COMPLEXITY: refinamento supera {max_faces} faces.')
    edges=defaultdict(set);removed=set();queue=[];errors={}
    initial=batch_bound(world,faces,reference_world) if batch_bound is not None else ()
    def add(i):
        tri=faces[i]
        for a,b in zip(tri,(*tri[1:],tri[0])):edges[tuple(sorted((a,b)))].add(i)
        error=(float(initial[i]) if i<len(initial) else
               bound([world[k] for k in tri],[reference_world[k] for k in tri]) if reference_world is not None
               else bound([world[k] for k in tri]))
        if crease_edges is not None and edge_bound is not None:
            for a,b in zip(tri,(*tri[1:],tri[0])):
                if tuple(sorted((a,b))) in crease_edges:
                    error=max(error,edge_bound(world[a],world[b],reference_world[a],reference_world[b])
                              if reference_world is not None else edge_bound(world[a],world[b]))
        errors[i]=error
        if error>tolerance:heapq.heappush(queue,(-error,i))
    for i in range(len(faces)):add(i)
    while queue:
        _,i=heapq.heappop(queue)
        if i in removed:continue
        tri=faces[i]
        a,b=max(((tri[j],tri[(j+1)%3]) for j in range(3)),key=lambda e:math.dist(world[e[0]],world[e[1]]))
        adjacent=list(edges[tuple(sorted((a,b)))])
        if len(adjacent)!=2:raise WaveError('BEND_MESH: aresta aberta durante o refinamento.')
        mid=len(vertices);vertices.append([(x+y)/2 for x,y in zip(vertices[a],vertices[b])]);world.append(tuple((x+y)/2 for x,y in zip(world[a],world[b])))
        if reference_world is not None:
            reference_world.append(tuple((x+y)/2 for x,y in zip(reference_world[a],reference_world[b])))
        if crease_edges is not None and tuple(sorted((a,b))) in crease_edges:
            crease_edges.remove(tuple(sorted((a,b))));crease_edges.update((tuple(sorted((a,mid))),tuple(sorted((mid,b)))))
        for j in adjacent:
            old=faces[j];removed.add(j)
            for u,v in zip(old,(*old[1:],old[0])):edges[tuple(sorted((u,v)))].discard(j)
            u,v,w=next((old[k],old[(k+1)%3],old[(k+2)%3]) for k in range(3) if {old[k],old[(k+1)%3]}=={a,b})
            for new in ((u,mid,w),(mid,v,w)):
                faces.append(new);add(len(faces)-1)
        if len(faces)-len(removed)>max_faces:raise WaveError(f'BEND_COMPLEXITY: refinamento supera {max_faces} faces.')
    result=[f for i,f in enumerate(faces) if i not in removed]
    # Vertices are immutable during refinement; surviving faces keep the same
    # complete face/crease certificate computed when they entered the queue.
    final=max((error for i,error in errors.items() if i not in removed),default=0.)
    return result,final


class BendingWarp(RegionalShellWarp):
    def __init__(self,snapshot,object_id,settings=None,region=None):
        self.object_id=str(object_id);self.region=dict(region or {});self.region_name=self.region.get('name','roof')
        self.settings=settings if isinstance(settings,RegionalShellSettings) else RegionalShellSettings(**(settings or {}))
        self.source_revision=snapshot.revision
        clean,normalization=normalize_snapshot(snapshot,self.object_id)
        if len(clean.objects)!=1:raise WaveError('BEND_SELECTION: deixe uma peça na placa para esta preparação.')
        obj=clean.objects[0];vol=obj['volumes'][0];inst=next(i for i in obj['instances_data'] if i.get('printable',True))
        self.mesh=mesh=SurfaceMesh(obj,SurfaceSettings())
        patches=roof_patches(mesh,vol['triangles'],self.settings.max_slope_deg)
        hint=self.region.get('top_plane_world')
        if hint is not None:
            seeds={i for i,f in enumerate(mesh.faces) if f.nz*mesh.orientation>0 and _same_plane(_plane(f),hint)}
            patches=[p for p in patches if p&seeds]
        threshold=max(4.,.02*(mesh.bounds[1][0]-mesh.bounds[0][0])*(mesh.bounds[1][1]-mesh.bounds[0][1]))
        candidates=[p for p in patches if sum(abs(mesh.faces[i].nz)/2 for i in p)>=threshold]
        if not candidates:raise WaveError('BEND_REGION: não há um teto conectado com área e inclinação suficientes.')
        ids=max(candidates,key=lambda p:(max(mesh.faces[i].zmax for i in p),sum(abs(mesh.faces[i].nz) for i in p)))
        self.top_faces=tuple(mesh.faces[i] for i in sorted(ids))
        # Area-weighted plane fit. Repeated STL tessellation does not bias selection.
        import numpy as np
        xyz=np.array([p for f in self.top_faces for p in f.points]);origin=xyz.mean(axis=0)
        weights=np.repeat(np.sqrt([abs(f.nz)/6 for f in self.top_faces]),3)
        design=np.column_stack((xyz[:,0]-origin[0],xyz[:,1]-origin[1],np.ones(len(xyz))))
        c=np.linalg.lstsq(design*weights[:,None],xyz[:,2]*weights,rcond=None)[0]
        self.top_plane=(float(c[0]),float(c[1]),float(c[2]-c[0]*origin[0]-c[1]*origin[1]))
        self.bottom_plane=self.top_plane;self.thickness_mm=0.;self.shell_scale=1.
        self.bounds_xy=tuple((mesh.bounds[0][k],mesh.bounds[1][k]) for k in (0,1))
        heights=[self._field(x,y) for x in self.bounds_xy[0] for y in self.bounds_xy[1]]
        h=self.settings.nominal_layer_height_mm
        self.flat_bottom_z=self.flat_top_z=math.ceil(max(p[2] for p in xyz)/h-1e-8)*h
        transition=max(5.,4*(max(heights)-min(heights)),10*h)
        self.anchor_z=max(mesh.bounds[0][2]+max(1.,5*h),min(min(heights),self.flat_top_z)-transition)
        if min(heights)<=self.anchor_z+max(.1,h):raise WaveError('BEND_HEIGHT: não há altura para preservar a base e a transição.')
        self.slope_deg=math.degrees(math.atan(math.hypot(*self.top_plane[:2])))
        if self.slope_deg>self.settings.max_slope_deg+1e-7:raise WaveError('BEND_SLOPE: plano ajustado supera a inclinação escolhida.')
        # Partition branch planes exactly. In barycentric coordinates the
        # roundtrip residual is sum(lambda_i*lambda_j*C_ij), with
        # C_ij=(D_j-D_i)*(n_i/D_i-n_j/D_j). Sum(lambda_i*lambda_j)<=1/3.
        # This bounds the complete face, including vertical walls, not samples.
        direction=_local_z_direction(inst['matrix'],vol['matrix'])
        world=[tuple(transform_point(p,inst['matrix'],vol['matrix'])) for p in vol['vertices']]
        self.original_world_vertices=tuple(world)
        vertices=copy.deepcopy(vol['vertices']);faces=[tuple(f) for f in vol['triangles']]
        initial=(len(vertices),len(faces))
        faces=_clip(vertices,faces,world,(0.,0.,1.,-self.anchor_z))
        faces=_clip(vertices,faces,world,(-self.top_plane[0],-self.top_plane[1],1.,-self.top_plane[2]))
        jmax=max(1.,(max(heights)-self.anchor_z)/(self.flat_top_z-self.anchor_z))
        def bound(points):
            if max(p[2] for p in points)<=self.anchor_z+1e-9 or all(p[2]>=self._field(*p[:2])-1e-9 for p in points):return 0.
            d=[self._field(*p[:2])-self.anchor_z for p in points]
            ratio=[(p[2]-self.anchor_z)/den for p,den in zip(points,d)]
            return max(abs((d[j]-d[i])*(ratio[i]-ratio[j])) for i in range(3) for j in range(i+1,3))/3
        faces,error=_refine(vertices,faces,world,bound,self.settings.tolerance_mm/2)
        flat=[]
        for local,p in zip(vertices,world):
            delta=self.flatten_point(p)[2]-p[2];flat.append([v+d*delta for v,d in zip(local,direction)])
        self.flattened_snapshot=copy.deepcopy(clean)
        target=self.flattened_snapshot.objects[0]['volumes'][0];target['vertices']=flat;target['triangles']=[list(f) for f in faces]
        SurfaceMesh(self.flattened_snapshot.objects[0],SurfaceSettings())
        residual=design@c-xyz[:,2]
        self.summary={'study_type':'roof_aligned_bending','surface_scope':'complete_solid_with_openings',
            'source_revision':self.source_revision,'top_plane_world':list(self.top_plane),
            'reference_roof_faces':len(ids),'reference_fit_max_residual_mm':float(abs(residual).max()),
            'anchor_z_mm':self.anchor_z,'flat_reference_z_mm':self.flat_top_z,'slope_deg':self.slope_deg,
            'xy_preserved':True,'base_unchanged':True,'holes_preserved':True,'planar_collar_mm':0.,
            'normalization':normalization,'added_vertices':len(vertices)-initial[0],'added_faces':len(faces)-initial[1],
            'mesh_roundtrip_error_bound_mm':error,'reference':'fitted roof plane; residual curvature retained',
            'min_vertical_jacobian':min(1.,(min(heights)-self.anchor_z)/(self.flat_top_z-self.anchor_z)),
            'max_vertical_jacobian':jmax,'physical_validation':False,'print_allowed':False}

    def _field(self,x,y):return super()._field(x,y)
    def _field_gradient(self,x,y):return super()._field_gradient(x,y)
    def expected_surface(self,x,y,face='top'):
        if face!='top':return None
        from .regional_shell import _contains_triangle
        zs=[f.height(x,y) for f in self.top_faces if f.xmin-1e-8<=x<=f.xmax+1e-8 and f.ymin-1e-8<=y<=f.ymax+1e-8 and _contains_triangle(f,x,y)]
        return max(zs) if zs else None
    def surface_heights(self,x,y):
        z=self.expected_surface(x,y)
        return (z,self.flatten_point((x,y,z))[2]) if z is not None else None
