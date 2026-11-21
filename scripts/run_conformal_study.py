"""Build a complete conformal preview using the real Orca engine; never transport it."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from orca_wave_studio import __version__
from orca_wave_studio.capture import atomic_write
from orca_wave_studio.conformal import process_conformal_gcode
from orca_wave_studio.conformal_geometry import ConformalWarp
from orca_wave_studio.contracts import ProjectSnapshot, WaveError, digest
from orca_wave_studio.geometry import analyze_snapshot
from orca_wave_studio.package import build_sliced_package, extract_plate_gcode
from orca_wave_studio.project_io import write_model_project
from orca_wave_studio.studio_ui import get_studio_html


def run(snapshot_path:Path, output:Path, orca:Path, reuse_slice:bool=False, name:str='torus-conformal', retain_native_short_edges:bool=False):
    started=time.monotonic()
    if not name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in name):
        raise WaveError('Nome de saída inválido.')
    d=json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot=ProjectSnapshot(d["session_id"],d["plate_index"],tuple(d["objects"]),d["settings"])
    if len(snapshot.objects)!=1:
        raise WaveError("A prova CLI requer uma única peça; a associação nativa de múltiplas peças é separada.")
    selected=str(snapshot.objects[0]["id"])
    warp=ConformalWarp(snapshot,selected,{'retain_native_short_edges':retain_native_short_edges})
    output.mkdir(parents=True,exist_ok=True)
    atomic_write(output/'warp-summary.json',json.dumps(warp.summary,ensure_ascii=False,indent=2).encode())
    settings_path=output/"settings.json"
    if not settings_path.is_file():
        settings=json.loads((ROOT/"study"/"fixtures"/"sovol-bench-settings.json").read_text(encoding="utf-8"))
        machine="Orca Wave SV06 conformal bench"
        settings.update({"printer_settings_id":machine,"print_compatible_printers":[machine],
            "print_settings_id":"OWS conformal 0.20","filament_settings_id":["OWS Generic PLA Bench"],
            "layer_height":"0.2","initial_layer_print_height":"0.2","wall_loops":"3",
            "top_shell_layers":"4","bottom_shell_layers":"3","sparse_infill_density":"10%",
            "machine_start_gcode":"G90\nG21\nM83\nG92 E0\n",
            "machine_end_gcode":"M104 S0\nM140 S0\nM84\n",
            "before_layer_change_gcode":"","layer_change_gcode":"G92 E0\n",
            "filament_type":["PLA"],"filament_density":["1.24"],"filament_flow_ratio":["0.98"],
            "filament_start_gcode":["; bench only"],"filament_end_gcode":["; end bench"],
            "wipe":["0"],"retraction_length":["0"],"filament_retraction_length":["0"],"seam_gap":"0%",
            "detect_narrow_internal_solid_infill":"0"})
        atomic_write(settings_path,json.dumps(settings,ensure_ascii=False,indent=2).encode())
    settings=json.loads(settings_path.read_text(encoding="utf-8"))
    # No print-host information or machine macros enter this preview fixture.
    settings.update({"print_host":"","printhost_apikey":"","printer_agent":"orca_wave_octoprint",
        "post_process":[],"slicing_pipeline_plugin":[],"enable_arc_fitting":"0","gcode_label_objects":"1"})
    source_model=output/"original.3mf"
    flat_model=output/"flattened.3mf"
    write_model_project(snapshot,source_model,settings)
    write_model_project(warp.flattened_snapshot,flat_model,settings)
    native=output/"native-flat"
    native.mkdir(exist_ok=True)
    gcode=native/"plate_1.gcode"
    sliced=native/"flat.gcode.3mf"
    binding=native/"input-binding.json"
    model_hash=digest(flat_model.read_bytes())
    if reuse_slice:
        recorded=json.loads(binding.read_text(encoding="utf-8"))
        if recorded!={"input_sha256":model_hash,"gcode_sha256":digest(gcode.read_bytes())}:
            raise WaveError("O cache CLI não corresponde à malha achatada e ao G-code vinculados.")
    else:
        startup=None
        if os.name=="nt":
            startup=subprocess.STARTUPINFO()
            startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow=0
        command=[str(orca),str(flat_model.resolve()),"--slice","0","--outputdir",str(native.resolve()),
                 "--export-3mf","flat.gcode.3mf"]
        completed=subprocess.run(command,cwd=native,capture_output=True,timeout=120,startupinfo=startup)
        atomic_write(native/"process-output.txt",completed.stdout+b"\n"+completed.stderr)
        if completed.returncode or not gcode.is_file() or not sliced.is_file():
            raise WaveError("O fatiamento nativo falhou; consulte native-flat/00000.log.")
        atomic_write(binding,json.dumps({"input_sha256":model_hash,"gcode_sha256":digest(gcode.read_bytes())},indent=2).encode())
    try:
        result=process_conformal_gcode(gcode.read_bytes(),warp,{0:selected},selected)
    except WaveError as exc:
        atomic_write(output/'generation-status.json',json.dumps({
            'status':'REJECTED','reason':str(exc),'source_sha256':digest(gcode.read_bytes()),
            'warp':warp.summary,'print_allowed':False,'native_preview_validated':False
        },ensure_ascii=False,indent=2).encode())
        raise
    final=output/(name+'.gcode')
    package=output/(name+'.gcode.3mf')
    atomic_write(final,result.gcode)
    package_info=build_sliced_package(result.gcode,package,project_3mf=sliced,plate_index=0,
        metadata={"bench_only":True,"print_allowed":False,"study_kind":"conformal"})
    if digest(extract_plate_gcode(package,0))!=result.sha256:
        raise WaveError("A trajetória mudou durante a montagem do pacote de Preview.")
    report={**result.report,"version":__version__,"warp":warp.summary,"package":package_info,
        "original_model_sha256":digest(source_model.read_bytes()),"flattened_model_sha256":model_hash,
        "original_snapshot_revision":snapshot.revision,"physical_validation":False,"print_allowed":False,
        "native_preview_status":"PENDING_GUI","elapsed_seconds":time.monotonic()-started,
        "orca_executable":str(orca),"orca_version":"2.5.1"}
    atomic_write(output/"conformal-report.json",json.dumps(report,ensure_ascii=False,indent=2).encode())
    atomic_write(output/'generation-status.json',json.dumps({'status':'GENERATED_PENDING_GUI',
        'sha256':result.sha256,'print_allowed':False,'native_short_edge_proposal':retain_native_short_edges},indent=2).encode())
    state={"demo":True,"native":False,"status":"ready","bench_only":True,
        "objects":analyze_snapshot(snapshot),"revision":snapshot.revision,"selected_object_ids":[selected],
        "message":"Peça completa com deposição conformal de bancada. Impressão real bloqueada.",
        "capture":{"sha256":result.report["source_sha256"],"revision":snapshot.revision,"origin":"native_cli"},
        "result":{"study_kind":"conformal","object_id":selected,"sha256":result.sha256,
            "revision":snapshot.revision,"gcode_path":str(final),"package_path":str(package),"report":report,
            **{key:report.get(key,[]) for key in ("original_points","deformed_points","layer_ids","break_indices")}}}
    atomic_write(output/"conformal-studio.html",get_studio_html(state).encode())
    return {"sha256":result.sha256,"bytes":len(result.gcode),"package":str(package.resolve()),
            "native_preview":"PENDING_GUI","print_allowed":False}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--snapshot",type=Path,default=ROOT/"study"/"evidence"/"torus-5mm"/"project-snapshot.json")
    parser.add_argument("--output",type=Path,default=ROOT/"study"/"evidence"/"conformal-full")
    parser.add_argument("--orca",type=Path,default=Path(r"C:\Program Files\OrcaSlicer\orca-slicer.exe"))
    parser.add_argument("--reuse-slice",action="store_true")
    parser.add_argument("--name",default='torus-conformal')
    parser.add_argument("--retain-native-short-edges",action='store_true',
        help='Proposta experimental, desativada no plugin: conserva quinas nativas abaixo de 0,15 mm.')
    args=parser.parse_args()
    print(json.dumps(run(args.snapshot.resolve(),args.output.resolve(),args.orca,args.reuse_slice,args.name,args.retain_native_short_edges),indent=2))
