"""Remove zero-area facets without moving vertices or filling missing surfaces."""
from __future__ import annotations

import copy
import math
from collections import defaultdict

from .contracts import WaveError


def normalize_snapshot(snapshot, object_id):
    result=copy.deepcopy(snapshot)
    obj=next((o for o in result.objects if str(o['id'])==str(object_id)),None)
    if obj is None:raise WaveError('A peça selecionada não pertence ao projeto.')
    if len(obj['volumes'])!=1:
        raise WaveError('A normalização requer um único volume sólido.')
    vol=obj['volumes'][0]
    verts=vol['vertices']
    faces=[tuple(t) for t in vol['triangles']]
    if len(faces)>250_000 or len(verts)>250_000:
        raise WaveError('O estudo aceita até 250 mil faces e vértices.')
    def area(face):
        a,b,c=(verts[k] for k in face)
        u=[v-w for v,w in zip(b,a)];v=[n-w for n,w in zip(c,a)]
        return math.hypot(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
    if any(len(f)!=3 or any(type(k) is not int or not 0<=k<len(verts) for k in f) for f in faces):
        raise WaveError('Índice de triângulo inválido.')
    if not all(len(p)==3 and all(math.isfinite(n) for n in p) for p in verts):
        raise WaveError('Malha sem coordenadas finitas.')
    unique={};canonical=[];indices=[]
    for p in verts:
        key=tuple(p)
        if key not in unique:
            unique[key]=len(canonical);canonical.append(p)
        indices.append(unique[key])
    welded=len(verts)-len(canonical)
    verts=canonical
    faces=[tuple(indices[k] for k in f) for f in faces]
    vol['vertices']=verts
    bad={i for i,f in enumerate(faces) if area(f)<1e-12}
    if not bad and not welded:
        return result,{'removed_zero_area_triangles':0,'split_neighbour_faces':0,
                       'exact_duplicate_vertices_welded':0,'vertices_moved':0,'surface_change_tolerance_mm':1e-9}
    edges=defaultdict(set)
    def register(i,f):
        for a,b in zip(f,(*f[1:],f[0])): edges[tuple(sorted((a,b)))].add(i)
    def unregister(i,f):
        for a,b in zip(f,(*f[1:],f[0])): edges[tuple(sorted((a,b)))].discard(i)
    for i,f in enumerate(faces):
        if i not in bad: register(i,f)
    removed=set(bad);splits=0
    # A collinear facet A-B-C can connect A-B/B-C to a neighbouring A-C.
    # Split that neighbour at B rather than filling the resulting boundary.
    for index in sorted(bad):
        f=faces[index]
        if len(set(f))<3: continue
        a,c=max(((f[i],f[j]) for i in range(3) for j in range(i+1,3)),
                key=lambda edge:math.dist(verts[edge[0]],verts[edge[1]]))
        b=next(k for k in f if k not in (a,c))
        length=math.dist(verts[a],verts[c])
        if not length: continue
        if abs(math.dist(verts[a],verts[b])+math.dist(verts[b],verts[c])-length)>1e-9:
            raise WaveError('Face fina não pode ser descartada sem alterar a superfície.')
        for neighbour in list(edges.get(tuple(sorted((a,c))),())):
            old=faces[neighbour]
            if neighbour in removed or b in old: continue
            unregister(neighbour,old);removed.add(neighbour)
            u,v,w=next((old[j],old[(j+1)%3],old[(j+2)%3]) for j in range(3)
                       if {old[j],old[(j+1)%3]}=={a,c})
            for new in ((u,b,w),(b,v,w)):
                if area(new)<1e-12:
                    raise WaveError('A retesselação produziu outra face degenerada.')
                faces.append(new);register(len(faces)-1,new)
            splits+=1
    # Consecutive collinear facets can expose a longer edge only after an
    # earlier split. Close those T junctions by further subdivision, never by
    # inventing a face across a finite-area hole.
    for _ in range(4*len(bad)+1):
        boundary=[edge for edge,ids in edges.items() if len(ids)==1]
        points={k for edge in boundary for k in edge}
        found=False
        for a,c in sorted(boundary,key=lambda e:math.dist(verts[e[0]],verts[e[1]]),reverse=True):
            length=math.dist(verts[a],verts[c])
            if not length: continue
            direction=[(v-u)/length for u,v in zip(verts[a],verts[c])]
            for b in points-{a,c}:
                delta=[v-u for u,v in zip(verts[a],verts[b])]
                along=sum(u*v for u,v in zip(delta,direction))
                distance=math.dist(delta,[along*v for v in direction])
                if not 1e-9<along<length-1e-9 or distance>1e-9: continue
                neighbour=next(iter(edges[tuple(sorted((a,c)))]))
                old=faces[neighbour]
                u,v,w=next((old[j],old[(j+1)%3],old[(j+2)%3]) for j in range(3)
                           if {old[j],old[(j+1)%3]}=={a,c})
                new=((u,b,w),(b,v,w))
                if any(area(f)<1e-12 for f in new): continue
                unregister(neighbour,old);removed.add(neighbour)
                for f in new:
                    faces.append(f);register(len(faces)-1,f)
                splits+=1;found=True;break
            if found: break
        if not found: break
    vol['triangles']=[list(f) for i,f in enumerate(faces) if i not in removed]
    return result,{'removed_zero_area_triangles':len(bad),'split_neighbour_faces':splits,'exact_duplicate_vertices_welded':welded,
                   'vertices_moved':0,'surface_change_tolerance_mm':1e-9}
