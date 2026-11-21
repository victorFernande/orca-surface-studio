"""Apply active-machine limits to generated wave modes without changing XYZ/E."""
import math
import re
from .contracts import ProcessedResult,WaveError,digest
from .engine_parser import read
from .conformal import _feed


def limit_result(result,profile,mapping):
    parsed=read(result.gcode,set(mapping.values()),mapping,profile_macros=True,require_planar=False)
    lines=[];current=None;changed=0;max_speed=max_accel=max_flow=0.;selected_seconds=0.
    for i,line in enumerate(parsed.lines):
        m=parsed.moves.get(i)
        if m is None:lines.append(line);continue
        desired=m.f
        complete=None not in m.start and None not in m.end
        length=math.dist(m.start,m.end) if complete else 0.
        if m.layer>=0 and complete:
            if not profile.contains(m.start) or not profile.contains(m.end):
                raise WaveError(f'PROFILE_BOUNDS: linha {i+1} fora do volume da impressora selecionada.')
            if length:
                if m.deposits and profile.max_volumetric_mm3_s:
                    volume=m.de*math.pi*(profile.filament_mm/2)**2
                    desired=min(desired,60*length*profile.max_volumetric_mm3_s/volume)
                desired,speed,accel=_feed(m.start,m.end,desired,profile.z_speed_mm_s,profile.z_acceleration_mm_s2)
                max_speed=max(max_speed,speed);max_accel=max(max_accel,accel)
                if m.deposits:max_flow=max(max_flow,m.de*math.pi*(profile.filament_mm/2)**2*desired/(60*length))
        if m.deposits and m.obj in mapping.values() and length and desired>0:
            selected_seconds+=60*length/desired
        if desired>0:
            body,sep,comment=line.partition(';')
            if 'F' in m.fields:
                if desired!=m.f:body=re.sub(r'(?i)F\s*[-+]?(?:\d+(?:\.\d*)?|\.\d+)',f'F{desired:.8f}',body,count=1);changed+=1
                line=body+sep+comment
            elif current is not None and abs(current-desired)>1e-8:
                lines.append(f'G1 F{desired:.8f}\n');changed+=1
            current=desired
        lines.append(line)
    data=''.join(lines).encode('latin1')
    report={**result.report,'printer_profile':profile.public_summary(),
        'profile_limits':{'feed_changes':changed,'max_z_speed_mm_s':max_speed,
                          'max_z_acceleration_mm_s2':max_accel,'max_volumetric_mm3_s':max_flow},
        'processed_sha256':digest(data)}
    if 'estimates' in report:
        report['estimates']={**report['estimates'],'processed_selected_deposition_seconds':selected_seconds}
    return ProcessedResult(data,report)
