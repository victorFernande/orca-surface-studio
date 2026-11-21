"""Finite bead sections, with logical layer pitch separate from feature height."""
from __future__ import annotations

import math
from .contracts import WaveError


def bridge_role(role):
    return 'bridge' in role


def native_section_role(role):
    return bridge_role(role) or role=='ironing'


def layer_pitches(parsed,object_id):
    levels={}
    for move in parsed.moves.values():
        if not move.deposits or move.obj!=object_id:continue
        if move.z is None:raise WaveError('BEAD_LAYER: falta a referência da camada lógica.')
        if move.layer in levels and abs(levels[move.layer]-move.z)>2e-5:
            raise WaveError('BEAD_LAYER: alturas incompatíveis na mesma camada lógica.')
        levels[move.layer]=move.z
    result={};previous=0.
    for layer,z in sorted(levels.items()):
        if z<=previous:raise WaveError('BEAD_LAYER: a sequência de camadas precisa ser crescente.')
        result[layer]=z-previous;previous=z
    return result


def section_area(width,height):
    """Stadium cross-section; a tall narrow bead has no supported solution."""
    if not (math.isfinite(width) and math.isfinite(height) and 0<height<=width+2e-5):
        raise WaveError('BEAD_SECTION: altura efetiva maior que a largura; recalcule o espaçamento.')
    return height*(width-height)+math.pi*height*height/4


def bead_portion(warp,left,right,move,base_e,pitch):
    """Return E and displayed section for this actual mapped source portion.

    Supported cells use the physical normal gap and a finite section, retaining
    the native flow factor and horizontal width. Bridges retain their native
    section and scale by path length, not by an unrelated layer-cell Jacobian.
    This model is geometric; it does not qualify bonding, unsupported bridges,
    the motion planner or the installed head.
    """
    source_length=math.dist(left,right)
    if source_length<=0:raise WaveError('BEAD_LENGTH: contribuição de comprimento nulo.')
    mid=tuple((a+b)/2 for a,b in zip(left,right))
    points=(left,mid,right);mapped=[warp.map_point(p) for p in points]
    ratios=[math.dist(a,b)/(source_length/2) for a,b in zip(mapped,mapped[1:])]
    if native_section_role(move.role):
        return base_e*sum(ratios)/2,move.h,move.w,None
    heights=[warp.normal_gap(*point,pitch) for point in points]
    native_area=section_area(move.w,move.h)
    areas=[section_area(move.w,h) for h in heights]
    # Composite trapezoid integrates area along the two mapped half-chords.
    extrusion=base_e*((areas[0]+areas[1])*ratios[0]+(areas[1]+areas[2])*ratios[1])/(4*native_area)
    return extrusion,sum(heights)/3,move.w,(min(heights),max(heights))
