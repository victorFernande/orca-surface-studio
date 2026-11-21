from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def prepare(destination:Path) -> Path:
    destination=destination.resolve()
    destination.mkdir(parents=True,exist_ok=True)
    (destination/"tmp").mkdir(exist_ok=True)
    config=destination/"OrcaSlicer.conf"
    if not config.exists():
        source=Path(os.environ.get("APPDATA",str(Path.home()/"AppData"/"Roaming")))/"OrcaSlicer"/"OrcaSlicer.conf"
        data={}
        if source.is_file():
            data,_=json.JSONDecoder().raw_decode(source.read_text(encoding="utf-8-sig").lstrip())
        minimal={"header":data.get("header",{}),"firstguide":data.get("firstguide",{}),
                 "models":data.get("models",{}),"local_machines":{},"presets":{},"recent":{},
                 "app":{"version":"2.5.1","language":"en_US","region":"Others","single_instance":False,
                        "use_printer_agents":True,"installed_networking":False,"auto_check_updates":False}}
        config.write_text(json.dumps(minimal,indent=2),encoding="utf-8")
    return destination


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--destination",type=Path,default=ROOT/"study"/"isolated_profile")
    parser.add_argument("--launch",action="store_true")
    parser.add_argument("--open",type=Path)
    parser.add_argument("--orca",type=Path,default=Path(r"C:\Program Files\OrcaSlicer\orca-slicer.exe"))
    args=parser.parse_args()
    profile=prepare(args.destination)
    print("Perfil de teste:",profile)
    if args.launch:
        env=os.environ.copy()
        env.update({"TEMP":str(profile/"tmp"),"TMP":str(profile/"tmp")})
        startup=None
        if os.name=="nt":
            startup=subprocess.STARTUPINFO()
            startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow=0
        command=[str(args.orca),"--datadir",str(profile)]
        if args.open:
            command.append(str(args.open.resolve()))
        process=subprocess.Popen(command,env=env,startupinfo=startup)
        print("Processo de teste:",process.pid)
