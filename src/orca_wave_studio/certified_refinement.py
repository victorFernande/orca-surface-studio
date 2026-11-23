"""Conforming longest-edge subdivision with complete face and crease bounds.

Several independent edges may be split in one round. Every adjacent triangle
uses the same midpoint, and unchanged faces retain their immutable certificate.
No vertex is moved, no surface is removed, and no error tolerance is relaxed.
"""
from __future__ import annotations
import numpy as np
from .contracts import WaveError


def _edge_keys(faces):
    other=np.roll(faces,-1,axis=1)
    return (np.minimum(faces,other).astype(np.uint64)<<np.uint64(32))|np.maximum(faces,other).astype(np.uint64)


def _endpoints(keys):
    return np.stack((keys>>np.uint64(32),keys&np.uint64(0xffffffff)),axis=-1).astype(np.int64)


def refine_mesh(vertices,faces,world,tolerance,max_faces,*,reference_world,crease_edges,
                face_bounds,edge_bounds,cancelled=lambda:False,progress=lambda message:None):
    if cancelled():raise WaveError('Geração cancelada.')
    if len(faces)>max_faces:raise WaveError(f'BEND_COMPLEXITY: refinamento supera {max_faces} faces.')
    local=np.asarray(vertices,dtype=float);physical=np.asarray(world,dtype=float)
    reference=np.asarray(reference_world,dtype=float);tri=np.asarray(faces,dtype=np.int64)
    keys=np.asarray(sorted((min(a,b)<<32)|max(a,b) for a,b in crease_edges),dtype=np.uint64)
    values=edge_bounds(reference[_endpoints(keys)]) if len(keys) else np.empty(0)
    if not np.isfinite(values).all() or np.any(values<0):raise WaveError('SPLINE_REFERENCE: certificado de quina inválido.')

    def bound(rows):
        result=np.asarray(face_bounds(physical,rows,reference),dtype=float)
        if len(keys):
            edges=_edge_keys(rows);pos=np.searchsorted(keys,edges);safe=np.minimum(pos,len(keys)-1)
            present=(pos<len(keys))&(keys[safe]==edges)
            result=np.maximum(result,np.where(present,values[safe],0.).max(axis=1))
        if not np.isfinite(result).all() or np.any(result<0):raise WaveError('SPLINE_REFERENCE: certificado de face inválido.')
        return result

    errors=bound(tri)
    for iteration in range(64):
        if cancelled():raise WaveError('Geração cancelada.')
        bad=errors>tolerance
        if not bad.any():
            vertices[:]=local.tolist();world[:]=list(map(tuple,physical));reference_world[:]=list(map(tuple,reference))
            return list(map(tuple,tri)),float(errors.max(initial=0.))
        progress(f'Conferindo as superfícies em lote: {len(tri)} faces, rodada {iteration+1}…')
        edge_keys=_edge_keys(tri)
        unique,inverse,counts=np.unique(edge_keys,return_inverse=True,return_counts=True)
        if np.any(counts!=2):raise WaveError('BEND_MESH: aresta aberta durante o refinamento.')
        inverse=inverse.reshape(tri.shape)
        p=physical[tri[bad]];delta=np.roll(p,-1,axis=1)-p
        longest=np.argmax(np.sum(delta*delta,axis=-1),axis=1)
        selected_ids=np.unique(inverse[bad][np.arange(np.count_nonzero(bad)),longest])
        selected=unique[selected_ids];ends=_endpoints(selected)
        midpoints=np.arange(len(local),len(local)+len(selected),dtype=np.int64)
        local=np.vstack((local,(local[ends[:,0]]+local[ends[:,1]])/2))
        physical=np.vstack((physical,(physical[ends[:,0]]+physical[ends[:,1]])/2))
        reference=np.vstack((reference,(reference[ends[:,0]]+reference[ends[:,1]])/2))
        mapping=np.full(len(unique),-1,dtype=np.int64);mapping[selected_ids]=midpoints
        mids=mapping[inverse];marked=mids>=0;number=marked.sum(axis=1)
        changed=number>0;generated=[]
        for count in (1,2,3):
            rows=tri[number==count];m=mids[number==count]
            if not len(rows):continue
            if count<3:
                j=np.argmax(m>=0,axis=1) if count==1 else (np.argmin(m>=0,axis=1)+1)%3
                order=(j[:,None]+np.arange(3))%3
                rows=np.take_along_axis(rows,order,axis=1);m=np.take_along_axis(m,order,axis=1)
            a,b,c=rows.T;ab,bc,ca=m.T
            if count==1:pieces=((a,ab,c),(ab,b,c))
            elif count==2:pieces=((ab,b,bc),(a,ab,c),(ab,bc,c))
            else:pieces=((a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca))
            generated.extend(np.stack(piece,axis=-1) for piece in pieces)
        new=np.concatenate(generated)
        if len(new)+np.count_nonzero(~changed)>max_faces:
            raise WaveError(f'BEND_COMPLEXITY: refinamento supera {max_faces} faces.')
        # Splitting a sharp original edge makes two sharp children with the
        # same original straight segment. Other crease values remain valid.
        if len(keys):
            pos=np.searchsorted(keys,selected);safe=np.minimum(pos,len(keys)-1)
            sharp=(pos<len(keys))&(keys[safe]==selected)
            if sharp.any():
                keep=np.ones(len(keys),dtype=bool);keep[pos[sharp]]=False
                e=ends[sharp];mid=midpoints[sharp]
                children=np.concatenate(((np.minimum(e[:,0],mid).astype(np.uint64)<<np.uint64(32))|np.maximum(e[:,0],mid).astype(np.uint64),
                                         (np.minimum(e[:,1],mid).astype(np.uint64)<<np.uint64(32))|np.maximum(e[:,1],mid).astype(np.uint64)))
                child_values=edge_bounds(reference[_endpoints(children)])
                if not np.isfinite(child_values).all() or np.any(child_values<0):raise WaveError('SPLINE_REFERENCE: certificado de quina inválido.')
                keys=np.concatenate((keys[keep],children));values=np.concatenate((values[keep],child_values))
                order=np.argsort(keys);keys=keys[order];values=values[order]
        new_errors=bound(new)
        tri=np.concatenate((tri[~changed],new));errors=np.concatenate((errors[~changed],new_errors))
    raise WaveError('SPLINE_COMPLEXITY: refinamento não convergiu dentro do limite de rodadas.')
