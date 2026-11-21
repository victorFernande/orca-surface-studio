import tempfile
import time
import unittest
import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))

from orca_wave_studio.controller import StudioController
from orca_wave_studio.geometry import analyze_snapshot
from orca_wave_studio.project_io import write_model_project
from orca_wave_studio.roof_fixtures import roof_coupon
from orca_wave_studio.regional_shell import RegionalShellWarp
from orca_wave_studio.contracts import WaveError


class RegionalControllerTests(unittest.TestCase):
    def make_controller(self,root):
        snapshot,_=roof_coupon(25);host=Mock()
        host.snapshot.return_value=snapshot
        host.allowed_source_roots.return_value=(root,)
        host.capture_ready.return_value=True
        host.project_path.return_value=''
        host.export_project.side_effect=lambda path:write_model_project(snapshot,path,{
            'zaa_enabled':'1','printer_settings_id':'Sovol SV06 0.4 nozzle',
            'nozzle_temperature':['245'],'hot_plate_temp':['80'],'enable_support':'0'})
        controller=StudioController(root,host)
        controller.snapshot=snapshot;controller._objects=analyze_snapshot(snapshot)
        return controller,host

    def wait(self,c):
        limit=time.monotonic()+5
        while time.monotonic()<limit:
            phase=(c.state().get('conformal') or {}).get('phase')
            if phase=='needs_open' or c.state()['status']=='error':return
            time.sleep(.01)
        self.fail('regional preparation did not complete')

    def test_regional_backend_preserves_backup_and_never_controls_host_by_worker(self):
        with tempfile.TemporaryDirectory() as folder:
            c,host=self.make_controller(Path(folder))
            c.prepare_conformal(['1'],{'backend':'regional_paired','max_slope_deg':25,
                                       'retain_native_short_edges':True})
            self.wait(c);self.assertIsNotNone(c.state()['conformal'],c.state()['message'])
            self.assertEqual(c.state()['conformal']['phase'],'needs_open')
            ctx=c._conformal_session
            self.assertIsInstance(ctx['warp'],RegionalShellWarp)
            self.assertTrue(Path(ctx['origin_backup']).is_file())
            self.assertTrue(Path(ctx['prepared_path']).is_file())
            self.assertEqual(ctx['settings']['backend'],'regional_paired')
            self.assertFalse(c.agent_context()['approval_current'])
            host.open_project.assert_not_called()
            host.open_preview.assert_not_called()
            from zipfile import ZipFile
            import json
            with ZipFile(ctx['prepared_path']) as archive:
                settings=json.loads(archive.read('Metadata/project_settings.config'))
                self.assertEqual(settings['zaa_enabled'],'0')
                self.assertEqual(settings['nozzle_temperature'],['0'])
                self.assertEqual(settings['hot_plate_temp'],['0'])
                self.assertEqual(settings['enable_support'],'1')
                self.assertEqual(settings['support_type'],'normal(auto)')
            with ZipFile(ctx['origin_backup']) as archive:
                original=json.loads(archive.read('Metadata/project_settings.config'))
                self.assertEqual(original['nozzle_temperature'],['245'])
                self.assertEqual(original['enable_support'],'0')

    def test_stale_manual_region_refuses_and_does_not_open_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            c,host=self.make_controller(Path(folder))
            c.prepare_conformal(['1'],{'backend':'regional_paired','region_id':'stale-id'})
            self.wait(c)
            self.assertEqual(c.state()['status'],'error')
            self.assertIn('região selecionada mudou',c.state()['message'])
            self.assertIsNone(c.state()['conformal'])
            host.open_project.assert_not_called()

    def test_unknown_backend_does_not_export_or_invalidate(self):
        with tempfile.TemporaryDirectory() as folder:
            c,host=self.make_controller(Path(folder))
            with self.assertRaisesRegex(WaveError,'motor'):
                c.prepare_conformal(['1'],{'backend':'other'})
            host.export_project.assert_not_called()
