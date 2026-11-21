"""Offline support-gap trials for the 25-degree coupon; never transports jobs."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from orca_wave_studio.roof_fixtures import roof_coupon
from orca_wave_studio.regional_shell import RegionalShellWarp
from orca_wave_studio.project_io import write_model_project
from orca_wave_studio.conformal import process_conformal_gcode
from orca_wave_studio.roof_audit import audit_regional_roof
from orca_wave_studio.contracts import digest
from run_roof_baselines import private_settings, startup_info, save


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gaps', type=float, nargs='+', default=[.4, .6])
    args = parser.parse_args()
    output = ROOT / 'study/evidence/physical-preflight/support-trials'
    output.mkdir(parents=True, exist_ok=True)
    isolated = ROOT / '.research/sv06-physical-preflight/native-profile'
    snapshot, truth = roof_coupon(25)
    warp = RegionalShellWarp(snapshot, '1', settings={'retain_native_short_edges': True}, region=truth['roof'])
    template = json.loads((ROOT / 'study/fixtures/sovol-bench-settings.json').read_bytes())
    index = []
    for gap in args.gaps:
        folder = output / f'gap-{gap:.2f}'
        folder.mkdir(exist_ok=True)
        settings = private_settings(template, zaa_mode='off')
        settings.update({'support_top_z_distance': str(gap), 'filament_type': ['PLA'],
                         'filament_density': ['1.24'], 'filament_flow_ratio': ['0.97'],
                         'filament_settings_id': ['OWS cold Voolt3D diagnostic; NOT PRINTABLE']})
        save(folder / 'diagnostic-settings.json', settings)
        flat = folder / 'flattened.3mf'
        write_model_project(warp.flattened_snapshot, flat, settings)
        command = [r'C:\Program Files\OrcaSlicer\orca-slicer.exe', '--datadir', str(isolated),
                   str(flat), '--slice', '0', '--outputdir', str(folder), '--export-3mf', 'native.gcode.3mf']
        completed = subprocess.run(command, cwd=folder, capture_output=True, timeout=120,
                                   startupinfo=startup_info(), env={**os.environ, 'TEMP': str(isolated), 'TMP': str(isolated)})
        (folder / 'native-output.txt').write_bytes(completed.stdout + b'\n' + completed.stderr)
        if completed.returncode:
            raise RuntimeError(f'Native slice failed at gap {gap}; see native-output.txt')
        source = (folder / 'plate_1.gcode').read_bytes()
        result = process_conformal_gcode(source, warp, {0: '1'}, '1')
        final = folder / 'regional-COLD-NOT-PRINTABLE.gcode'
        final.write_bytes(result.gcode)
        audit = audit_regional_roof(result.gcode, warp, {0: '1'}, '1')
        save(folder / 'assessment.json', audit)
        row = {'native_gap_mm': gap, 'gcode_path': str(final), 'sha256': digest(result.gcode),
               'audit': audit, 'print_allowed': False, 'real_printer_contacted': False}
        index.append(row)
        save(output / 'index.json', index)
        print(json.dumps({'gap_mm': gap, 'audit': audit}, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    main()
