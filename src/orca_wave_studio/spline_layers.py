"""Smooth joint surface coordinates with original-face and crease bounds."""
from __future__ import annotations
import copy
from dataclasses import replace
import numpy as np
from .bending import _clip
from .continuous_layers import _creases
from .contracts import WaveError
from .geometry import transform_point
from .mesh_normalization import normalize_snapshot
from .regional_shell import _local_z_direction
from .surface_coordinates import SurfaceCoordinates
from .certified_refinement import refine_mesh


def _face_bounds(field,p,tolerance):
    """Accept a cheap complete global enclosure, tighten only when necessary."""
    n=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]);length=np.linalg.norm(n,axis=1)
    if np.any(length<1e-20):raise WaveError('SPLINE_REFERENCE: face original degenerada.')
    projection=abs(n[:,2])/length
    d=np.roll(p,-1,axis=1)-p
    curve=sum(h*abs(d[:,:,i]*d[:,:,j])*(1 if i==j else 2) for (i,j),h in field.global_hessian.items())
    error=projection*(curve.max(axis=1)/6+1e-9)/field.cmin+1e-8
    inactive=(abs(n[:,2])<=1e-12*length)|(p[:,:,2].max(axis=1)<=field.anchor)
    error[inactive]=0.
    tighten=error>tolerance;q=p[tighten]
    if len(q):error[tighten]=projection[tighten]*field.inverse_phase_errors(q,field.phase_triangle_errors(q))+1e-8
    return error


