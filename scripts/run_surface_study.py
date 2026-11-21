"""Reproduce a geometric surface study from the model copied by the native host."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from orca_wave_studio.capture import atomic_write
from orca_wave_studio.contracts import ProjectSnapshot
from orca_wave_studio.geometry import analyze_snapshot
from orca_wave_studio.studio_ui import get_studio_html
from orca_wave_studio.surface import SurfaceSettings, build_surface_study


def run(source:Path, output:Path, object_id:str|None=None):
    value=json.loads(source.read_text(encoding="utf-8"))
    snapshot=ProjectSnapshot(value["session_id"],value["plate_index"],tuple(value["objects"]),value["settings"])
    selected=object_id or str(snapshot.objects[0]["id"])
    options=SurfaceSettings()
    result=build_surface_study(snapshot,selected,options)
    path=output/"surface-study.gcode"
    atomic_write(path,result.gcode)
    report={**result.report,"snapshot_revision":snapshot.revision,"print_allowed":False,
            "physical_validation":False,"source_snapshot":str(source.resolve())}
    atomic_write(output/"surface-report.json",json.dumps(report,ensure_ascii=False,indent=2).encode())
    state={"demo":True,"native":False,"status":"ready","bench_only":True,
        "message":"Percurso da superfície real. Estudo geométrico sem deposição; impressão indisponível.",
        "objects":analyze_snapshot(snapshot),"revision":snapshot.revision,"selected_object_ids":[selected],
        "capture":None,"result":{"study_kind":"surface","object_id":selected,"settings":asdict(options),
            "sha256":result.sha256,"revision":snapshot.revision,"gcode_path":str(path.resolve()),"report":report,
            **{key:report.get(key,[]) for key in
               ("original_points","deformed_points","layer_ids","break_indices")}}}
    atomic_write(output/"surface-studio.html",get_studio_html(state).encode())
    return {"sha256":result.sha256,"print_allowed":False,"preview":str((output/"surface-studio.html").resolve())}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--snapshot",type=Path,default=ROOT/"study"/"evidence"/"torus-5mm"/"project-snapshot.json")
    parser.add_argument("--output",type=Path,default=ROOT/"study"/"evidence"/"torus-5mm")
    parser.add_argument("--object-id")
    args=parser.parse_args()
    print(json.dumps(run(args.snapshot,args.output,args.object_id),ensure_ascii=False,indent=2))
