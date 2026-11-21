"""Conservative vertical-cell bounds and phase-preserving extra slice intervals."""
from __future__ import annotations

import math
import numpy as np
from .bead_deposition import bridge_role,layer_pitches
from .continuous_certificates import _coordinates,_height
from .continuous_layers import LayerGridStage
from .contracts import WaveError
from .engine_parser import read


def cell_vertical_scale_upper(stages,left,right,pitch,xy_padding=0.):
    """Bound physical vertical cell span / pitch over each entire XY box.

    A normal gap is no greater than the vertical gap. Composition multiplies
    positive Jacobian suprema over interval images, not just midpoint samples.
    XY boxes include both chord endpoints and optional planning padding.
    """
    left=np.asarray(left,dtype=float);right=np.asarray(right,dtype=float)
    lo=np.minimum(left,right).copy();hi=np.maximum(left,right).copy()
    lo[:,:2]-=xy_padding;hi[:,:2]+=xy_padding;lo[:,2]-=np.asarray(pitch)
    upper=np.ones(len(lo));uniform_vertical=True
    for stage in reversed(stages):
        a=lo[:,2];b=hi[:,2]
        if hasattr(stage,'flat'):
            mapped_a=np.where((a<=stage.flat[0])|(a>=stage.flat[-1]),a,np.interp(a,stage.flat,stage.physical))
            mapped_b=np.where((b<=stage.flat[0])|(b>=stage.flat[-1]),b,np.interp(b,stage.flat,stage.physical))
            if uniform_vertical:
                # Before the first XY-dependent stage, both cell boundaries
                # are constant over XY. Use their exact finite secant, including
                # knots. A zero-measure neighbouring slope must not create an
                # endless demand for additional boundary layers.
                upper*=(mapped_b-mapped_a)/(b-a)
                lo[:,2]=mapped_a;hi[:,2]=mapped_b
                continue
            bound=np.ones(len(a))
            for i,j in enumerate(stage.slopes):
                bound=np.where((a<=stage.flat[i+1])&(b>=stage.flat[i]),np.maximum(bound,j),bound)
            # Starting at one is conservative even when every local slope <1.
            # For density stages this would erase their useful contraction:
            inside=(a>stage.flat[0])&(b<stage.flat[-1]);local=np.zeros(len(a))
            for i,j in enumerate(stage.slopes):
                local=np.where((a<=stage.flat[i+1])&(b>=stage.flat[i]),np.maximum(local,j),local)
            bound=np.where(inside,local,bound)
            upper*=bound
            lo[:,2]=mapped_a;hi[:,2]=mapped_b
            continue
        uniform_vertical=False
        field=stage.field;box=np.stack((lo,hi),axis=1);xy=_coordinates(field,box)
        ur=((xy[:,:,0]-field.origin[0])/field.scale[0]);vr=((xy[:,:,1]-field.origin[1])/field.scale[1])
        _,c,d,e,f,g=field.coefficients
        gx=np.maximum.reduce([abs(c+2*e*ur[:,i]+f*vr[:,j]) for i in (0,1) for j in (0,1)])/field.scale[0]
        gy=np.maximum.reduce([abs(d+f*ur[:,i]+2*g*vr[:,j]) for i in (0,1) for j in (0,1)])/field.scale[1]
        center=(lo+hi)/2;hc=_height(field,center)
        radius=gx*(hi[:,0]-lo[:,0])/2+gy*(hi[:,1]-lo[:,1])/2+1e-9
        hs=(np.maximum(field.low,hc-radius),np.minimum(field.high,hc+radius))
        bound=np.where((a<=stage.anchor)|(b>=stage.cap),1.,0.)
        for start,end,reverse in ((stage.anchor,stage.reference,False),(stage.reference,stage.cap,True)):
            l=np.maximum(a,start);r=np.minimum(b,end);active=l<=r;width=end-start
            u=(l-start)/width;v=(r-start)/width
            for h in hs:
                j=(stage.cap-h)/width if reverse else (h-stage.anchor)/width
                c0=np.full(len(a),stage.tangent if reverse else 1.);c1=3*j-1-stage.tangent;c2=np.full(len(a),1. if reverse else stage.tangent)
                den=c0-2*c1+c2
                t=np.divide(c0-c1,den,out=np.zeros_like(den),where=abs(den)>1e-20);t=np.minimum(v,np.maximum(u,t))
                for q in (u,v,t):
                    value=(1-q)**2*c0+2*q*(1-q)*c1+q*q*c2
                    bound=np.where(active,np.maximum(bound,value),bound)
        upper*=np.minimum(stage.jmax,bound+1e-8)
        def interval_image(z,h):
            below=z<=stage.reference;u=(z-stage.anchor)/(stage.reference-stage.anchor);v=(z-stage.reference)/(stage.cap-stage.reference)
            low=stage.anchor+(h-stage.anchor)*(3*u*u-2*u**3)+(stage.reference-stage.anchor)*(u**3-2*u*u+u)+(
                stage.reference-stage.anchor)*stage.tangent*(u**3-u*u)
            high=stage.cap+(h-stage.cap)*(2*v**3-3*v*v+1)+(stage.cap-stage.reference)*stage.tangent*(v**3-2*v*v+v)+(
                stage.cap-stage.reference)*(v**3-v*v)
            return np.where((z<=stage.anchor)|(z>=stage.cap),z,np.where(below,low,high))
        lo[:,2]=interval_image(a,hs[0]);hi[:,2]=interval_image(b,hs[1])
    return upper