def _crease_bounds(field,p,tolerance):
    d=p[:,1]-p[:,0]
    curve=sum(h*abs(d[:,i]*d[:,j])*(1 if i==j else 2) for (i,j),h in field.global_hessian.items())
    error=(curve/8+1e-9)/field.cmin+1e-8
    inactive=np.linalg.norm(d[:,:2],axis=1)<1e-10
    error[inactive]=0.
    tighten=error>tolerance;q=p[tighten]
    if len(q):error[tighten]=field.inverse_phase_errors(q,field.phase_edge_errors(q))+1e-8
    return error


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
        reference=list(world);self.original_world_vertices=tuple(world);creases=_creases(faces,world)
        def batch(points,triangles,original):
            p=np.asarray(original)[np.asarray(triangles)]
            return _face_bounds(field,p,settings.tolerance_mm)
        progress('Preservando o formato e as quinas com um campo contínuo suave…')
        def edge_batch(points):
            return _crease_bounds(field,points,settings.tolerance_mm)
        faces,error=refine_mesh(vertices,faces,world,settings.tolerance_mm,3000000,
            reference_world=reference,crease_edges=creases,face_bounds=batch,edge_bounds=edge_batch,
            cancelled=cancelled,progress=progress)
        phase=field.flatten_points(np.asarray(world))
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

    def replan_spacing(self,profile,minimum,maximum,failure,*,feedback=None,progress=lambda message:None,cancelled=lambda:False):
        """Quantize the same phase field at a compatible pitch, then re-slice.

        This adjusts the slicing copy, never an already restored G-code. The
        same whole-reference certificates must fit the new native slice bands.
        """
        from .phase_planning import assess_phase_field
        from .bead_deposition import BeadMinimumError
        if cancelled():raise WaveError('Geração cancelada.')
        before=self.nominal_slice_height_mm
        ceiling=before*min(.99,.99*failure.limit_mm/failure.height_mm)
        floor=None;preferred=None
        if isinstance(failure,BeadMinimumError) and feedback is None:
            raise WaveError('BEAD_REPLAN: a correção da altura mínima precisa da conferência completa de espaçamento.')
        if feedback is not None:
            floor=before*minimum/feedback['minimum_mm']
            ceiling=before*maximum/feedback['maximum_mm']
            if isinstance(failure,BeadMinimumError):floor=max(floor,before*failure.limit_mm/failure.height_mm)
            else:ceiling=min(ceiling,before*failure.limit_mm/failure.height_mm)
            preferred=(floor+ceiling)/2
        regions=getattr(self,'_spacing_regions',None)
        if not regions:raise WaveError('BEAD_REPLAN: faltam as referências completas para redistribuir as camadas.')
        progress('Conferindo novamente as superfícies para um espaçamento compatível…')
        candidate=assess_phase_field(self.grid,regions,profile,minimum,maximum,
            'same phase; emitted bead spacing retry',self.anchor_z,self.grid.domain[2][1],
            require_global_profile_bounds=False,pitch_ceiling=ceiling,pitch_floor=floor,preferred_pitch=preferred)
        if candidate is None:
            raise WaveError('BEAD_REPLAN: não há espaçamento compatível com as superfícies alinhadas dentro do perfil.')
        _,grid,audit=candidate
        self.regrid_phase(grid,audit,cancelled=cancelled)
        record={'failed_height_mm':failure.height_mm,'profile_maximum_mm':maximum,
                'profile_minimum_mm':minimum,'sampled_feedback':feedback,
                'previous_pitch_mm':before,'new_pitch_mm':self.nominal_slice_height_mm,
                'same_phase_field':True,'reference_bands_reverified':True,'new_native_slice_required':True}
        self.summary.setdefault('automatic_spacing',[]).append(record)
        progress(f'Redistribuindo as camadas: {before:.5f} → {self.nominal_slice_height_mm:.5f} mm; perfil preservado…')
        return record

    def regrid_phase(self,grid,audit,*,cancelled=lambda:False):
        """Pair an affine copy change with its inverse; inherit the mesh bound.

        Splitting at BOTH maps' knots makes the conversion affine on every
        triangle. Restoring the new copy therefore gives exactly the same
        preceding phase triangle and its existing source/crease certificate.
        """
        if not all(r.get('core_in_one_band') and r.get('certified_reference_area_fraction',0)>=.9
                   for r in audit['reference_regions']):
            raise WaveError('BEAD_ALIGNMENT: uma superfície perdeu a faixa certificada.')
        old=self.layer_grid;obj=self.flattened_snapshot.objects[0];vol=obj['volumes'][0]
        instance=next(i for i in obj['instances_data'] if i.get('printable',True))
        vertices=copy.deepcopy(vol['vertices']);faces=[tuple(f) for f in vol['triangles']]
        world=list(self.flat_world_vertices);references=list(self.reference_world_vertices)
        for value in grid.physical:
            if cancelled():raise WaveError('Geração cancelada.')
            plane=[0.,0.,1.,-old.flatten_point((0,0,value))[2]]
            faces=_clip(vertices,faces,world,plane,reference_world=references)
            if len(faces)>3000000:raise WaveError('BEAD_COMPLEXITY: redistribuição supera três milhões de faces.')
        phase=np.asarray(world,dtype=float);z=phase[:,2]
        phase[:,2]=np.where((z<=old.flat[0])|(z>=old.flat[-1]),z,np.interp(z,old.flat,old.physical))
        flat=phase.copy();z=phase[:,2]
        flat[:,2]=np.where((z<=grid.physical[0])|(z>=grid.physical[-1]),z,np.interp(z,grid.physical,grid.flat))
        direction=_local_z_direction(instance['matrix'],vol['matrix'])
        vertices=[[v+d*(q[2]-p[2]) for v,d in zip(local,direction)] for local,p,q in zip(vertices,world,flat)]
        if cancelled():raise WaveError('Geração cancelada.')
        vol['vertices']=vertices;vol['triangles']=[list(f) for f in faces]
        self.layer_grid=grid;self.reference_world_vertices=tuple(references);self.flat_world_vertices=tuple(map(tuple,flat))
        self.nominal_slice_height_mm=audit['pitch'];self.settings=replace(self.settings,nominal_layer_height_mm=audit['pitch'])
        self.summary.update(reference_alignment=audit['reference_regions'],flattened_faces=len(faces),flattened_vertices=len(vertices),
            reference_certificate_version=audit['whole_reference_band_certificate_version'])
