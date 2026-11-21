"""Prepare the authorized PLA coupon for offline review; no transport or release.

The resulting candidate keeps the engine's PRINT DISABLED marker. A separate
head/deposition assessment must approve the exact payload before any transport.
"""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import copy
from dataclasses import replace
from zipfile import ZipFile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from orca_wave_studio.roof_fixtures import roof_coupon
from orca_wave_studio.regional_shell import RegionalShellWarp
from orca_wave_studio.project_io import write_model_project
from orca_wave_studio.conformal import process_conformal_gcode
from orca_wave_studio.roof_audit import audit_regional_roof
from orca_wave_studio.package import build_sliced_package, extract_plate_gcode
from orca_wave_studio.contracts import digest
from orca_wave_studio.paired_support import with_paired_support_gap
from orca_wave_studio.trial_travels import lift_trial_travels
from orca_wave_studio.engine_parser import read
from run_roof_baselines import startup_info, save


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gap', type=float, default=.6)
    parser.add_argument('--layer', type=float, default=.2)
    parser.add_argument('--physical-support-gap', type=float, default=.35)
    parser.add_argument('--base-layer', type=float)
    parser.add_argument('--line-width', type=float)
    parser.add_argument('--support-xy-gap', type=float, default=.35)
    parser.add_argument('--lift-travels', action='store_true')
    parser.add_argument('--rotate-180', action='store_true')
    args = parser.parse_args()
    root = ROOT / 'study/evidence/physical-preflight'
    folder = root / f'candidate-gap{args.gap:.2f}-layer{args.layer:.2f}'
    if args.base_layer is not None:
        folder = root / f'candidate-gap{args.gap:.2f}-layer{args.layer:.2f}-base{args.base_layer:.2f}'
    if args.line_width is not None:
        folder = folder.with_name(folder.name + f'-w{args.line_width:.2f}-xy{args.support_xy_gap:.2f}')
    if args.rotate_180:
        folder = folder.with_name(folder.name + '-r180')
    folder.mkdir(exist_ok=True)
    isolated = ROOT / '.research/sv06-physical-preflight/native-profile'
    source = ROOT / '.research/sv06-physical-preflight/resolved-native-settings.json'
    settings = json.loads(source.read_bytes())
    assert settings['printer_settings_id'] == 'Sovol SV06 0.4 nozzle -3DPrinter'
    assert settings['filament_settings_id'] == ['Sovol Generic PLA - Voolt3D']
    assert settings['filament_type'] == ['PLA']
    assert settings['nozzle_temperature'][0] == '195'
    assert settings['nozzle_temperature_initial_layer'][0] == '200'
    assert settings['hot_plate_temp_initial_layer'] == ['65']
    assert settings['filament_flow_ratio'][0] == '0.97'
    # Preserve the user's startup, correcting its out-of-range XY index only
    # in this isolated job. Persistent presets are never written by this tool.
    original_start = settings['machine_start_gcode']
    settings['machine_start_gcode'] = original_start.replace('first_layer_print_min[5]', 'first_layer_print_min[1]')
    original_end = settings['machine_end_gcode']
    settings['machine_end_gcode'] = '; Machine end appended after regional transform\n'
    base_layer = args.base_layer if args.base_layer is not None else args.layer
    settings.update({'layer_height': str(base_layer), 'initial_layer_print_height': str(base_layer),
                     'wall_loops': '3', 'top_shell_layers': '4', 'bottom_shell_layers': '4',
                     'sparse_infill_density': '15%', 'enable_support': '1',
                     'support_type': 'normal(auto)', 'support_style': 'grid',
                     'support_threshold_angle': '40', 'support_on_build_plate_only': '0',
                     'support_top_z_distance': str(args.gap), 'support_bottom_z_distance': '.2',
                     'support_object_xy_distance': str(args.support_xy_gap), 'support_interface_top_layers': '3',
                     'support_interface_bottom_layers': '3', 'support_interface_spacing': '.2',
                     'support_critical_regions_only': '0', 'gcode_label_objects': '1',
                     'belt_printer': '0', 'spiral_mode': '0', 'enable_arc_fitting': 'disabled',
                     'zaa_enabled': '0', 'post_process': [], 'slicing_pipeline_plugin': [],
                     'printer_agent': '', 'print_host': '', 'printhost_apikey': '',
                     'raft_layers': '0', 'brim_width': '0', 'enable_prime_tower': '0',
                     'seam_gap': '0%', 'detect_narrow_internal_solid_infill': '0',
                     'wipe': ['0'], 'filament_wipe': ['0'], 'use_firmware_retraction': '0'})
    if args.line_width is not None:
        if not .35 <= args.line_width <= .45:
            raise ValueError('Trial line width outside the planned 0.4 mm nozzle range.')
        for key in ['line_width', 'outer_wall_line_width', 'inner_wall_line_width', 'sparse_infill_line_width',
                    'internal_solid_infill_line_width', 'top_surface_line_width', 'support_line_width']:
            settings[key] = str(args.line_width)
        settings['wall_generator'] = 'classic'
    for key in ['outer_wall_speed', 'inner_wall_speed', 'sparse_infill_speed',
                'internal_solid_infill_speed', 'top_surface_speed', 'support_speed',
                'support_interface_speed', 'initial_layer_speed', 'initial_layer_infill_speed']:
        settings[key] = ['20'] if isinstance(settings.get(key), list) else '20'
    settings['travel_speed'] = '60'
    settings['default_acceleration'] = ['500'] if isinstance(settings.get('default_acceleration'), list) else '500'
    settings['print_settings_id'] = f'OWS isolated 25 degree PLA {args.layer:.2f}'
    settings['print_compatible_printers'] = [settings['printer_settings_id'], 'Sovol SV06 0.4 nozzle']
    # This is a complete independent snapshot, not a parent-relative preset.
    # Clear inherited override tracking only in the isolated project copy.
    settings['inherits_group'] = ['', '', '']
    settings['different_settings_to_system'] = ['', '', '']
    snapshot, truth = roof_coupon(25)
    if args.rotate_180:
        snapshot=copy.deepcopy(snapshot)
        for obj in snapshot.objects:
            for instance in obj['instances_data']:
                old=copy.deepcopy(instance['matrix'])
                for axis in (0,1):
                    instance['matrix'][axis]=[-v for v in old[axis]]
                    instance['matrix'][axis][3]+=220.
        truth=copy.deepcopy(truth)
        for key in ['top_plane_world','bottom_plane_world']:
            a,b,c=truth['roof'][key]
            truth['roof'][key]=[-a,-b,c+220*(a+b)]
        low,high=truth['roof']['free_span_bounds_xy_world_mm']
        truth['roof']['free_span_bounds_xy_world_mm']=[[220-high[0],220-high[1]],[220-low[0],220-low[1]]]
        truth.pop('local_to_world_translation_mm',None)
        truth['local_to_world_matrix']=snapshot.objects[0]['instances_data'][0]['matrix']
        truth['rotation_z_deg']=180.
    snapshot=replace(snapshot,settings={'layer_height':str(base_layer),'nozzle_diameter':'0.4',
        'filament_type':'PLA','gcode_flavor':settings['gcode_flavor'],'gcode_label_objects':'1'})
    save(folder / 'project-snapshot.json',snapshot.to_dict())
    save(folder / 'fixture-truth.json',truth)
    warp = RegionalShellWarp(snapshot, '1', settings={'retain_native_short_edges': True,
                             'nominal_layer_height_mm': args.layer,
                             'align_layer_grid_to_anchor': args.base_layer is not None}, region=truth['roof'])
    save(folder / 'settings.json', settings)
    save(folder / 'warp-summary.json', warp.summary)
    flat = folder / 'flattened.3mf'
    write_model_project(warp.flattened_snapshot, flat, settings)
    if args.base_layer is not None:
        if abs(warp.anchor_z/base_layer - round(warp.anchor_z/base_layer)) > 1e-8:
            raise ValueError('The fixed base must end on an exact base-layer boundary.')
        objects = ET.Element('objects')
        item = ET.SubElement(objects, 'object', id='1')
        interval = ET.SubElement(item, 'range', min_z=str(warp.anchor_z), max_z=str(warp.flat_top_z))
        ET.SubElement(interval, 'option', opt_key='layer_height').text = str(args.layer)
        with ZipFile(flat, 'a') as archive:
            archive.writestr('Metadata/layer_config_ranges.xml', ET.tostring(objects, encoding='utf8', xml_declaration=True))
    native = folder / 'native'
    native.mkdir(exist_ok=True)
    command = [r'C:\Program Files\OrcaSlicer\orca-slicer.exe', '--datadir', str(isolated),
               str(flat), '--slice', '0', '--outputdir', str(native), '--export-3mf', 'native.gcode.3mf']
    completed = subprocess.run(command, cwd=native, capture_output=True, timeout=120,
                               startupinfo=startup_info(), env={**os.environ, 'TEMP': str(isolated), 'TMP': str(isolated)})
    (folder / 'native-output.txt').write_bytes(completed.stdout + b'\n' + completed.stderr)
    if completed.returncode:
        raise RuntimeError('Native slice failed; see native-output.txt')
    with ZipFile(native / 'native.gcode.3mf') as archive:
        effective = json.loads(archive.read('Metadata/project_settings.config'))
    for key in ['layer_height', 'initial_layer_print_height', 'enable_support', 'gcode_label_objects',
                'support_top_z_distance', 'filament_type', 'filament_flow_ratio',
                'nozzle_temperature', 'nozzle_temperature_initial_layer', 'machine_start_gcode']:
        if effective.get(key) != settings.get(key):
            raise RuntimeError(f'Native preset restored or changed requested setting: {key}')
    native_source = (native / 'plate_1.gcode').read_bytes()
    warp = with_paired_support_gap(warp, native_source, {0: '1'}, '1', vertical_gap_mm=args.physical_support_gap)
    save(folder / 'warp-summary.json', warp.summary)
    result = process_conformal_gcode(native_source, warp, {0: '1'}, '1')
    body = result.gcode
    if args.lift_travels:
        body, travel_report = lift_trial_travels(body, {0: '1'}, anchor_z_mm=warp.anchor_z,
            clearance_mm=3., maximum_z_mm=float(settings['printable_height']), z_speed_mm_s=5.)
        save(folder / 'travel-report.json', travel_report)
        # Native progress commands predate the inserted lifts. Retain feature
        # metadata but avoid publishing their stale remaining-time claims.
        body=b''.join(line for line in body.splitlines(keepends=True) if not line.lstrip().startswith(b'M73 '))
    else:
        travel_report = None
    if args.lift_travels:
        printed=read(body,set(),{0:'1'})
        peak=max(max(m.start[2],m.end[2]) for m in printed.moves.values() if m.deposits and None not in m.start+m.end)
        shutdown=(f'\n; Explicit isolated trial shutdown\nM400\nG90\nM83\nG1 Z{peak+3:.6f} F300\n'
                  'M104 S0\nM140 S0\nM107\nG1 X10 Y200 F3000\nM400\nM84 X Y E\n').encode('ascii')
    else:
        shutdown=b'\n; Isolated user-profile shutdown follows\n'+original_end.encode('latin1')+b'\n'
    proposed = body+shutdown
    held = folder / 'HOLD-coupon25-SV06-Voolt3D.gcode'
    held.write_bytes(proposed)
    # Geometry audit omits the restored shutdown, which includes G91/G27 and
    # is outside the engine parser's strict planar benchmark dialect.
    audit = audit_regional_roof(body, warp, {0: '1'}, '1', sample_pitch_mm=.05, support_gap_mm=args.physical_support_gap)
    save(folder / 'assessment.json', audit)
    save(folder / 'processing-report.json', result.report)
    package = folder / 'HOLD-coupon25-SV06-Voolt3D.gcode.3mf'
    build_sliced_package(proposed, package, project_3mf=native/'native.gcode.3mf', plate_index=0,
                         metadata={'bench_only': True, 'print_allowed': False, 'physical_candidate_held': True})
    assert extract_plate_gcode(package, 0) == proposed
    report = {'status': 'HELD_PENDING_HEAD_AND_DEPOSITION_REVIEW', 'print_allowed': False,
              'printer_contacted': False, 'user_presets_modified': False,
              'profile_source_sha256': digest(source.read_bytes()), 'gcode_sha256': digest(proposed),
              'engine_body_sha256': result.sha256, 'audited_body_sha256': digest(body), 'native_gap_mm': args.gap,
              'travel_report': travel_report,
              'independent_support': warp.summary['independent_support_field'],
              'layer_height_mm': args.layer, 'startup_xy_index_5_corrected_to_1_in_job_only': original_start != settings['machine_start_gcode'],
              'base_layer_height_mm': base_layer, 'proxy_layer_ranges_used': args.base_layer is not None,
              'rotation_z_deg':180 if args.rotate_180 else 0,'explicit_shutdown':args.lift_travels,
              'temperatures_c': {'first_layer': 200, 'subsequent_layers': 195, 'bed': 65},
              'gcode_path': str(held), 'package_path': str(package), 'support': audit['support'],
              'head_clearance': 'NOT_APPROVED', 'physical_validation': False}
    (folder / 'regional-body-for-audit.gcode').write_bytes(body)
    save(folder / 'candidate.json', report)
    print(json.dumps({k: report[k] for k in ['status','gcode_path','gcode_sha256','support']}, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
