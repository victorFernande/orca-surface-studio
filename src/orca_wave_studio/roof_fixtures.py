"""Deterministic, closed roof coupons for digital nonplanar comparisons.

The target roof is 10 x 10 mm in XY and 2 mm thick in vertical Z. A base
and low-edge anchor make one connected solid; the remaining underside needs
removable supports. Metadata describes intended geometry, never print approval.
"""
from __future__ import annotations

from collections import defaultdict
import copy
import math

from .contracts import ProjectSnapshot, WaveError
from .geometry import IDENTITY


ROOF_ANGLES = (5, 10, 15, 20, 25)
WORLD_TRANSLATION = (105.0, 105.0, 0.0)


def roof_coupon(angle_deg: float) -> tuple[ProjectSnapshot, dict]:
    """Return one connected solid and region truth, centered on an SV06 bed.

    Plane arrays ``[a,b,c]`` mean ``z = a*x + b*y + c``. Triangle indices
    address the sole volume. ``underside`` is the exposed x=2..10 roof span;
    x=0..2 is attached to the anchor and has no exposed bottom skin.
    """
    if type(angle_deg) not in {int, float} or not math.isfinite(angle_deg) or angle_deg not in ROOF_ANGLES:
        raise WaveError('Escolha um cupom de 5, 10, 15, 20 ou 25 graus.')
    slope = math.tan(math.radians(angle_deg))
    vertices, vertex_ids = [], {}
    boundary = {}

    def vertex(p):
        key = tuple(float(v) for v in p)
        if key not in vertex_ids:
            vertex_ids[key] = len(vertices)
            vertices.append(list(key))
        return vertex_ids[key]

    def cell(x0, x1, y0, y1, bottom, top, kind):
        coords = [(x0,y0,bottom(x0)),(x1,y0,bottom(x1)),
                  (x1,y1,bottom(x1)),(x0,y1,bottom(x0)),
                  (x0,y0,top(x0)),(x1,y0,top(x1)),
                  (x1,y1,top(x1)),(x0,y1,top(x0))]
        ids = [vertex(p) for p in coords]
        faces = ((0,3,2,1),(4,5,6,7),(0,1,5,4),
                 (1,2,6,5),(2,3,7,6),(3,0,4,7))
        for side, face in enumerate(faces):
            quad = tuple(ids[k] for k in face)
            key = tuple(sorted(quad))
            if key in boundary:
                del boundary[key]  # Shared full face is internal to the solid.
            else:
                region = ('underside' if side == 0 else 'top' if side == 1 else 'border') if kind == 'roof' else kind
                boundary[key] = quad, region

    xs, ys = (-2.,0.,2.,10.,12.), (-2.,0.,10.,12.)
    for x0,x1 in zip(xs,xs[1:]):
        for y0,y1 in zip(ys,ys[1:]):
            cell(x0,x1,y0,y1,lambda x:0.,lambda x:1.,'base')
    lower = lambda x:3. + slope*x
    upper = lambda x:5. + slope*x
    cell(0.,2.,0.,10.,lambda x:1.,lower,'anchor')
    for x0,x1 in ((0.,2.),(2.,10.)):
        cell(x0,x1,0.,10.,lower,upper,'roof')
    triangles, regions = [], defaultdict(list)
    for quad, region in boundary.values():
        a,b,c,d = quad
        for tri in ((a,b,c),(a,c,d)):
            regions[region].append(len(triangles))
            triangles.append(list(tri))
    matrix = copy.deepcopy(IDENTITY)
    for i,value in enumerate(WORLD_TRANSLATION):
        matrix[i][3] = value
    name = f'Roof coupon {angle_deg:g} deg - digital study'
    snapshot = ProjectSnapshot(f'roof-coupon-{angle_deg:g}',0,({
        'id':'1','name':name,'config':{},
        'instances_data':[{'id':'1','printable':True,'matrix':matrix}],
        'volumes':[{'id':'1','kind':'part','negative':False,'matrix':copy.deepcopy(IDENTITY),
                    'vertices':vertices,'triangles':triangles,'manifold':True}],
    },),{'layer_height':'0.2','nozzle_diameter':'0.4','filament_type':'PETG',
         'gcode_flavor':'marlin','gcode_label_objects':'1'})
    constant = 3. - slope*WORLD_TRANSLATION[0]
    metadata = {
        'schema_version':1,'kind':'roof_coupon','name':name,
        'angle_deg':float(angle_deg),'angle_reference':'surface relative to horizontal XY bed',
        'nozzle_axis':'vertical Z','single_object':True,'plate_index':0,
        'local_to_world_translation_mm':list(WORLD_TRANSLATION),
        'roof':{'size_xy_mm':[10.,10.],'vertical_thickness_mm':2.,
                'top_plane_world':[slope,0.,constant+2.],
                'bottom_plane_world':[slope,0.,constant],
                'bounds_xy_world_mm':[[105.,105.],[115.,115.]],
                'free_span_bounds_xy_world_mm':[[107.,105.],[115.,115.]],
                'top_projected_area_mm2':100.,'exposed_underside_projected_area_mm2':80.,
                'top_surface_area_mm2':100./math.cos(math.radians(angle_deg)),
                'exposed_underside_surface_area_mm2':80./math.cos(math.radians(angle_deg))},
        'base':{'bounds_local_mm':[[-2.,-2.,0.],[12.,12.,1.]]},
        'anchor':{'bounds_xy_local_mm':[[0.,0.],[2.,10.]],'bottom_z_mm':1.,'top':'roof bottom plane'},
        'regions':{key:{'triangle_indices':value} for key,value in sorted(regions.items())},
        'support_required':True,'support_target':'exposed underside including transition at local X=2',
        'support_type':'normal(auto)','support_material':'same PETG, removable, not soluble',
        'support_gaps_mm':{'top_z':.2,'bottom_z':.2,'xy':.35},
        'acceptance_targets':{'surface_error_mm':.05,'status':'TARGET_ONLY_NOT_VALIDATED',
            'rois':['top','border','underside'],'exclude_base_and_anchor':True},
        'physical_gate':{'status':'UNKNOWN','reason':'No measured SV06 head envelope or physical deposition test.',
                         'print_allowed':False},
        'snapshot_revision':snapshot.revision,
    }
    return snapshot, metadata


def roof_coupon_snapshot(angle_deg: float) -> ProjectSnapshot:
    return roof_coupon(angle_deg)[0]
