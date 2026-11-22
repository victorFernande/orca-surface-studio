"""Joint phase planning with independent geometric acceptance criteria.

The optimizer proposes a field. A solver status, alone, never accepts a mesh
or a print: complete C2 derivative bounds, actual reference bands and emitted
finite bead heights are checked separately.
"""
from __future__ import annotations
import math
import numpy as np

from .contracts import WaveError
from .continuous_layers import HeightField,LayerGridStage
from .bending import roof_patches
from .mesh_normalization import normalize_snapshot
from .surface import SurfaceMesh,SurfaceSettings


def _surface_quadrature(faces,spacing=1.2,*,cancelled=lambda:False):
    """Area-weighted interior samples, plus a dense constraint mesh.

    Original corner vertices alone miss phase bumps inside large STL faces.
    Each accepted subtriangle contributes its centroid and exact projected
    area. Its vertices also participate in the proposed reference fit.
    """
    points=[];weights=[];constraints=[];triangles=[]
    for face in faces:
        pending=[np.asarray(face.points,dtype=float)]
        while pending:
            if len(points)%1024==0 and cancelled():raise WaveError('Geração cancelada.')
            tri=pending.pop()
            if max(np.linalg.norm(a[:2]-b[:2]) for a,b in zip(tri,np.roll(tri,-1,axis=0)))<=spacing:
                area=abs(float(np.cross(tri[1]-tri[0],tri[2]-tri[0])[2]))/2
                points.append(tri.mean(axis=0));weights.append(area);constraints.extend(tri);triangles.append(tri)
            else:
                a,b,c=tri;ab=(a+b)/2;bc=(b+c)/2;ca=(c+a)/2
                pending.extend((np.array([a,ab,ca]),np.array([ab,b,bc]),np.array([ca,bc,c]),np.array([ab,bc,ca])))
            if len(points)+len(pending)>200000:
                raise WaveError('SPLINE_REFERENCES: a referência excede o limite deste estudo.')
    return np.asarray(points),np.asarray(weights),np.unique(np.asarray(constraints),axis=0),np.asarray(triangles)


def _references(snapshot,object_id,slope,extension,*,cancelled=lambda:False):
    clean,_=normalize_snapshot(snapshot,object_id);obj=clean.objects[0]
    mesh=SurfaceMesh(obj,SurfaceSettings());threshold=max(4.,.02*math.prod(mesh.bounds[1][k]-mesh.bounds[0][k] for k in (0,1)))
    regions=[]
    for patch in roof_patches(mesh,obj['volumes'][0]['triangles'],slope):
        faces=[mesh.faces[i] for i in patch];area=sum(abs(f.nz)/2 for f in faces)
        if area<threshold:continue
        points=np.asarray([p for f in faces for p in f.points]);weights=np.repeat(np.asarray([abs(f.nz)/6 for f in faces]),3)
        field=HeightField(points,np.sqrt(weights),extension)
        interior,interior_weights,unique,triangles=_surface_quadrature(faces,cancelled=cancelled)
        fitted=unique.copy();fitted[:,2]=[field.height(x,y) for x,y in unique[:,:2]]
        regions.append({'points':interior,'weights':interior_weights,'fitted':fitted,'area':area,
                        'reference_sampling':'subtriangle interiors weighted by exact projected area; max XY edge 1.2 mm',
                        'surface_triangles':triangles,
                        'original_z_range':[float(points[:,2].min()),float(points[:,2].max())],
                        'fit_rms_mm':field.rms,'fit_maximum_residual_mm':field.max_residual})
    if not regions:raise WaveError('PHASE_REFERENCE: não há superfícies extensas compatíveis para estudar.')
    return mesh,regions




