"""Persist the complete automated test result, independently of native GUI QA."""
from datetime import datetime,timezone
import io
import json
from pathlib import Path
import platform
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from orca_wave_studio import __version__
from orca_wave_studio.capture import atomic_write
from orca_wave_studio.contracts import digest

stream=io.StringIO()
suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
folder=ROOT/'study/evidence/roof-study/verification'
atomic_write(folder/'unit-tests.txt',stream.getvalue().encode())
report={'status':'PASS_AUTOMATED_TESTS' if result.wasSuccessful() else 'FAIL_AUTOMATED_TESTS',
    'version':__version__,'date_utc':datetime.now(timezone.utc).isoformat(),
    'python_version':platform.python_version(),'tests_run':result.testsRun,
    'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
    'source_sha256':{str(p.relative_to(ROOT)):digest(p.read_bytes()) for folder_name in ('src','scripts','tests')
        for p in sorted((ROOT/folder_name).rglob('*')) if p.suffix in {'.py','.cjs'}},
    'native_preview_validated':False,'physical_validation':False,'print_allowed':False,
    'study_approval_status':'ISSUES','automated_success_is_not_surface_or_physical_approval':True}
atomic_write(folder/'automated-checks.json',json.dumps(report,ensure_ascii=False,indent=2).encode())
print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},ensure_ascii=False,indent=2))
sys.exit(0 if result.wasSuccessful() else 1)
