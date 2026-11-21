"""Check observed native lines against immutable files, without controlling UI."""
from datetime import datetime,timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from orca_wave_studio.capture import atomic_write
from orca_wave_studio.contracts import digest
from orca_wave_studio.engine_parser import read
from orca_wave_studio.package import extract_plate_gcode

folder=ROOT/'study/evidence/roof-study'
evidence=folder/'native-preview'
load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
observations=load(evidence/'observations.json')
manifest=load(folder/'preview-comparison/manifest.json')
packages={r['name']:r for r in manifest['jobs']}
parsed={};samples=[];checks=[]
for row in observations['observations']:
    if 'image' in row:
        image=evidence/row['image']
        checks.append(image.is_file())
    if 'line' not in row:continue
    case=row['case'];item=packages[case]
    if case not in parsed:
        gcode=extract_plate_gcode(Path(item['path']),0)
        checks.append(digest(gcode)==item['gcode_sha256'])
        parsed[case]=read(gcode,set(),{0:'1'})
    move=parsed[case].moves.get(row['line']-1)
    flags={'line_is_deposition':bool(move and move.deposits),
        'logical_layer_matches':bool(move and move.layer+1==row['native_layer']),
        'z_matches_file':bool(move and abs(move.end[2]-row['command_z_mm'])<=1e-6),
        'e_matches_file':bool(move and abs(move.de-row['command_e_mm'])<=1e-7),
        'role_matches_file':bool(move and move.role==row['role'].lower())}
    if 'marker_z_mm' in row:
        flags['marker_matches_rounded_z']=abs(row['marker_z_mm']-row['command_z_mm'])<=.00051
    checks.extend(flags.values())
    samples.append({**row,'checks':flags})

# A native model export can regenerate timestamp, thumbnails and preset comments.
# Keep the whole-file mismatch, even if every executable command is identical.
baseline=packages['20-planar']
original=extract_plate_gcode(Path(baseline['path']),0)
exported=(evidence/'20-planar-export.gcode').read_bytes()
def commands(data):
    return [s.split(';',1)[0].strip() for s in data.decode('latin1').splitlines()
            if s.split(';',1)[0].strip()]
export_check={'source_sha256':digest(original),'native_export_sha256':digest(exported),
    'full_bytes_equal':original==exported,'executable_commands_equal':commands(original)==commands(exported),
    'source_command_count':len(commands(original)),'export_command_count':len(commands(exported)),
    'interpretation':'Whole-file equality failed; timestamp, thumbnails and configuration comments changed. No integrity approval is substituted by command equality.'}
report={'status':'PASS_VISUAL_SAMPLES_WITH_INTEGRITY_LIMIT' if all(checks) else 'ISSUES_OBSERVATION_MISMATCH',
    'checked_at_utc':datetime.now(timezone.utc).isoformat(),'all_observed_lines_match_source':all(checks),
    'samples_checked':len(samples),'comparison_cases':observations['comparison_cases'],
    'plugin_version_observed':observations['plugin_version_observed'],
    'plugin_activation':observations['plugin_activation'],'samples':samples,
    'baseline_native_export':export_check,
    'regional_native_byte_roundtrip':'NOT_VERIFIED_EXPORT_BUTTON_NO_DIALOG',
    'native_capture_pipeline_exercised_this_run':False,
    'native_preview_geometry_status':'OBSERVED_TOP_AND_UNDERSIDE_Z_VARIATION',
    'native_preview_full_integrity_approval':False,'native_print_status':'NOT_RUN',
    'physical_validation':False,'print_allowed':False,'digital_surface_approval':False,
    'head_clearance_status':'UNKNOWN','final_case':observations['final_case'],
    'final_layer':observations['final_layer'],'final_step':observations['final_step'],
    'images':{p.name:digest(p.read_bytes()) for p in sorted(evidence.glob('*.png'))},
    'observations_sha256':digest((evidence/'observations.json').read_bytes())}
atomic_write(evidence/'native-preview-audit.json',json.dumps(report,ensure_ascii=False,indent=2).encode())
print(json.dumps({k:v for k,v in report.items() if k not in {'samples','images'}},ensure_ascii=False,indent=2))
sys.exit(0 if all(checks) else 1)
