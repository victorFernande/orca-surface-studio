"""Generate a cold-source, held coupon comparison; no printer connection."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from orca_wave_studio.inclined_coupon_trial import upper_proxy, render_held_trial, PITCH
from orca_wave_studio.project_io import write_model_project
from orca_wave_studio.package import build_sliced_package, extract_plate_gcode
from run_roof_baselines import save,startup_info


def main():
    root=ROOT/'study/evidence/physical-preflight'
    folder=root/'constant-pitch25-held'
    folder.mkdir(exist_ok=True)
    source=root/'candidate-gap0.60-layer0.30-base0.20-w0.40-xy1.00-r180'
    settings=json.loads((source/'settings.json').read_bytes())
    settings=copy.deepcopy(settings)
    settings.update({'layer_height':str(PITCH),'initial_layer_print_height':str(PITCH),
        # Virtual pitch differs from deposited normal spacing (.259 mm).
        # This source-only bound is not a change to the real printer profile.
        'max_layer_height':[str(PITCH)],
        'enable_support':'0','skirt_loops':'0','skirt_height':'0','skirt_distance':'0',
        'machine_start_gcode':'G90\nG21\nM83\nG92 E0', 'machine_end_gcode':'',
        'print_settings_id':'OWS constant pitch isolated source',
        'before_layer_change_gcode':'','layer_change_gcode':'G92 E0',
        'filament_start_gcode':[''],'filament_end_gcode':[''],
        'retraction_length':['0'],'filament_retraction_length':['0'],
        'retract_before_wipe':['0'],'retract_when_changing_layer':['0'],
        'filament_retract_when_changing_layer':['0'],'wipe':['0'],'filament_wipe':['0'],
        'use_relative_e_distances':'1'})
    settings.update({'bbl_use_printhost':'0','printhost_authorization_type':'key','printhost_ssl_ignore_revoke':'0'})
    for key,value in list(settings.items()):
        if key in {'nozzle_temperature','nozzle_temperature_initial_layer','chamber_temperature','idle_temperature'} or key.endswith('_plate_temp') or key.endswith('_plate_temp_initial_layer'):
            settings[key]=['0']*len(value) if isinstance(value,list) else '0'
    snapshot=upper_proxy()
    save(folder/'source-snapshot.json',snapshot.to_dict())
    save(folder/'source-settings.json',settings)
    model=folder/'source-upper.3mf'
    write_model_project(snapshot,model,settings)
    native=folder/'native'
    native.mkdir(exist_ok=True)
    isolated=ROOT/'.research/sv06-physical-preflight/native-profile'
    cmd=[r'C:\Program Files\OrcaSlicer\orca-slicer.exe','--debug','4','--datadir',str(isolated),
         str(model),'--slice','0','--outputdir',str(native),'--export-3mf','source.gcode.3mf']
    completed=subprocess.run(cmd,cwd=native,capture_output=True,timeout=120,startupinfo=startup_info(),
        env={**os.environ,'TEMP':str(isolated),'TMP':str(isolated)})
    (folder/'native-output.txt').write_bytes(completed.stdout+b'\n'+completed.stderr)
    if completed.returncode:
        raise RuntimeError(f'Native source slicing failed ({completed.returncode}); see native-output.txt')
    with ZipFile(native/'source.gcode.3mf') as archive:
        effective=json.loads(archive.read('Metadata/project_settings.config'))
    for key in ('layer_height','initial_layer_print_height','enable_support','gcode_label_objects','retraction_length','filament_retraction_length','machine_start_gcode'):
        a,b=settings[key],effective[key]
        same=(abs(float(a)-float(b))<1e-6 if key in {'layer_height','initial_layer_print_height'}
              else all(float(v)==0 for v in b) if key in {'retraction_length','filament_retraction_length'}
              else a==b)
        if not same:
            raise RuntimeError('Restored native setting: '+key)
    body,report=render_held_trial((source/'native/plate_1.gcode').read_bytes(),(native/'plate_1.gcode').read_bytes())
    gcode=folder/'HOLD-constant-pitch25-SV06.gcode'
    gcode.write_bytes(body)
    package=folder/'HOLD-constant-pitch25-SV06.gcode.3mf'
    build_sliced_package(body,package,project_3mf=source/'native/native.gcode.3mf',plate_index=0,
        metadata={'bench_only':True,'print_allowed':False,'constant_pitch_trial':True})
    assert extract_plate_gcode(package,0)==body
    report.update({'gcode_path':str(gcode),'package_path':str(package),
        'printer_contacted':False,'user_presets_modified':False,'installed_plugin_modified':False})
    save(folder/'assessment.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
