import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

from orca_wave_studio.controller import StudioController
from orca_wave_studio.fixtures import cylinder_snapshot
from orca_wave_studio.geometry import analyze_snapshot
from orca_wave_studio.contracts import digest
from orca_wave_studio.package import build_sliced_package


class SurfaceWorkflowControllerTests(unittest.TestCase):
    def test_study_does_not_open_preview_until_the_user_sends_the_result(self):
        for auto_open in (False,True):
            with self.subTest(auto_open=auto_open),tempfile.TemporaryDirectory() as root:
                storage=Path(root);snapshot=cylinder_snapshot();host=Mock()
                host.snapshot.return_value=snapshot;host.allowed_source_roots.return_value=(storage,)
                host.capture_ready.return_value=True
                def export(path):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'original')
                host.export_project.side_effect=export
                controller=StudioController(storage,host);controller.snapshot=snapshot;controller._objects=analyze_snapshot(snapshot)
                result={'sha256':'study','package_path':'study.gcode.3mf','revision':snapshot.revision}
                with patch('orca_wave_studio.surface_workflow.build_surface',return_value=result):
                    controller.build_surface(['100'],{},open_after_study=auto_open)
                    deadline=time.monotonic()+2
                    while controller._job and time.monotonic()<deadline:time.sleep(.01)
                self.assertEqual(controller.state()['status'],'ready')
                self.assertEqual(controller._pending_open,auto_open)
                host.open_preview.assert_not_called()

    def test_old_study_hash_cannot_be_sent_from_the_last_step(self):
        with tempfile.TemporaryDirectory() as root:
            host=Mock();host.allowed_source_roots.return_value=()
            controller=StudioController(Path(root),host);controller._result={'sha256':'new'}
            state=controller.handle({'action':'open_preview','sha256':'old'})
            self.assertEqual(state['state']['status'],'error')
            host.open_preview.assert_not_called()

    def test_reopening_the_page_does_not_restart_the_same_mesh_analysis(self):
        started=threading.Event();release=threading.Event()
        with tempfile.TemporaryDirectory() as root:
            snapshot=cylinder_snapshot();host=Mock();host.snapshot.return_value=snapshot
            host.allowed_source_roots.return_value=(Path(root),)
            controller=StudioController(Path(root),host)
            def preview(*args):started.set();release.wait(3);return {'objects':[],'id':'test'}
            with patch('orca_wave_studio.model_preview.model_preview',side_effect=preview),\
                 patch('orca_wave_studio.roof_regions.roof_region_catalog',side_effect=AssertionError('eager catalog')):
                controller.refresh();self.assertTrue(started.wait(2));job=controller._analysis_job
                controller.refresh();self.assertEqual(controller._analysis_job,job)
                release.set()
                deadline=time.monotonic()+2
                while controller._analysis_job and time.monotonic()<deadline:time.sleep(.01)
            self.assertTrue(controller.state()['objects'])

    def test_identical_calculation_reuses_only_intact_current_files(self):
        with tempfile.TemporaryDirectory() as root:
            storage=Path(root);snapshot=cylinder_snapshot();host=Mock()
            host.snapshot.return_value=snapshot;host.allowed_source_roots.return_value=(storage,)
            host.capture_ready.return_value=True
            host.export_project.side_effect=lambda path:(path.parent.mkdir(parents=True,exist_ok=True),path.write_bytes(b'backup'))
            c=StudioController(storage,host);c.snapshot=snapshot;c._objects=analyze_snapshot(snapshot)
            data=b'; fixture only\nG1 X1 Y1 Z.2\n';gcode=storage/'test.gcode';gcode.write_bytes(data)
            package=storage/'test.gcode.3mf';build_sliced_package(data,package)
            result={'sha256':digest(data),'package_path':str(package),'gcode_path':str(gcode),
                    'plate_index':0,'revision':snapshot.revision,'report':{'print_allowed':False}}
            def wait():
                deadline=time.monotonic()+2
                while c._job and time.monotonic()<deadline:time.sleep(.01)
                self.assertEqual(c.state()['status'],'ready')
            with patch('orca_wave_studio.surface_workflow.build_surface',return_value=result) as builder:
                c.build_surface(['100'],{'backend':'continuous_layers'},open_after_study=False);wait()
                c.build_surface(['100'],{'backend':'continuous_layers'},open_after_study=False);wait()
                self.assertEqual(builder.call_count,1);self.assertEqual(host.export_project.call_count,1)
                c._status='error';c._message='Permissão de Preview pendente.'
                c.build_surface(['100'],{'backend':'continuous_layers'},open_after_study=False);wait()
                self.assertEqual(builder.call_count,1,'a Preview error must not repeat a valid calculation')
                self.assertFalse(c.state()['result']['report']['print_allowed']);self.assertFalse(c._preview_verified)
                self.assertFalse(c._pending_open)
                gcode.write_bytes(b'changed')
                c.build_surface(['100'],{'backend':'continuous_layers'},open_after_study=False);wait()
                self.assertEqual(builder.call_count,2)
                gcode.write_bytes(data);build_sliced_package(b'tampered',package)
                c.build_surface(['100'],{'backend':'continuous_layers'},open_after_study=False);wait()
                self.assertEqual(builder.call_count,3)
                build_sliced_package(data,package)
                c.build_surface(['100'],{'backend':'native_local'},open_after_study=False);wait()
                self.assertEqual(builder.call_count,4)
                # A source/profile revision change must never inherit the reuse key.
                from dataclasses import replace
                host.snapshot.return_value=replace(snapshot,settings={**snapshot.settings,'layer_height':.24})
                c.build_surface(['100'],{'backend':'native_local'},open_after_study=False);wait()
                self.assertEqual(builder.call_count,5)
            host.open_preview.assert_not_called()

    def test_cancelled_worker_cannot_publish_or_open_a_stale_preview(self):
        started=threading.Event();release=threading.Event()
        with tempfile.TemporaryDirectory() as root:
            storage=Path(root);snapshot=cylinder_snapshot();host=Mock()
            host.snapshot.return_value=snapshot;host.allowed_source_roots.return_value=(storage,)
            host.capture_ready.return_value=True
            def export(path):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'private-original')
            host.export_project.side_effect=export
            controller=StudioController(storage,host);controller.snapshot=snapshot;controller._objects=analyze_snapshot(snapshot)
            def builder(*args,**kwargs):
                kwargs['progress']('Refinando as camadas…');started.set();release.wait(3)
                self.assertTrue(kwargs['cancelled']())
                return {'sha256':'old','package_path':'stale.gcode.3mf'}
            with patch('orca_wave_studio.surface_workflow.build_surface',side_effect=builder):
                controller.build_surface(['100'],{})
                self.assertTrue(started.wait(2))
                self.assertEqual(controller.state()['calculation']['phase'],'Refinando as camadas…')
                self.assertGreaterEqual(controller.state()['calculation']['elapsed_seconds'],0)
                duplicate=controller.handle({'action':'build_surface','object_ids':['100'],
                                             'client_request_id':'duplicate-from-other-panel'})['state']
                self.assertEqual(duplicate['status'],'processing')
                self.assertEqual(duplicate['build_client_request_id'],'duplicate-from-other-panel')
                self.assertEqual(host.export_project.call_count,1)
                controller.handle({'action':'cancel_build'});release.set()
                time.sleep(.05)
            self.assertIsNone(controller.state()['result'])
            self.assertIsNone(controller.state()['calculation'])
            self.assertFalse(controller._pending_open)
            host.open_preview.assert_not_called();host.prepare_vase.assert_not_called()

    def test_state_reuses_the_revision_of_the_frozen_snapshot(self):
        from orca_wave_studio.contracts import ProjectSnapshot
        with tempfile.TemporaryDirectory() as root:
            controller=StudioController(Path(root));snapshot=cylinder_snapshot();controller.snapshot=snapshot
            getter=ProjectSnapshot.revision.fget;calls=[]
            def counted(s):calls.append(s);return getter(s)
            with patch.object(ProjectSnapshot,'revision',property(counted)):
                a=controller.state();b=controller.state()
                controller.snapshot=cylinder_snapshot(two_objects=True);c=controller.state()
            self.assertEqual(len(calls),2)
            self.assertEqual(a['revision'],b['revision']);self.assertNotEqual(b['revision'],c['revision'])
