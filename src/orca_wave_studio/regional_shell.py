"""Experimental paired-skin roof transform, with an analytic chord certificate.

This deliberately accepts only rectangular, parallel planar skins and vertical
walls above an unchanged base. It does not claim a general Benchy solver.
Coordinates outside the roof use the continuous clamped extension of its plane,
so support/travel paths do not jump at the footprint boundary. Physical support
gaps, material deposition and collision/order approval belong to a later audit.
"""
from __future__ import annotations

import copy
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from itertools import pairwise

from .contracts import ProjectSnapshot, WaveError
from .geometry import transform_point
from .mesh_normalization import normalize_snapshot
from .surface import SurfaceMesh, SurfaceSettings


@dataclass(frozen=True)
class RegionalShellSettings:
    step_mm: float = .4
    min_segment_mm: float = .15
    tolerance_mm: float = .02
    max_slope_deg: float = 30.
    nominal_layer_height_mm: float = .2
    anchor_z_mm: float | None = None
    retain_native_short_edges: bool = False
    align_layer_grid_to_anchor: bool = False
    max_curve_height_mm: float | None = None

    def __post_init__(self):
        numeric = {k:v for k,v in asdict(self).items()
                   if k not in {'retain_native_short_edges', 'align_layer_grid_to_anchor'} and v is not None}
        if not all(type(v) in (int,float) and math.isfinite(v) for v in numeric.values()):
            raise WaveError('REGIONAL_SETTINGS: use números finitos.')
        if type(self.retain_native_short_edges) is not bool or type(self.align_layer_grid_to_anchor) is not bool:
            raise WaveError('REGIONAL_SETTINGS: preservação de quinas deve ser booleana e explícita.')
        if not (.15 <= self.min_segment_mm <= self.step_mm <= 2
                and 0 < self.tolerance_mm <= .02 and 0 < self.max_slope_deg < 90
                and 0 < self.nominal_layer_height_mm <= 1
                and (self.anchor_z_mm is None or self.anchor_z_mm >= 0)):
            raise WaveError('REGIONAL_SETTINGS: limites de amostragem, camada ou inclinação inválidos.')
        h=self.max_curve_height_mm
        if h is not None and (not .1<=h<=5. or abs(h*10-round(h*10))>1e-8):
            raise WaveError('CURVE_HEIGHT: use de 0,1 a 5,0 mm, em passos de 0,1 mm.')


def _plane(face):
    x,y,z = face.points[0]
    return face.gx,face.gy,z-face.gx*x-face.gy*y


def _same_plane(a,b):
    return max(abs(x-y) for x,y in zip(a,b)) <= 1e-7


def _height(plane,x,y):
    return plane[0]*x+plane[1]*y+plane[2]


def _contains_triangle(face,x,y):
    a,b,c = face.points
    u=((c[1]-a[1])*(x-a[0])+(a[0]-c[0])*(y-a[1]))/face.nz
    v=((a[1]-b[1])*(x-a[0])+(b[0]-a[0])*(y-a[1]))/face.nz
    return min(u,v,1-u-v) >= -1e-8


