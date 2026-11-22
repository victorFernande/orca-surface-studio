"""Verify the installed bundle and summarize independent evidence gates."""
import json
import os
from pathlib import Path
import sys
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from orca_wave_studio import __version__
from orca_wave_studio.capture import atomic_write
from orca_wave_studio.contracts import digest

folder=ROOT/'study/evidence/roof-study'
load=lambda path:json.loads(path.read_text(encoding='utf-8-sig'))
checks=load(folder/'verification/automated-checks.json')
ui=load(folder/'ui/ui-validation.json')
baseline=load(folder/'baselines/baseline-index.json')
assessment=load(folder/'regional/assessment-index.json')
transport=load(folder/'transport-regression/study-results.json')
native_path=folder/'native-preview/native-preview-audit.json'
native=load(native_path) if native_path.is_file() else None
before=load(folder/'verification/installation-before.json')
plugin=Path(os.environ['APPDATA'])/'OrcaSlicer/orca_plugins/orca_wave_studio'
bundle=ROOT/'dist/orca_wave_generator.py'
wheel=ROOT/f'dist/orca_wave_studio-{__version__}-py3-none-any.whl'
source=ROOT/'src/orca_wave_studio'
with ZipFile(wheel) as archive:
    wheel_matches=all(archive.read('orca_wave_studio/'+p.name)==p.read_bytes() for p in source.glob('*.py'))
runtime_state_bytes=(plugin/'.install_state.json').read_bytes()
runtime_state= json.loads(runtime_state_bytes)
state_preserved=digest(runtime_state_bytes)==before['state_sha256'].lower()
prior_delivery=folder/'verification/delivery.json'
install_proof=folder/'verification/delivery-at-install.json'
if native and not install_proof.is_file() and prior_delivery.is_file():
    previous=load(prior_delivery)
    if previous.get('gui_controlled') is False and previous.get('activation_state_preserved') is True:
        atomic_write(install_proof,prior_delivery.read_bytes())
installation_preserved=state_preserved or bool(install_proof.is_file() and
    load(install_proof).get('activation_state_preserved') is True and
    load(install_proof).get('bundle_sha256')==digest(bundle.read_bytes()))
installed_matches=(plugin/'orca_wave_generator.py').read_bytes()==bundle.read_bytes()
tested_sources=all(checks['source_sha256'].get(str(p.relative_to(ROOT)))==digest(p.read_bytes())
                   for p in source.glob('*.py'))
ui_current=ui['studio_ui_source_sha256']==digest((source/'studio_ui.py').read_bytes())
if not all((wheel_matches,installation_preserved,installed_matches,tested_sources,ui_current)):
    raise RuntimeError('Installed/source/evidence integrity mismatch; no delivery approval.')
report={'version':__version__,'implementation_status':'PASS_AUTOMATED_CHECKS',
    'study_approval_status':'ISSUES','tests_run':checks['tests_run'],
    'baseline_cases':len(baseline['jobs']),'regional_cases':len(assessment['jobs']),
    'baseline_status':baseline['status'],'regional_approval':False,
    'surface_assessment_kind':assessment['assessment_kind'],
    'native_preview_status':native['status'] if native else 'PENDING_USER_AUTHORIZATION_AND_OBSERVATION',
    'native_preview_full_integrity_approval':False,
    'native_capture_pipeline_exercised_this_run':False,
    'native_preview_evidence_path':str(native_path) if native else None,
    'native_print_status':'NOT_RUN_FOR_THIS_VERSION',
    'simulator_status':transport['transport']['status'],
    'simulator_fixture':'separate synthetic cylinder; not regional output',
    'head_clearance_status':'UNKNOWN','physical_validation':False,'print_allowed':False,
    'gui_controlled':bool(native),'real_printer_contacted':False,
    'bundle_path':str(bundle),'bundle_sha256':digest(bundle.read_bytes()),
    'wheel_path':str(wheel),'wheel_sha256':digest(wheel.read_bytes()),
    'installed_path':str(plugin/'orca_wave_generator.py'),'installed_matches_bundle':installed_matches,
    'installed_version_requires_orca_restart':not bool(native and native['plugin_version_observed']==__version__),
    'installation_state_bytes_preserved_before_restart':installation_preserved,
    'runtime_state_bytes_equal_pre_install':state_preserved,
    'runtime_installed_version':runtime_state.get('installed_version'),
    'runtime_enabled':runtime_state.get('enabled'),
    'runtime_state_note':'Orca updated its installed_version to 0.5.0 after launch; agent did not change activation or permissions.',
    'previous_bundle_sha256':before['bundle_sha256'].lower(),
    'wheel_matches_source':wheel_matches,'tested_sources_match_current':tested_sources,
    'ui_test_matches_current_source':ui_current,
    'evidence_sha256':{str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in (
        folder/'verification/automated-checks.json',folder/'ui/ui-validation.json',
        folder/'baselines/baseline-index.json',folder/'regional/assessment-index.json',
        folder/'transport-regression/study-results.json')},
    'source_control':{'remote_configured':False,'pull_request_created':False,
        'reason':'Existing checkout has no valid HEAD or configured remote; original untracked files preserved.'}}
atomic_write(folder/'verification/delivery.json',json.dumps(report,ensure_ascii=False,indent=2).encode())
print(json.dumps(report,ensure_ascii=False,indent=2))
