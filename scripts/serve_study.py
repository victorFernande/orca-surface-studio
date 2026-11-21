from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import threading

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from orca_wave_studio.capture import atomic_write
from orca_wave_studio.simulator import OctoPrintSimulator


if __name__=="__main__":
    parser=argparse.ArgumentParser(description="Receptor de bancada; nunca conecta a uma impressora.")
    parser.add_argument("--storage",type=Path,default=ROOT/"study"/"isolated_profile"/"orca_plugins"/"plugin_data"/"orca_wave_generator")
    parser.add_argument("--evidence",type=Path,default=ROOT/"study"/"evidence"/"native-print")
    args=parser.parse_args()
    args.evidence.mkdir(parents=True,exist_ok=True)
    stop=threading.Event()
    with OctoPrintSimulator(api_key="orca-wave-bench-local") as sim:
        atomic_write(args.storage/"study_connection.json",json.dumps({"base_url":sim.base_url,"api_key":sim.api_key,"bench_only":True}).encode())
        print("Receptor de bancada pronto:",sim.base_url,flush=True)
        print("Nenhum arquivo é encaminhado a uma impressora.",flush=True)
        previous=0
        try:
            while not stop.wait(.2):
                if len(sim.captures)!=previous:
                    previous=len(sim.captures)
                    captures=[{k:v for k,v in item.items() if k!="gcode"} for item in sim.captures]
                    atomic_write(args.evidence/"receipts.json",json.dumps(captures,indent=2).encode())
                    for index,item in enumerate(sim.captures):
                        atomic_write(args.evidence/f"received-{index+1}.gcode",item["gcode"])
                    print("Recebido:",previous,"arquivo(s); último SHA-256",sim.captures[-1]["sha256"],flush=True)
        except KeyboardInterrupt:
            pass
