"""Digital paired-roof experiment using native slices, never printer transport."""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from orca_wave_studio.capture import atomic_write
from orca_wave_studio.conformal import process_conformal_gcode
from orca_wave_studio.contracts import WaveError,digest
from orca_wave_studio.engine_parser import read
from orca_wave_studio.package import build_sliced_package,extract_plate_gcode
from orca_wave_studio.project_io import write_model_project
from orca_wave_studio.regional_shell import RegionalShellWarp
from orca_wave_studio.roof_fixtures import ROOF_ANGLES,roof_coupon
from orca_wave_studio.roof_audit import audit_regional_roof
from run_roof_baselines import private_settings,startup_info,save,gcode_audit


def run(args):
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    source=args.profile.read_bytes();template=json.loads(source)
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8]
    isolated=output/'private-profile';isolated.mkdir(exist_ok=True)
    if not (isolated/'OrcaSlicer.conf').exists():save(isolated/'OrcaSlicer.conf',{
        'local_machines':{},'presets':{},'recent':{},'app':{'version':'2.5.1','single_instance':False,
            'installed_networking':False,'auto_check_updates':False,'use_printer_agents':False}})
    temporary=isolated/'tmp';temporary.mkdir(exist_ok=True)
    environment={**os.environ,'TEMP':str(temporary),'TMP':str(temporary)}
    summary={'status':'GENERATED_PENDING_AUDIT','run_id':run_id,'jobs':[],
        'source_profile_sha256':digest(source),'orca_executable':str(args.orca.resolve()),
        'orca_executable_sha256':digest(args.orca.read_bytes()),'expected_orca_version':'2.5.1',
        'coverage_pending':True,'physical_gate':'UNKNOWN','physical_validation':False,
        'print_allowed':False,'printer_contacted':False,'gui_opened':False,
        'native_short_edges':'explicit Preview exception approved; preserve original XY corners, no subdivision'}
    for angle in args.angles:
        case=output/f'{angle:02d}';case.mkdir(exist_ok=True)
        snapshot,truth=roof_coupon(angle);selected=str(snapshot.objects[0]['id'])
        save(case/'project-snapshot.json',snapshot.to_dict());save(case/'fixture-truth.json',truth)
        folder=case/run_id;folder.mkdir()
        row={'angle_deg':angle,'status':'ISSUES','generation_status':'NOT_GENERATED','folder':str(folder),
            'original_snapshot_revision':snapshot.revision,'original_object_id':selected,
            'coverage_pending':True,'print_allowed':False,'physical_gate':'UNKNOWN'}
        try:
            warp=RegionalShellWarp(snapshot,selected,settings={'retain_native_short_edges':True},region=truth['roof'])
            save(folder/'warp-summary.json',warp.summary)
            save(folder/'flattened-snapshot.json',warp.flattened_snapshot.to_dict())
            settings=private_settings(template,zaa_mode='off')
            settings['print_settings_id']='OWS Regional Roof PETG 0.20'
            save(folder/'settings.json',settings)
            original=folder/'original.3mf';flat=folder/'flattened.3mf'
            write_model_project(snapshot,original,settings);write_model_project(warp.flattened_snapshot,flat,settings)
            native=folder/'native-flat';native.mkdir()
            package=native/'native-flat.gcode.3mf';gcode=native/'plate_1.gcode'
            command=[str(args.orca),'--datadir',str(isolated),str(flat),'--slice','0',
                     '--outputdir',str(native),'--export-3mf',package.name]
            completed=subprocess.run(command,cwd=native,capture_output=True,timeout=120,
                startupinfo=startup_info(),env=environment)
            atomic_write(folder/'process-output.txt',completed.stdout+b'\n'+completed.stderr)
            row['native_exit_code']=completed.returncode
            if completed.returncode or not gcode.is_file() or not package.is_file():
                raise WaveError('Fatiamento nativo não gerou os dois artefatos esperados.')
            native_audit=gcode_audit(gcode.read_bytes(),package,'off',truth)
            row.update(native_audit=native_audit,native_gcode_sha256=digest(gcode.read_bytes()),
                       native_gcode_path=str(gcode),native_package_path=str(package),
                       flattened_model_sha256=digest(flat.read_bytes()),original_model_sha256=digest(original.read_bytes()))
            if not native_audit['all_checks_pass']:
                raise WaveError('Proxy nativo inválido: '+', '.join(k for k,v in native_audit['checks'].items() if not v))
            parsed=read(gcode.read_bytes(),set(),{0:selected})
            support_moves=[move for move in parsed.moves.values() if move.deposits and 'support' in move.role]
            support_owners=sorted({str(move.obj) for move in support_moves})
            support_status='SUPPORTED_OWNER_LABELS' if support_moves and all(move.obj==selected for move in support_moves) else 'UNASSOCIATED_SUPPORT_PATHS'
            ownership={'status':support_status,'source_support_deposition_moves':len(support_moves),
                'source_support_owner_ids':support_owners,
                'source_support_label_pairs':[list(pair) for pair in sorted({move.label for move in support_moves if move.label is not None})],
                'source_support_logical_layers':sorted({move.layer for move in support_moves}),
                'source_support_max_metadata_z_rounding_mm':max((max(abs(move.start[2]-move.z),abs(move.end[2]-move.z)) for move in support_moves if move.z is not None),default=0.),
                'support_gap_validated':False,'support_gap_status':'NOT_EVALUATED'}
            row['support_ownership']=ownership
            if support_status!='SUPPORTED_OWNER_LABELS':
                raise WaveError('Suporte sem associação inequívoca à única peça; transformação recusada.')
            result=process_conformal_gcode(gcode.read_bytes(),warp,{0:selected},selected)
            final=folder/f'regional-{angle:02d}.gcode';preview=folder/f'regional-{angle:02d}.gcode.3mf'
            atomic_write(final,result.gcode)
            info=build_sliced_package(result.gcode,preview,project_3mf=package,plate_index=0,
                metadata={'bench_only':True,'print_allowed':False,'study_kind':'regional_paired_shell'})
            if digest(extract_plate_gcode(preview,0))!=result.sha256:
                raise WaveError('O pacote de Preview alterou o G-code processado.')
            digital_audit=audit_regional_roof(result.gcode,warp,{0:selected},selected)
            report={**result.report,'warp':warp.summary,'fixture_truth':truth,'package':info,
                'digital_audit':digital_audit,'digital_approval':False,
                'assessment_kind':'SAMPLED_NOT_CERTIFIED',
                'support_mapping_status':support_status,'support_ownership':ownership,'support_gap_validated':False,
                'collision_order_validated':False,'material_deposition_validated':False,
                'physical_gate':'UNKNOWN','physical_validation':False,'print_allowed':False,
                'native_preview_validated':False,'coverage_pending':True}
            save(folder/'conformal-report.json',report)
            row.update(status='ISSUES',generation_status='GENERATED_FOR_DIGITAL_AUDIT',
                reason='Auditoria amostrada sem certificação de todas as regiões, deposição ou cabeçote.',
                digital_audit=digital_audit,digital_approval=False,
                assessment_kind='SAMPLED_NOT_CERTIFIED',
                support_mapping_status=support_status,gcode_path=str(final),package_path=str(preview),
                gcode_sha256=result.sha256,package_sha256=digest(preview.read_bytes()),
                report_path=str(folder/'conformal-report.json'))
        except subprocess.TimeoutExpired as exc:
            row.update(status='ISSUES',reason='Timeout nativo de 120 segundos.')
            atomic_write(folder/'process-output.txt',(exc.stdout or b'')+b'\n'+(exc.stderr or b''))
        except Exception as exc:
            row.update(status='ISSUES',reason=str(exc))
        save(folder/'report.json',row);summary['jobs'].append(row)
        save(output/'regional-index.json',summary)
    summary['original_profile_preserved']=args.profile.read_bytes()==source
    if not summary['original_profile_preserved'] or any(r['status']=='ISSUES' for r in summary['jobs']):summary['status']='ISSUES'
    save(output/'regional-index.json',summary)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'study/evidence/roof-study/regional')
    parser.add_argument('--profile',type=Path,default=ROOT/'study/fixtures/sovol-bench-settings.json')
    parser.add_argument('--orca',type=Path,default=Path(r'C:\Program Files\OrcaSlicer\orca-slicer.exe'))
    parser.add_argument('--angles',type=int,nargs='+',choices=ROOF_ANGLES,default=list(ROOF_ANGLES))
    args=parser.parse_args()
    try:
        result=run(args)
        print(json.dumps({'status':result['status'],'run_id':result['run_id'],'jobs':result['jobs']},ensure_ascii=False,indent=2))
        sys.exit(1 if result['status']=='ISSUES' else 0)
    except Exception as exc:
        print(json.dumps({'status':'ISSUES','reason':str(exc),'print_allowed':False}),file=sys.stderr);sys.exit(1)
