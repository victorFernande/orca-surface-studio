"""Nominal SV06 CAD/body height bound; no printer API or physical release."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from orca_wave_studio.contracts import digest
from orca_wave_studio.engine_parser import read
from orca_wave_studio.package import extract_plate_gcode
from orca_wave_studio.readiness import nominal_body_height_bound


def geometry_digest(content,mapping):
    parsed=read(content,set(),mapping,profile_macros=True,require_planar=False)
    h=hashlib.sha256();count=0
    for m in parsed.moves.values():
        if m.start==m.end and not m.de:continue
        if None in m.end:raise ValueError('Incomplete endpoint cannot establish native path identity.')
        h.update(struct.pack('<4d',*m.end,m.de));count+=1
    return {'sha256':h.hexdigest(),'moves':count}


def audit(job,cad):
    report=json.loads((job/'report.json').read_text());data=(job/'surface.gcode').read_bytes()
    if digest(data)!=report['processed_sha256']:raise ValueError('G-code/report mismatch.')
    assembly=json.loads(cad.read_text());components=assembly['components']
    nozzle=next(c for c in components if c['name']=='brass nozzle 0.4mm_M6x0.4')
    tcp=[r[3] for r in nozzle['placement_3x4']]
    body=[c for c in components if 'brass nozzle' not in c['name'].lower()]
    floor=math.nextafter(min(tcp[1]-c['bounds_cad_mm'][4] for c in body),-math.inf)
    mapping={0:str(report.get('selected_object_id','66'))}
    result=nominal_body_height_bound(data,mapping,floor)
    result.update(nominal_component_count=len(body),
        nominal_axis='printer Z = negative CAD Y',nominal_tcp_cad_mm=tcp,
        cad_metadata_sha256=digest(cad.read_bytes()),
        cad_source_revision='75f8a0da6ff822c67b6aff62cfa85c7a441e2271',
        source_mode=report['study_type'],
        package_payload_equal=extract_plate_gcode(job/'surface.gcode.3mf',0)==data,
        effective_profile_fields_verified=len(report['effective_profile_verification']['verified_fields']))
    if report['study_type']=='native_local_surfaces':
        before=geometry_digest((job/'slice/plate_1.gcode').read_bytes(),mapping)
        after=geometry_digest(data,mapping)
        result['native_xyz_e_identity']={'before':before,'after':after,'equal':before==after}
        if before!=after:raise ValueError('Native XYZ/E changed in the local path.')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True)
    p.add_argument('--cad',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=audit(a.job,a.cad);a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(r,ensure_ascii=False,indent=2))
