"""Nominal body bound for the isolated shear coupon; nozzle release excluded.

The filled bound encloses the temporal material prefix above the flat base.
Disjointness proves only the stated ideal CAD/body model, not the installed
head, bead formation or manufacturing tolerances. There is no printer I/O.
"""
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.venv/Lib/site-packages'))
sys.path.insert(0,str(ROOT/'src'))
from OCP.TopoDS import TopoDS_Shape
from OCP.BRepTools import BRepTools
from OCP.BRep import BRep_Builder
from OCP.gp import gp_Pnt,gp_Vec
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon,BRepBuilderAPI_MakeFace
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from orca_wave_studio.engine_parser import read
from orca_wave_studio.inclined_coupon_trial import SLOPE,BASE


def main():
    folder=ROOT/'study/evidence/physical-preflight/constant-pitch25-held'
    source=(folder/'HOLD-constant-pitch25-SV06.gcode').read_bytes()
    moves=list(read(source,set(),{0:'1'}).moves.values())
    upper=[m for m in moves if m.deposits and m.obj=='1' and m.layer>=5]
    # Upper deposition only; base and startup purge are flat and lower than
    # every non-nozzle body component even at the lowest model TCP position.
    lows=[min(min(m.start[k],m.end[k])-m.w/2 for m in upper) for k in (0,1)]
    highs=[max(max(m.start[k],m.end[k])+m.w/2 for m in upper) for k in (0,1)]
    positions=[p for m in upper for p in (m.start,m.end)]
    radius=max(max(highs[k]-min(p[k] for p in positions),
                       max(p[k] for p in positions)-lows[k]) for k in (0,1))
    radius=math.ceil(radius*1000+1e-8)/1000
    prior_q=prior_peak=-math.inf
    offset=0.
    complete_travel=True
    upper_lines={m.i for m in upper}
    for m in moves:
        if None in m.start+m.end or m.layer<5:
            continue
        # Lifted horizontal transfers and final park are above all prior
        # material. The remaining moves are vertical or constant-pitch deposit.
        wholly_above=min(m.start[2],m.end[2])>prior_peak+1e-5
        if not m.deposits and m.start[:2]!=m.end[:2] and not wholly_above:
            complete_travel=False
        if not wholly_above:
            offset=max(offset,prior_q-min(p[2]+SLOPE*p[0] for p in (m.start,m.end)))
        if m.i in upper_lines:
            prior_q=max(prior_q,max(p[2]+SLOPE*p[0] for p in (m.start,m.end))+SLOPE*m.w/2)
            prior_peak=max(prior_peak,m.start[2],m.end[2])
    if not complete_travel:
        raise RuntimeError('Uncovered horizontal travel below the material prefix.')
    offset=math.ceil(offset*1000000+1e-8)/1000000
    cache=ROOT/'.research/sv06-physical-preflight'
    assembly=json.loads((cache/'assembled-components.json').read_text())
    components=assembly['components']
    nozzle=next(c for c in components if c['name']=='brass nozzle 0.4mm_M6x0.4')
    tcp=[p[3] for p in nozzle['placement_3x4']]
    wedges=[]
    for lo,hi,slope in ((-radius,0.,0.),(0.,radius,SLOPE)):
        polygon=BRepBuilderAPI_MakePolygon()
        for x,y in ((lo,-radius),(hi,-radius),(hi,radius),(lo,radius)):
            polygon.Add(gp_Pnt(tcp[0]+x,tcp[1]-(offset+slope*x),tcp[2]+y))
        polygon.Close()
        face=BRepBuilderAPI_MakeFace(polygon.Wire()).Face()
        wedges.append(BRepPrimAPI_MakePrism(face,gp_Vec(0.,15.,0.)).Shape())
    rows=[]
    for c in components:
        if 'brass nozzle' in c['name'].lower():
            continue
        b=c['bounds_cad_mm']
        xmin,xmax=b[0]-tcp[0],b[3]-tcp[0]
        ymin,ymax=b[2]-tcp[2],b[5]-tcp[2]
        zmin=tcp[1]-b[4]
        lower=max((zmin-offset-SLOPE*max(0.,xmax))/math.hypot(1,SLOPE),
                  max(0.,xmin-radius,-radius-xmax,ymin-radius,-radius-ymax))
        if lower>.3:
            rows.append({'component':c['name'],'distance_lower_bound_mm':lower,
                         'method':'conservative AABB separation'})
            continue
        shape=TopoDS_Shape()
        if not BRepTools.Read_s(shape,str(cache/c['brep_file']),BRep_Builder()):
            raise RuntimeError('Missing BREP: '+c['name'])
        distances=[]
        for wedge in wedges:
            d=BRepExtrema_DistShapeShape(shape,wedge)
            if not d.IsDone():raise RuntimeError('CAD distance failed.')
            distances.append(d.Value())
        rows.append({'component':c['name'],'minimum_distance_mm':min(distances),
                     'method':'exact nominal BREP to enclosing signed wedge',
                     'brep_sha256':hashlib.sha256((cache/c['brep_file']).read_bytes()).hexdigest()})
    margin=min(r.get('minimum_distance_mm',r.get('distance_lower_bound_mm')) for r in rows)
    result={'status':'PASS_NOMINAL_BODY_BOUND' if margin>1e-6 else 'POTENTIAL_BODY_INTERFERENCE',
        'print_allowed':False,'gcode_sha256':hashlib.sha256(source).hexdigest(),
        'geometry_source_revision':'75f8a0da6ff822c67b6aff62cfa85c7a441e2271',
        'frame':'CAD delta=(-printer X,-printer Z,-printer Y)',
        'installed_head_registration_verified':False,'manufacturing_uncertainty_included':False,
        'material_model':'uncalibrated swept horizontal disks below each trace',
        'nozzle_and_growing_bead_contact':'UNASSESSED_NO_EXCLUSION_OR_RELEASE',
        'signed_wedge_offset_mm':offset,'domain_radius_mm':radius,
        'flat_base_and_purge_body_separation':'nominal body bottom is above all flat-prefix material',
        'travel_prefix_height_coverage':complete_travel,'nominal_body_minimum_bound_mm':margin,
        'rows':rows}
    (folder/'nominal-body-bound.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))


if __name__=='__main__':main()
