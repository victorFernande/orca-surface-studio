"""Resolve screen rays against original geometry, then make native modifiers.

The display mesh uses GPU float32 precision. It must never be the authority
for the surface that a click selects or for the generated printing geometry.
"""
from __future__ import annotations

import math
import numpy as np

from .contracts import WaveError
from .geometry import transform_point


MAX_AREAS = 24


def _vector(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 3
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise WaveError('WALL_RAY: clique inválido; selecione novamente na peça.')
    return np.asarray(value, dtype=float)


def resolve_areas(snapshot, object_id, options):
    mode = options.get('selection_mode', 'all')
    if mode not in ('all', 'paint'):
        raise WaveError('WALL_SELECTION: modo de seleção desconhecido.')
    rays = options.get('wall_selection', [])
    if not isinstance(rays, list) or len(rays) > MAX_AREAS:
        raise WaveError(f'WALL_SELECTION: use até {MAX_AREAS} áreas por peça.')
    if mode == 'all':
        if rays:
            raise WaveError('WALL_SELECTION: seleção de áreas incompatível com todas as superfícies.')
        return []
    if options.get('selection_revision') != snapshot.revision:
        raise WaveError('WALL_STALE: a peça ou o perfil mudou; selecione as áreas novamente.')
    if not rays:
        raise WaveError('WALL_EMPTY: clique nas áreas da peça que deseja suavizar.')
    obj = next((o for o in snapshot.objects if str(o['id']) == str(object_id)), None)
    if obj is None:
        raise WaveError('WALL_OBJECT: a peça selecionada não está mais na placa.')
    if len(obj['volumes'])!=1:
        raise WaveError('WALL_VOLUME: a seleção por áreas requer uma única parte sólida.')
    instances = [i for i in obj['instances_data'] if i.get('printable', True)]
    if len(instances) != 1:
        raise WaveError('WALL_INSTANCES: selecione uma peça com uma única instância.')
    triangles = []
    for volume in obj['volumes']:
        if volume.get('negative') or volume['kind'] != 'part':
            raise WaveError('WALL_VOLUME: esta seleção requer uma peça sem modificadores prévios.')
        points = [transform_point(p, instances[0]['matrix'], volume['matrix']) for p in volume['vertices']]
        triangles.extend([[points[i] for i in face] for face in volume['triangles']])
    tri = np.asarray(triangles, dtype=float)
    if tri.shape[0] == 0 or not np.isfinite(tri).all():
        raise WaveError('WALL_MESH: a peça não tem uma malha válida para seleção.')
    a, edge1, edge2 = tri[:, 0], tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0]
    areas = []
    for ray in rays:
        if not isinstance(ray, dict) or set(ray) != {'origin', 'direction', 'radius_mm'}:
            raise WaveError('WALL_RAY: parâmetros de seleção desconhecidos.')
        origin, direction = _vector(ray['origin']), _vector(ray['direction'])
        norm = np.linalg.norm(direction)
        radius = ray['radius_mm']
        if (not 1e-12 < norm < 1e12 or type(radius) not in (int, float)
                or not math.isfinite(radius) or not 1 <= radius <= 15):
            raise WaveError('WALL_RADIUS: use um raio de área entre 1 e 15 mm.')
        direction = direction/norm
        p = np.cross(direction, edge2)
        det = np.einsum('ij,ij->i', edge1, p)
        valid = abs(det) > 1e-12
        inverse = np.divide(1., det, out=np.zeros_like(det), where=valid)
        tvec = origin-a
        u = np.einsum('ij,ij->i', tvec, p)*inverse
        q = np.cross(tvec, edge1)
        v = q@direction*inverse
        distance = np.einsum('ij,ij->i', edge2, q)*inverse
        valid &= (u >= -1e-9) & (v >= -1e-9) & (u+v <= 1+1e-9) & (distance >= 0)
        hits = np.flatnonzero(valid)
        if not len(hits):
            raise WaveError('WALL_MISS: o clique não atingiu a malha original; aproxime e tente novamente.')
        index = int(hits[np.argmin(distance[hits])])
        center = origin+distance[index]*direction
        normal = np.cross(edge1[index], edge2[index]); normal /= np.linalg.norm(normal)
        areas.append({'center':center.tolist(), 'radius_mm':float(radius),
                      'source_triangle':index, 'normal':normal.tolist()})
    return areas


