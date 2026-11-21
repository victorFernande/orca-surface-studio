"""Test the unmodified reference Benchy against the existing conformal mode.

This is an offline capability test, not an automatic region planner or a print.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from orca_wave_studio.capture import atomic_write
from orca_wave_studio.conformal_geometry import ConformalWarp
from orca_wave_studio.contracts import ProjectSnapshot, WaveError, digest
from orca_wave_studio.geometry import IDENTITY
from orca_wave_studio.project_io import write_model_project


def read_reference(path: Path) -> ProjectSnapshot:
    ns={'m':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
    with zipfile.ZipFile(path) as archive:
        model=ET.fromstring(archive.read('3D/3dmodel.model'))
    objects=model.findall('m:resources/m:object',ns)
    build=model.findall('m:build/m:item',ns)
    if (model.get('unit')!='millimeter' or len(objects)!=1 or len(build)!=1
            or build[0].get('transform') or build[0].get('objectid')!=objects[0].get('id')):
        raise ValueError('This probe expects the original single-mesh millimeter Benchy 3MF.')
    obj=objects[0]
    vertices=[[float(v.get(k)) for k in ('x','y','z')] for v in obj.findall('m:mesh/m:vertices/m:vertex',ns)]
    triangles=[[int(t.get(k)) for k in ('v1','v2','v3')] for t in obj.findall('m:mesh/m:triangles/m:triangle',ns)]
    if not vertices or not triangles:
        raise ValueError('Original mesh missing.')
    low=[min(v[k] for v in vertices) for k in range(3)]
    high=[max(v[k] for v in vertices) for k in range(3)]
    matrix=copy.deepcopy(IDENTITY)
    matrix[0][3]=110-(low[0]+high[0])/2
    matrix[1][3]=110-(low[1]+high[1])/2
    matrix[2][3]=-low[2]
    return ProjectSnapshot('benchy-reference',0,({'id':'1','name':'3DBenchy original — teste do teto',
        'instances_data':[{'id':'1','printable':True,'matrix':matrix}],
        'volumes':[{'id':'1','kind':'part','negative':False,'matrix':copy.deepcopy(IDENTITY),
                    'vertices':vertices,'triangles':triangles}]},),{})


def run(source: Path, output: Path, *, slice_baseline: bool=False) -> dict:
    output.mkdir(parents=True,exist_ok=True)
    snapshot=read_reference(source)
    selected=snapshot.objects[0]
    volume=selected['volumes'][0]
    shift=[r[3] for r in selected['instances_data'][0]['matrix'][:3]]
    vertices=[[v+s for v,s in zip(p,shift)] for p in volume['vertices']]
    tri=[[vertices[i] for i in face] for face in volume['triangles']]
    normals=[]
    for a,b,c in tri:
        u=[v-w for v,w in zip(b,a)];v=[n-w for n,w in zip(c,a)]
        normals.append((u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]))
    area2=[math.hypot(*n) for n in normals]
    orientation=1 if sum(sum((v-w)*n for v,w,n in zip(t[0],vertices[0],normal)) for t,normal in zip(tri,normals))>0 else -1
    bounds=[[min(p[k] for p in vertices) for k in range(3)],
            [max(p[k] for p in vertices) for k in range(3)]]
    anchor=bounds[1][2]-1.2
    bands=defaultdict(lambda:{'sloped_faces':0,'surface_area_mm2':0.0})
    below=0
    for points,normal,size in zip(tri,normals,area2):
        gradient=math.hypot(*normal[:2])/abs(normal[2]) if normal[2] else math.inf
        if size<1e-12 or normal[2]*orientation<=0 or not 1e-4<gradient<=math.tan(math.radians(30)):
            continue
        centroid=sum(p[2] for p in points)/3
        band=int(centroid//5)*5
        bands[band]['sloped_faces']+=1
        bands[band]['surface_area_mm2']+=float(size/2)
        below+=max(p[2] for p in points)<=anchor
    report={'source_sha256':digest(source.read_bytes()),'mesh_vertices':len(selected['volumes'][0]['vertices']),
        'mesh_triangles':len(tri),'degenerate_triangles':sum(a<1e-12 for a in area2),
        'bounds_mm':bounds,'default_anchor_z_mm':anchor,
        'upward_sloped_faces_below_default_anchor':below,
        'sloped_surface_height_bands':{f'{k}-{k+5}':v for k,v in sorted(bands.items())},
        'geometry_changed':False,'printer_contacted':False,'print_allowed':False,
        'physical_validation':False,'baseline':None}
    try:
        warp=ConformalWarp(snapshot,'1')
        report['warp_summary']=warp.summary
        report['conformal_status']='ACCEPTED_GEOMETRY' if warp.summary['lifted_vertices'] else 'NO_EFFECT'
    except WaveError as exc:
        report.update(conformal_status='REJECTED_UNSUPPORTED_GEOMETRY',conformal_error=str(exc))
    atomic_write(output/'project-snapshot.json',json.dumps(snapshot.to_dict(),ensure_ascii=False).encode())
    settings=json.loads((ROOT/'study/fixtures/sovol-bench-settings.json').read_text(encoding='utf-8'))
    machine='OWS SV06 Benchy Preview'
    settings.update({'printer_settings_id':machine,'print_compatible_printers':[machine],
        'printer_model':'Sovol SV06','belt_printer':'0','print_settings_id':'OWS Benchy 0.20',
        'filament_settings_id':['OWS PLA Preview'],'layer_height':'0.2','initial_layer_print_height':'0.2',
        'wall_loops':'3','top_shell_layers':'4','bottom_shell_layers':'3','sparse_infill_density':'10%',
        'spiral_mode':'0','enable_arc_fitting':'0','gcode_label_objects':'1','post_process':[],
        'slicing_pipeline_plugin':[],'print_host':'','printhost_apikey':'','printer_agent':'orca_wave_octoprint',
        'machine_start_gcode':'G90\nG21\nM83\nG92 E0\n','machine_end_gcode':'M104 S0\nM140 S0\nM84\n',
        'before_layer_change_gcode':'','layer_change_gcode':'G92 E0\n',
        'filament_start_gcode':['; Preview only'],'filament_end_gcode':['; Preview only']})
    model=output/'benchy-sv06-baseline.3mf'
    write_model_project(snapshot,model,settings)
    if slice_baseline:
        native=output/'native-baseline';native.mkdir(exist_ok=True)
        startup=None
        if os.name=='nt':
            startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
        completed=subprocess.run([r'C:\Program Files\OrcaSlicer\orca-slicer.exe',str(model.resolve()),
            '--slice','0','--outputdir',str(native.resolve()),'--export-3mf','benchy-planar.gcode.3mf'],
            cwd=native,capture_output=True,timeout=180,startupinfo=startup)
        atomic_write(native/'process-output.txt',completed.stdout+b'\n'+completed.stderr)
        gcode=native/'plate_1.gcode'
        report['baseline']={'exit_code':completed.returncode,'kind':'ordinary planar slicing',
            'gcode_sha256':digest(gcode.read_bytes()) if gcode.is_file() else None}
    atomic_write(output/'capability-report.json',json.dumps(report,ensure_ascii=False,indent=2).encode())
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=ROOT/'study/evidence/benchy-roof/3DBenchy-original.3mf')
    parser.add_argument('--output',type=Path,default=ROOT/'study/evidence/benchy-roof')
    parser.add_argument('--slice-baseline',action='store_true')
    args=parser.parse_args()
    print(json.dumps(run(args.source.resolve(),args.output.resolve(),slice_baseline=args.slice_baseline),indent=2,ensure_ascii=False))
