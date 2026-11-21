"""Local top-facing contouring delegated to Orca, never inverse-mapped again."""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import math
import re

from .capture import atomic_write
from .contracts import ProcessedResult,WaveError,digest
from .engine import STALE
from .engine_parser import read
from .package import build_sliced_package,extract_plate_gcode
from .profile_limits import limit_result
from .project_io import write_model_project
from .wall_selection import resolve_areas,sphere_modifier,audit_selected_paths

LOCAL_FIELDS=('zaa_enabled','zaa_min_z','zaa_minimize_perimeter_height','zaa_dont_alternate_fill_direction')


def local_settings(resolved):
    result=dict(resolved)
    # These are native deposition controls, not a head-clearance angle.
    layer=float(result['layer_height'])
    result.update(zaa_enabled='1',zaa_min_z=str(min(.05,layer/4)),
                  zaa_minimize_perimeter_height='1',zaa_dont_alternate_fill_direction='0')
    return result


def contour_result(data,profile,mapping):
    """Preserve native XYZ/E; limit only feed and remove stale estimates."""
    parsed=read(data,set(),mapping,profile_macros=True,require_planar=False)
    if not re.search(rb'(?mi)^;\s*zaa_enabled\s*=\s*1\s*$',data):
        raise WaveError('LOCAL_SOURCE: o próprio Orca precisa confirmar Z Contouring ativo.')
    if b'OrcaWaveStudio BENCH ONLY' in data or b'OrcaSurfaceStudio LOCAL' in data:
        raise WaveError('LOCAL_DUPLICATE: use somente a fatia nativa ainda sem processamento.')
    content=''.join(line for line in parsed.lines if not STALE.match(line)).encode('latin1')
    limited=limit_result(ProcessedResult(content,{}),profile,mapping)
    parsed=read(limited.gcode,set(),mapping,profile_macros=True,require_planar=False)
    points=[];layers=[];breaks=[];counts=Counter();roles=Counter();nonplanar_layers=Counter();previous=None
    source_segments=0
    for m in parsed.moves.values():
        if not m.deposits or m.obj not in mapping.values():previous=None;continue
        if None in m.start+m.end:raise WaveError('LOCAL_POSITION: deposição com posição incompleta.')
        source_segments+=1
        roles[m.role]+=1
        if abs(m.end[2]-m.start[2])>2e-6:counts[m.role]+=1;nonplanar_layers[m.layer]+=1
        if previous!=m.start:
            breaks.append(len(points));points.append(m.start);layers.append(m.layer)
        points.append(m.end);layers.append(m.layer);previous=m.end
    if not source_segments:raise WaveError('LOCAL_EMPTY: nenhuma trajetória da peça foi produzida.')
    report={**limited.report,'study_type':'native_local_surfaces','surface_scope':'eligible_top_facing_patches',
        'surface_algorithm':'Orca native Z Contouring; no roof inverse map',
        'source_sha256':digest(data),'segment_count':source_segments,'segments':source_segments,
        'output_segments_by_role':dict(roles),'nonplanar_extrusion_segments_by_role':dict(counts),
        'nonplanar_extrusion_detected':bool(counts),'xy_e_preserved_from_native':True,
        'local_nonplanar_layers':dict(nonplanar_layers),
        'original_points':points,'deformed_points':points,'layer_ids':layers,'break_indices':breaks,
        'comparison_scope':'native path only; no separate planar baseline',
        'max_z_speed_mm_s':limited.report['profile_limits']['max_z_speed_mm_s'],
        'max_z_acceleration_mm_s2':limited.report['profile_limits']['max_z_acceleration_mm_s2'],
        'physical_validation':False,'print_allowed':False,
        'unsupported_surface_scope':['downward_facing_surfaces','all_vertical_wall_smoothing'],
        'native_preview_validated':False,'printer_contacted':False}
    final=b'; OrcaSurfaceStudio LOCAL - native contouring; physical qualification pending\n'+limited.gcode
    report['processed_sha256']=digest(final)
    return ProcessedResult(final,report)


