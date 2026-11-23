"""Bounded sampled feedback; final emitted bead audits remain mandatory."""
from __future__ import annotations
import math
import numpy as np
from .bead_deposition import layer_pitches,native_section_role
from .engine_parser import read
from .contracts import WaveError


def sampled_supported_heights(data,warp,mapping,object_id,*,cancelled=lambda:False,progress=lambda message:None):
    if cancelled():raise WaveError('Geração cancelada.')
    parsed=read(data,{object_id},mapping,profile_macros=True)
    pitches=layer_pitches(parsed,object_id);points=[];heights=[];lines=[]
    result={'sampled':True,'samples':0,'minimum_mm':math.inf,'maximum_mm':0.,'maximum_line_1based':0,'minimum_line_1based':0,
            'final_emitted_audit_required':True,'physical_validation':False}
    def flush():
        if not points:return
        if cancelled():raise WaveError('Geração cancelada.')
        gaps=warp.normal_gaps(points,heights)
        if not np.isfinite(gaps).all() or np.any(gaps<=0):raise WaveError('BEAD_REPLAN: espaçamento amostrado inválido.')
        k=int(np.argmax(gaps));j=int(np.argmin(gaps))
        if gaps[j]<result['minimum_mm']:
            result['minimum_mm']=float(gaps[j]);result['minimum_line_1based']=lines[j]
        if gaps[k]>result['maximum_mm']:
            result['maximum_mm']=float(gaps[k]);result['maximum_line_1based']=lines[k]
        result['samples']+=len(points);points.clear();heights.clear();lines.clear()
        if result['samples']>2000000:raise WaveError('BEAD_REPLAN: amostragem excede o limite deste estudo.')
        if result['samples']%65536==0:progress(f'Conferindo espaçamento: {result["samples"]} pontos amostrados…')
    step=max(.075,warp.settings.step_mm/2)
    for move in parsed.moves.values():
        if not move.deposits or move.obj!=object_id or native_section_role(move.role):continue
        n=max(1,math.ceil(math.dist(move.start,move.end)/step))
        if n>10000:raise WaveError('BEAD_REPLAN: segmento excede o limite de amostragem.')
        for j in range(n+1):
            t=j/n;points.append(tuple(a+t*(b-a)for a,b in zip(move.start,move.end)))
            heights.append(pitches[move.layer]);lines.append(move.i+1)
            if len(points)>=4096:flush()
    flush()
    if not result['samples']:raise WaveError('BEAD_REPLAN: não há cordões apoiados.')
    progress(f'Conferência de espaçamento: {result["minimum_mm"]:.4f}–{result["maximum_mm"]:.4f} mm nas amostras; auditoria final ainda obrigatória…')
    return result
