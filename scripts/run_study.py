from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import threading
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from orca_wave_studio.capture import CaptureStore, atomic_write
from orca_wave_studio.contracts import WaveParameters, digest
from orca_wave_studio.engine import process_gcode
from orca_wave_studio.fixtures import cylinder_gcode, cylinder_snapshot, write_cylinder_stl
from orca_wave_studio.geometry import analyze_snapshot
from orca_wave_studio.native_agent import BenchAgent, configure_native_agent, DEVICE_ID
from orca_wave_studio.package import build_sliced_package, extract_plate_gcode
from orca_wave_studio.simulator import OctoPrintSimulator
from orca_wave_studio.studio_ui import get_studio_html
from types import SimpleNamespace
from orca_wave_studio import __version__


def run(output:Path) -> dict:
    output.mkdir(parents=True,exist_ok=True)
    snapshot=cylinder_snapshot(two_objects=True)
    objects=analyze_snapshot(snapshot)
    source=cylinder_gcode(two_objects=True)
    path=output/"cylinders-base.gcode"
    atomic_write(path,source)
    write_cylinder_stl(output/"cylinder-bench.stl")
    store=CaptureStore(output,allowed_source_roots=(output.resolve(),))
    store.begin(snapshot,{0:"100",1:"101"})
    store.export_started(snapshot.session_id,str(path))
    capture=store.finish(snapshot.session_id,str(path))
    params=WaveParameters(mode="z",amplitude_mm=.08,start_height_mm=1.,end_height_mm=7.6)
    result=process_gcode(Path(capture.copy_path).read_bytes(),{"100":params},{0:"100",1:"101"})
    atomic_write(output/"waves-bench.gcode",result.gcode)
    package=output/"waves-bench.gcode.3mf"
    envelope=build_sliced_package(result.gcode,package,plate_index=0,metadata={"bench_only":True})
    reopened=extract_plate_gcode(package,0)
    progress=[]
    with OctoPrintSimulator() as simulator:
        configure_native_agent(lambda:{"base_url":simulator.base_url,"api_key":simulator.api_key,
            "bench_only":True,"approval_current":True,"expected_sha256":result.sha256,
            "plate_index":0,"approval_id":"offline-study"})
        agent=BenchAgent()
        ready=threading.Event()
        agent.set_on_local_message_fn(lambda *_:ready.set())
        authority=urlsplit(simulator.base_url).netloc
        if agent.connect_printer(SimpleNamespace(dev_id=DEVICE_ID,host=authority,port=""))!=0 or not ready.wait(5):
            raise RuntimeError("A conexão de bancada não ficou pronta.")
        reply=agent.start_local_print(SimpleNamespace(filename=str(package),plate_index=1,dev_id=DEVICE_ID,dev_ip=authority),
            lambda *args:progress.append(args),lambda:False)
        if reply!=0 or len(simulator.captures)!=1:
            raise RuntimeError("O receptor de bancada não confirmou exatamente um envio: "+str(agent.last_event))
        received=simulator.captures[0]
        hashes={"generated":result.sha256,"package_reopened":digest(reopened),
                "agent_extracted":agent.last_event["gcode_sha256"],"simulator_received":received["sha256"]}
        if len(set(hashes.values()))!=1 or received["gcode"]!=result.gcode:
            raise RuntimeError("Os bytes diferem entre geração, pacote, agente e receptor.")
        agent.disconnect_printer()
    report={"version":__version__,"bench_only":True,"source":"synthetic two-object cylinder fixture",
        "orca_reference_commit":"eef7710cb102fdb51a9bcdbd9efd61047f44774a",
        "capture":{"status":"PASS_OFFLINE","sha256":capture.sha256,"plate_index":0},
        "engine":{"status":"PASS_OFFLINE","report":result.report},
        "package":{"status":"PASS_OFFLINE",**envelope},
        "transport":{"status":"PASS_SIMULATOR","uploads":1,"bytes":len(result.gcode),
                     "effectivePrint":received["receipt"]["effectivePrint"],"hashes":hashes,"progress":progress},
        "native_capture":{"status":"PENDING_GUI","reason":"Callbacks reais e auditoria ainda precisam ser observados."},
        "native_preview":{"status":"PENDING_GUI","reason":"Hash do pacote reaberto não comprova leitura pelo viewer."},
        "native_print":{"status":"PENDING_GUI","reason":"BenchAgent exercitado por Python; botão Print ainda não observado."},
        "physical_validation":{"status":"NOT_RUN","reason":"Envelope do cabeçote e limites ativos ainda não confirmados."}}
    atomic_write(output/"study-results.json",json.dumps(report,ensure_ascii=False,indent=2).encode())
    state={"demo":True,"status":"ready","message":"Resultado real do estudo offline; conexão com o Orca não estabelecida.",
        "objects":objects,"revision":snapshot.revision,"bench_only":True,"capture":capture.to_dict(),
        "selected_object_ids":["100"],"parameters":params.to_dict(),"parameters_by_object":{"100":params.to_dict()},
        "result":{"sha256":result.sha256,"package_path":str(package),"report":result.report,
                  "original_points":result.report["original_points"],"deformed_points":result.report["deformed_points"],
                  "layer_ids":result.report["layer_ids"],"break_indices":result.report.get("break_indices",[])}}
    atomic_write(output/"studio-demo.html",get_studio_html(state).encode())
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=ROOT/"study"/"evidence"/"offline")
    args=parser.parse_args()
    report=run(args.output.resolve())
    print(json.dumps({"status":"PASS_OFFLINE_AND_SIMULATOR","bytes":report["transport"]["bytes"],
                      "hashes":report["transport"]["hashes"],"native_gui":"PENDING","physical":"NOT_RUN"},indent=2))
