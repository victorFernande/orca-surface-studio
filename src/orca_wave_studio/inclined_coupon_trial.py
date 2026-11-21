"""Isolated constant-pitch 25-degree coupon experiment; never grants a release.

Unlike the regional column warp, a shear preserves vertical layer spacing.
The virtual extension at the base exists only to sample the cut cell; its
extrusion is clipped against the already printed base. This is deliberately
not an arbitrary-model backend or part of the installed Studio UI.
"""
from __future__ import annotations

import math
import re
from .contracts import ProjectSnapshot, WaveError, digest
from .geometry import IDENTITY
from .engine_parser import read

PITCH = 2.0 / 7.0
BASE = 1.0
SLOPE = math.tan(math.radians(25.0))
FLAT_BOTTOM = 24 * PITCH


def bottom(x):
    # Original coupon, rotated 180 degrees around (110,110).
    return 3.0 + SLOPE * (115.0 - x)


def unflatten(p):
    return (p[0], p[1], p[2] + bottom(p[0]) - FLAT_BOTTOM)


def cut_fraction(z0, z1, pitch=PITCH):
    """Exact average of clamp((tip Z - base)/pitch, 0, 1) on a line."""
    if not all(math.isfinite(v) for v in (z0, z1, pitch)) or pitch <= 0:
        raise WaveError('Invalid cut cell.')
    cuts = [0., 1.]
    if z1 != z0:
        cuts += [(z-z0)/(z1-z0) for z in (BASE, BASE+pitch)
                 if 0 < (z-z0)/(z1-z0) < 1]
    cuts.sort()
    def f(t):
        return min(1., max(0., (z0+(z1-z0)*t-BASE)/pitch))
    return sum((b-a)*(f(a)+f(b))*.5 for a,b in zip(cuts,cuts[1:]))


def _mesh(cells):
    vertices, ids, faces = [], {}, {}
    def v(p):
        key = tuple(round(t, 12) for t in p)
        if key not in ids:
            ids[key] = len(vertices)
            vertices.append(list(p))
        return ids[key]
    for x0,x1,y0,y1,low,high in cells:
        vi = [v((x,y,z(x))) for z in (low,high)
              for x,y in ((x0,y0),(x1,y0),(x1,y1),(x0,y1))]
        for face in ((0,3,2,1),(4,5,6,7),(0,1,5,4),
                     (1,2,6,5),(2,3,7,6),(3,0,4,7)):
            q = tuple(vi[i] for i in face)
            key = tuple(sorted(q))
            if key in faces:
                del faces[key]
            else:
                faces[key] = q
    triangles = []
    for a,b,c,d in faces.values():
        triangles.extend(((a,b,c),(a,c,d)))
    return vertices, triangles


def upper_proxy():
    """Closed source meshes; dummy islands hold world Z during native import."""
    roof_top = lambda x: bottom(x)+2.
    floor = lambda x: BASE-PITCH/2.
    # Identical upper original model, with a virtual half-cell below the base.
    body = [(113.,115.,105.,115.,floor,bottom),
            (113.,115.,105.,115.,bottom,roof_top),
            (105.,113.,105.,115.,bottom,roof_top)]
    supports = [(x-.2,x+.2,105.3,114.7,floor,lambda x: bottom(x)-PITCH)
                for x in (105.6,107.4,109.2,111.0)]
    objects = []
    for i,cells in enumerate([body]+[[cell] for cell in supports]):
        vertices,triangles = _mesh(cells)
        vertices = [[x,y,z-bottom(x)+FLAT_BOTTOM] for x,y,z in vertices]
        dummy_vs,dummy_ts = _mesh([(195.+3*i,197.+3*i,195.,197.,
                                    lambda x:0.,lambda x:FLAT_BOTTOM+2.)])
        off = len(vertices)
        vertices += dummy_vs
        triangles += [tuple(t+off for t in tri) for tri in dummy_ts]
        config = ({'wall_loops':'1','top_shell_layers':'0','bottom_shell_layers':'0',
                   'sparse_infill_density':'0%'} if i else {})
        objects.append({'id':str(i+1),'name':'Coupon upper' if not i else f'Removable slat {i}',
                        'config':config,'instances_data':[{'id':'1','printable':True,'matrix':IDENTITY}],
                        'volumes':[{'id':'1','kind':'part','negative':False,'matrix':IDENTITY,
                                    'vertices':vertices,'triangles':triangles,'manifold':True}]})
    return ProjectSnapshot('coupon25-constant-pitch',0,tuple(objects),{})


