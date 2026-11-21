import copy
import json
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zipfile import ZipFile

from orca_wave_studio.contracts import ProcessedResult, WaveError
from orca_wave_studio.controller import StudioController
from orca_wave_studio.fixtures import cylinder_gcode, cylinder_snapshot
from orca_wave_studio.prepared_model import PreparedMesh
from orca_wave_studio.project_io import write_model_project


class PreparedFlowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.model = cylinder_snapshot()
        self.host = Mock()
        self.host.snapshot.return_value = self.model
        self.host.project_path.return_value = str(self.folder/"old.3mf")
        self.host.allowed_source_roots.return_value = (self.folder,)
        self.host.validate_source.return_value = True
        self.host.capture_ready.return_value = True
        self.settings = {"printer_settings_id":"Bench", "slicing_pipeline_plugin":["Existing pipeline"]}
        self.host.export_project.side_effect = self.export
        self.c = StudioController(self.folder/"studio", self.host)
        flat = copy.deepcopy(self.model)
        for v in flat.objects[0]["volumes"][0]["vertices"]:
            v[2] *= .87
        self.flat = flat
        self.warp = SimpleNamespace(object_id="100", flattened_snapshot=flat)
        self.patcher = patch("orca_wave_studio.conformal_geometry.ConformalWarp", return_value=self.warp)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def export(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        write_model_project(self.host.snapshot.return_value, path, self.settings)

    def wait(self, predicate):
        limit = time.monotonic()+8
        while time.monotonic()<limit:
            if predicate():
                return
            time.sleep(.01)
        self.fail(str(self.c.state()["message"]))

    def prepare(self):
        self.c.prepare_conformal(["100"], {})
        self.wait(lambda: self.c.state()["conformal"]["phase"]=="needs_open")
        return Path(self.c.state()["conformal"]["prepared_path"])

    def bind(self):
        path = self.prepare()
        self.c.poll_prepared()
        self.host.open_model.assert_called_once_with(path)
        with ZipFile(path) as archive:
            settings=json.loads(archive.read("Metadata/project_settings.config"))
        self.assertEqual(settings["slicing_pipeline_plugin"], ["Orca Wave Studio Capture"])
        with ZipFile(self.c.state()["conformal"]["origin_backup"]) as archive:
            original_settings=json.loads(archive.read("Metadata/project_settings.config"))
        self.assertEqual(original_settings["slicing_pipeline_plugin"], ["Existing pipeline"])
        self.assertEqual(settings["gcode_label_objects"], "1")
        self.assertEqual(settings["detect_narrow_internal_solid_infill"], "0")
        self.assertEqual(settings['zaa_enabled'],'0')
        self.assertNotIn("detect_narrow_internal_solid_infill", original_settings)
        loaded = replace(copy.deepcopy(self.flat), session_id="loaded")
        loaded.objects[0]["id"]="987"
        loaded.objects[0]["volumes"][0]["triangles"].reverse()
        self.host.snapshot.return_value=loaded
        self.host.project_path.return_value=str(path)
        self.assertTrue(self.c.prepared_project_opened(str(path)))
        self.wait(lambda: self.c.state()["conformal"]["phase"]=="awaiting_slice")
        self.assertTrue(self.c.prepared_project_opened(str(path)))
        return loaded

    def capture(self, loaded, mapped="987"):
        self.c.slice_started(loaded.session_id)
        self.c.capture_begin(loaded,{0:mapped})
        source=self.folder/"native.gcode"
        source.write_bytes(cylinder_gcode(layers=2))
        self.c.captures.export_started(loaded.session_id,str(source))
        self.c.capture_finished(loaded.session_id,str(source),True)
        self.c.slicing_completed(loaded.session_id,True)
        return source.read_bytes()

    def test_native_ids_translate_after_verified_capture_only(self):
        loaded=self.bind()
        with self.assertRaises(WaveError):
            self.c.generate(["987"],{},conformal=True)
        source=self.capture(loaded)
        with self.assertRaises(WaveError):
            self.c.generate(["100"],{},conformal=True)
        result=ProcessedResult(source+b"\n; test mapped\n", {"print_allowed":False})
        with patch("orca_wave_studio.conformal.process_conformal_gcode",return_value=result) as process:
            self.c.generate(["987"],{},conformal=True)
            self.wait(lambda:self.c.state()["status"]!="processing")
        process.assert_called_once_with(source,self.warp,{0:"100"},"100")
        state=self.c.state()
        self.assertEqual(state["result"]["study_kind"],"conformal")
        self.assertEqual(state["result"]["report"]["prepared_print_object_map"],{0:"987"})
        self.c._preview_verified=True
        self.assertFalse(self.c.agent_context()["approval_current"])

    def test_native_short_edge_choice_is_explicit_and_bound_to_preparation(self):
        with self.assertRaises(WaveError):
            self.c.prepare_conformal(['100'],{'retain_native_short_edges':'yes'})
        self.assertIsNone(self.c.state().get('conformal'))
        self.c.prepare_conformal(['100'],{'retain_native_short_edges':True})
        self.wait(lambda:self.c.state()['conformal']['phase']=='needs_open')
        self.assertTrue(self.c.state()['conformal']['settings']['retain_native_short_edges'])

    def test_changed_source_during_prepare_and_foreign_open(self):
        self.prepare()
        self.host.snapshot.return_value=replace(self.model,session_id="other")
        self.c.poll_prepared()
        self.host.open_model.assert_not_called()
        self.assertIsNone(self.c.state()["conformal"])

    def test_opened_mesh_wrong_position_rejected(self):
        path=self.prepare()
        self.c.poll_prepared()
        foreign=copy.deepcopy(self.flat)
        foreign.objects[0]["instances_data"][0]["matrix"][0][3] += .01
        self.host.project_path.return_value=str(path)
        self.host.snapshot.return_value=foreign
        self.assertFalse(self.c.prepared_project_opened(str(self.folder/"different.3mf")))
        self.c.prepared_project_opened(str(path))
        self.wait(lambda:self.c.state()["conformal"] is None)

    def test_capture_tamper_and_wrong_mapping(self):
        loaded=self.bind()
        self.capture(loaded)
        Path(self.c.captures.captured.copy_path).write_bytes(b"; changed")
        with self.assertRaises(WaveError):
            self.c.generate(["987"],{},conformal=True)
        with self.assertRaises(WaveError):
            self.capture(loaded,mapped="other")
        self.assertIsNone(self.c.state()["conformal"])

    def test_winding_change_is_detected(self):
        stored=PreparedMesh(self.flat)
        changed=copy.deepcopy(self.flat)
        triangles=changed.objects[0]["volumes"][0]["triangles"]
        triangles[0]=triangles[0][::-1]
        self.assertFalse(stored.matches(changed))

    def test_pending_open_accepts_only_own_named_preset_and_expires(self):
        path=self.prepare()
        self.c.poll_prepared()
        self.assertTrue(self.c.prepared_transition("PresetSelected", SimpleNamespace(name="Bench("+path.name+")")))
        self.assertFalse(self.c.prepared_transition("PresetSelected", SimpleNamespace(name="Other printer")))
        self.assertFalse(self.c.prepared_project_opened(str(self.folder/"other.3mf")))
        saved=self.folder/"original-saved-as.3mf"
        self.host.project_path.return_value=str(saved)
        self.assertTrue(self.c.prepared_transition("ProjectClosed", SimpleNamespace(name=str(saved.with_suffix("")))))
        self.c._conformal_session["expires"]=0
        self.c.poll_prepared()
        self.assertIsNone(self.c.state()["conformal"])
        self.assertFalse(self.c.agent_context()["approval_current"])

    def test_opened_project_must_apply_capture_profile_and_original_dimensions(self):
        path=self.prepare()
        self.c.poll_prepared()
        self.host.project_path.return_value=str(path)
        self.host.snapshot.return_value=replace(self.flat,settings={**self.flat.settings,"layer_height":"1.7"})
        self.host.capture_ready.return_value=False
        self.c.poll_prepared()
        self.assertEqual(self.c.state()["conformal"]["phase"],"opening")
        self.host.capture_ready.return_value=True
        self.c.poll_prepared()
        self.wait(lambda:self.c.state()["conformal"] is None)
