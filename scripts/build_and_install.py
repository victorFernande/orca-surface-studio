from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
import zipfile
import zlib

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/"src"/"orca_wave_studio"
PAGE_NAME="Surface Studio"
LEGACY_PAGE_NAME="Estúdio de Ondas Senoidais"


def renamed_page_state(content:bytes) -> bytes:
    """Rename only the tab's saved visibility; never add or alter a grant."""
    state=json.loads(content)
    if not isinstance(state,dict) or not isinstance(state.get('capabilities'),list):return content
    caps=state['capabilities']
    if any(isinstance(c,dict) and PAGE_NAME in c for c in caps):return content
    old=[c for c in caps if isinstance(c,dict) and LEGACY_PAGE_NAME in c]
    if len(old)!=1 or type(old[0][LEGACY_PAGE_NAME]) is not bool:return content
    entry=old[0]
    entry[PAGE_NAME]=entry.pop(LEGACY_PAGE_NAME)
    return (json.dumps(state,ensure_ascii=False,indent=2)+'\n').encode('utf-8')


def build() -> tuple[Path,Path]:
    project=tomllib.loads((ROOT/"pyproject.toml").read_text(encoding="utf-8"))["project"]
    version=project["version"]
    dependencies=project.get("dependencies",[])
    modules={"orca_wave_studio"+("" if p.stem=="__init__" else "."+p.stem):p.read_text(encoding="utf-8")
             for p in sorted(PACKAGE.glob("*.py"))}
    # Use the same data-only discovery in source, wheels and standalone installs.
    sys.path.insert(0,str(ROOT/'src'))
    from orca_wave_studio.language_packs import read_language_pack_files
    packs,issues=read_language_pack_files(PACKAGE/'locales',strict=True)
    embedded={code:pack for code,pack in packs.items()}
    key='orca_wave_studio.language_packs'
    modules[key]=modules[key].replace('_BUNDLED_LANGUAGE_PACKS = {}',
                                    '_BUNDLED_LANGUAGE_PACKS = '+repr(embedded),1)
    for name,source in modules.items():
        compile(source,name,"exec")
    payload=base64.b64encode(zlib.compress(json.dumps(modules).encode(),9)).decode()
    header=f'''# /// script
# requires-python = ">=3.12"
# dependencies = {json.dumps(dependencies)}
#
# [tool.orcaslicer.plugin]
# name = "Orca Surface Studio"
# description = "Superficies inclinadas e ondas com o perfil selecionado no OrcaSlicer"
# author = "Orca Surface Studio"
# version = "{version}"
# ///
'''
    loader='''
import base64 as _b64, zlib as _zl, json as _js, sys as _sys
import importlib.abc as _abc, importlib.util as _util
_wave_sources = _js.loads(_zl.decompress(_b64.b64decode(_WAVE_PAYLOAD)))
for _name in list(_sys.modules):
    if _name == "orca_wave_studio" or _name.startswith("orca_wave_studio."):
        _sys.modules.pop(_name,None)
_sys.meta_path[:] = [finder for finder in _sys.meta_path if not getattr(finder,"_orca_wave_bundle",False)]
class _WaveLoader(_abc.MetaPathFinder, _abc.Loader):
    _orca_wave_bundle=True
    def find_spec(self, fullname, path=None, target=None):
        if fullname in _wave_sources:
            return _util.spec_from_loader(fullname,self,is_package=fullname=="orca_wave_studio")
    def create_module(self,spec): return None
    def exec_module(self,module):
        module.__file__=__file__
        if module.__name__=="orca_wave_studio": module.__path__=[]
        exec(compile(_wave_sources[module.__name__],__file__+":"+module.__name__,"exec"),module.__dict__)
_sys.meta_path.insert(0,_WaveLoader())
from orca_wave_studio.plugin import *
'''
    dist=ROOT/"dist"
    dist.mkdir(exist_ok=True)
    bundle=dist/"orca_wave_generator.py"
    content=header+"\n_WAVE_PAYLOAD = "+repr(payload)+"\n"+loader
    bundle.write_text(content,encoding="utf-8",newline="\n")
    (dist/"orca_wave_generator_any.py").write_bytes(bundle.read_bytes())
    distribution=re.sub(r"[-_.]+","_",project['name']).lower()
    info=f"{distribution}-{version}.dist-info"
    requirements=''.join(f'Requires-Dist: {dependency}\n' for dependency in dependencies)
    metadata=f"Metadata-Version: 2.1\nName: {project['name']}\nVersion: {version}\nSummary: Orca Surface Studio integration study\nAuthor: Orca Surface Studio\nLicense: MIT\nRequires-Python: >=3.12\n{requirements}Import-Name: orca_wave_studio\n"
    entries={f"orca_wave_studio/{p.name}":p.read_bytes() for p in sorted(PACKAGE.glob("*.py"))}
    for p in (PACKAGE/"assets").glob("*"):
        if p.is_file(): entries[f"orca_wave_studio/assets/{p.name}"]=p.read_bytes()
    for p in (PACKAGE/'locales').glob('*.json'):
        entries[f'orca_wave_studio/locales/{p.name}']=p.read_bytes()
    entries[f"{info}/METADATA"]=metadata.encode()
    entries[f"{info}/WHEEL"]=b"Wheel-Version: 1.0\nGenerator: orca-wave-studio\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    entries[f"{info}/top_level.txt"]=b"orca_wave_studio\n"
    if (ROOT/"LICENSE").is_file(): entries[f"{info}/LICENSE"]=(ROOT/"LICENSE").read_bytes()
    record=io.StringIO()
    writer=csv.writer(record,lineterminator="\n")
    for name,data in entries.items():
        sha=base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        writer.writerow([name,"sha256="+sha,str(len(data))])
    writer.writerow([f"{info}/RECORD","",""])
    entries[f"{info}/RECORD"]=record.getvalue().encode()
    wheel=dist/f"{distribution}-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel,"w",compression=zipfile.ZIP_DEFLATED) as archive:
        for name,data in entries.items():
            item=zipfile.ZipInfo(name,(2026,1,1,0,0,0))
            item.compress_type=zipfile.ZIP_DEFLATED
            item.external_attr=0o644<<16
            archive.writestr(item,data)
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dist.iterdir())
              if p.suffix in {".py",".whl"}}
    (dist/"SHA256SUMS.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return bundle,wheel


def install(bundle:Path,plugins_root:Path,*,enable_new:bool=False) -> Path:
    target=plugins_root.resolve()/"orca_wave_studio"
    target.mkdir(parents=True,exist_ok=True)
    sidecar=target/".install_state.json"
    before=sidecar.read_bytes() if sidecar.is_file() else None
    after=renamed_page_state(before) if before is not None else None
    temp=target/"orca_wave_generator.py.tmp"
    shutil.copyfile(bundle,temp)
    temp.replace(target/"orca_wave_generator.py")
    if before is not None and sidecar.read_bytes()!=before:
        raise RuntimeError("O estado de instalação foi alterado.")
    if after is not None and after!=before:
        # Keep the original sidecar beside it for recovery. Only UI visibility
        # changes key; all permissions and unrelated settings keep their values.
        backup=target/".install_state.before-surface-tab.json"
        if not backup.exists():backup.write_bytes(before)
        pending=target/".install_state.json.tmp"
        pending.write_bytes(after)
        pending.replace(sidecar)
    if before is None and enable_new:
        version=tomllib.loads((ROOT/"pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
        initial={"plugin_name":"Orca Wave Studio","installed_version":version,"installed_from":"local",
                 "enabled":True,"capabilities":[{PAGE_NAME:True},
                    {"Orca Wave Studio • Painel":True},{"Orca Wave Studio Capture":True},
                    {"Orca Wave • OctoPrint (bancada)":True}]}
        sidecar.write_text(json.dumps(initial,ensure_ascii=False,indent=2),encoding="utf-8")
    return target


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--install-root",type=Path)
    parser.add_argument("--install-user",action="store_true")
    parser.add_argument("--enable-new",action="store_true",help="Ativa somente instalações novas; não altera permissões ou estados existentes.")
    parser.add_argument("--test",action="store_true")
    args=parser.parse_args()
    if args.install_user and args.install_root:
        parser.error("Escolha --install-user ou --install-root.")
    if args.test:
        subprocess.run([sys.executable,"-m","unittest","discover","-s","tests","-v"],cwd=ROOT,check=True)
    bundle,wheel=build()
    subprocess.run([sys.executable,"-c",f"import runpy; runpy.run_path({str(bundle)!r}); print('bundle import OK (outside native host)')"],check=True)
    if args.install_user:
        args.install_root=Path(os.environ.get("APPDATA",str(Path.home()/"AppData"/"Roaming")))/"OrcaSlicer"/"orca_plugins"
    if args.install_root:
        print("Installed:",install(bundle,args.install_root,enable_new=args.enable_new))
    print("Bundle:",bundle)
    print("Wheel:",wheel)


if __name__=="__main__":
    main()
