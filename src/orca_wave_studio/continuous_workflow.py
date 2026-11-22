"""One planar native slice in surface coordinates, then one inverse mapping."""
from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import replace
from pathlib import Path

from .capture import atomic_write
from .spline_planning import prepare_spline_warp
from .conformal import process_conformal_gcode
from .contracts import WaveError,digest
from .geometry import transform_point
from .package import build_sliced_package,extract_plate_gcode
from .printer_profile import number
from .project_io import write_model_project
from .regional_shell import RegionalShellSettings
from .surface_finishing import verify_finishing_ranges,audit_finishing


def build_continuous(snapshot,object_id,backup,folder,executable,resolved,profile,slicer,workspace,cancelled,progress,options,verify):
    from .surface_workflow import _result
    if options.get('selection_mode','all')!='all' or options.get('wall_selection'):
        raise WaveError('LAYERS_SELECTION: o planejamento contínuo requer Peça inteira nesta versão.')
    slope=options.get('max_slope_deg',30)
    minimum=number(resolved,'min_layer_height',profile.nozzle_mm*.2)
    maximum=number(resolved,'max_layer_height',profile.nozzle_mm*.75)
    flat_height=min(profile.layer_mm,max(minimum,round(profile.layer_mm*.6,3)))
    if not minimum<=flat_height<=maximum:raise WaveError('LAYERS_PROFILE: confira os limites de camada do perfil selecionado.')
    settings=RegionalShellSettings(step_mm=options.get('step_mm',.4),max_slope_deg=slope,
        nominal_layer_height_mm=flat_height,tolerance_mm=.01,
        retain_native_short_edges=options.get('retain_native_short_edges',True))
    warp=prepare_spline_warp(snapshot,object_id,settings,profile,resolved,progress=progress,cancelled=cancelled,
                             cache_folder=folder.parent/'phase-cache')
    flat_height=getattr(warp,'nominal_slice_height_mm',flat_height)
    if not minimum<=flat_height<=maximum:raise WaveError('LAYERS_PROFILE: a altura planejada saiu dos limites do perfil.')
    settings=replace(settings,nominal_layer_height_mm=flat_height)
    # Split the 0.02 mm coordinate budget between the slicing-copy surface
    # certificate and the emitted inverse-mapped chords.
    mesh_error=float(warp.summary.get('mesh_normal_and_crease_error_budget_mm',.01))
    if not math.isfinite(mesh_error) or not 0<=mesh_error<=settings.tolerance_mm+1e-9:
        raise WaveError('LAYERS_SHAPE: a cópia ultrapassa seu orçamento de erro geométrico.')
    if cancelled():raise WaveError('Geração cancelada.')
    native_settings={**resolved,'zaa_enabled':'0'}
    plan={'nominal_layer_mm':profile.layer_mm,'finishing_layer_mm':flat_height,
        'profile_minimum_layer_mm':minimum,'profile_maximum_layer_mm':maximum,
        'first_layer_mm':profile.initial_layer_mm,
        'sampling_reduction_percent':100*(1-flat_height/profile.layer_mm),
        'source_mesh_unchanged':True,'xyz_e_rewritten':True,
        'scope':'continuous surface coordinates on the copied solid; physical output restored once'}
    model=folder/'prepared.3mf'
    warp.settings=replace(settings,tolerance_mm=max(.001,.02-mesh_error-1e-7))
    spacing_runs=[];spacing_enabled=getattr(warp,'spacing_enabled',False)
    for attempt in range(3):
        if cancelled():raise WaveError('Geração cancelada.')
        atomic_write(folder/'surface-coordinates.json',json.dumps(warp.summary,ensure_ascii=False).encode())
        flat=copy.deepcopy(warp.flattened_snapshot)
        for obj in flat.objects:
            obj.setdefault('config',{})['zaa_enabled']='0'
            for volume in obj['volumes']:volume.setdefault('config',{})['zaa_enabled']='0'
        maximum_z=max(transform_point(p,i['matrix'],v['matrix'])[2]
                      for o in flat.objects for i in o['instances_data'] if i.get('printable',True)
                      for v in o['volumes'] for p in v['vertices'])
        plan['ranges']=[{'min_z':profile.initial_layer_mm,'max_z':maximum_z,'layer_height':flat_height}]
        write_model_project(flat,model,native_settings,layer_ranges=plan['ranges'])
        progress('Fatiando camadas contínuas nas coordenadas das superfícies…')
        source,package=slicer(executable,model,folder/('slice' if not attempt else f'slice-spacing-{attempt}'),cancelled,workspace=workspace)
        receipt=verify(package,native_settings,extra_fields=('zaa_enabled',));ranges=verify_finishing_ranges(package,plan)
        data=source.read_bytes()
        labels={int(m) for m in re.findall(rb'(?mi)^;\s*printing object\s+.*?\bid:(\d+)\s+copy\s+0\s*$',data)}
        if len(labels)!=1:raise WaveError('LAYERS_LABELS: a fatia precisa identificar uma única peça.')
        mapping={next(iter(labels)):str(object_id)}
        if not spacing_enabled:break
        from .spacing_plan import plan_spacing
        progress('Conferindo a altura efetiva dos cordões e o material necessário…')
        grid,spacing=plan_spacing(data,warp,mapping,str(object_id),maximum,profile.initial_layer_mm,profile.height_mm)
        spacing_runs.append(spacing)
        if not spacing['extra_slice_intervals']:break
        if warp.summary.get('partial_adaptation'):
            raise WaveError('BEAD_ADAPTATION: reduza a adaptação para respeitar a altura máxima dos cordões.')
        if attempt==2:raise WaveError('BEAD_ITERATIONS: o espaçamento ainda exige outra distribuição; o resultado foi recusado.')
        warp.regrid_spacing(grid,spacing,progress=progress,cancelled=cancelled,initial_layer_mm=profile.initial_layer_mm)
    finite_beads=getattr(warp,'finite_beads',spacing_enabled)
    enforce_height_limits=warp.summary.get('enforce_height_limits',warp.summary.get('partial_adaptation'))
    if finite_beads:
        warp.deposition_model={'model':'logical_pitch_finite_bead_v1','profile_minimum_mm':minimum,'profile_maximum_mm':maximum,
                               'reject_below_profile_minimum':bool(enforce_height_limits)}
    progress('Restaurando o formato, a extrusão e as transições em XYZ…')
    result=process_conformal_gcode(data,warp,mapping,str(object_id),printer_profile=profile,progress=progress,cancelled=cancelled)
    if enforce_height_limits:
        beads=result.report.get('bead_deposition',{})
        if not beads or beads['below_profile_minimum_occurrences'] or beads['above_profile_maximum_occurrences']:
            raise WaveError('BEAD_ADAPTATION: o cordão efetivo saiu dos limites do perfil; o resultado foi recusado.')
    if not sum(result.report['nonplanar_extrusion_segments_by_role'].values()):
        raise WaveError('LAYERS_NO_EFFECT: a fatia não confirmou camadas com movimento contínuo em Z.')
    audit=audit_finishing(result.gcode,mapping,plan,slope)
    if cancelled():raise WaveError('Geração cancelada.')
    report={**result.report,'study_type':'continuous_surface_layers','warp':warp.summary,
        'coordinate_error_budget_mm':{'total':.02,'mesh':mesh_error,'path_chords':warp.settings.tolerance_mm},
        'workflow':'integrated','profile_preview_only':False,'profile_preserved':True,
        'original_revision':snapshot.revision,'original_backup_sha256':digest(Path(backup).read_bytes()),
        'native_transport_preserved':True,'effective_profile_verification':receipt,
        'native_contouring_disabled':True,'wall_selection':{'mode':'all','areas':[],'wall_speed_factor':1},
        'finishing':{**plan,'native_verification':ranges,'path_audit':audit},
        'motion_slope_review':{'limit_deg':slope,'maximum_deg':audit['maximum_motion_slope_deg'],
                               'within_study_limit':True,'head_clearance_certified':False},
        'physical_gate':'CONTINUOUS_LAYERS_HEAD_AND_DEPOSITION_VALIDATION_REQUIRED',
        'physical_validation':False,'print_allowed':False,'printer_contacted':False}
    if spacing_enabled:report['deposition_planning']={'passes':spacing_runs,'complete_cell_upper_bound_checked':True,
        'minimum_height_and_physical_bonding_qualified':False,
        'minimum_height_checked':bool(warp.summary.get('partial_adaptation')),
        'physical_bonding_qualified':False}
    report['local_nonplanar_layers']={k:v['up']+v['down'] if isinstance(v,dict) else v
                                     for k,v in report.get('nonplanar_extrusion_layers',{}).items()}
    output=folder/'surface.gcode';native=folder/'surface.gcode.3mf'
    atomic_write(output,result.gcode)
    build_sliced_package(result.gcode,native,project_3mf=package,plate_index=0,
                         metadata={'study_kind':'continuous_surface_layers','print_allowed':False})
    if extract_plate_gcode(native,0)!=result.gcode:raise WaveError('LAYERS_PACKAGE: conteúdo alterado no pacote final.')
    return _result(snapshot,object_id,folder,options,report,output,native,'continuous_layers')
