"""Smooth joint surface coordinates with original-face and crease bounds."""
from __future__ import annotations
import copy
import math
from functools import lru_cache
import numpy as np
from .bending import _refine,_clip
from .continuous_layers import _creases
from .contracts import WaveError
from .geometry import transform_point
from .mesh_normalization import normalize_snapshot
from .regional_shell import _local_z_direction
from .surface_coordinates import SurfaceCoordinates


class SplineLayerWarp(SurfaceCoordinates):
    def __init__(self,snapshot,object_id,field,layer_grid,settings,*,reference_audit,
                 progress=lambda message:None,cancelled=lambda:False):
        self.object_id=str(object_id);self.source_revision=snapshot.revision
        self.grid=field;self.layer_grid=layer_grid;self.settings=settings;self.anchor_z=field.anchor
        self.nominal_slice_height_mm=settings.nominal_layer_height_mm
        self.spacing_enabled=False;self.finite_beads=True;self.resample_full_edges=False
        clean,normalization=normalize_snapshot(snapshot,self.object_id)
        obj=clean.objects[0];volume=obj['volumes'][0];instance=next(i for i in obj['instances_data'] if i.get('printable',True))
        direction=_local_z_direction(instance['matrix'],volume['matrix'])
        vertices=copy.deepcopy(volume['vertices']);faces=[tuple(f) for f in volume['triangles']]
        world=[tuple(transform_point(v,instance['matrix'],volume['matrix'])) for v in vertices]
        reference=list(world);self.original_world_vertices=tuple(world);creases=_creases(faces,world);calls=0
        def bound(points,original):
            nonlocal calls
            calls+=1
            if calls%4096==0:
                if cancelled():raise WaveError('Geração cancelada.')
                progress(f'Conferindo transições suaves: {calls} faces adicionais…')
            p=np.asarray(original);n=np.cross(p[1]-p[0],p[2]-p[0]);length=float(np.linalg.norm(n))
            if length<1e-20:raise WaveError('SPLINE_REFERENCE: face original degenerada.')
            if abs(n[2])<=1e-12*length:return 0.
            return abs(n[2])/length*field.inverse_phase_error(p,field.phase_triangle_error(p))+1e-8
        edge_calls=0
        @lru_cache(maxsize=300000)
        def edge(a,b):
            nonlocal edge_calls
            edge_calls+=1
            if edge_calls%2048==0:
                if cancelled():raise WaveError('Geração cancelada.')
                progress(f'Conferindo quinas no campo suave: {edge_calls} arestas…')
            if math.dist(a[:2],b[:2])<1e-10:return 0.
            return field.inverse_phase_error((a,b),field.phase_edge_error(a,b))+1e-8
        def batch(points,triangles,original):
            p=np.asarray(original)[np.asarray(triangles)];d=np.roll(p,-1,axis=1)-p
            n=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]);length=np.linalg.norm(n,axis=1)
            if np.any(length<1e-20):raise WaveError('SPLINE_REFERENCE: face original degenerada.')
            h={key:float(abs(values).max()) for key,values in field.hessian.items()}
            curvature=sum(h[i,j]*abs(d[:,:,i]*d[:,:,j])*(1 if i==j else 2) for i,j in h)
            error=abs(n[:,2])/length*curvature.max(axis=1)/(6*field.cmin)+1e-8
            return np.where((abs(n[:,2])<=1e-12*length)|(p[:,:,2].max(axis=1)<=field.anchor),0.,error)
        progress('Preservando o formato e as quinas com um campo contínuo suave…')
        faces,error=_refine(vertices,faces,world,bound,settings.tolerance_mm,max_faces=3000000,
            crease_edges=creases,edge_bound=lambda a,b,ra,rb:edge(*sorted((tuple(ra),tuple(rb)))),
            reference_world=reference,batch_bound=batch)
        edge.cache_clear();phase=field.flatten_points(np.asarray(world))
        local_phase=[[v+d*(q[2]-p[2]) for v,d in zip(local,direction)] for local,p,q in zip(vertices,world,phase)]
        phase_world=list(map(tuple,phase))
        for k,value in layer_grid.clipping_planes():
            if cancelled():raise WaveError('Geração cancelada.')
            plane=[0.,0.,0.,-value];plane[k]=1.
            faces=_clip(local_phase,faces,phase_world,plane,reference_world=reference)
            if len(faces)>3000000:raise WaveError('SPLINE_COMPLEXITY: alinhamento supera três milhões de faces.')
        flat=[layer_grid.flatten_point(p) for p in phase_world]
        vertices=[[v+d*(q[2]-p[2]) for v,d in zip(local,direction)] for local,p,q in zip(local_phase,phase_world,flat)]
        self.flattened_snapshot=copy.deepcopy(clean);target=self.flattened_snapshot.objects[0]['volumes'][0]
        target['vertices']=vertices;target['triangles']=[list(f) for f in faces]
        self.reference_world_vertices=tuple(reference);self.flat_world_vertices=tuple(flat)
        self.summary={'study_type':'smooth_joint_surface_phase','transition_kernel':'cubic_spline_phase_v1',
            'source_revision':snapshot.revision,'normalization':normalization,
            'mesh_normal_and_crease_error_budget_mm':float(error),
            'mesh_certificate':'complete C2 phase Hessian interpolation bound on original faces and creases, divided by positive phase-Z derivative',
            'flattened_faces':len(faces),'flattened_vertices':len(vertices),'positive_jacobian':True,
            'grid_bounds':field.bounds,'reference_alignment':reference_audit['reference_regions'],
            'reference_scope':'at least 90 percent of each source patch covered by complete C2 subtriangle band bounds',
            'optimizer_status':reference_audit['optimizer_status'],'independent_checks_required':True,
            'reference_certificate_version':reference_audit.get('whole_reference_band_certificate_version'),
            'partial_adaptation':False,'source_mesh_unchanged':True,'xy_preserved':True,'base_unchanged':True,
            'holes_preserved':True,'enforce_height_limits':True,'physical_validation':False,'print_allowed':False}
