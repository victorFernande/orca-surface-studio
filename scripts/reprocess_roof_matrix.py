"""Regenerate regional artifacts from immutable native slices, without Orca CLI."""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from orca_wave_studio.capture import atomic_write
from orca_wave_studio.conformal import process_conformal_gcode
from orca_wave_studio.contracts import WaveError,digest
from orca_wave_studio.package import build_sliced_package,extract_plate_gcode
from orca_wave_studio.regional_shell import RegionalShellWarp
from orca_wave_studio.roof_audit import audit_regional_roof
from audit_roof_matrix import read_snapshot
from run_roof_baselines import save


def run(args):
    index_path=args.index.resolve();regional_root=index_path.parent
    previous_bytes=index_path.read_bytes();previous=json.loads(previous_bytes)
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-corrected-'+uuid4().hex[:8]
    history=regional_root/f'previous-index-{run_id}.json'
    atomic_write(history,previous_bytes)
    result={**{k:v for k,v in previous.items() if k not in {'jobs','run_id'}},
        'status':'ISSUES','run_id':run_id,'jobs':[],
        'source_run_id':previous.get('run_id'),'source_index_sha256':digest(previous_bytes),
        'previous_index_path':str(history),'native_slicing_performed':False,
        'digital_approval':False,'assessment_kind':'SAMPLED_NOT_CERTIFIED',
        'reprocessing_reason':'Emit mapped XYZ on retained native short edges even when extrusion and feed are unchanged.',
        'conformal_implementation_sha256':digest((ROOT/'src/orca_wave_studio/conformal.py').read_bytes()),
        'regional_implementation_sha256':digest((ROOT/'src/orca_wave_studio/regional_shell.py').read_bytes())}
    for prior in previous['jobs']:
        angle=prior['angle_deg'];case=regional_root/f'{angle:02d}';folder=case/run_id
        folder.mkdir()
        row={k:v for k,v in prior.items() if k not in {
            'digital_audit','gcode_path','package_path','gcode_sha256','package_sha256','report_path'}}
        row.update(folder=str(folder),status='ISSUES',generation_status='NOT_GENERATED',
            previous_result_folder=prior['folder'],digital_approval=False,
            native_slicing_performed=False,assessment_kind='SAMPLED_NOT_CERTIFIED')
        preserved={}
        try:
            snapshot_path=case/'project-snapshot.json';truth_path=case/'fixture-truth.json'
            native_gcode=Path(prior['native_gcode_path']);native_package=Path(prior['native_package_path'])
            for path in (snapshot_path,truth_path,native_gcode,native_package):
                preserved[path]=digest(path.read_bytes())
            if preserved[native_gcode]!=prior['native_gcode_sha256']:
                raise WaveError('NATIVE_GCODE_HASH_MISMATCH')
            if digest(extract_plate_gcode(native_package,0))!=preserved[native_gcode]:
                raise WaveError('NATIVE_PACKAGE_PAYLOAD_MISMATCH')
            snapshot=read_snapshot(snapshot_path)
            if snapshot.revision!=prior['original_snapshot_revision']:
                raise WaveError('SOURCE_INDEX_REVISION_MISMATCH')
            truth=json.loads(truth_path.read_text(encoding='utf-8'))
            selected=str(prior['original_object_id'])
            warp=RegionalShellWarp(snapshot,selected,
                settings={'retain_native_short_edges':True},region=truth['roof'])
            transformed=process_conformal_gcode(native_gcode.read_bytes(),warp,{0:selected},selected)
            final=folder/f'regional-{angle:02d}.gcode';package=folder/f'regional-{angle:02d}.gcode.3mf'
            atomic_write(final,transformed.gcode)
            info=build_sliced_package(transformed.gcode,package,project_3mf=native_package,
                plate_index=0,metadata={'bench_only':True,'print_allowed':False,
                'study_kind':'regional_paired_shell','source_run_id':previous.get('run_id')})
            if digest(extract_plate_gcode(package,0))!=transformed.sha256:
                raise WaveError('GENERATED_PACKAGE_PAYLOAD_MISMATCH')
            audit=audit_regional_roof(transformed.gcode,warp,{0:selected},selected)
            report={**transformed.report,'warp':warp.summary,'fixture_truth':truth,'package':info,
                'digital_audit':audit,'digital_approval':False,'physical_validation':False,
                'physical_gate':'UNKNOWN','print_allowed':False,'assessment_kind':'SAMPLED_NOT_CERTIFIED',
                'support_ownership':prior['support_ownership'],
                'support_mapping_status':prior['support_mapping_status'],
                'support_gap_validated':False,'material_deposition_validated':False,
                'collision_order_validated':False,'native_preview_validated':False,
                'native_slicing_performed':False,'previous_result_folder':prior['folder'],
                'coverage_pending':True}
            save(folder/'warp-summary.json',warp.summary)
            save(folder/'flattened-snapshot.json',warp.flattened_snapshot.to_dict())
            save(folder/'conformal-report.json',report)
            row.update(generation_status='GENERATED_FOR_DIGITAL_AUDIT',digital_audit=audit,
                reason='Amostragem não certifica todas as regiões, deposição ou cabeçote.',
                gcode_path=str(final),package_path=str(package),gcode_sha256=transformed.sha256,
                package_sha256=digest(package.read_bytes()),report_path=str(folder/'conformal-report.json'),
                native_package_sha256=preserved[native_package])
        except Exception as exc:
            row.update(reason=str(exc))
        row['source_artifacts_preserved']=all(
            path.is_file() and digest(path.read_bytes())==sha for path,sha in preserved.items())
        if not row['source_artifacts_preserved']:
            row.update(status='ISSUES',reason='SOURCE_ARTIFACT_CHANGED_DURING_REPROCESSING')
        save(folder/'report.json',row);result['jobs'].append(row)
    result['all_regenerated']=all(row['generation_status']=='GENERATED_FOR_DIGITAL_AUDIT' for row in result['jobs'])
    save(index_path,result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index',type=Path,
        default=ROOT/'study/evidence/roof-study/regional/regional-index.json')
    result=run(parser.parse_args())
    print(json.dumps({'status':result['status'],'run_id':result['run_id'],
        'all_regenerated':result['all_regenerated'],
        'jobs':[{k:row.get(k) for k in ('angle_deg','generation_status','reason','gcode_sha256')}
                for row in result['jobs']]},ensure_ascii=False,indent=2))
    sys.exit(0 if result['all_regenerated'] else 1)
