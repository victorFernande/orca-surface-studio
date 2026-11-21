"""Measured, deliberately non-certifying finite-bead audit of the roof study.

The estimate is a horizontal disk swept along each deposited segment, bounded
above by the nozzle path and below by its mapped layer-cell height. This is an
explicit model, not a calibrated prediction of PETG flow or bridge sag. Samples
provide counterexamples, never a maximum-error certificate over a whole face.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math

from .contracts import WaveError, digest
from .engine_parser import read

SUPPORT_ROLES = {'support','support material','support interface',
                 'support material interface','support transition','support base'}


@dataclass(frozen=True)
class Bead:
    start: tuple
    end: tuple
    height_start: float
    height_end: float
    width: float
    line: int
    role: str

    def interval_at(self, x, y):
        """Exact vertical interval through the defined swept-disk bead."""
        dx,dy=self.end[0]-self.start[0],self.end[1]-self.start[1]
        ux,uy=self.start[0]-x,self.start[1]-y
        a=dx*dx+dy*dy; b=2*(dx*ux+dy*uy)
        c=ux*ux+uy*uy-(self.width/2)**2
        if a<1e-20:
            if c>1e-12:return None
            lo,hi=0.,1.
        else:
            disc=b*b-4*a*c
            if disc<0:return None
            root=math.sqrt(disc)
            lo,hi=max(0.,(-b-root)/(2*a)),min(1.,(-b+root)/(2*a))
            if lo>hi:return None
        tops=[self.start[2]+t*(self.end[2]-self.start[2]) for t in (lo,hi)]
        bottoms=[self.start[2]-self.height_start+t*(self.end[2]-self.height_end-
                   self.start[2]+self.height_start) for t in (lo,hi)]
        return min(bottoms),max(tops)


class BeadIndex:
    def __init__(self, beads, cell=.5):
        self.beads=tuple(beads);self.cell=cell;self.grid=defaultdict(list)
        for bead in self.beads:
            r=bead.width/2
            ranges=[range(math.floor((min(bead.start[k],bead.end[k])-r)/cell),
                          math.floor((max(bead.start[k],bead.end[k])+r)/cell)+1) for k in (0,1)]
            for ix in ranges[0]:
                for iy in ranges[1]:self.grid[ix,iy].append(bead)

    def at(self,x,y):
        return [(b,span) for b in self.grid.get((math.floor(x/self.cell),math.floor(y/self.cell)),())
                if (span:=b.interval_at(x,y)) is not None]


def _height(warp,p,h):
    flat=warp.flatten_point(p)
    below=warp.map_point((flat[0],flat[1],flat[2]-h))
    return p[2]-below[2]


def _beads(gcode,warp,mapping,object_id):
    parsed=read(gcode,set(),mapping);model=[];support=[];unknown=[]
    for move in parsed.moves.values():
        if not move.deposits:continue
        if move.obj!=object_id:
            if move.role in SUPPORT_ROLES:unknown.append(move.i+1)
            continue
        if None in move.start or None in move.end or not move.h or not move.w:
            raise WaveError(f'AUDIT_GEOMETRY_METADATA: linha {move.i+1}.')
        field=getattr(warp,'support_warp',warp) if move.role in SUPPORT_ROLES else warp
        hs,he=(_height(field,p,move.h) for p in (move.start,move.end))
        if min(hs,he)<=0:raise WaveError('AUDIT_NONPOSITIVE_CELL_HEIGHT')
        bead=Bead(move.start,move.end,hs,he,move.w,move.i+1,move.role)
        if move.role in SUPPORT_ROLES:support.append(bead)
        else:
            # Ignore the unchanged base and the stem below the paired shell.
            flats=[warp.flatten_point(p)[2] for p in (move.start,move.end)]
            if max(flats)>warp.flat_bottom_z+1e-5 and min(flats)-move.h<warp.flat_top_z+1e-5:
                model.append(bead)
    return model,support,unknown


def _surface(index,warp,face,pitch,tolerance):
    (xmin,xmax),(ymin,ymax)=warp.bounds_xy
    nx,ny=(max(1,math.ceil((hi-lo)/pitch)) for lo,hi in warp.bounds_xy)
    norm=math.sqrt(1+sum(v*v for v in warp.top_plane[:2]))
    total=covered=0;worst=None;maximum=0.;squared=0.
    # Cell centres avoid pretending that finite sampling proves edge coverage.
    for ix in range(nx):
        x=xmin+(ix+.5)*(xmax-xmin)/nx
        for iy in range(ny):
            y=ymin+(iy+.5)*(ymax-ymin)/ny
            if not warp.surface_is_exposed(x,y,face):continue
            total+=1;intervals=index.at(x,y)
            if not intervals:continue
            measured=(max(span[1] for _,span in intervals) if face=='top'
                      else min(span[0] for _,span in intervals))
            expected=warp.expected_surface(x,y,face)
            error=abs(measured-expected)/norm
            covered+=1;squared+=error*error
            if error>maximum:
                maximum=error;worst={'xy_mm':[x,y],'expected_z_mm':expected,
                    'estimated_z_mm':measured,'normal_error_mm':error}
    violation=maximum>tolerance
    return {'status':'FAIL_ESTIMATE_WITNESS' if violation else 'NOT_CERTIFIED',
        'samples':total,'covered_samples':covered,'uncovered_samples':total-covered,
        'sample_pitch_mm':pitch,'sampled_max_normal_error_mm':maximum if covered else None,
        'sampled_rms_normal_error_mm':math.sqrt(squared/covered) if covered else None,
        'worst_witness':worst,'maximum_over_entire_face_certified':False,
        'reason':'Amostras não certificam o máximo entre pontos nem a forma real do cordão.'}


def _outer_bounds(beads,warp):
    """Conservative one-sided overshoot bounds; exceeding them is not a witness."""
    m,n,b=warp.top_plane;_,_,bottom=warp.bottom_plane
    norm=math.sqrt(1+m*m+n*n);slope=math.hypot(m,n)
    top=under=border=0.
    for bead in beads:
        r=bead.width/2
        w=[p[2]-m*p[0]-n*p[1] for p in (bead.start,bead.end)]
        top=max(top,(max(w)+r*slope-b)/norm)
        under=max(under,(bottom-min(w[0]-bead.height_start,w[1]-bead.height_end)+r*slope)/norm)
        for k,(lo,hi) in enumerate(warp.bounds_xy):
            border=max(border,lo-min(bead.start[k],bead.end[k])+r,
                       max(bead.start[k],bead.end[k])+r-hi)
    return {'top_normal_overshoot_bound_mm':top,'underside_normal_overshoot_bound_mm':under,
        'border_axis_overshoot_bound_mm':border,'bound_only':True,
        'note':'Limites conservadores do modelo de cordão; não são erro observado nem certificado bilateral.'}


def _support(index,warp,pitch,target_gap,model_index=None):
    (xmin,xmax),(ymin,ymax)=warp.bounds_xy
    nx,ny=(max(1,math.ceil((hi-lo)/pitch)) for lo,hi in warp.bounds_xy)
    gaps=[];target_gaps=[];total=covered=material_samples=0;worst=None;intersections=[]
    norm=math.sqrt(1+sum(v*v for v in warp.bottom_plane[:2]))
    for ix in range(nx):
        x=xmin+(ix+.5)*(xmax-xmin)/nx
        for iy in range(ny):
            y=ymin+(iy+.5)*(ymax-ymin)/ny
            if not warp.surface_is_exposed(x,y,'underside'):continue
            total+=1;spans=index.at(x,y)
            if not spans:continue
            expected=warp.expected_surface(x,y,'underside')
            support_top=max(span[1] for _,span in spans)
            target_gap_at=(expected-support_top)/norm
            target_gaps.append(target_gap_at);covered+=1
            model_spans=model_index.at(x,y) if model_index is not None else []
            if model_spans:
                material_samples+=1
                material_bottom=min(span[0] for _,span in model_spans)
                gap=(material_bottom-support_top)/norm
                gaps.append(gap)
                for sb,ss in spans:
                    for mb,ms in model_spans:
                        overlap=min(ss[1],ms[1])-max(ss[0],ms[0])
                        if overlap>1e-6 and len(intersections)<20:
                            intersections.append({'xy_mm':[x,y],'vertical_overlap_mm':overlap,
                                'support_line':sb.line,'model_line':mb.line})
            else:
                gap=target_gap_at
            if worst is None or abs(gap-target_gap)>abs(worst['normal_gap_mm']-target_gap):
                worst={'xy_mm':[x,y],'normal_gap_mm':gap,'underside_z_mm':expected,
                    'support_top_z_mm':support_top,'reference':'deposited_material' if model_spans else 'target_mesh_only'}
    return {'status':'FAIL_ESTIMATE_INTERSECTION' if intersections else 'NOT_CERTIFIED',
        'sampled_normal_gap_range_mm':[min(gaps),max(gaps)] if gaps else None,
        'gap_reference':'estimated_deposited_material',
        'sampled_support_to_target_mesh_normal_gap_range_mm':[min(target_gaps),max(target_gaps)] if target_gaps else None,
        'model_material_samples':material_samples,'intersection_witnesses':intersections,
        'requested_native_vertical_gap_mm':target_gap,
        'samples':total,'covered_samples':covered,'uncovered_samples':total-covered,
        'worst_witness':worst,'order_and_removability_validated':False,
        'reason':'Folga entre envelopes estimados de suporte e peça; distância à malha ideal separada. Cobertura contínua, ordem e remoção não certificadas.'}


def audit_head_path(gcode,warp,mapping,object_id,profile=None):
    """Adapt all known moves and all deposited roles in their emitted order."""
    from .head_clearance import AABB,TCPMotion,MaterialDeposit,check_head_clearance
    parsed=read(gcode,set(),mapping);motions=[];material=[];incomplete=[]
    for move in parsed.moves.values():
        if move.start==move.end:continue
        if None in move.start or None in move.end:
            incomplete.append(move.i+1);continue
        motions.append(TCPMotion(move.i,move.start,move.end,
            'extrusion' if move.deposits else 'travel',str(move.i+1)))
        if not move.deposits:continue
        if not move.h or not move.w:
            incomplete.append(move.i+1);continue
        field=getattr(warp,'support_warp',warp) if move.role in SUPPORT_ROLES else warp
        heights=[_height(field,p,move.h) if move.obj==object_id else move.h
                 for p in (move.start,move.end)]
        r=move.w/2
        low=tuple(min(move.start[k],move.end[k])-r for k in (0,1))+(min(
            move.start[2]-heights[0],move.end[2]-heights[1]),)
        high=tuple(max(move.start[k],move.end[k])+r for k in (0,1))+(max(move.start[2],move.end[2]),)
        material.append(MaterialDeposit(move.i,AABB(low,high),move.role or 'unknown',str(move.i+1)))
    result=check_head_clearance(motions,material,profile,
        motions_complete=not incomplete,material_prefix_complete=False)
    result.update(input_model='finite bead estimate; uncalibrated material enclosure',
        incomplete_gcode_lines=incomplete[:20],material_geometry_calibrated=False)
    return result


def audit_regional_roof(gcode,warp,mapping,object_id,*,sample_pitch_mm=.1,
                        surface_tolerance_mm=.05,support_gap_mm=.2,head_profile=None):
    if not (.025<=sample_pitch_mm<=1 and 0<surface_tolerance_mm<=.05):
        raise WaveError('AUDIT_SETTINGS: resolução ou tolerância inválida.')
    model,support,unknown=_beads(gcode,warp,mapping,object_id)
    index=BeadIndex(model)
    faces={face:_surface(index,warp,face,sample_pitch_mm,surface_tolerance_mm)
           for face in ('top','underside')}
    envelope=_outer_bounds(model,warp)
    support_report=_support(BeadIndex(support),warp,sample_pitch_mm,support_gap_mm,index)
    if unknown:support_report.update(status='UNKNOWN_OBJECT_OWNERSHIP',unassociated_lines=unknown[:20])
    clearance=audit_head_path(gcode,warp,mapping,object_id,head_profile)
    return {'status':'INCOMPLETE','print_allowed':False,'physical_validation':False,
        'gcode_sha256':digest(gcode),'surface_tolerance_mm':surface_tolerance_mm,
        'deposition_model':'horizontal swept disks; top at nozzle Z; bottom at mapped layer cell',
        'deposition_model_calibrated':False,'model_segments':len(model),'support_segments':len(support),
        'faces':faces,'outer_envelope':envelope,'support':support_report,'head_clearance':clearance,
        'selected_regions':['top','underside','border'],
        'border':{'status':'NOT_CERTIFIED','axis_overshoot_bound_mm':envelope['border_axis_overshoot_bound_mm']},
        'digital_approval':False,'reason':'Todas as regiões selecionadas devem passar; estimativa e cabeçote não certificados.'}
