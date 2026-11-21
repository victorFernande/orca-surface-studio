"""Conforming edge subdivisions; the occupied piecewise-planar surface is unchanged."""
from __future__ import annotations

import copy
import heapq
import math
from collections import defaultdict
from .contracts import WaveError
from .geometry import transform_point


def refine_region(snapshot, object_id, selected_faces, max_edge_mm=3.0):
    result=copy.deepcopy(snapshot)
    obj=next(o for o in result.objects if str(o['id'])==str(object_id))
    vol=obj['volumes'][0];instance=next(i for i in obj['instances_data'] if i.get('printable',True))
    verts=vol['vertices'];faces=[tuple(f) for f in vol['triangles']]
    world=[transform_point(v,instance['matrix'],vol['matrix']) for v in verts]
    edges=defaultdict(set);active=set(selected_faces);removed=set();queue=[]
    def register(i,f):
        for a,b in zip(f,(*f[1:],f[0])):
            a,b=sorted((a,b));edges[a,b].add(i)
            if i in active:
                length=math.dist(world[a],world[b])
                if length>max_edge_mm+1e-9:heapq.heappush(queue,(-length,a,b))
    def unregister(i,f):
        for a,b in zip(f,(*f[1:],f[0])):edges[tuple(sorted((a,b)))].discard(i)
    for i,f in enumerate(faces):register(i,f)
    initial_vertices=len(verts);initial_faces=len(faces)
    while queue:
        _,a,b=heapq.heappop(queue)
        adjacent=list(edges[a,b])
        if not any(i in active for i in adjacent):continue
        if len(adjacent)!=2:raise WaveError('A região requer duas faces por aresta antes de refinar.')
        mid=len(verts)
        verts.append([(u+v)/2 for u,v in zip(verts[a],verts[b])])
        world.append([(u+v)/2 for u,v in zip(world[a],world[b])])
        for i in adjacent:
            old=faces[i];was_active=i in active
            unregister(i,old);active.discard(i);removed.add(i)
            u,v,w=next((old[j],old[(j+1)%3],old[(j+2)%3]) for j in range(3)
                       if {old[j],old[(j+1)%3]}=={a,b})
            for new in ((u,mid,w),(mid,v,w)):
                index=len(faces);faces.append(new)
                if was_active:active.add(index)
                register(index,new)
        if len(faces)-len(removed)>250_000 or len(verts)>250_000:
            raise WaveError('O refinamento da superfície supera 250 mil faces ou vértices.')
    vol['triangles']=[list(f) for i,f in enumerate(faces) if i not in removed]
    return result,{'added_vertices':len(verts)-initial_vertices,
                   'added_faces':len(vol['triangles'])-initial_faces,'max_region_edge_mm':max_edge_mm,
                   'existing_vertices_moved':0}
