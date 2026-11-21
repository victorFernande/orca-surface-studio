"""Raise non-depositing XY moves above the printed prefix in an offline trial.

This changes no deposition and confers no printing approval. The input is the
strict single-tool absolute-XYZ dialect, before the machine shutdown macro.
"""
import math

from .contracts import WaveError, digest
from .engine_parser import read


def lift_trial_travels(source, mapping, *, anchor_z_mm, clearance_mm, maximum_z_mm, z_speed_mm_s=5.):
    for value in (anchor_z_mm, clearance_mm, maximum_z_mm, z_speed_mm_s):
        if type(value) not in (int, float) or not math.isfinite(value):
            raise WaveError('TRIAL_TRAVEL_LIMITS: finite millimetre limits are required.')
    if min(clearance_mm, maximum_z_mm, z_speed_mm_s) <= 0 or anchor_z_mm < 0:
        raise WaveError('TRIAL_TRAVEL_LIMITS: invalid lift or machine envelope.')
    parsed = read(source, set(), mapping)
    output = []
    highest = 0.
    changed = []
    maximum_lift = 0.
    newline = '\r\n' if b'\r\n' in source else '\n'

    def emit(line):
        output.append(line + newline)

    for index, line in enumerate(parsed.lines):
        move = parsed.moves.get(index)
        if move is None:
            output.append(line)
            continue
        if not move.xyz_abs:
            raise WaveError('TRIAL_TRAVEL_MODE: only absolute XYZ is supported.')
        if move.deposits:
            highest = max(highest, *(z for z in (move.start[2], move.end[2]) if z is not None))
        complete = None not in move.start + move.end
        xy_travel = complete and move.start[:2] != move.end[:2] and not move.deposits
        if not xy_travel or highest <= anchor_z_mm + 1e-6:
            output.append(line)
            continue
        lift = max(highest + clearance_mm, move.start[2], move.end[2])
        if lift > maximum_z_mm:
            raise WaveError('TRIAL_TRAVEL_ENVELOPE: required lift exceeds the configured Z travel.')
        if move.de < -1e-9:
            emit(f'G1 E{move.fields["E"]:.8f} F{min(move.f, 1800):.3f} ; preserve source retraction before lift')
        emit(f'G1 Z{lift:.6f} F{60*z_speed_mm_s:.3f} ; OWS prefix clearance')
        emit(f'G1 X{move.end[0]:.6f} Y{move.end[1]:.6f} F{move.f:.3f}')
        emit(f'G1 Z{move.end[2]:.6f} F{60*z_speed_mm_s:.3f}')
        if 'E' in move.fields and abs(move.de) <= 1e-9:
            emit(f'G1 E{move.fields["E"]:.8f}')
        emit(f'G1 F{move.f:.3f}')
        if move.comment:
            emit(';' + move.comment)
        changed.append(index + 1)
        maximum_lift = max(maximum_lift, lift)
    result = ''.join(output).encode('latin1')
    return result, {'source_sha256': digest(source), 'sha256': digest(result),
                    'changed_source_lines_1based': changed, 'changed_travels': len(changed),
                    'maximum_lift_z_mm': maximum_lift, 'clearance_mm': clearance_mm,
                    'maximum_z_mm': maximum_z_mm, 'z_speed_mm_s': z_speed_mm_s,
                    'deposition_changed': False, 'print_allowed': False}
