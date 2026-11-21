"""Prepare short, hash-checked comparison paths without opening any window."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from orca_wave_studio.capture import atomic_write
from orca_wave_studio.contracts import digest
from orca_wave_studio.package import extract_plate_gcode

folder=ROOT/'study/evidence/roof-study'
load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
baseline=load(folder/'baselines/baseline-index.json')
regional=load(folder/'regional/regional-index.json')
output=folder/'preview-comparison';rows=[]
for angle in (20,25):
    case=f'coupon-{angle:02d}'
    for mode in ('off','on'):
        row=next(r for r in baseline['jobs'] if r['case']==case and r['zaa_mode']==mode)
        rows.append((f'{angle}-'+('planar' if mode=='off' else 'zaa-native'),
                     Path(row['native_package_path']),row['gcode_sha256']))
    row=next(r for r in regional['jobs'] if r['angle_deg']==angle)
    rows.append((f'{angle}-regional-INCOMPLETE',Path(row['package_path']),row['gcode_sha256']))
for mode in ('off','on'):
    row=next(r for r in baseline['jobs'] if r['case']=='benchy-original' and r['zaa_mode']==mode)
    rows.append(('benchy-'+('planar' if mode=='off' else 'zaa-native'),
                 Path(row['native_package_path']),row['gcode_sha256']))
manifest={'status':'PREPARED_NOT_OPENED','native_preview_validated':False,
    'print_allowed':False,'printer_contacted':False,'jobs':[]}
for name,source,expected in rows:
    target=output/(name+'.gcode.3mf');data=source.read_bytes()
    atomic_write(target,data)
    payload=digest(extract_plate_gcode(target,0))
    if payload!=expected:raise RuntimeError('Comparison payload differs from audited input.')
    manifest['jobs'].append({'name':name,'source':str(source),'path':str(target),
        'package_sha256':digest(data),'gcode_sha256':payload,'source_preserved':source.read_bytes()==data})
atomic_write(output/'manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2).encode())
print(json.dumps({'status':manifest['status'],'cases':len(manifest['jobs']),'manifest':str(output/'manifest.json')}))
