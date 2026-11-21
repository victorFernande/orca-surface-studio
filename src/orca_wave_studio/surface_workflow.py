"""Private copied project -> native Orca slice -> bent path -> native Preview.

No upload, printer API, preset mutation or shell command is part of this module.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from zipfile import ZipFile

from .bending import BendingWarp
from .capture import atomic_write
from .conformal import process_conformal_gcode
from .contracts import WaveError,digest
from .package import build_sliced_package,extract_plate_gcode
from .prepared_model import exported_settings
from .printer_profile import PrinterProfile
from .project_io import write_model_project
from .regional_shell import RegionalShellSettings
from .roof_regions import roof_region_catalog,selected_region


PROFILE_FIELDS=('gcode_flavor','nozzle_diameter','filament_diameter','layer_height','initial_layer_print_height',
    'machine_max_speed_z','machine_max_acceleration_z','filament_max_volumetric_speed','printable_area','printable_height',
    'nozzle_temperature','hot_plate_temp','nozzle_temperature_initial_layer','machine_start_gcode','machine_end_gcode',
    'use_relative_e_distances','retraction_length','filament_retraction_length','printer_agent','print_host','printhost_apikey','enable_support')


def verify_profile(package,requested,*,extra_fields=()):
    with ZipFile(package) as archive:actual=json.loads(archive.read('Metadata/project_settings.config'))
    fields=(*PROFILE_FIELDS,*extra_fields)
    mismatch=[key for key in fields if requested.get(key)!=actual.get(key)]
    if mismatch:raise WaveError('PROFILE_CHANGED: o fatiamento alterou '+', '.join(mismatch)+'.')
    return {'verified_fields':list(fields),'matched':True}


def slice_command(executable,workspace=None,*,native_local=False):
    # Relative arguments make the exact grant independent of callback-only
    # plugin.storage(). Popen always receives an explicit private cwd below.
    command=[str(Path(executable).resolve()),'--datadir','profile','input.3mf',
            '--gcode-label-objects','--gcode-comments','--slice','0','--outputdir','output',
            '--export-3mf','source.gcode.3mf']
    if native_local:command.extend(['--zaa-enabled=1','--zaa-minimize-perimeter-height=1'])
    return command


def slice_project(executable,model,folder,cancelled=lambda:False,*,workspace=None):
    executable=Path(executable).resolve(strict=True);folder=Path(folder).resolve()
    folder.mkdir(parents=True,exist_ok=True)
    workspace=Path(workspace or folder/'runner').resolve();workspace.mkdir(parents=True,exist_ok=True)
    busy=workspace/'.busy'
    try:busy.mkdir()
    except FileExistsError:raise WaveError('O fatiador do Studio já está ocupado. Aguarde a tarefa anterior.')
    try:
        return _slice_locked(executable,model,folder,cancelled,workspace)
    finally:busy.rmdir()


def _slice_locked(executable,model,folder,cancelled,workspace):
    data=workspace/'profile';temp=workspace/'temp';output=workspace/'output'
    for directory in (data,temp,output):directory.mkdir(exist_ok=True)
    atomic_write(workspace/'input.3mf',Path(model).read_bytes())
    for name in ('plate_1.gcode','source.gcode.3mf'):(output/name).unlink(missing_ok=True)
    with ZipFile(workspace/'input.3mf') as archive:
        local=str(json.loads(archive.read('Metadata/project_settings.config')).get('zaa_enabled','0'))=='1'
    command=slice_command(executable,workspace,native_local=local)
    options={}
    if os.name=='nt':
        startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
        options['startupinfo']=startup
    # Write bounded-by-disk diagnostics, not stdout pipes which could deadlock.
    with (folder/'slicing.log').open('wb') as log:
        process=subprocess.Popen(command,cwd=str(workspace),stdout=log,stderr=log,env={**os.environ,'TEMP':str(temp),'TMP':str(temp)},**options)
        started=time.monotonic()
        try:
            while process.poll() is None:
                if cancelled():raise WaveError('Geração cancelada. Nenhum arquivo foi enviado à impressora.')
                if time.monotonic()-started>300:raise WaveError('O fatiamento excedeu cinco minutos.')
                time.sleep(.1)
            if process.returncode:raise WaveError('O Orca não concluiu o fatiamento da cópia. Consulte o diagnóstico local.')
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait()
    package=output/'source.gcode.3mf';source=output/'plate_1.gcode'
    if not package.is_file() or not source.is_file():raise WaveError('O Orca não produziu o G-code e o pacote da placa.')
    if extract_plate_gcode(package,0)!=source.read_bytes():raise WaveError('O pacote nativo diverge do G-code fatiado.')
    # Freeze this generation outside the reusable, exactly authorized workspace.
    for path in (source,package):shutil.copyfile(path,folder/path.name)
    return folder/source.name,folder/package.name


def build_surface(snapshot,object_id,backup,folder,executable,settings=None,*,progress=lambda message:None,
                  cancelled=lambda:False,slicer=slice_project,workspace=None):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);options=dict(settings or {})
    if set(options)-{'step_mm','max_slope_deg','retain_native_short_edges','backend','region_id',
                     'selection_mode','selection_revision','wall_selection'}:
        raise WaveError('Parâmetro de superfície desconhecido.')
    backend=options.pop('backend','roof_bending');region_id=options.pop('region_id',None)
    if backend not in ('roof_bending','native_local'):raise WaveError('Método de superfície desconhecido.')
    resolved=exported_settings(Path(backup),active_profile=True)
    profile=PrinterProfile.from_settings(resolved)
    if backend=='native_local':
        from .native_surfaces import build_local
        report,gcode,package=build_local(snapshot,backup,folder,executable,resolved,profile,slicer,workspace,cancelled,progress,verify_profile,options,object_id)
        return _result(snapshot,object_id,folder,settings,report,gcode,package,backend)
    if any(k in options for k in ('selection_mode','selection_revision','wall_selection')):
        raise WaveError('A seleção por clique é usada no método de superfícies locais.')
    options['nominal_layer_height_mm']=profile.layer_mm
    progress('Preparando a peça completa e preservando suas aberturas…')
    warp=BendingWarp(snapshot,object_id,RegionalShellSettings(**options),
                     region=selected_region(roof_region_catalog(snapshot,object_id),region_id))
    if cancelled():raise WaveError('Geração cancelada.')
    flat=folder/'prepared.3mf';write_model_project(warp.flattened_snapshot,flat,resolved)
    progress('Fatiando a cópia com a impressora e o filamento selecionados…')
    source,source_package=slicer(executable,flat,folder/'slice',cancelled,workspace=workspace)
    profile_receipt=verify_profile(source_package,resolved)
    data=source.read_bytes()
    labels={int(m) for m in re.findall(rb'(?mi)^;\s*printing object\s+.*?\bid:(\d+)\s+copy\s+0\s*$',data)}
    if len(labels)!=1:raise WaveError('A fatia precisa conter exatamente a peça da cópia preparada.')
    mapping={next(iter(labels)):str(object_id)}
    progress('Aplicando Z, extrusão e os limites do perfil ativo…')
    result=process_conformal_gcode(data,warp,mapping,str(object_id),printer_profile=profile)
    if cancelled():raise WaveError('Geração cancelada.')
    gcode=folder/'surface.gcode';package=folder/'surface.gcode.3mf'
    atomic_write(gcode,result.gcode)
    build_sliced_package(result.gcode,package,project_3mf=source_package,plate_index=0,
                         metadata={'study_kind':'roof_bending','print_allowed':False})
    if extract_plate_gcode(package,0)!=result.gcode:raise WaveError('O pacote final alterou a trajetória gerada.')
    report={**result.report,'warp':warp.summary,'workflow':'integrated','profile_preview_only':False,
            'profile_preserved':True,'original_revision':snapshot.revision,'original_backup_sha256':digest(Path(backup).read_bytes()),
            'prepared_model_sha256':digest(flat.read_bytes()),'source_package_sha256':digest(source_package.read_bytes()),
            'native_transport_preserved':True,'printer_contacted':False,
            'effective_profile_verification':profile_receipt,
            'physical_gate':'HEAD_AND_DEPOSITION_VALIDATION_REQUIRED','print_allowed':False}
    return _result(snapshot,object_id,folder,settings,report,gcode,package,backend,
                   (warp.flat_top_z-profile.initial_layer_mm)/profile.layer_mm)


def _result(snapshot,object_id,folder,settings,report,gcode,package,backend,reference_index=None):
    atomic_write(folder/'report.json',json.dumps(report,ensure_ascii=False).encode())
    # Bound the WebView transport. Whole logical layers retain their breaks;
    # the native Preview always receives the complete, unsampled G-code.
    layers=report['layer_ids'];counts={}
    for layer in layers:counts[layer]=counts.get(layer,0)+1
    selected_layers=set();budget=6000
    if reference_index is None:reference_index=max(counts,default=0)
    preferred=[int(layer) for layer in report.get('local_nonplanar_layers',{})]
    # Show multiple heights in the Studio, rather than spending the entire
    # transport budget on a planar chimney cap. Native Preview stays complete.
    centers=([sorted(preferred)[round(i*(len(preferred)-1)/3)] for i in range(4)] if preferred else [reference_index])
    order=sorted(counts,key=lambda layer:(min(abs(layer-c) for c in centers),abs(layer-reference_index)))
    for layer in order:
        if counts[layer]<=budget:selected_layers.add(layer);budget-=counts[layer]
    indices=[i for i,layer in enumerate(layers) if layer in selected_layers]
    original_breaks=set(report['break_indices']);breaks=[];previous=-2
    for j,i in enumerate(indices):
        if i!=previous+1 or i in original_breaks:breaks.append(j)
        previous=i
    trace={key:[report[key][i] for i in indices] for key in ('original_points','deformed_points','layer_ids')}
    trace['break_indices']=breaks
    lightweight={k:v for k,v in report.items() if k not in {'original_points','deformed_points','layer_ids','break_indices','point_object_ids'}}
    lightweight['studio_display']={'sampled':len(indices)!=len(layers),'displayed_points':len(indices),'total_points':len(layers),
                                   'native_preview_complete':True,'displayed_layers':sorted(selected_layers)}
    return {'sha256':report['processed_sha256'],'gcode_path':str(gcode),'package_path':str(package),
            'plate_index':0,'revision':snapshot.revision,'object_id':str(object_id),'study_kind':'conformal',
            'workflow':'integrated','settings':{'step_mm':.4,'max_slope_deg':30,
                'retain_native_short_edges':False,'region_id':None,**(settings or {}),'backend':backend},'report':lightweight,**trace}
