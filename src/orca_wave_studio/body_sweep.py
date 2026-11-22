"""Conservative fixed-head AABB sweeps over earlier finite bead footprints.

A clear result is conditional on the supplied rigid envelopes and ideal bead
upper surfaces. A box overlap is inconclusive, never proof of a collision.
The nozzle/developing-bead contact and installed registration remain separate.
"""
from __future__ import annotations
import math
import numpy as np
from .contracts import WaveError,digest
from .engine_parser import read


def nominal_spatial_body_bound(gcode,mapping,components,*,bed_mm=(220.,220.),cell_mm=.4,
                               rotation_deg=0.,center_mm=(110.,110.),minimum_required_gap_mm=.5,cancelled=lambda:False):
    if not components or not .05<=cell_mm<=2:raise WaveError('BODY_SWEEP: envelopes ou resolução inválidos.')
    if not math.isfinite(minimum_required_gap_mm) or minimum_required_gap_mm<0:
        raise WaveError('BODY_SWEEP: margem de folga inválida.')
    for c in components:
        if len(c['minimum'])!=3 or len(c['maximum'])!=3 or any(not math.isfinite(v) for v in (*c['minimum'],*c['maximum'])):
            raise WaveError('BODY_SWEEP: envelope não finito.')
        if c['minimum'][2]<=0 or any(a>b for a,b in zip(c['minimum'],c['maximum'])):
            raise WaveError('BODY_SWEEP: o corpo deve ficar acima da ponta do bico.')
    buckets={}
    for index,c in enumerate(components):buckets.setdefault(c.get('group',('single',index)),[]).append(c)
    groups=[]
    for name,members in buckets.items():
        parent=members[0] if len(members)==1 else {'name':str(name)+' [conservative parent]',
            'minimum':[min(c['minimum'][k] for c in members) for k in range(3)],
            'maximum':[max(c['maximum'][k] for c in members) for k in range(3)]}
        groups.append((parent,members))
    parsed=read(gcode,set(),mapping,profile_macros=True,require_planar=False)
    if len(bed_mm)!=2 or any(not math.isfinite(v) or v<=0 for v in bed_mm):
        raise WaveError('BODY_SWEEP: dimensões da mesa inválidas.')
    shape=tuple(math.ceil(v/cell_mm)+1 for v in bed_mm)
    if math.prod(shape)>25000000:raise WaveError('BODY_SWEEP: a grade de folga excede o limite de memória.')
    height=np.full(shape,-math.inf,dtype=float)
    peak=unknown=-math.inf;minimum=math.inf;checked=queries=growing=0;pruned=leaf_checks=0;potentials=[];missing=[]
    minimum_by_motion={'extrusion':math.inf,'travel':math.inf};worst_by_motion={}
    angle=math.radians(rotation_deg);cs,sn=math.cos(angle),math.sin(angle)
    def position(p,rotate):
        if not rotate or not rotation_deg:return p
        x,y,z=p;u=x-center_mm[0];v=y-center_mm[1]
        return center_mm[0]+cs*u-sn*v,center_mm[1]+sn*u+cs*v,z
    def region(lo,hi,padding=0):
        left=[max(0,math.floor(v/cell_mm)-padding) for v in lo]
        right=[min(n,math.floor(v/cell_mm)+1+padding) for v,n in zip(hi,shape)]
        if any(a>=b for a,b in zip(left,right)):return None
        return tuple(slice(a,b) for a,b in zip(left,right))
    def bound(c,a,b):
        nonlocal queries
        bottom=math.nextafter(min(a[2],b[2])+c['minimum'][2],-math.inf)
        # A merely positive global bound can be arbitrarily close to zero.
        # Refine it spatially unless it already proves the required margin.
        if math.nextafter(bottom-peak,-math.inf)>minimum_required_gap_mm:material=peak
        else:
            queries+=1
            box=region([min(a[k],b[k])+c['minimum'][k] for k in (0,1)],
                       [max(a[k],b[k])+c['maximum'][k] for k in (0,1)],padding=1)
            material=max(unknown,float(height[box].max()) if box is not None else -math.inf)
        return math.nextafter(bottom-material,-math.inf),bottom,material
    def record(c,a,b,m,gap,bottom,material,count=1):
        nonlocal minimum,checked
        checked+=count;minimum=min(minimum,gap);kind='extrusion' if m.deposits else 'travel'
        if gap<=0 and len(potentials)<30:
            potentials.append({'line_1based':m.i+1,'component':c['name'],'motion':kind,
                'body_lower_z_mm':bottom,'material_upper_z_mm':material,'lower_gap_bound_mm':gap})
        if gap<minimum_by_motion[kind]:
            minimum_by_motion[kind]=gap
            worst_by_motion[kind]={'line_1based':m.i+1,'component':c['name'],'role':m.role,
                'start':list(a),'end':list(b),'body_lower_z_mm':bottom,'material_upper_z_mm':material,
                'lower_gap_bound_mm':gap}
    for count,m in enumerate(parsed.moves.values()):
        if count%4096==0 and cancelled():raise WaveError('Geração cancelada.')
        if m.start==m.end:continue
        if None in m.start+m.end:
            if m.layer>=0 or m.deposits:missing.append(m.i+1)
            continue
        a=position(m.start,m.layer>=0);b=position(m.end,m.layer>=0)
        top=math.nextafter(max(a[2],b[2]),math.inf)
        if m.deposits:
            peak=max(peak,top)
            if m.w and m.w>0:
                radius=m.w/2
                box=region([min(a[k],b[k])-radius for k in (0,1)],[max(a[k],b[k])+radius for k in (0,1)])
                if box is not None:height[box]=np.maximum(height[box],top)
            else:unknown=max(unknown,top)
        if m.layer<0:continue
        growing+=m.deposits
        for parent,members in groups:
            gap,bottom,material=bound(parent,a,b)
            if len(members)==1:
                leaf_checks+=1;record(parent,a,b,m,gap,bottom,material)
            elif gap>minimum_required_gap_mm:
                pruned+=len(members);record(parent,a,b,m,gap,bottom,material,len(members))
            else:
                for c in members:
                    leaf_checks+=1;record(c,a,b,m,*bound(c,a,b))
    covered=bool(checked) and not missing and math.isfinite(minimum)
    return {'status':'PASS_NOMINAL_SPATIAL_BODY_BOUND' if covered and minimum>minimum_required_gap_mm else 'INCONCLUSIVE',
        'gcode_sha256':digest(gcode),'minimum_nominal_gap_mm':minimum if math.isfinite(minimum) else None,
        'component_motion_sweeps_checked':checked,'spatial_queries':queries,'growing_bead_checks':growing,
        'leaf_sweeps_evaluated':leaf_checks,'child_sweeps_proven_by_parent':pruned,
        'minimum_by_motion_mm':{key:value if math.isfinite(value) else None for key,value in minimum_by_motion.items()},
        'worst_by_motion':worst_by_motion,
        'cell_mm':cell_mm,'rotation_deg_hypothesis':rotation_deg,'minimum_required_gap_mm':minimum_required_gap_mm,
        'potential_overlaps':potentials,'incomplete_lines':missing[:30],
        'coverage':'Every complete labelled linear motion; component swept AABBs and earlier/current XY bead bounding cells',
        'installed_head_registration_verified':False,'nozzle_contact':'UNASSESSED','material_physically_calibrated':False,
        'physical_validation':False,'print_allowed':False,'printer_contacted':False}
