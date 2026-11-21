"""Replay a nominal CAD/body interference witness. Never authorizes a print.

Requires numpy (project environment) and OCP (optional CAD environment).
No printer/network operations or source-file changes are performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from orca_wave_studio.engine_parser import read


def replay(gcode,assembly,record,cad_root):
    from OCP.TopoDS import TopoDS_Shape
    from OCP.BRepTools import BRepTools
    from OCP.BRep import BRep_Builder
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_IN
    from OCP.gp import gp_Pnt

    if hashlib.sha256(gcode).hexdigest()!=record['source_sha256']:
        raise ValueError('The witness does not belong to this G-code.')
    w=record['witness'];components=assembly['components']
    nozzle=[c for c in components if c['name']=='brass nozzle 0.4mm_M6x0.4']
    target=[c for c in components if c['name']==w['component']]
    if len(nozzle)!=1 or len(target)!=1:raise ValueError('Ambiguous CAD components.')
    target=target[0];tcp=[row[3] for row in nozzle[0]['placement_3x4']]
    body=[c for c in components if not any(s in c['name'].lower() for s in ('silicone','brass nozzle'))]
    # User's 4 mm hypothesis defines a second, explicitly unmeasured TCP
    # registration. The solid geometry and relative X/Y placement stay intact.
    old_y=tcp[1]
    tcp[1]=max(c['bounds_cad_mm'][4] for c in body)+record['user_body_floor_hypothesis_mm']
    if abs((tcp[1]-old_y)-record['hypothetical_tcp_y_shift_mm'])>1e-8:
        raise ValueError('Inconsistent hypothetical TCP registration.')
    parsed=read(gcode,set(),{0:'1'},profile_macros=True,require_planar=False)
    current=parsed.moves[w['current_line_1based']-1]
    prior=parsed.moves[w['prior_line_1based']-1]
    if not (prior.deposits and prior.i<current.i and prior.layer<current.layer):
        raise ValueError('The material must belong to an already completed earlier layer.')
    def interpolate(move,t):return [a+(b-a)*t for a,b in zip(move.start,move.end)]
    p=interpolate(current,w['current_move_fraction'])
    q=interpolate(prior,w['prior_trace_fraction'])
    depth=min(.02,.2*prior.h);q[2]-=depth
    if (math.dist(p,w['current_nozzle_xyz'])>1e-7
            or math.dist(q,w['prior_material_point_xyz'])>1e-7):
        raise ValueError('Coordinates do not match the source motions.')
    delta=[a-b for a,b in zip(q,p)]
    cad=[tcp[0]-delta[0],tcp[1]-delta[2],tcp[2]-delta[1]]
    if math.dist(cad,w['point_in_cad_frame'])>1e-7:raise ValueError('CAD frame mismatch.')
    root=Path(cad_root).resolve();brep=(root/target['brep_file']).resolve(strict=True)
    if not brep.is_relative_to(root) or brep.suffix.lower()!='.brep':
        raise ValueError('CAD component must be a BREP inside the supplied CAD directory.')
    sha=hashlib.sha256(brep.read_bytes()).hexdigest()
    if sha!=w['component_brep_sha256']:raise ValueError('CAD component changed.')
    shape=TopoDS_Shape()
    if not BRepTools.Read_s(shape,str(brep),BRep_Builder()):raise ValueError('Cannot read the CAD solid.')
    classifier=BRepClass3d_SolidClassifier(shape);classifier.Perform(gp_Pnt(*cad),1e-7)
    inside=classifier.State()==TopAbs_IN
    if not inside:raise ValueError('The reported point is not strictly inside the nominal solid.')
    return {'status':'REPRODUCED_NOMINAL_INTERFERENCE','source_sha256':record['source_sha256'],
        'component_brep_sha256':sha,'cad_classifier':'IN','prior_layer_completed':True,
        'body_floor_hypothesis_mm':record['user_body_floor_hypothesis_mm'],
        'current_line_1based':current.i+1,'prior_line_1based':prior.i+1,
        'prior_material_height_above_tcp_mm':delta[2],
        'installed_head_registration_verified':False,'bead_geometry_physically_calibrated':False,
        'physical_validation':False,'print_allowed':False,'printer_contacted':False}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--gcode',type=Path,required=True)
    ap.add_argument('--assembly',type=Path,required=True)
    ap.add_argument('--record',type=Path,required=True)
    ap.add_argument('--cad-root',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    if args.output.resolve() in {p.resolve() for p in (args.gcode,args.assembly,args.record)}:
        raise ValueError('The audit output must not overwrite an input file.')
    result=replay(args.gcode.read_bytes(),json.loads(args.assembly.read_text(encoding='utf-8')),
                  json.loads(args.record.read_text(encoding='utf-8')),args.cad_root)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