def build_local(snapshot,backup,folder,executable,resolved,profile,slicer,workspace,cancelled,progress,verify,options=None,object_id=None):
    folder=Path(folder);settings=local_settings(resolved)
    slope_limit=(options or {}).get('max_slope_deg',30)
    if type(slope_limit) not in (int,float) or not math.isfinite(slope_limit) or not 5<=slope_limit<=45:
        raise WaveError('WALL_SLOPE: o limite do estudo precisa ficar entre 5 e 45 graus.')
    object_id=str(object_id or snapshot.objects[0]['id'])
    obj=next((o for o in snapshot.objects if str(o['id'])==object_id),None)
    if obj is None:raise WaveError('Selecione um modelo da placa.')
    if sum(i.get('printable',True) for i in obj['instances_data'])!=1:
        raise WaveError('Este estudo requer uma cópia do modelo selecionado.')
    areas=resolve_areas(snapshot,object_id,options or {})
    modifiers=[sphere_modifier(area,i+1) for i,area in enumerate(areas)]
    effective={**resolved,**obj.get('config',{}),**obj['volumes'][0].get('config',{})}
    for modifier in modifiers:
        for key in ('outer_wall_speed','inner_wall_speed'):
            value=effective.get(key)
            values=value if isinstance(value,list) else [value]
            try:
                speeds=[float(v)*.8 for v in values]
                if not all(0<v<10000 for v in speeds):raise ValueError()
            except (ValueError,TypeError):
                raise WaveError('WALL_SPEED: o perfil precisa informar velocidades de parede numéricas.')
            modifier['config'][key]=';'.join(f'{v:.9g}' for v in speeds)
    progress('Fatiando as superfícies locais com o contorno em Z do próprio Orca…')
    from dataclasses import replace
    model=folder/'prepared.3mf';write_model_project(replace(snapshot,objects=(obj,)),model,settings,modifiers=modifiers)
    if cancelled():raise WaveError('Geração cancelada.')
    source,package=slicer(executable,model,folder/'slice',cancelled,workspace=workspace)
    receipt=verify(package,settings,extra_fields=LOCAL_FIELDS)
    if areas:
        verify_area_modifiers(package,modifiers)
    data=source.read_bytes();labels={int(m) for m in re.findall(rb'(?mi)^;\s*printing object\s+.*?\bid:(\d+)\s+copy\s+0\s*$',data)}
    if len(labels)!=1:raise WaveError('LOCAL_LABELS: a fatia precisa identificar uma única peça.')
    mapping={next(iter(labels)):object_id}
    selection_audit=audit_selected_paths(data,mapping,areas) if areas else None
    progress('Conferindo os caminhos locais e os limites da impressora selecionada…')
    result=contour_result(data,profile,mapping)
    if cancelled():raise WaveError('Geração cancelada.')
    output=folder/'surface.gcode';native=folder/'surface.gcode.3mf'
    atomic_write(output,result.gcode)
    build_sliced_package(result.gcode,native,project_3mf=package,plate_index=0,
                         metadata={'study_kind':'native_local','print_allowed':False})
    if extract_plate_gcode(native,0)!=result.gcode:raise WaveError('LOCAL_PACKAGE: divergência de conteúdo.')
    report={**result.report,'workflow':'integrated','profile_preview_only':False,'profile_preserved':True,
        'original_revision':snapshot.revision,'original_backup_sha256':digest(Path(backup).read_bytes()),
        'native_transport_preserved':True,'effective_profile_verification':receipt,
        'physical_gate':'HEAD_AND_LOCAL_DEPOSITION_VALIDATION_REQUIRED',
        'wall_selection':{'mode':'paint' if areas else 'all','areas':areas,
            'scope':'closed native modifier spheres including wall thickness',
            'native_modifiers_verified':bool(areas),'wall_speed_factor':.8 if areas else 1},
        'wall_selection_audit':selection_audit,
        'perimeter_minimization_angle_deg':1}
    if selection_audit:
        report['motion_slope_review']={'limit_deg':slope_limit,
            'maximum_deg':selection_audit['maximum_motion_slope_deg'],
            'within_study_limit':selection_audit['maximum_motion_slope_deg']<=slope_limit,
            'head_clearance_certified':False}
        if not report['motion_slope_review']['within_study_limit']:
            report['physical_gate']='MOTION_SLOPE_ABOVE_STUDY_LIMIT'
    return report,output,native


def verify_area_modifiers(package,expected):
    from xml.etree import ElementTree as ET
    from zipfile import ZipFile
    with ZipFile(package) as archive:
        root=ET.fromstring(archive.read('Metadata/model_settings.config'))
    count=expected if isinstance(expected,int) else len(expected)
    objects=root.findall('object')
    if len(objects)!=1:
        raise WaveError('WALL_NATIVE: a cópia fatiada perdeu a identificação da peça.')
    obj=objects[0]
    config={m.get('key'):m.get('value') for m in obj.findall('metadata')}
    parts=[p for p in obj.findall('part') if p.get('subtype')=='modifier_part']
    normal=[p for p in obj.findall('part') if p.get('subtype')=='normal_part']
    if (config.get('zaa_enabled')!='1' or len(parts)!=count or len(normal)!=1 or
            {m.get('key'):m.get('value') for m in normal[0].findall('metadata')}.get('zaa_enabled')!='0'):
        raise WaveError('WALL_NATIVE: o Orca não preservou os limites das áreas selecionadas.')
    for i,part in enumerate(parts,1):
        values={m.get('key'):m.get('value') for m in part.findall('metadata')}
        if values.get('zaa_enabled')!='1' or values.get('name')!=f'Surface Studio area {i}':
            raise WaveError('WALL_NATIVE: a ativação seletiva foi alterada pelo fatiador.')
        if not isinstance(expected,int):
            for key,wanted in expected[i-1]['config'].items():
                if values.get(key)!=wanted:
                    raise WaveError('WALL_NATIVE: o fatiador alterou '+key+' na área selecionada.')
