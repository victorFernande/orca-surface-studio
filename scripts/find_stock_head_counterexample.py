"""Search an official stock-head BREP for an earlier-layer bead witness.

A witness rejects the proposed trial under the stated deposition estimate.
No-witness sampling never grants print approval. No printer I/O exists here.
Run with the isolated CAD Python prepared in .research/sv06-physical-preflight.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.venv/Lib/site-packages'))
sys.path.insert(0, str(ROOT / 'src'))
import numpy as np
from OCP.TopoDS import TopoDS_Shape
from OCP.BRepTools import BRepTools
from OCP.BRep import BRep_Builder
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.TopAbs import TopAbs_IN
from OCP.gp import gp_Pnt
from orca_wave_studio.engine_parser import read


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gcode', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--budget', type=int, default=100000)
    parser.add_argument('--probe-depth', type=float, default=.05)
    args = parser.parse_args()
    if not 0 < args.probe_depth < .1:
        raise ValueError('Probe depth must be positive and below 0.1 mm')
    cache = ROOT / '.research/sv06-physical-preflight'
    assembly = json.loads((cache / 'assembled-components.json').read_text())
    components = assembly['components']
    nozzle = next(c for c in components if c['name'] == 'brass nozzle 0.4mm_M6x0.4')
    tcp = np.array(nozzle['placement_3x4'])[:, 3]
    source = args.gcode.read_bytes()
    moves = list(read(source, set(), {0: '1'}).moves.values())
    deposits = [m for m in moves if m.deposits and m.obj == '1'
                and m.w and m.h and m.layer >= 0 and None not in m.start + m.end]
    # Probe actual earlier model traces, not the target mesh or future layers.
    positions, owners, fractions, offsets = [], [], [], []
    for i, m in enumerate(deposits):
        for fraction in (0., .5, 1.):
            point = np.array(m.start) * (1-fraction) + np.array(m.end) * fraction
            for angle in range(0, 360, 45):
                radius = .42 * m.w
                shift = np.array([radius * math.cos(math.radians(angle)),
                                  radius * math.sin(math.radians(angle)), -args.probe_depth])
                positions.append(point + shift)
                owners.append(i)
                fractions.append(fraction)
                offsets.append(shift.tolist())
    points = np.array(positions)
    owner_indices = np.array(owners)
    lines = np.array([deposits[i].i for i in owners])
    layers = np.array([deposits[i].layer for i in owners])
    maximum_prior_z = {layer: float(np.max(points[layers < layer, 2]))
                       for layer in {m.layer for m in moves if m.layer >= 0}
                       if np.any(layers < layer)}
    candidates = sorted((m for m in moves if None not in m.start + m.end and m.layer >= 0),
                        key=lambda m: (-m.layer, m.end[0], m.i))
    report = {'source_sha256': hashlib.sha256(source).hexdigest(), 'status': 'INCOMPLETE_NO_APPROVAL',
              'print_allowed': False, 'printer_contacted': False,
              'geometry_source': 'official stock assembly 75f8a0da6ff822c67b6aff62cfa85c7a441e2271',
              'real_head_registration_verified': False,
              'frame_assumptions': 'Nominal CAD delta=(-printer X,-printer Z,-printer Y); signs checked against X motor/tensioner and stock firmware probe offset; installed TCP unmeasured',
              'deposition_assumptions': f'horizontal finite bead; interior sample {args.probe_depth} mm below prior trace, radius 0.42*width (less than half width); uncalibrated',
              'witness_requires_completed_earlier_logical_layer': True,
              'sample_count': len(points), 'classifications': 0, 'witness': None}
    # Start at the small parts near the nozzle; other components remain included.
    components = sorted(components, key=lambda c: (0 if c is nozzle else 1,
                                                  tcp[1] - c['bounds_cad_mm'][4]))
    for component in components:
        bounds = np.array(component['bounds_cad_mm'])
        if tcp[1] - bounds[4] > 10 or bounds[0] - tcp[0] > 17 or bounds[3] - tcp[0] < -17:
            continue  # Entire coupon envelope is smaller than these separations.
        shape = TopoDS_Shape()
        if not BRepTools.Read_s(shape, str(cache / component['brep_file']), BRep_Builder()):
            raise RuntimeError('Could not read cached BREP')
        classifier = BRepClass3d_SolidClassifier(shape)
        for sign in (-1,):
            for move in candidates:
                if maximum_prior_z.get(move.layer, -math.inf) < min(move.start[2], move.end[2]) + tcp[1] - bounds[4]:
                    continue
                for current_fraction in (0., .5, 1.):
                    current = np.array(move.start) * (1-current_fraction) + np.array(move.end) * current_fraction
                    delta = points - current
                    cad = tcp + np.column_stack((-delta[:,0], -delta[:,2], sign*delta[:,1]))
                    mask = ((lines < move.i) & (layers < move.layer)
                            & np.all(cad > bounds[:3], axis=1) & np.all(cad < bounds[3:], axis=1))
                    indices = np.flatnonzero(mask)
                    if len(indices):
                        indices = indices[np.argsort(np.sum(delta[indices] ** 2, axis=1))]
                    for idx in indices:
                        report['classifications'] += 1
                        if report['classifications'] > args.budget:
                            report['resource_limit_reached'] = True
                            args.output.write_text(json.dumps(report, indent=2))
                            print(json.dumps({k: report[k] for k in ['status','classifications','witness']}))
                            return
                        classifier.Perform(gp_Pnt(*cad[idx]), 1e-7)
                        if classifier.State() != TopAbs_IN:
                            continue
                        prior = deposits[owner_indices[idx]]
                        report['status'] = 'FAIL_ESTIMATED_EARLIER_LAYER_INTERFERENCE'
                        report['witness'] = {'component': component['name'], 'component_brep': component['brep_file'],
                            'current_line_1based': move.i+1, 'current_layer': move.layer,
                            'current_move_fraction': current_fraction, 'current_nozzle_xyz': current.tolist(),
                            'current_role': move.role, 'current_is_deposition': move.deposits,
                            'prior_line_1based': prior.i+1, 'prior_layer': prior.layer, 'prior_role': prior.role,
                            'prior_trace_fraction': fractions[idx], 'bead_interior_offset_mm': offsets[idx],
                            'prior_material_point_xyz': points[idx].tolist(), 'point_in_cad_frame': cad[idx].tolist(),
                            'printer_y_sign': sign, 'exact_cad_point_classification': 'IN'}
                        args.output.write_text(json.dumps(report, indent=2))
                        print(json.dumps(report, indent=2))
                        return
    report['search_exhausted_without_witness'] = True
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ['status','classifications','witness']}))


if __name__ == '__main__':
    main()
