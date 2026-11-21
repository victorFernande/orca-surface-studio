import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from zipfile import ZipFile

from orca_wave_studio.contracts import WaveError
from orca_wave_studio.surface_workflow import slice_command,verify_profile


class SurfaceWorkflowTests(unittest.TestCase):
    def test_process_permission_names_an_exact_command_with_no_job_or_shell(self):
        with tempfile.TemporaryDirectory() as folder:
            workspace=Path(folder)/'private workspace'
            command=slice_command(Path(folder)/'OrcaSlicer.exe',workspace)
            self.assertIn('input.3mf',command)
            self.assertEqual(command,slice_command(Path(folder)/'OrcaSlicer.exe',workspace))
            self.assertEqual(command,slice_command(Path(folder)/'OrcaSlicer.exe',Path(folder)/'another job'))
            self.assertNotIn('--send',command)
            self.assertNotIn('cmd.exe',command)
            self.assertIn('input.3mf',subprocess.list2cmdline(command))
            local=slice_command(Path(folder)/'OrcaSlicer.exe',native_local=True)
            self.assertEqual(local[:-2],command)
            self.assertEqual(local[-2:],['--zaa-enabled=1','--zaa-minimize-perimeter-height=0'])

    def test_changed_material_or_transport_stops_before_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'native.3mf';wanted={'nozzle_temperature':['205'],'printer_agent':'native'}
            with ZipFile(p,'w') as archive:archive.writestr('Metadata/project_settings.config',json.dumps(wanted))
            self.assertTrue(verify_profile(p,wanted)['matched'])
            with self.assertRaisesRegex(WaveError,'nozzle_temperature'):
                verify_profile(p,{**wanted,'nozzle_temperature':['240']})
            with self.assertRaisesRegex(WaveError,'printer_agent'):
                verify_profile(p,{**wanted,'printer_agent':'simulator'})
            with self.assertRaisesRegex(WaveError,'zaa_enabled'):
                verify_profile(p,{**wanted,'zaa_enabled':'1'},extra_fields=('zaa_enabled',))