def _local_z_direction(instance,volume):
    if any(tuple(m[3]) != (0.,0.,0.,1.) for m in (instance,volume)):
        raise WaveError('REGIONAL_TRANSFORM: a transformação precisa ser afim.')
    m=[[sum(instance[i][k]*volume[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    a,b,c=m
    cof=(a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
    det=sum(x*y for x,y in zip(c,cof))
    if abs(det)<1e-14:
        raise WaveError('REGIONAL_TRANSFORM: transformação singular.')
    return tuple(x/det for x in cof)


class RegionalShellWarp:
    """Flatten both roof skins while fixing the base and retaining every edge.

    ``region`` may specify ``bounds_xy_world_mm``, ``anchor_z_mm`` and plane
    hints ``top_plane_world``/``bottom_plane_world``. Bounds must cover the
    entire detected top. An arbitrary interior cut cannot silently acquire a
    discontinuous transition. ``expected_surface(..., 'bottom')`` is the paired
    plane; ``surface_is_exposed`` distinguishes actual underside from the
    virtual continuation through an integrated support/stem.
    """
    def __init__(self,snapshot:ProjectSnapshot,object_id:str,settings=None,region=None):
        self.object_id=str(object_id)
        try:
            self.settings=(settings if isinstance(settings,RegionalShellSettings)
                           else RegionalShellSettings(**(settings or {})))
        except TypeError as exc:
            raise WaveError(f'REGIONAL_SETTINGS: configuração desconhecida ou inválida: {exc}') from exc
        if region is not None and not isinstance(region,dict):
            raise WaveError('REGIONAL_REGION: a seleção precisa descrever uma região retangular.')
        self.region=dict(region or {})
        self.region_name=str(self.region.get('name','paired_roof'))
        for key in ('top_plane_world','bottom_plane_world'):
            value=self.region.get(key)
            if value is not None and (not isinstance(value,(list,tuple)) or len(value)!=3
                    or not all(type(v) in (int,float) and math.isfinite(v) for v in value)):
                self._reject('INVALID_REGION',f'{key} precisa conter três coeficientes finitos.')
        self.source_revision=snapshot.revision
        clean,normalization=normalize_snapshot(snapshot,self.object_id)
        if len(clean.objects)!=1 or str(clean.objects[0]['id'])!=self.object_id:
            self._reject('MULTI_OBJECT','a primeira prova aceita uma peça por placa.')
        obj=clean.objects[0]
        self.mesh=SurfaceMesh(obj,SurfaceSettings())
        up=[(i,f) for i,f in enumerate(self.mesh.faces) if f.nz*self.mesh.orientation>1e-10]
        down=[(i,f) for i,f in enumerate(self.mesh.faces) if f.nz*self.mesh.orientation<-1e-10]
        if not up or not down:
            self._reject('UNPAIRED_SKINS','não há faces superior e inferior orientadas.')
        top_hint=self.region.get('top_plane_world')
        selected=([(i,f) for i,f in up if _same_plane(_plane(f),top_hint)] if top_hint is not None else up)
        if not selected:
            self._reject('UNMATCHED_REGION','o plano superior solicitado não pertence à malha.')
        _,highest=max(selected,key=lambda pair:pair[1].zmax)
        self.top_plane=_plane(highest)
        top_ids={i for i,f in up if _same_plane(_plane(f),self.top_plane)}
        self.top_faces=tuple(self.mesh.faces[i] for i in sorted(top_ids))
        self.bounds_xy=tuple((min(p[k] for f in self.top_faces for p in f.points),
                              max(p[k] for f in self.top_faces for p in f.points)) for k in (0,1))
        if min(hi-lo for lo,hi in self.bounds_xy)<=1e-8:
            self._reject('EMPTY_REGION','a projeção do teto é vazia.')
        requested=self.region.get('bounds_xy_world_mm')
        expected=((self.bounds_xy[0][0],self.bounds_xy[1][0]),(self.bounds_xy[0][1],self.bounds_xy[1][1]))
        if requested is not None:
            if (not isinstance(requested,(list,tuple)) or len(requested)!=2
                    or any(not isinstance(row,(list,tuple)) or len(row)!=2 for row in requested)
                    or not all(type(v) in (int,float) and math.isfinite(v) for row in requested for v in row)):
                self._reject('INVALID_REGION','os limites XY precisam conter dois pares finitos.')
            if max(abs(requested[i][j]-expected[i][j]) for i in (0,1) for j in (0,1))>1e-6:
                self._reject('TRANSITION_UNPROVEN','um recorte interior exigiria uma transição ainda não demonstrada.')
        self._validate_rectangular_top(obj['volumes'][0]['triangles'],top_ids)
        candidates=[]
        for i,f in down:
            plane=_plane(f)
            if max(abs(plane[k]-self.top_plane[k]) for k in (0,1))<=1e-8:
                thickness=self.top_plane[2]-plane[2]
                if thickness>1e-7:
                    candidates.append((plane[2],plane))
        bottom_hint=self.region.get('bottom_plane_world')
        if bottom_hint is not None:
            candidates=[item for item in candidates if _same_plane(item[1],bottom_hint)]
        if not candidates:
            self._reject('UNPAIRED_SKINS','a face inferior precisa ser paralela ao teto nesta prova.')
        self.bottom_plane=max(candidates,key=lambda item:item[0])[1]
        self.thickness_mm=self.top_plane[2]-self.bottom_plane[2]
        bottom_ids={i for i,f in down if _same_plane(_plane(f),self.bottom_plane)}
        self.bottom_faces=tuple(self.mesh.faces[i] for i in sorted(bottom_ids))
        corners=[(x,y) for x in self.bounds_xy[0] for y in self.bounds_xy[1]]
        bottom_range=[min(_height(self.bottom_plane,*p) for p in corners),
                      max(_height(self.bottom_plane,*p) for p in corners)]
        hint_anchor=self.region.get('anchor_z_mm',self.settings.anchor_z_mm)
        if (self.region.get('anchor_z_mm') is not None and self.settings.anchor_z_mm is not None
                and abs(self.region['anchor_z_mm']-self.settings.anchor_z_mm)>1e-8):
            self._reject('ANCHOR_CONFLICT','a seleção e as configurações indicam âncoras diferentes.')
        if hint_anchor is None:
            bases=[f.points[0][2] for i,f in up if i not in top_ids and f.gradient<1e-10
                   and f.points[0][2]<bottom_range[0]-1e-7]
            hint_anchor=max(bases,default=0.)
        if type(hint_anchor) not in (int,float) or not math.isfinite(hint_anchor) or hint_anchor<0:
            self._reject('INVALID_ANCHOR','a âncora precisa ser finita e não negativa.')
        self.anchor_z=float(hint_anchor)
        if bottom_range[0]-self.anchor_z<=1e-6:
            self._reject('NONPOSITIVE_JACOBIAN','a face inferior alcança ou atravessa a base fixa.')
        slope=math.degrees(math.atan(math.hypot(*self.top_plane[:2])))
        if slope>self.settings.max_slope_deg+1e-7:
            self._reject('SLOPE_EXCEEDED',f'inclinação {slope:.6f}° acima do limite geométrico solicitado.')
        self.slope_deg=slope
        h=self.settings.nominal_layer_height_mm
        grid_origin = self.anchor_z if self.settings.align_layer_grid_to_anchor else 0.
        self.flat_bottom_z=grid_origin+math.ceil((bottom_range[1]-grid_origin)/h-1e-8)*h
        flat_thickness=math.ceil(self.thickness_mm/h-1e-8)*h
        self.flat_top_z=self.flat_bottom_z+flat_thickness
        self.shell_scale=self.thickness_mm/flat_thickness
        self._validate_other_faces(top_ids,bottom_ids)
        self.flattened_snapshot=copy.deepcopy(clean)
        vol=obj['volumes'][0];instance=next(i for i in obj['instances_data'] if i.get('printable',True))
        direction=_local_z_direction(instance['matrix'],vol['matrix'])
        self.original_world_vertices=tuple(tuple(transform_point(v,instance['matrix'],vol['matrix']))
                                           for v in vol['vertices'])
        flat_vertices=[]
        for local,world in zip(vol['vertices'],self.original_world_vertices):
            delta=self.flatten_point(world)[2]-world[2]
            flat_vertices.append([v+d*delta for v,d in zip(local,direction)])
        self.flattened_snapshot.objects[0]['volumes'][0]['vertices']=flat_vertices
        SurfaceMesh(self.flattened_snapshot.objects[0],SurfaceSettings())
        min_scale=min(1.,self.shell_scale,(bottom_range[0]-self.anchor_z)/(self.flat_bottom_z-self.anchor_z))
        rectangle_area=(self.bounds_xy[0][1]-self.bounds_xy[0][0])*(self.bounds_xy[1][1]-self.bounds_xy[1][0])
        self.summary={
            'study_type':'regional_paired_shell_experimental','object_id':self.object_id,
            'region':self.region_name,'surface_scope':'complete_rectangular_paired_shell',
            'source_revision':self.source_revision,'normalized_revision':clean.revision,
            'flattened_revision':self.flattened_snapshot.revision,'normalization':normalization,
            'bounds_xy_world_mm':[list(expected[0]),list(expected[1])],
            'top_plane_world':list(self.top_plane),'bottom_plane_world':list(self.bottom_plane),
            'anchor_z_mm':self.anchor_z,'flat_bottom_z_mm':self.flat_bottom_z,'flat_top_z_mm':self.flat_top_z,
            'nominal_layer_height_mm':h,'thickness_mm':self.thickness_mm,'slope_deg':slope,
            'min_vertical_jacobian':min_scale,'max_vertical_jacobian':max(1.,self.shell_scale),
            'projected_top_area_mm2':rectangle_area,
            'projected_exposed_underside_area_mm2':sum(abs(f.nz)/2 for f in self.bottom_faces),
            'top_triangle_indices':sorted(top_ids),'underside_triangle_indices':sorted(bottom_ids),
            'planar_collar_mm':0.,'xy_preserved':True,'base_unchanged':True,
            'support_extension':'continuous XY-clamped plane; piecewise differentiable; never a physical approval',
            'volume_model':'exact vertical cell Jacobian; finite bead shape and support interface unvalidated',
            'normal_gap_model':'local tangent spacing; exact on parallel planar shell layers',
            'chord_certificate':'analytic piecewise quadratic extrema including clamp/layer boundaries and endpoint rounding',
            'geometry_mapping_validated':True,'material_deposition_validated':False,
            'support_gap_validated':False,'collision_order_validated':False,
            'native_preview_validated':False,'physical_validation':False,'print_allowed':False,
            'settings':asdict(self.settings),
        }

    def _reject(self,code,detail):
        raise WaveError(f'REGIONAL_{code} [{self.region_name}]: {detail}')

    def _validate_rectangular_top(self,triangles,ids):
        edges=defaultdict(int)
        for i in ids:
            tri=triangles[i]
            for a,b in zip(tri,(*tri[1:],tri[0])):edges[tuple(sorted((a,b)))]+=1
        verts={i:p for face_id in ids for i,p in zip(triangles[face_id],self.mesh.faces[face_id].points)}
        boundary=[edge for edge,count in edges.items() if count==1]
        if not boundary:
            self._reject('HOLES_OR_TOPOLOGY','o teto não tem fronteira retangular simples.')
        for a,b in boundary:
            p,q=verts[a],verts[b]
            if not any(abs(p[k]-edge)<1e-7 and abs(q[k]-edge)<1e-7
                       for k in (0,1) for edge in self.bounds_xy[k]):
                self._reject('HOLES_OR_TOPOLOGY','há furo, recorte ou fronteira interna no teto.')
        area=sum(abs(self.mesh.faces[i].nz)/2 for i in ids)
        expected=math.prod(hi-lo for lo,hi in self.bounds_xy)
        if abs(area-expected)>max(1e-6,expected*1e-8):
            self._reject('HOLES_OR_TOPOLOGY','a projeção do teto não cobre o retângulo exatamente uma vez.')

    def _validate_other_faces(self,top_ids,bottom_ids):
        for i,f in enumerate(self.mesh.faces):
            if i in top_ids or i in bottom_ids:continue
            if f.zmax<=self.anchor_z+1e-7:continue
            if abs(f.nz)>1e-10:
                self._reject('TRANSITION_UNPROVEN',f'face {i} acima da âncora não pertence às duas peles; cavidade/detalhe/transição não demonstrada.')
            for p in f.points:
                if p[2]>self.anchor_z+1e-7 and not self.contains_xy(*p[:2]):
                    self._reject('TRANSITION_UNPROVEN',f'face {i} liga o teto a corpo fora do domínio selecionado.')

    def contains_xy(self,x,y):
        return all(lo-1e-8<=v<=hi+1e-8 for v,(lo,hi) in zip((x,y),self.bounds_xy))

    def _field(self,x,y):
        xx=max(self.bounds_xy[0][0],min(self.bounds_xy[0][1],x))
        yy=max(self.bounds_xy[1][0],min(self.bounds_xy[1][1],y))
        return _height(self.bottom_plane,xx,yy)

    def _field_gradient(self,x,y):
        return tuple(g if lo<=v<=hi else 0. for g,v,(lo,hi) in zip(self.bottom_plane[:2],(x,y),self.bounds_xy))

    def expected_surface(self,x,y,face='top'):
        if face not in ('top','bottom','underside'):
            raise WaveError('REGIONAL_SURFACE: escolha top, bottom ou underside.')
        if not self.contains_xy(x,y):return None
        return self._field(x,y)+(self.thickness_mm if face=='top' else 0.)

    def surface_is_exposed(self,x,y,face='top'):
        if face not in ('top','bottom','underside'):
            raise WaveError('REGIONAL_SURFACE: escolha top, bottom ou underside.')
        faces=self.top_faces if face=='top' else self.bottom_faces
        return self.contains_xy(x,y) and any(_contains_triangle(f,x,y) for f in faces)

    def surface_heights(self,x,y):
        top=self.expected_surface(x,y,'top')
        return (top,self.flat_top_z) if top is not None else None

    def flatten_point(self,point):
        x,y,z=point
        if not all(math.isfinite(v) for v in point):
            raise WaveError('REGIONAL_POINT: coordenada não finita.')
        if z<=self.anchor_z:return tuple(point)
        bottom=self._field(x,y);top=bottom+self.thickness_mm
        if z<bottom:
            value=self.anchor_z+(z-self.anchor_z)*(self.flat_bottom_z-self.anchor_z)/(bottom-self.anchor_z)
        elif z<=top:
            value=self.flat_bottom_z+(z-bottom)/self.shell_scale
        else:value=self.flat_top_z+(z-top)
        return x,y,value

    def map_point(self,point):
        x,y,z=point
        if not all(math.isfinite(v) for v in point):
            raise WaveError('REGIONAL_POINT: coordenada não finita.')
        if z<=self.anchor_z:return tuple(point)
        bottom=self._field(x,y)
        if z<self.flat_bottom_z:
            value=self.anchor_z+(z-self.anchor_z)*(bottom-self.anchor_z)/(self.flat_bottom_z-self.anchor_z)
        elif z<=self.flat_top_z:value=bottom+(z-self.flat_bottom_z)*self.shell_scale
        else:value=bottom+self.thickness_mm+z-self.flat_top_z
        return x,y,value

    def local_scale(self,x,y,z_flat=None):
        if z_flat is None:return self.shell_scale
        if z_flat<=self.anchor_z:return 1.
        if z_flat<self.flat_bottom_z:
            return (self._field(x,y)-self.anchor_z)/(self.flat_bottom_z-self.anchor_z)
        if z_flat<=self.flat_top_z:return self.shell_scale
        return 1.

    def volume_scale(self,x,y,z_flat,h_flat):
        if not math.isfinite(h_flat) or h_flat<=0:
            raise WaveError('REGIONAL_VOLUME: altura de célula inválida.')
        return (self.map_point((x,y,z_flat))[2]-self.map_point((x,y,z_flat-h_flat))[2])/h_flat

    def gradient(self,x,y,z_flat):
        if z_flat<=self.anchor_z:return 0.,0.
        factor=min(1.,(z_flat-self.anchor_z)/(self.flat_bottom_z-self.anchor_z))
        return tuple(factor*g for g in self._field_gradient(x,y))

    def normal_gap(self,x,y,z_flat,h_flat):
        vertical=h_flat*self.volume_scale(x,y,z_flat,h_flat)
        return vertical/math.hypot(1.,*self.gradient(x,y,z_flat))

    def _cuts(self,a,b):
        cuts={0.,1.}
        for k,values in ((0,self.bounds_xy[0]),(1,self.bounds_xy[1]),
                         (2,(self.anchor_z,self.flat_bottom_z,self.flat_top_z))):
            delta=b[k]-a[k]
            if delta:
                cuts.update(t for value in values if 0<(t:=(value-a[k])/delta)<1)
        return sorted(cuts)

    def chord_error_bound(self,flat_a,flat_b,out_a,out_b):
        """A true bound: extrema of each quadratic residual, not sampled checks."""
        if not all(math.isfinite(v) for p in (flat_a,flat_b,out_a,out_b) for v in p):
            raise WaveError('REGIONAL_CHORD: coordenada não finita.')
        hx=max(math.dist(flat_a[:2],out_a[:2]),math.dist(flat_b[:2],out_b[:2]))
        z_error=0.
        def native(t):return tuple(x+t*(y-x) for x,y in zip(flat_a,flat_b))
        for left,right in pairwise(self._cuts(flat_a,flat_b)):
            a,b=native(left),native(right);mid_z=(a[2]+b[2])/2
            ba,bb=self._field(*a[:2]),self._field(*b[:2]);db=bb-ba;dz=b[2]-a[2]
            if mid_z<=self.anchor_z:c0,c1,c2=a[2],dz,0.
            elif mid_z<self.flat_bottom_z:
                width=self.flat_bottom_z-self.anchor_z
                c0=self.anchor_z+(a[2]-self.anchor_z)*(ba-self.anchor_z)/width
                c1=((a[2]-self.anchor_z)*db+dz*(ba-self.anchor_z))/width
                c2=dz*db/width
            elif mid_z<=self.flat_top_z:
                c0=ba+(a[2]-self.flat_bottom_z)*self.shell_scale;c1=db+dz*self.shell_scale;c2=0.
            else:
                c0=ba+self.thickness_mm+a[2]-self.flat_top_z;c1=db+dz;c2=0.
            oz=out_b[2]-out_a[2]
            c0-=out_a[2]+left*oz;c1-=(right-left)*oz
            candidates=[0.,1.]
            if c2:
                vertex=-c1/(2*c2)
                if 0<vertex<1:candidates.append(vertex)
            z_error=max(z_error,*(abs(c0+c1*t+c2*t*t) for t in candidates))
        return math.hypot(hx,z_error)+1e-10
