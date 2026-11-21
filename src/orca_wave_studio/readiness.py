"""Auditable nominal body bound, deliberately separate from print approval."""
from __future__ import annotations
import math
from .contracts import WaveError,digest
from .engine_parser import read


def nominal_body_height_bound(gcode,mapping,minimum_body_z_mm,*,registration_verified=False):
    """Bound every labelled linear motion against all earlier estimated material.

    If the complete rigid body lies above the supplied relative-TCP Z floor,
    its entire sweep lies above min(TCP.Z)+floor. All earlier finite beads are
    enclosed below their largest TCP.Z, regardless of XY. This is conservative
    and continuous on a linear move. It does not certify the nozzle/developing
    bead, installed geometry, bead swelling, startup, homing or footer macros.
    A negative bound is inconclusive, not proof of a physical collision.
    """
    if type(minimum_body_z_mm) not in (int,float) or not math.isfinite(minimum_body_z_mm) or minimum_body_z_mm<=0:
        raise WaveError('BODY_FLOOR: informe um limite inferior positivo e finito relativo à ponta do bico.')
    parsed=read(gcode,set(),mapping,profile_macros=True,require_planar=False)
    prefix=-math.inf;minimum=math.inf;worst=None;count=0;unknown=[];growing=0
    max_deficit=-math.inf
    for m in parsed.moves.values():
        if m.start==m.end:continue
        complete=None not in m.start+m.end and all(math.isfinite(v) for v in m.start+m.end)
        top=max(m.start[2],m.end[2]) if complete else None
        if m.layer>=0:
            if not complete:unknown.append(m.i+1)
            else:
                count+=1
                # Enclose material created during this motion too; do not
                # silently omit it from the body check.
                upper=max(prefix,top) if m.deposits else prefix
                if m.deposits:growing+=1
                if math.isfinite(upper):
                    deficit=upper-min(m.start[2],m.end[2])
                    body_bottom=math.nextafter(min(m.start[2],m.end[2])+minimum_body_z_mm,-math.inf)
                    gap=math.nextafter(body_bottom-math.nextafter(upper,math.inf),-math.inf)
                    max_deficit=max(max_deficit,deficit)
                    if gap<minimum:
                        minimum=gap;worst={'line_1based':m.i+1,'role':m.role,
                            'motion':'extrusion' if m.deposits else 'travel',
                            'tcp_segment_z_range_mm':[min(m.start[2],m.end[2]),top],
                            'material_upper_z_mm':upper,'nominal_lower_bound_mm':gap}
        if m.deposits:
            if not complete:unknown.append(m.i+1)
            else:prefix=max(prefix,top)
    covered=bool(count) and not unknown and math.isfinite(minimum)
    return {'status':'PASS_NOMINAL_BODY_BOUND' if covered and minimum>0 else 'INCONCLUSIVE',
        'gcode_sha256':digest(gcode),'minimum_body_z_mm':minimum_body_z_mm,
        'minimum_nominal_body_gap_mm':minimum if math.isfinite(minimum) else None,
        'maximum_material_above_tcp_mm':max_deficit if math.isfinite(max_deficit) else None,
        'motions_checked':count,'growing_bead_body_checks':growing,'incomplete_lines':sorted(set(unknown))[:30],
        'coverage':'All parsed linear motions in labelled print body; startup/homing/footer not certified',
        'material_model':'Earlier and current finite beads enclosed below maximum trace Z; uncalibrated',
        'installed_head_registration_verified':registration_verified,'worst_bound':worst,
        'nozzle_contact':'UNASSESSED','manufacturing_uncertainty_included':False,
        'physical_validation':False,'print_allowed':False,'printer_contacted':False}
