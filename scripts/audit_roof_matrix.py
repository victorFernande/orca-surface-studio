"""Audit persisted regional roof artifacts without slicing or printer access.

Sampling may produce a counterexample; it never certifies the entire deposited
surface or a real head envelope. Input G-code, packages and snapshots are read
only. Each assessment is kept beside its originating run.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from orca_wave_studio.contracts import ProjectSnapshot,WaveError,digest
from orca_wave_studio.package import extract_plate_gcode
from orca_wave_studio.regional_shell import RegionalShellWarp
from orca_wave_studio.roof_audit import audit_regional_roof
from run_benchy_probe import read_reference
from run_roof_baselines import save


def read_snapshot(path):
    data=json.loads(path.read_text(encoding='utf-8'))
    snapshot=ProjectSnapshot(data['session_id'],data['plate_index'],
                             tuple(data['objects']),data.get('settings',{}))
    if snapshot.revision!=data['revision']:
        raise WaveError('SNAPSHOT_REVISION_MISMATCH: '+str(path))
    return snapshot


def assess_case(source_row,regional_root):
    angle=source_row['angle_deg']
    case=regional_root/f'{angle:02d}'
    folder=Path(source_row['folder'])
    assessment={'angle_deg':angle,'status':'ISSUES','digital_approval':False,
        'assessment_kind':'SAMPLED_NOT_CERTIFIED','print_allowed':False,
        'physical_validation':False,'physical_gate':'UNKNOWN',
        'source_run_folder':str(folder),'generation_status':source_row.get('generation_status')}
    inputs={}
    try:
        snapshot_path=case/'project-snapshot.json'
        truth_path=case/'fixture-truth.json'
        gcode_path=Path(source_row['gcode_path'])
        package_path=Path(source_row['package_path'])
        for path in (snapshot_path,truth_path,gcode_path,package_path):
            inputs[path]=digest(path.read_bytes())
        snapshot=read_snapshot(snapshot_path)
        if snapshot.revision!=source_row['original_snapshot_revision']:
            raise WaveError('SOURCE_INDEX_REVISION_MISMATCH')
        truth=json.loads(truth_path.read_text(encoding='utf-8'))
        object_id=str(source_row['original_object_id'])
        warp=RegionalShellWarp(snapshot,object_id,
            settings={'retain_native_short_edges':True},region=truth['roof'])
        gcode=gcode_path.read_bytes()
        hashes={'gcode_sha256':digest(gcode),'package_sha256':digest(package_path.read_bytes()),
                'package_payload_sha256':digest(extract_plate_gcode(package_path,snapshot.plate_index))}
        checks={'gcode_matches_source_index':hashes['gcode_sha256']==source_row['gcode_sha256'],
                'package_matches_source_index':hashes['package_sha256']==source_row['package_sha256'],
                'package_payload_matches_gcode':hashes['package_payload_sha256']==hashes['gcode_sha256']}
        assessment.update(hashes=hashes,integrity_checks=checks,
            snapshot_revision=snapshot.revision,object_id=object_id,
            source_gcode_path=str(gcode_path),source_package_path=str(package_path))
        if not all(checks.values()):raise WaveError('SOURCE_ARTIFACT_HASH_MISMATCH')
        audit=audit_regional_roof(gcode,warp,{0:object_id},object_id)
        assessment.update(digital_audit=audit,audit_completed=True,
            reason='Amostragem não certifica todas as regiões nem a geometria real do material e cabeçote.')
    except Exception as exc:
        assessment.update(audit_completed=False,reason=str(exc))
    assessment['source_artifacts_preserved']=all(
        path.is_file() and digest(path.read_bytes())==sha for path,sha in inputs.items())
    if not assessment['source_artifacts_preserved']:
        assessment.update(audit_completed=False,reason='SOURCE_ARTIFACT_CHANGED_DURING_AUDIT')
    assessment_path=folder/'assessment.json'
    assessment['assessment_path']=str(assessment_path)
    save(assessment_path,assessment)
    return assessment


def assess_benchy(path):
    result={'status':'ISSUES','source':str(path.resolve()),'digital_approval':False,
        'print_allowed':False,'physical_validation':False,'scope':'unmodified original Benchy'}
    try:
        before=digest(path.read_bytes());snapshot=read_reference(path)
        result.update(source_sha256=before,snapshot_revision=snapshot.revision)
        selected=str(snapshot.objects[0]['id'])
        warp=RegionalShellWarp(snapshot,selected,settings={'retain_native_short_edges':True})
        result.update(regional_acceptance='ACCEPTED_WITHOUT_PATH_GENERATION',warp=warp.summary,
            reason='Aceitação geométrica não comprova cobertura; nenhum novo G-code foi gerado.')
    except Exception as exc:
        result.update(regional_acceptance='REFUSED',reason=str(exc))
    if path.is_file() and 'source_sha256' in result:
        result['source_preserved']=digest(path.read_bytes())==result['source_sha256']
    return result


def run(args):
    index_path=args.index.resolve();regional_root=index_path.parent
    source=index_path.read_bytes();index=json.loads(source)
    result={'status':'ISSUES','source_index':str(index_path),
        'source_index_sha256':digest(source),'source_run_id':index.get('run_id'),
        'assessed_at_utc':datetime.now(timezone.utc).isoformat(),
        'assessment_kind':'SAMPLED_NOT_CERTIFIED','digital_approval':False,
        'print_allowed':False,'physical_validation':False,'physical_gate':'UNKNOWN',
        'native_slicing_performed':False,'printer_contacted':False,'gui_opened':False,
        'jobs':[assess_case(row,regional_root) for row in index['jobs']],
        'benchy_original':assess_benchy(args.benchy)}
    result['source_index_preserved']=index_path.read_bytes()==source
    save(regional_root/'assessment-index.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index',type=Path,
        default=ROOT/'study/evidence/roof-study/regional/regional-index.json')
    parser.add_argument('--benchy',type=Path,
        default=ROOT/'study/evidence/benchy-roof/3DBenchy-original.3mf')
    args=parser.parse_args()
    result=run(args)
    rows=[]
    for row in result['jobs']:
        audit=row.get('digital_audit',{})
        rows.append({'angle_deg':row['angle_deg'],'audit_completed':row['audit_completed'],
            'faces':audit.get('faces'), 'support':audit.get('support'),
            'integrity_checks':row.get('integrity_checks'),'reason':row['reason']})
    print(json.dumps({'status':result['status'],'jobs':rows,
        'benchy_original':result['benchy_original']},ensure_ascii=False,indent=2))
    sys.exit(1 if any(not row['audit_completed'] for row in result['jobs']) else 0)