def sphere_modifier(area, number):
    """Closed inscribed spherical modifier; the UI shows its radius envelope."""
    center = area['center']; radius = area['radius_mm']
    rings, segments = 12, 24
    vertices = [[center[0], center[1], center[2]+radius]]
    for ring in range(1, rings):
        phi = math.pi*ring/rings
        for j in range(segments):
            angle = math.tau*j/segments
            vertices.append([center[0]+radius*math.sin(phi)*math.cos(angle),
                             center[1]+radius*math.sin(phi)*math.sin(angle),
                             center[2]+radius*math.cos(phi)])
    bottom = len(vertices); vertices.append([center[0],center[1],center[2]-radius])
    triangles = []
    for j in range(segments):
        nxt = (j+1)%segments
        triangles.append([0,1+j,1+nxt])
        for ring in range(rings-2):
            a = 1+ring*segments+j; b = 1+ring*segments+nxt
            triangles.extend([[a,a+segments,b+segments],[a,b+segments,b]])
        triangles.append([bottom,1+(rings-2)*segments+nxt,1+(rings-2)*segments+j])
    # Do not rely on native automatic mesh repair for the modifier orientation.
    volume = sum(float(np.dot(vertices[a],np.cross(vertices[b],vertices[c])))
                 for a,b,c in triangles)/6
    if volume < 0: triangles = [[a,c,b] for a,b,c in triangles]
    return {'name':f'Surface Studio area {number}', 'vertices':vertices,
            'triangles':triangles, 'config':{'zaa_enabled':'1'}}


def audit_selected_paths(data,mapping,areas):
    """Reject lost regional settings; never accept a merely highlighted model."""
    from .engine_parser import read
    parsed=read(data,set(),mapping,profile_macros=True,require_planar=False)
    counts=[0]*len(areas); affected=0; nonplanar=0; max_slope=0.
    for move in parsed.moves.values():
        if not move.deposits or move.obj not in mapping.values() or move.z is None:
            continue
        if max(abs(p[2]-move.z) for p in (move.start,move.end))<=2e-5:
            continue
        affected+=1
        margin=max(.3,(move.w or .4)/2+.05)
        for point in (move.start,move.end):
            if not any(math.dist(point,area['center'])<=area['radius_mm']+margin for area in areas):
                raise WaveError('WALL_SCOPE: o fatiador inclinou uma trajetória fora das áreas escolhidas.')
        for i,area in enumerate(areas):
            if any(math.dist(p,area['center'])<=area['radius_mm']+margin for p in (move.start,move.end)):
                counts[i]+=1
        dz=abs(move.end[2]-move.start[2])
        if dz>2e-6:
            nonplanar+=1
            max_slope=max(max_slope,math.degrees(math.atan2(dz,math.dist(move.start[:2],move.end[:2]))))
    missing=[str(i+1) for i,count in enumerate(counts) if not count]
    if missing:
        raise WaveError('WALL_NO_EFFECT: sem contorno compatível nas áreas '+', '.join(missing)+
                        '. Selecione a borda superior inclinada ou remova essas áreas.')
    return {'affected_segments':affected,'nonplanar_segments':nonplanar,
            'affected_segments_per_area':counts,'outside_scope_segments':0,
            'scope_margin':'half bead width plus 0.05 mm, at least 0.3 mm',
            'maximum_motion_slope_deg':max_slope,'print_allowed':False}
