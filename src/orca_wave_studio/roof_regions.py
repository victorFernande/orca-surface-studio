"""Immutable plane candidates for the regional study, not a printability claim."""
from __future__ import annotations

from collections import defaultdict
import math

from .contracts import digest
from .mesh_normalization import normalize_snapshot
from .surface import SurfaceMesh,SurfaceSettings


def roof_region_catalog(snapshot,object_id):
    # A revision serializes the complete mesh. Freeze it once for this immutable
    # catalogue; recomputing it per distinct plane makes curved models quadratic.
    revision=snapshot.revision
    try:
        clean,_=normalize_snapshot(snapshot,str(object_id))
        obj=next(obj for obj in clean.objects if str(obj['id'])==str(object_id))
        mesh=SurfaceMesh(obj,SurfaceSettings())
        groups=defaultdict(list)
        for i,face in enumerate(mesh.faces):
            if face.nz*mesh.orientation<=1e-10:continue
            x,y,z=face.points[0]
            key=tuple(round(v,7) for v in (face.gx,face.gy,z-face.gx*x-face.gy*y))
            groups[key].append((i,face))
        rows=[]
        for plane,faces in groups.items():
            area=sum(abs(f.nz)/2 for _,f in faces)
            slope=math.degrees(math.atan(math.hypot(*plane[:2])))
            rows.append({'id':digest(repr((revision,str(object_id),plane)).encode())[:16],
                'top_plane_world':list(plane),'slope_deg':slope,'projected_area_mm2':area,
                'z_max_mm':max(f.zmax for _,f in faces),'triangle_count':len(faces),
                'triangle_indices':[i for i,_ in faces],
                'map_triangles_xy':[[list(p[:2]) for p in f.points] for _,f in faces[:2000]],
                'map_truncated':len(faces)>2000})
        # Prefer an extensive inclined skin, rather than a high chimney cap.
        rows.sort(key=lambda r:(r['slope_deg']>1e-4,r['projected_area_mm2'],r['z_max_mm']),reverse=True)
        budget=2000
        for row in rows:
            triangles=row['map_triangles_xy']
            row['map_triangles_xy']=triangles[:budget]
            budget-=len(row['map_triangles_xy'])
            row['map_truncated']=row['triangle_count']>len(row['map_triangles_xy'])
        for i,row in enumerate(rows):row['label']=f"Região {i+1} · {row['slope_deg']:.1f}° · {row['projected_area_mm2']:.1f} mm²"
        return {'revision':revision,'object_id':str(object_id),'status':'CANDIDATES_ONLY',
            'automatic_region_id':rows[0]['id'] if rows else None,'regions':rows[:100],
            'candidates_truncated':len(rows)>100,'head_capability_deg':None,
            'physical_gate':'HEAD_GEOMETRY_UNVERIFIED','print_allowed':False,
            'selected_faces':['top','underside','border'],
            'note':'A seleção escolhe o topo de referência. O motor exige as duas faces e a borda juntas.'}
    except Exception as exc:
        return {'revision':revision,'object_id':str(object_id),'status':'UNSUPPORTED_GEOMETRY',
            'automatic_region_id':None,'regions':[],'reason':str(exc),'print_allowed':False}


def selected_region(catalog,region_id=None):
    chosen=region_id or catalog.get('automatic_region_id')
    match=next((row for row in catalog['regions'] if row['id']==chosen),None)
    if match is None:raise ValueError('A região selecionada mudou. Atualize a análise da peça.')
    return {'name':match['id'],'top_plane_world':match['top_plane_world']}