def assess_phase_field(grid,regions,profile,minimum,maximum,status,anchor,cap,*,require_global_profile_bounds=True):
    bounds=grid.bounds
    rows=[];enclosures=[]
    for region in regions:
        phase=grid.flatten_points(region['points'])[:,2];order=np.argsort(phase)
        cumulative=np.cumsum(region['weights'][order]);cumulative/=cumulative[-1]
        low,high=np.interp([.05,.95],cumulative,phase[order])
        rows.append({'original_z_range':region['original_z_range'],'area':region['area'],
            'fit_rms_mm':region['fit_rms_mm'],'fit_maximum_residual_mm':region['fit_maximum_residual_mm'],
            'reference_sampling':region.get('reference_sampling','legacy vertices'),
            'core_phase_interval':[float(low),float(high)],'phase_center':float((low+high)/2),
            'core_span':float(high-low),'all_phase_interval':[float(phase.min()),float(phase.max())]})
        triangles=region.get('surface_triangles')
        if triangles is None:
            raise WaveError('SPLINE_REFERENCE_COVERAGE: faltam os interiores das faces de referência.')
        mapped=grid.flatten_points(triangles)[:,:,2]
        errors=np.array([grid.phase_triangle_error(triangle) for triangle in triangles])
        enclosures.append(np.stack((mapped.min(axis=1)-errors,mapped.max(axis=1)+errors),axis=-1))
    choices=[];first=profile.initial_layer_mm
    for value in np.linspace(max(minimum,profile.layer_mm*.8),min(maximum,profile.layer_mm*1.05),51):
        pitch=round(float(value),5);old=[anchor];new=[anchor]
        groups=[]
        for row in sorted(rows,key=lambda r:r['core_phase_interval'][0]):
            left,right=row['core_phase_interval']
            if (groups and left-groups[-1][1]<pitch*.25 and max(right,groups[-1][1])-groups[-1][0]<pitch*.9):
                groups[-1][1]=max(right,groups[-1][1])
            else:groups.append([left,right])
        for left,right in groups:
            level=(left+right)/2
            if level<=anchor+1e-5:break
            target=first+round((level-first)/pitch)*pitch
            if target<=new[-1]+1e-6:target=new[-1]+pitch
            old.append(level);new.append(target)
        else:
            if cap<=max(old[-1],new[-1])+1e-6:continue
            old.append(cap);new.append(cap);regrid=LayerGridStage(new,old)
            lower=pitch*regrid.jmin/(bounds['maximum_phase_z_derivative']*math.hypot(1,bounds['maximum_slope']))
            upper=pitch*regrid.jmax/bounds['minimum_phase_z_derivative']
            same=True
            for row in rows:
                a,b=[regrid.flatten_point((0,0,z))[2] for z in row['core_phase_interval']]
                same &= int(math.floor((a-first)/pitch+.5))==int(math.floor((b-first)/pitch+.5))
            coverage=[]
            for row,region,intervals in zip(rows,regions,enclosures):
                z=intervals.ravel()
                mapped=np.where((z<=regrid.physical[0])|(z>=regrid.physical[-1]),z,
                                np.interp(z,regrid.physical,regrid.flat)).reshape(intervals.shape)
                center=regrid.flatten_point((0,0,row['phase_center']))[2]
                band=int(math.floor((center-first)/pitch+.5))
                low=first+(band-.5)*pitch;high=low+pitch
                contained=(mapped[:,0]>=low)&(mapped[:,1]<=high)
                fraction=float(region['weights'][contained].sum()/region['weights'].sum())
                coverage.append(fraction);same &= fraction>=.90
            if same and (not require_global_profile_bounds or (lower>=minimum+.001 and upper<=maximum-.001)):
                score=min(lower-minimum,maximum-upper) if require_global_profile_bounds else -abs(pitch-profile.layer_mm)
                choices.append((score,pitch,new,old,lower,upper,coverage))
    if not choices:return None
    _,pitch,new,old,lower,upper,coverage=max(choices);regrid=LayerGridStage(new,old)
    for row,fraction in zip(rows,coverage):
        row['quantized_core_phase_interval']=[regrid.flatten_point((0,0,z))[2] for z in row['core_phase_interval']]
        row['core_in_one_band']=True
        row['certified_reference_area_fraction']=fraction
        row['band_certificate']='complete C2 Hessian phase enclosure on each included original subtriangle'
    audit={'optimizer_status':status,'acceptance':'independent whole-grid derivatives, finite-height bounds and area-weighted reference bands',
        'reference_regions':rows,'pitch':pitch,'normal_gap_lower_bound_mm':lower,'vertical_gap_upper_bound_mm':upper,
        'profile_height_bounds_pass':lower>=minimum and upper<=maximum,'all_reference_cores_in_one_band':True,
        'whole_reference_band_certificate_version':2,
        'emitted_profile_audit_required':not require_global_profile_bounds,
        'physical_validation':False,'print_allowed':False}
    return grid,regrid,audit


