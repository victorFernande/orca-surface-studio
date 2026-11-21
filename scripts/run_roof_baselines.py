"""Generate isolated native PLANAR/ZAA roof baselines. Never prints or opens GUI."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from orca_wave_studio.capture import atomic_write
from orca_wave_studio.contracts import ProjectSnapshot,WaveError,digest
from orca_wave_studio.engine_parser import read
from orca_wave_studio.geometry import IDENTITY
from orca_wave_studio.package import extract_plate_gcode
from orca_wave_studio.project_io import write_model_project
from orca_wave_studio.roof_fixtures import ROOF_ANGLES,roof_coupon


def save(path,value):
    atomic_write(path,json.dumps(value,ensure_ascii=False,indent=2).encode())


def private_settings(template:dict, *, zaa_mode:str) -> dict:
    settings=json.loads(json.dumps(template))
    # Strip credentials/hosts and all executable macros from the copied profile.
    for key,value in list(settings.items()):
        low=key.lower()
        if any(word in low for word in ('password','apikey','api_key','token','access_code','certificate','print_host','printhost')):
            settings[key]=''
        elif low.endswith('_gcode') or low.endswith('_script'):
            settings[key]=['']*len(value) if isinstance(value,list) else ''
        elif (low in {'nozzle_temperature','nozzle_temperature_initial_layer','chamber_temperature','idle_temperature'}
              or low.endswith('_plate_temp') or low.endswith('_plate_temp_initial_layer')):
            # Orca otherwise synthesizes heating commands even without startup
            # macros. Cold values are exclusive to this non-printable profile.
            settings[key]=['0']*len(value) if isinstance(value,list) else '0'
    machine='OWS Digital Roof SV06 0.4 PETG'
    settings.update({
        'printer_settings_id':machine,'printer_model':'Sovol SV06','printer_variant':'0.4',
        'print_compatible_printers':[machine],'print_settings_id':'OWS Roof 0.20 '+zaa_mode.upper(),
        'filament_settings_id':['OWS PETG Digital Bench'],'filament_type':['PETG'],
        'filament_density':['1.27'],'filament_flow_ratio':['1'],'nozzle_diameter':['0.4'],
        'layer_height':'0.2','initial_layer_print_height':'0.2','wall_loops':'3',
        'top_shell_layers':'4','bottom_shell_layers':'4','sparse_infill_density':'15%',
        'gcode_flavor':'marlin','use_relative_e_distances':'1','gcode_label_objects':'1',
        'belt_printer':'0','spiral_mode':'0','enable_arc_fitting':'disabled',
        'enable_support':'1','support_type':'normal(auto)','support_style':'grid',
        'support_threshold_angle':'40','support_on_build_plate_only':'0',
        'support_top_z_distance':'0.2','support_bottom_z_distance':'0.2','support_object_xy_distance':'0.35',
        'support_interface_top_layers':'3','support_interface_bottom_layers':'3',
        'support_interface_spacing':'0.2','support_critical_regions_only':'0',
        'raft_layers':'0','brim_width':'0','enable_prime_tower':'0',
        'post_process':[],'slicing_pipeline_plugin':[],'printer_agent':'',
        'print_host':'','printhost_apikey':'','machine_start_gcode':'G90\nG21\nM83\nG92 E0\n',
        'machine_end_gcode':'; Digital study only; no printer transport\n',
        'layer_change_gcode':'G92 E0\n','before_layer_change_gcode':'',
        'filament_start_gcode':['; PETG metadata; digital study only'],
        'filament_end_gcode':['; digital study only'],
        'wipe':['0'],'filament_wipe':['0'],'retraction_length':['0'],'filament_retraction_length':['0'],
        'use_firmware_retraction':'0','seam_gap':'0%','detect_narrow_internal_solid_infill':'0',
        'zaa_enabled':'1' if zaa_mode=='on' else '0',
        'zaa_min_z':'0.05','zaa_minimize_perimeter_height':'35','zaa_dont_alternate_fill_direction':'0',
    })
    return settings


def benchy_snapshot(path:Path) -> ProjectSnapshot:
    ns={'m':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
    with ZipFile(path) as archive:model=ET.fromstring(archive.read('3D/3dmodel.model'))
    objects=model.findall('m:resources/m:object',ns);items=model.findall('m:build/m:item',ns)
    if model.get('unit')!='millimeter' or len(objects)!=1 or len(items)!=1 or items[0].get('transform'):
        raise WaveError('A referência Benchy precisa ser o 3MF original de malha única em milímetros.')
    item=objects[0]
    if items[0].get('objectid')!=item.get('id'):raise WaveError('Associação Benchy inválida.')
    vertices=[[float(v.get(k)) for k in ('x','y','z')] for v in item.findall('m:mesh/m:vertices/m:vertex',ns)]
    triangles=[[int(t.get(k)) for k in ('v1','v2','v3')] for t in item.findall('m:mesh/m:triangles/m:triangle',ns)]
    if not vertices or not triangles:raise WaveError('A referência Benchy está vazia.')
    matrix=[list(row) for row in IDENTITY]
    for k in (0,1):matrix[k][3]=110-(min(v[k] for v in vertices)+max(v[k] for v in vertices))/2
    matrix[2][3]=-min(v[2] for v in vertices)
    return ProjectSnapshot('roof-benchy-original',0,({'id':'1','name':'3DBenchy original roof reference',
        'instances_data':[{'id':'1','printable':True,'matrix':matrix}],
        'volumes':[{'id':'1','kind':'part','negative':False,'matrix':[list(row) for row in IDENTITY],
                    'vertices':vertices,'triangles':triangles}]},),{})


def startup_info():
    if os.name!='nt':return None
    value=subprocess.STARTUPINFO();value.dwFlags|=subprocess.STARTF_USESHOWWINDOW;value.wShowWindow=0
    return value


def gcode_audit(content:bytes, native_package:Path, zaa_mode:str, truth:dict|None=None) -> dict:
    parsed=read(content,set(),{0:'1'})
    roles=Counter();nonplanar=Counter();supports=0
    roof_top=roof_top_nonplanar=0
    roof=(truth or {}).get('roof')
    for move in parsed.moves.values():
        if not move.deposits:continue
        roles[move.role]+=1
        if 'support' in move.role:supports+=1
        if abs(move.end[2]-move.start[2])>2e-6:nonplanar[move.role]+=1
        if roof and move.role=='top surface':
            (x0,y0),(x1,y1)=roof['bounds_xy_world_mm'];a,b,c=roof['top_plane_world']
            lower=min(a*x+b*y+c for x in (x0,x1) for y in (y0,y1))-.25
            if x0<=move.end[0]<=x1 and y0<=move.end[1]<=y1 and min(move.start[2],move.end[2])>=lower:
                roof_top+=1
                roof_top_nonplanar+=abs(move.end[2]-move.start[2])>2e-6
    comments={}
    for line in content.decode('latin1').splitlines():
        match=re.match(r'^;\s*(filament_type|nozzle_diameter|layer_height|zaa_enabled|zaa_min_z|zaa_minimize_perimeter_height|support_type|support_top_z_distance|support_bottom_z_distance|support_object_xy_distance)\s*=\s*(.*?)\s*$',line)
        if match:comments[match[1]]=match[2]
    with ZipFile(native_package) as archive:
        effective=json.loads(archive.read('Metadata/project_settings.config'))
    expected='1' if zaa_mode=='on' else '0'
    checks={
        'orca_251_in_generated_header':re.search(rb'^; generated by OrcaSlicer 2\.5\.1\b',content,re.M) is not None,
        'petg_in_gcode_metadata':comments.get('filament_type','').strip('"')=='PETG',
        'petg_in_native_package':effective.get('filament_type')==['PETG'],
        'sv06_nozzle_and_layer_in_native_package':effective.get('nozzle_diameter')==['0.4'] and str(effective.get('layer_height'))=='0.2' and effective.get('printer_model')=='Sovol SV06',
        'nozzle_and_layer_in_gcode_metadata':comments.get('nozzle_diameter')=='0.4' and comments.get('layer_height')=='0.2',
        'zaa_in_gcode_metadata':comments.get('zaa_enabled')==expected,
        'zaa_in_native_package':str(effective.get('zaa_enabled'))==expected,
        'normal_removable_support_config':effective.get('support_type')=='normal(auto)' and str(effective.get('enable_support'))=='1',
        'support_deposition_present':supports>0,
        'package_payload_matches_gcode':digest(extract_plate_gcode(native_package,0))==digest(content),
        'zaa_observable_in_model_deposition':sum(nonplanar[role] for role in ('top surface','outer wall','inner wall'))>0 if zaa_mode=='on' else sum(nonplanar.values())==0,
    }
    # Inspect executable lines only. Macros in the source profile were removed.
    forbidden=[]
    for number,line in enumerate(content.decode('latin1').splitlines(),1):
        command=line.split(';',1)[0].strip()
        if re.match(r'^(G28|G29|G27|M420|M109|M190)\b',command):forbidden.append(number)
        if re.match(r'^M(?:104|140)\b',command):
            temperature=re.search(r'\bS([\d.]+)',command)
            if temperature and float(temperature[1])>0:forbidden.append(number)
    checks['no_homing_heating_or_parking_macros']=not forbidden
    return {'checks':checks,'all_checks_pass':all(checks.values()),'effective_gcode_metadata':comments,
        'deposition_moves_by_role':dict(roles),'nonplanar_deposition_moves_by_role':dict(nonplanar),
        'support_deposition_moves':supports,'forbidden_startup_command_lines':forbidden,
        'coverage_pending':True,'coverage_status':'NOT_EVALUATED',
        'roof_roi_top_surface_deposition_moves':roof_top if roof else None,
        'roof_roi_top_surface_nonplanar_moves':roof_top_nonplanar if roof else None,
        'roof_roi_method':'Coupon only: declared XY footprint, top-surface role and Z >= lowest roof top - 0.25 mm; excludes the horizontal base. This is a location diagnostic, not surface-fidelity approval.',
        'physical_gate':'UNKNOWN','physical_validation':False,'print_allowed':False,
        'underside_nonplanar_capability':'NOT_PROVIDED_BY_NATIVE_ZAA'}


def run(args) -> dict:
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    template_bytes=args.profile.read_bytes();template=json.loads(template_bytes)
    source_hash=digest(template_bytes)
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8]
    profile_dir=output/'private-profile';profile_dir.mkdir(exist_ok=True)
    config=profile_dir/'OrcaSlicer.conf'
    if not config.exists():save(config,{'local_machines':{},'presets':{},'recent':{},'app':{
        'version':'2.5.1','language':'en_US','single_instance':False,'installed_networking':False,
        'auto_check_updates':False,'use_printer_agents':False}})
    temp=profile_dir/'tmp';temp.mkdir(exist_ok=True)
    environment={**os.environ,'TEMP':str(temp),'TMP':str(temp)}
    cases=[]
    if args.models in {'all','coupons'}:
        for angle in args.angles:
            snapshot,truth=roof_coupon(angle);cases.append((f'coupon-{angle:02d}',snapshot,truth))
    if args.models in {'all','benchy'}:
        cases.append(('benchy-original',benchy_snapshot(args.benchy),{
            'kind':'original_benchy','source':str(args.benchy.resolve()),'source_sha256':digest(args.benchy.read_bytes()),
            'geometry_modified':False,'support_required':True,'physical_gate':{'status':'UNKNOWN','print_allowed':False}}))
    summary={'status':'PREPARED_ONLY' if args.prepare_only else 'PASS_BASELINE_GENERATION',
        'run_id':run_id,'expected_orca_version':'2.5.1','orca_version_method':'verify generated G-code header for each job; --version unsupported',
        'orca_executable':str(args.orca.resolve()),'orca_executable_sha256':digest(args.orca.read_bytes()),
        'profile_source':str(args.profile.resolve()),'profile_source_sha256':source_hash,
        'profile_private':str(profile_dir),'jobs':[],'physical_gate':'UNKNOWN','physical_validation':False,
        'print_allowed':False,'printer_contacted':False,'gui_opened':False,'coverage_pending':True}
    for name,snapshot,truth in cases:
        case=output/name;case.mkdir(exist_ok=True)
        save(case/'project-snapshot.json',snapshot.to_dict());save(case/'fixture-truth.json',truth)
        for mode in ('off','on'):
            job=case/('planar' if mode=='off' else 'zaa')/run_id;job.mkdir(parents=True)
            settings=private_settings(template,zaa_mode=mode)
            save(job/'settings.json',settings)
            model=job/'input.3mf';write_model_project(snapshot,model,settings)
            row={'case':name,'zaa_mode':mode,'status':'PREPARED_ONLY','folder':str(job),
                'snapshot_revision':snapshot.revision,'input_sha256':digest(model.read_bytes()),
                'settings_sha256':digest((job/'settings.json').read_bytes()),
                'support_gaps_mm':{'top_z':.2,'bottom_z':.2,'xy':.35},'print_allowed':False,'coverage_pending':True}
            row['thermal_profile']='cold digital preview; PETG material metadata retained; not a printable temperature preset'
            if not args.prepare_only:
                native=job/'native';native.mkdir()
                package=native/'native.gcode.3mf';gcode=native/'plate_1.gcode'
                command=[str(args.orca), '--datadir',str(profile_dir),str(model), '--slice','0',
                         '--outputdir',str(native),'--export-3mf',package.name]
                try:
                    completed=subprocess.run(command,cwd=native,capture_output=True,timeout=120,
                        startupinfo=startup_info(),env=environment)
                    atomic_write(job/'process-output.txt',completed.stdout+b'\n'+completed.stderr)
                    row['exit_code']=completed.returncode
                    if completed.returncode or not gcode.is_file() or not package.is_file():
                        raise WaveError('O Orca falhou ou não produziu os dois artefatos nativos.')
                    row.update(gcode_path=str(gcode),native_package_path=str(package),
                        gcode_sha256=digest(gcode.read_bytes()),native_package_sha256=digest(package.read_bytes()))
                    row['audit']=gcode_audit(gcode.read_bytes(),package,mode,truth)
                    row['status']='PASS_BASELINE_GENERATION' if row['audit']['all_checks_pass'] else 'ISSUES'
                    if row['status']=='ISSUES':
                        row['reason']='Verificações não atendidas: '+', '.join(key for key,value in row['audit']['checks'].items() if not value)
                except subprocess.TimeoutExpired as exc:
                    row.update(status='ISSUES',reason='Timeout nativo de 120 segundos.')
                    atomic_write(job/'process-output.txt',(exc.stdout or b'')+b'\n'+(exc.stderr or b''))
                except Exception as exc:
                    row.update(status='ISSUES',reason=str(exc))
                if row['status']=='ISSUES':summary['status']='ISSUES'
            save(job/'report.json',row);summary['jobs'].append(row)
            save(output/'baseline-index.json',summary)
    summary['original_profile_preserved']=args.profile.read_bytes()==template_bytes
    if not summary['original_profile_preserved']:summary['status']='ISSUES'
    save(output/'baseline-index.json',summary)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'study/evidence/roof-study/baselines')
    parser.add_argument('--profile',type=Path,default=ROOT/'study/fixtures/sovol-bench-settings.json')
    parser.add_argument('--orca',type=Path,default=Path(r'C:\Program Files\OrcaSlicer\orca-slicer.exe'))
    parser.add_argument('--benchy',type=Path,default=ROOT/'study/evidence/benchy-roof/3DBenchy-original.3mf')
    parser.add_argument('--angles',nargs='+',type=int,choices=ROOF_ANGLES,default=list(ROOF_ANGLES))
    parser.add_argument('--models',choices=['all','coupons','benchy'],default='all')
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    try:
        result=run(args)
        print(json.dumps({key:result[key] for key in ('status','run_id','original_profile_preserved','print_allowed')},indent=2))
        print(json.dumps([{'case':row['case'],'zaa_mode':row['zaa_mode'],'status':row['status'],
                          'reason':row.get('reason')} for row in result['jobs']],indent=2))
        sys.exit(1 if result['status']=='ISSUES' else 0)
    except Exception as exc:
        print(json.dumps({'status':'ISSUES','reason':str(exc),'print_allowed':False}),file=sys.stderr)
        sys.exit(1)