def plan_spacing(data,warp,mapping,object_id,maximum_height,first_layer,maximum_copy_height):
    parsed=read(data,{object_id},mapping,profile_macros=True);pitches=layer_pitches(parsed,object_id)
    moves=[m for m in parsed.moves.values() if m.deposits and m.obj==object_id and not bridge_role(m.role) and m.role!='ironing']
    if not moves:raise WaveError('BEAD_PLAN: não há cordões apoiados para estudar o espaçamento.')
    # Cover neighbourhoods that a new intermediate contour may reach. The
    # emitted paths are independently audited again after the second slice.
    bounds=cell_vertical_scale_upper(warp.stages,[m.start for m in moves],[m.end for m in moves],
                              [pitches[m.layer] for m in moves],xy_padding=warp.settings.step_mm)
    counts={m.layer:1 for m in moves};limits={};upper={}
    for move,bound in zip(moves,bounds):
        if not move.w or move.w<=0:raise WaveError('BEAD_WIDTH: falta a largura de um cordão apoiado.')
        limit=min(maximum_height,move.w)*.90
        value=pitches[move.layer]*float(bound)
        n=1 if move.layer==0 else max(1,math.ceil(value/limit))
        counts[move.layer]=max(counts[move.layer],n);upper[move.layer]=max(upper.get(move.layer,0.),value)
        limits[move.layer]=min(limits.get(move.layer,limit),limit)
    levels={m.layer:m.z for m in parsed.moves.values() if m.deposits and m.obj==object_id}
    if any(n>4 for n in counts.values()):raise WaveError('BEAD_DENSITY: a peça exige mais de quatro subdivisões locais; reduza a região.')
    flat=[0.];physical=[0.];rows=[]
    for layer,z in sorted(levels.items()):
        n=counts.get(layer,1);flat.append(flat[-1]+pitches[layer]*n);physical.append(z)
        rows.append(dict(layer=layer,source_z_mm=z,subdivisions=n,vertical_cell_bound_mm=upper.get(layer,0.)))
    top=max(p[2] for p in warp.flat_world_vertices)
    if top>physical[-1]+1e-7:
        flat.append(flat[-1]+top-physical[-1]);physical.append(top)
    if flat[-1]>maximum_copy_height+1e-7:
        raise WaveError('BEAD_COPY_HEIGHT: a cópia de estudo excederia a altura do perfil selecionado.')
    cap=max(flat[-1],physical[-1])+1.;flat.append(cap);physical.append(cap)
    grid=LayerGridStage(flat,physical)
    if abs(grid.map_point((0,0,first_layer))[2]-first_layer)>1e-7:
        raise WaveError('BEAD_BASE: o planejamento alteraria a primeira camada.')
    return grid,dict(model='logical_pitch_finite_bead_v1',source_layer_count=len(levels),
        extra_slice_intervals=sum(r['subdivisions']-1 for r in rows),maximum_subdivisions=max(counts.values()),
        maximum_supported_height_mm=maximum_height,planning_margin=.90,
        bound='positive vertical Jacobian interval supremum; XY endpoint boxes padded by step_mm',layers=rows)