def render_held_trial(base_source:bytes, upper_source:bytes):
    """Keep native flat base, replace upper moves, and explicitly lift transfers.

    Source upper retractions must be disabled: their values cannot be folded
    into material deposition. Travel, dummy islands and source macros are not
    imported. Absolute XYZ and relative E are emitted with explicit feeds.
    """
    bp = read(base_source,set(),{0:'1'})
    base_moves = [m for m in bp.moves.values() if m.deposits and m.obj == '1'
                  and None not in m.start+m.end and max(m.start[2],m.end[2]) <= BASE+1e-6]
    if not base_moves or abs(base_moves[-1].end[2]-BASE)>1e-6:
        raise WaveError('A complete 1 mm flat base is required.')
    last = base_moves[-1]
    if not last.xyz_abs or last.e_abs or last.label != (0,0):
        raise WaveError('Unexpected flat-base extrusion mode or ownership.')
    prefix = ''.join(line for line in bp.lines[:last.i+1]
                     if not line.lstrip().startswith('M73 '))
    # Native prefix has a start label whose matching stop was beyond the cut.
    lines = [prefix, '; stop printing object coupon id:0 copy 0\n',
             '; OWS CONSTANT PITCH TRIAL / BENCH ONLY / PRINT DISABLED\nG90\nM83\nG92 E0\n']
    up = read(upper_source,set(),{i:str(i+1) for i in range(5)})
    if any(m.de < -1e-7 for m in up.moves.values()):
        raise WaveError('Upper source contains retractions; use the isolated zero-retract source.')
    pos = last.end
    peak = BASE
    previous_layer = None
    active = False
    accepted = filtered = short = transfers = 0
    e_sum = 0.
    heights = []
    width_max = 0.
    for m in up.moves.values():
        if not m.deposits:
            continue
        if m.obj is None or None in m.start+m.end:
            raise WaveError('Unowned or unknown upper deposition.')
        inside = [104.9 <= p[0] <= 115.1 and 104.9 <= p[1] <= 115.1 for p in (m.start,m.end)]
        if not any(inside):
            if min(m.start[0],m.end[0]) < 190 or min(m.start[1],m.end[1]) < 190:
                raise WaveError('Unexpected source island outside coupon or dummy domains.')
            filtered += 1
            continue
        if not all(inside) or not m.xyz_abs or m.e_abs or abs(m.start[2]-m.end[2])>1e-6:
            raise WaveError('Upper source must have complete planar relative-E moves.')
        if m.h is None or abs(m.h-PITCH)>2e-5 or m.w is None or m.w <= 0:
            raise WaveError('Source layer pitch or width differs from the experiment.')
        a,b = unflatten(m.start),unflatten(m.end)
        # The virtual half-cell samples the transition; never move below base.
        if min(a[2],b[2]) < BASE-1e-5:
            raise WaveError('Native source crosses below the already printed base.')
        if m.layer != previous_layer:
            if active:
                lines.append('; stop printing object coupon id:0 copy 0\n')
            lines.append(f';LAYER_CHANGE\n;Z:{m.z:.6f}\n;HEIGHT:{PITCH:.9f}\n'
                         '; printing object coupon id:0 copy 0\n')
            active = True
            previous_layer = m.layer
        role = m.role if m.obj == '1' else 'support interface'
        lines.append(f';TYPE:{role.capitalize()}\n;WIDTH:{m.w:.6f}\n')
        if math.dist(pos,a)>1e-5:
            lifted = max(peak,pos[2],a[2])+3.
            if lifted > 250:
                raise WaveError('Travel exceeds printer height.')
            lines.append(f'G1 E-0.5 F1800\nG1 Z{lifted:.6f} F300\n'
                         f'G1 X{a[0]:.6f} Y{a[1]:.6f} F3600\nG1 Z{a[2]:.6f} F300\nG1 E0.5 F1800\n')
            transfers += 1
        length = math.dist(a,b)
        count = max(1,math.ceil(length/.4))
        if length < .15:
            short += 1  # Original native edge, explicitly retained and reported.
        elif length/count < .15-1e-9:
            raise WaveError('A new segment would be shorter than 0.15 mm.')
        feed = min(1200.,m.f*length/math.dist(m.start,m.end))
        if abs(b[2]-a[2])>1e-9:
            feed = min(feed,300.*length/abs(b[2]-a[2]))
        for j in range(count):
            p = tuple(a[k]+(b[k]-a[k])*j/count for k in range(3))
            q = tuple(a[k]+(b[k]-a[k])*(j+1)/count for k in range(3))
            fraction = cut_fraction(p[2],q[2])
            extrusion = m.de/count*fraction
            if extrusion <= 0:
                raise WaveError('Empty source cell would require a deposition omission.')
            lines.append(f'G1 X{q[0]:.6f} Y{q[1]:.6f} Z{q[2]:.6f} E{extrusion:.8f} F{feed:.3f}\n')
            e_sum += extrusion
            heights.append(min(PITCH,max(0.,q[2]-BASE)))
        peak = max(peak,a[2],b[2])
        pos = b
        width_max = max(width_max,m.w)
        accepted += 1
    if not accepted or not active:
        raise WaveError('No accepted upper paths.')
    lines += ['; stop printing object coupon id:0 copy 0\n',
              f'M400\nG90\nM83\nG1 E-0.5 F1800\nG1 Z{peak+3:.6f} F300\n'
              'M104 S0\nM140 S0\nM107\nG1 X10 Y200 F3000\nM400\nM84 X Y E\n']
    text = ''.join(lines)
    text += '; EXECUTABLE_BLOCK_END\n'
    source_text=base_source.decode('latin1')
    config=re.search(r'(?ms)^; CONFIG_BLOCK_START\s*\n.*?^; CONFIG_BLOCK_END\s*\n',source_text)
    if config:
        text+='\n'+config[0]
    total=text.count(';LAYER_CHANGE\n')
    text=re.sub(r'(?m)^; total layer number: .*$',f'; total layer number: {total}',text)
    text=re.sub(r'(?m)^; max_z_height: .*$',f'; max_z_height: {peak:.6f}',text)
    result = text.encode('latin1')
    read(result,set(),{0:'1'})
    return result, {'status':'HELD_CONSTANT_PITCH_EXPERIMENT','print_allowed':False,
        'source_base_sha256':digest(base_source),'source_upper_sha256':digest(upper_source),
        'gcode_sha256':digest(result),'flat_base_prefix_sha256':digest(prefix.encode('latin1')),
        'flat_base_last_source_line':last.i+1,'upper_source_moves':accepted,'dummy_moves_discarded':filtered,
        'original_short_edges_retained':short,'lifted_transfers':transfers,
        'upper_relative_filament_mm':e_sum,'maximum_width_mm':width_max,
        'vertical_pitch_mm':PITCH,'normal_pitch_mm':PITCH*math.cos(math.radians(25)),
        'base_cut_cell_vertical_height_range_mm':[min(heights),max(heights)],
        'peak_deposition_z_mm':peak,'geometry_rotation_z_deg':180.,
        'shear_jacobian':1.,'base_cell_extrusion':'exact clipped vertical cell fraction',
        'head_clearance':'UNASSESSED','physical_validation':False}
