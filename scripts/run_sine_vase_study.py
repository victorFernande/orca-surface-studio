"""Reproduce combined sine mode with Orca's headless slicer. Never open a GUI or send a print."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from orca_wave_studio.contracts import WaveParameters, digest
from orca_wave_studio.engine import process_gcode
from orca_wave_studio.fixtures import cylinder_snapshot
from orca_wave_studio.geometry import analyze_snapshot
from orca_wave_studio.package import build_sliced_package, extract_plate_gcode
from orca_wave_studio.project_io import write_model_project
from orca_wave_studio.studio_ui import get_studio_html


def vase_snapshot(height=30, radius=12):
    model=cylinder_snapshot()
    count, bands=160, 61
    verts=[]
    for j in range(bands):
        z=height*j/(bands-1)
        r=radius+min(1,height/30)*(3*(z/height)+2*math.sin(math.pi*z/height)**2)
        verts.extend([[r*math.cos(i*math.tau/count),r*math.sin(i*math.tau/count),z]
                      for i in range(count)])
    triangles=[]
    for j in range(bands-1):
        for i in range(count):
            a=j*count+i;b=j*count+(i+1)%count
            triangles.extend([[a,b,b+count],[a,b+count,a+count]])
    bottom,top=len(verts),len(verts)+1
    verts.extend([[0,0,0],[0,0,height]])
    for i in range(count):
        n=(i+1)%count
        triangles.extend([[bottom,n,i],[top,(bands-1)*count+i,(bands-1)*count+n]])
    obj=model.objects[0]
    obj['name']='Vaso de validação · contorno variável'
    obj['volumes'][0].update(vertices=verts,triangles=triangles)
    return model


def run(output, orca, reuse=False, *, height=30, amplitude=1.5):
    if not math.isfinite(height) or not 2 <= height <= 100 or not math.isfinite(amplitude) or not 0 <= amplitude <= 5:
        raise ValueError('Use height 2–100 mm and amplitude 0–5 mm for the preview fixture.')
    output.mkdir(parents=True,exist_ok=True)
    model=vase_snapshot(height)
    settings=json.loads((ROOT/'study/fixtures/sovol-bench-settings.json').read_text(encoding='utf-8'))
    machine='OWS SV06 vaso senoidal Preview'
    settings.update({
        'printer_settings_id':machine, 'print_compatible_printers':[machine],
        'print_settings_id':'OWS Vaso 0.20', 'filament_settings_id':['OWS PLA Preview'],
        'printer_model':'Sovol SV06', 'belt_printer':'0',
        'layer_height':'0.2','initial_layer_print_height':'0.2','wall_loops':'1',
        'top_shell_layers':'0','bottom_shell_layers':'3','bottom_shell_thickness':'0',
        'sparse_infill_density':'0%','spiral_mode':'0','detect_overhang_wall':'0',
        'enable_arc_fitting':'0','gcode_label_objects':'1','seam_gap':'10%',
        'machine_start_gcode':'G90\nG21\nM83\nG92 E0\n',
        'machine_end_gcode':'M104 S0\nM140 S0\nM84\n',
        'before_layer_change_gcode':'','layer_change_gcode':'G92 E0\n',
        'filament_start_gcode':['; Preview only'],'filament_end_gcode':['; Preview only'],
        'wipe':['0'],'retraction_length':['0'],'filament_retraction_length':['0'],
        'post_process':[],'slicing_pipeline_plugin':[], 'print_host':'','printhost_apikey':'',
        'printer_agent':'orca_wave_octoprint', 'use_relative_e_distances':'1',
    })
    original=output/'vase-original.3mf'
    write_model_project(model,original,settings)
    native=output/'native';native.mkdir(exist_ok=True)
    binding=native/'input-binding.json'
    model_hash=digest(original.read_bytes())
    if reuse:
        expected={'model_sha256':model_hash,'source_sha256':digest((native/'plate_1.gcode').read_bytes())}
        if not binding.is_file() or json.loads(binding.read_text(encoding='utf-8'))!=expected:
            raise ValueError('The cached slice is not bound to this model and configuration; run without --reuse-slice.')
    if not reuse:
        startup=None
        if os.name=='nt':
            startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
        completed=subprocess.run([str(orca),str(original.resolve()),'--slice','0','--outputdir',str(native.resolve()),
            '--export-3mf','vase-planar.gcode.3mf'],cwd=native,capture_output=True,timeout=120,startupinfo=startup)
        (native/'process-output.txt').write_bytes(completed.stdout+b'\n'+completed.stderr)
        if completed.returncode:
            raise RuntimeError('Native slicing failed; see process-output.txt and 00000.log.')
        binding.write_text(json.dumps({'model_sha256':model_hash,'source_sha256':digest((native/'plate_1.gcode').read_bytes())},indent=2),encoding='utf-8')
    source=(native/'plate_1.gcode').read_bytes()
    parameters=WaveParameters(mode='combined',amplitude_mm=amplitude,wave_count=6,z_ratio=.5,start_height_mm=1)
    result=process_gcode(source,{'100':parameters},{0:'100'})
    gcode=output/'vase-sine.gcode';gcode.write_bytes(result.gcode)
    package=output/'vase-sine.gcode.3mf'
    info=build_sliced_package(result.gcode,package,project_3mf=native/'vase-planar.gcode.3mf',
        metadata={'bench_only':True,'print_allowed':False,'study_kind':'sine_vase'})
    assert extract_plate_gcode(package,0)==result.gcode
    report={**result.report,'parameters':parameters.to_dict(),'package':info,
            'native_slicing':'PASS_ORCA_CLI','native_preview':'PENDING_USER_PERMISSION',
            'physical_validation':False,'print_allowed':False,
            'fixture':'Generated rotational vase with changing radius; not the user vase.',
            'fixture_height_mm':height,'source_model_sha256':model_hash}
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    state={'status':'ready','demo':True,'revision':model.revision,'objects':analyze_snapshot(model),
        'selected_object_ids':['100'],'parameters':parameters.to_dict(),'parameters_by_object':{'100':parameters.to_dict()},
        'message':'Vaso senoidal de validação. Sem envio à impressora.',
        'capture':{'sha256':digest(source),'revision':model.revision},
        'result':{'sha256':result.sha256,'package_path':str(package),'gcode_path':str(gcode),'report':report,
            **{k:report[k] for k in ('original_points','deformed_points','layer_ids','break_indices')}}}
    (output/'studio.html').write_text(get_studio_html(state),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('segments','max_geometric_error_mm','min_segment_mm',
        'vertical_spacing_mm','max_z_speed_mm_s','max_z_acceleration_mm_s2','output_sha256')},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'study/evidence/sine-vase')
    parser.add_argument('--orca',type=Path,default=Path(r'C:\Program Files\OrcaSlicer\orca-slicer.exe'))
    parser.add_argument('--reuse-slice',action='store_true')
    parser.add_argument('--height',type=float,default=30)
    parser.add_argument('--amplitude',type=float,default=1.5)
    args=parser.parse_args()
    run(args.output.resolve(),args.orca,args.reuse_slice,height=args.height,amplitude=args.amplitude)
