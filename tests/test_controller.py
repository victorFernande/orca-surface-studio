import json
import os
import sys
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from orca_wave_studio.contracts import StaleArtifactError, digest
from orca_wave_studio.controller import StudioController
from orca_wave_studio.engine import process_gcode
from orca_wave_studio.fixtures import cylinder_gcode, cylinder_snapshot
from orca_wave_studio.package import extract_plate_gcode
from orca_wave_studio.plugin import NativeHost, WaveCapturePipeline


class ControllerTests(unittest.TestCase):
    def test_combined_result_never_grants_transport_even_with_preview_verified(self):
        c=self.controller
        self.capture()
        c.generate(["100"],{"mode":"combined","amplitude_mm":.3,"start_height_mm":.4})
        produced=self.result()
        self.assertFalse(produced["report"]["print_allowed"])
        c._preview_verified=True
        self.assertFalse(c.agent_context()["approval_current"])
        self.assertEqual(Path(produced["gcode_path"]).read_bytes(),extract_plate_gcode(Path(produced["package_path"]),0))

    def test_vase_preparation_requires_one_object_and_saves_backup_before_editing(self):
        model=cylinder_snapshot()
        host=Mock()
        host.snapshot.return_value=model
        host.capture_ready.return_value=True
        host.allowed_source_roots.return_value=(self.root,)
        host.validate_source.return_value=True
        order=[]
        def export(path):
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(b'original project')
            order.append('backup')
        host.export_project.side_effect=export
        host.prepare_vase.side_effect=lambda:order.append('edit')
        c=StudioController(self.root/'vase',host)
        c.handle({'action':'prepare_vase','object_ids':['100']})
        self.assertEqual(order,['backup','edit'])
        self.assertTrue(c._gui_armed)
        event=[e for e in c.state()['events'] if e['event']=='vase_prepared'][0]
        self.assertEqual(Path(event['original_backup']).read_bytes(),b'original project')
        host.snapshot.return_value=cylinder_snapshot(two_objects=True)
        c.handle({'action':'prepare_vase','object_ids':['100']})
        self.assertEqual(c.state()['status'],'error')
        self.assertEqual(order,['backup','edit'])

    def test_surface_study_needs_no_slice_and_never_grants_print(self):
        from orca_wave_studio.contracts import ProcessedResult
        c=self.controller
        c.snapshot=cylinder_snapshot()
        report={"original_points":[[0,0,1],[1,0,1]],
                "deformed_points":[[0,0,1],[1,0,1.1]],"break_indices":[0],"layer_ids":[0,0]}
        result=ProcessedResult(b"; geometry only\nG1 X1 Y0 Z1.1\n",report)
        with patch("orca_wave_studio.surface.build_surface_study",return_value=result):
            c.surface_study(["100"],{"step_mm":.4,"max_slope_deg":30})
            produced=self.result()
        self.assertIsNone(c.captures.captured)
        self.assertEqual(produced["study_kind"],"surface")
        self.assertEqual(produced["object_id"],"100")
        self.assertFalse(produced["report"]["print_allowed"])
        c._preview_verified=True
        self.assertFalse(c.agent_context()["approval_current"])
        c.host=Mock()
        with self.assertRaisesRegex(ValueError,"não contém deposição"):
            c.open_preview()
        c.host.open_preview.assert_not_called()

    def preview_files(self):
        c = self.controller
        self.capture()
        c.generate(["100"], {"mode": "xy", "start_height_mm": 0, "amplitude_mm": 0})
        result = self.result()
        host = NativeHost()
        host.allowed_source_roots = lambda: (self.root,)
        host.project_path = Mock(return_value=str(self.root / "original.3mf"))
        host.open_preview = Mock()
        c.host = host
        c.open_preview()
        path = (
            self.root
            / "orcaslicer_model"
            / "Thu_Nov_19"
            / f"15_34_10#{os.getpid()}#176"
            / "Metadata"
            / "plate_1.gcode"
        )
        path.parent.mkdir(parents=True)
        path.write_bytes(Path(result["gcode_path"]).read_bytes())
        host.project_path.return_value = result["package_path"]
        return c, path, result["package_path"]

    def test_loaded_package_path_alone_never_approves(self):
        c, path, package = self.preview_files()
        self.assertFalse(c.verify_preview(package))
        c.preview_cache_event(True, "77", str(path), True)
        self.assertFalse(c.verify_preview(package))
        c.preview_cache_event(False, "77", str(path), True)
        self.assertFalse(c.verify_preview(package))
        c.preview_completed("88", True)
        self.assertFalse(c.agent_context()["approval_current"])
        self.assertIsNone(c.captures.captured)

    def test_mutated_native_cache_cannot_authorize_matching_package(self):
        c, path, package = self.preview_files()
        c.preview_cache_event(True, "77", str(path), True)
        c.preview_cache_event(False, "77", str(path), True)
        path.write_bytes(path.read_bytes() + b"; modified bytes\n")
        c.preview_completed("77", True)
        self.assertFalse(c.verify_preview(package))
        self.assertFalse(c.agent_context()["approval_current"])
        self.assertFalse(Path(package).with_name("preview-receipt.json").exists())

    def test_preview_waits_for_user_permission_then_verifies_the_same_cache(self):
        c,path,package=self.preview_files()
        c.preview_cache_event(True,"77",str(path),True)
        with patch.object(Path,"read_bytes",side_effect=RuntimeError(
                'Plugin attempted audited operation "open" without permission: audit permission required')):
            c.preview_cache_event(False,"77",str(path),True)
            c.preview_completed("77",True)
            self.assertFalse(c.verify_preview(package))
        self.assertIsNotNone(c._result)
        self.assertFalse(c.agent_context()["approval_current"])
        self.assertFalse(Path(package).with_name("preview-receipt.json").exists())
        c._preview_request["retry_after"]=0
        with patch.object(Path,"read_bytes",side_effect=AssertionError('Hidden/modal Studio must not read')):
            self.assertFalse(c.verify_preview(package))
            c.handle({"action":"poll","ui_focused":False})
        self.assertTrue(c.verify_preview(package,resume_access=True))
        receipt=json.loads(Path(package).with_name("preview-receipt.json").read_text())
        self.assertEqual(receipt["cache_path"],str(path.resolve()))
        self.assertEqual(receipt["sha256"],digest(path.read_bytes()))
        self.assertIn("Preview do Orca confirmado",c.state()["message"])

    def test_preview_changed_while_waiting_for_permission_is_rejected(self):
        c,path,package=self.preview_files()
        c.preview_cache_event(True,"77",str(path),True)
        with patch.object(Path,"read_bytes",side_effect=RuntimeError(
                'Plugin attempted audited operation "open" without permission: audit permission required')):
            c.preview_cache_event(False,"77",str(path),True)
            c.preview_completed("77",True)
        path.write_bytes(path.read_bytes()+b'; altered while dialog open\n')
        c._preview_request["retry_after"]=0
        self.assertFalse(c.verify_preview(package,resume_access=True))
        self.assertIsNone(c._result)
        self.assertFalse(Path(package).with_name("preview-receipt.json").exists())

    def test_preview_permission_retry_does_not_loop_after_another_denial(self):
        c,path,package=self.preview_files()
        c.preview_cache_event(True,"77",str(path),True)
        with patch.object(Path,"read_bytes",side_effect=RuntimeError(
                'Plugin attempted audited operation "open" without permission: audit permission required')):
            c.preview_cache_event(False,"77",str(path),True)
            c.preview_completed("77",True)
            c._preview_request["retry_after"]=0
            self.assertFalse(c.verify_preview(package,resume_access=True))
            self.assertIsNone(c._preview_request)
            self.assertIsNone(c._result)

    def test_native_permission_modal_cannot_reenter_preview_verification(self):
        c,path,package=self.preview_files()
        c.preview_cache_event(True,"77",str(path),True)
        c.preview_cache_event(False,"77",str(path),True)
        original=Path.read_bytes
        reads=[]
        def modal_read(candidate):
            if candidate==path:
                reads.append(candidate)
                self.assertFalse(c.verify_preview(package))
            return original(candidate)
        with patch.object(Path,"read_bytes",autospec=True,side_effect=modal_read):
            c.preview_completed("77",True)
        self.assertEqual(len(reads),1)
        self.assertTrue(c.verify_preview(package))
        self.assertEqual(len([e for e in c.state()["events"] if e["event"]=="preview_package_verified"]),1)

    def test_mutation_inside_native_permission_modal_cannot_publish_receipt(self):
        c,path,package=self.preview_files()
        c.preview_cache_event(True,"77",str(path),True)
        c.preview_cache_event(False,"77",str(path),True)
        original=Path.read_bytes
        def modal_read(candidate):
            if candidate==path:
                c.invalidate('Project changed inside nested native message loop')
            return original(candidate)
        with patch.object(Path,"read_bytes",autospec=True,side_effect=modal_read):
            c.preview_completed("77",True)
        self.assertFalse(c.agent_context()["approval_current"])
        self.assertFalse(Path(package).with_name("preview-receipt.json").exists())

    def test_preview_reader_rejects_correct_bytes_outside_process_cache(self):
        c, path, package = self.preview_files()
        outside = self.root / path.name
        outside.write_bytes(path.read_bytes())
        c.preview_cache_event(True, "77", str(outside), True)
        self.assertFalse(c.verify_preview(package))
        self.assertIsNone(c.captures.captured)

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.controller = StudioController(self.root / "state")
        self.source = self.root / "source.gcode"
        self.data = cylinder_gcode(layers=6, two_objects=True)
        self.source.write_bytes(self.data)

    def capture(self, plate=0):
        snapshot = cylinder_snapshot(plate_index=plate, two_objects=True)
        c = self.controller
        c.capture_begin(snapshot, {0: "100", 1: "101"})
        c.captures.export_started(snapshot.session_id, str(self.source))
        c.capture_finished(snapshot.session_id, str(self.source), True)
        self.assertEqual(c.state()["status"], "idle")
        return snapshot

    def result(self):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            state = self.controller.state()
            if state["status"] != "processing":
                self.assertEqual(state["status"], "ready", state["message"])
                return state["result"]
            time.sleep(0.01)
        self.fail("Worker did not publish its result within 15 seconds.")

    def stage_native_capture(self):
        host = Mock(
            spec=[
                "snapshot",
                "capture_ready",
                "allowed_source_roots",
                "validate_source",
                "export_project",
            ]
        )
        host.allowed_source_roots.return_value = (self.root,)
        host.capture_ready.return_value = True
        host.validate_source.return_value = True
        model = cylinder_snapshot(two_objects=True)
        gui = replace(
            model,
            settings={
                **model.settings,
                "enable_prime_tower": "1",
                "filament_nozzle_map": "1",
            },
        )
        effective = replace(
            model,
            settings={
                **gui.settings,
                "enable_prime_tower": "0",
                "filament_nozzle_map": "0",
            },
        )
        host.snapshot.return_value = gui
        c = StudioController(self.root / "two-revisions", host)
        c.refresh()
        c.slice_started(gui.session_id)
        c.capture_begin(effective, {0: "100", 1: "101"})
        c.captures.export_started(gui.session_id, str(self.source))
        c.capture_finished(gui.session_id, str(self.source), True)
        self.assertIsNone(c.captures.captured)
        with self.assertRaises(StaleArtifactError):
            c.captures.current(gui)
        return c, gui, effective

    def test_native_validation_compares_gui_to_gui_and_audits_effective_values(self):
        c, gui, effective = self.stage_native_capture()
        c.slicing_completed(gui.session_id, True)
        capture = c.captures.current(gui)
        self.assertEqual(capture.revision, gui.revision)
        self.assertNotEqual(capture.revision, effective.revision)
        audit = json.loads(
            Path(capture.copy_path)
            .with_suffix(".snapshots.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(audit["gui_before"]["revision"], gui.revision)
        self.assertEqual(audit["slicer_effective"]["revision"], effective.revision)
        self.assertEqual(audit["gui_before"]["settings"]["filament_nozzle_map"], "1")
        self.assertEqual(
            audit["slicer_effective"]["settings"]["filament_nozzle_map"], "0"
        )
        self.controller = c
        c.generate(["100"], {"amplitude_mm": 0, "start_height_mm": 0})
        self.assertEqual(
            self.result()["report"]["effective_snapshot_revision"], effective.revision
        )
        self.assertFalse(c.agent_context()["approval_current"])

    def pending_native_capture(self):
        original_read=Path.read_bytes
        def audited_read(path):
            if path==self.source:
                raise RuntimeError('Plugin attempted audited operation "open" without permission: audit permission required')
            return original_read(path)
        with patch.object(Path,"read_bytes",autospec=True,side_effect=audited_read):
            c,gui,effective=self.stage_native_capture()
            c.slicing_completed(gui.session_id,True)
            self.assertIsNotNone(c._capture_access_pending)
            self.assertIsNone(c.captures.captured)
        c._capture_access_pending["retry_after"]=0
        return c,gui,effective

    def test_capture_resumes_after_permission_without_reslicing(self):
        c,gui,_=self.pending_native_capture()
        with patch.object(Path,"read_bytes",side_effect=AssertionError('Hidden/modal Studio must not read')):
            c.handle({"action":"poll","ui_focused":False})
        self.assertIsNotNone(c._capture_access_pending)
        original=Path.read_bytes
        reads=[]
        def modal_read(path):
            if path==self.source:
                reads.append(path)
                c.handle({"action":"poll","ui_focused":True})
            return original(path)
        with patch.object(Path,"read_bytes",autospec=True,side_effect=modal_read):
            c.handle({"action":"poll","ui_focused":True})
        self.assertEqual(len(reads),1)
        self.assertIsNone(c._capture_access_pending)
        self.assertEqual(c.captures.current(gui).sha256,digest(self.source.read_bytes()))
        self.assertTrue(any(e["event"]=="capture_gui_verified" for e in c.state()["events"]))

    def test_capture_permission_wait_rejects_changed_file_or_project_and_cancel(self):
        for change in ("file","project","cancel","timeout","denial"):
            with self.subTest(change=change):
                c,gui,effective=self.pending_native_capture()
                if change=="file":
                    self.source.write_bytes(self.source.read_bytes()+b';changed\n')
                elif change=="project":
                    c.host.snapshot.return_value=effective
                elif change=="cancel":
                    c.slicing_completed(gui.session_id,False)
                elif change=="timeout":
                    c._capture_access_pending["expires"]=0
                if change=="denial":
                    with patch.object(Path,"read_bytes",side_effect=RuntimeError(
                            'Plugin attempted audited operation "open" without permission: audit permission required')):
                        c.handle({"action":"poll","ui_focused":True})
                else:
                    c.handle({"action":"poll","ui_focused":True})
                self.assertIsNone(c.captures.captured)
                self.assertIsNone(c._capture_access_pending)

    def test_even_editing_an_engine_derived_gui_field_revokes_capture(self):
        c, gui, effective = self.stage_native_capture()
        # Live GUI now equals the effective snapshot, but changed since before slicing.
        c.host.snapshot.return_value = effective
        c.slicing_completed(gui.session_id, True)
        self.assertIsNone(c.captures.captured)
        self.assertEqual(c.state()["status"], "slicing_required")

    def test_job_cancel_and_unarmed_capture_cannot_publish(self):
        c, gui, effective = self.stage_native_capture()
        c.slicing_completed(gui.session_id, False)
        c.slicing_completed(gui.session_id, True)
        self.assertIsNone(c.captures.captured)
        c.slice_started(gui.session_id)
        with self.assertRaises(StaleArtifactError):
            c.capture_begin(effective, {0: "100", 1: "101"})

    def test_two_parameter_sets_are_reflected_in_actual_package(self):
        self.capture(2)
        c = self.controller
        c.generate(
            ["100", "101"],
            {"start_height_mm": 0, "fade_layers": 1},
            {
                "100": {"mode": "z", "amplitude_mm": 0.04},
                "101": {"mode": "xy", "amplitude_mm": 0.12},
            },
        )
        result = self.result()
        expected = Path(result["gcode_path"]).read_bytes()
        self.assertNotEqual(expected, self.data)
        self.assertEqual(self.source.read_bytes(), self.data)
        self.assertEqual(extract_plate_gcode(Path(result["package_path"]), 2), expected)
        self.assertEqual(result["sha256"], digest(expected))
        report = result["report"]
        self.assertEqual(report["parameters"]["100"]["mode"], "z")
        self.assertEqual(report["parameters"]["101"]["mode"], "xy")
        original, deformed = report["original_points"], report["deformed_points"]
        self.assertEqual(len(original), len(report["point_object_ids"]))
        self.assertEqual(len(original), len(deformed))
        self.assertTrue(
            any(
                abs(a[2] - b[2]) > 0.025
                for i, a, b in zip(report["point_object_ids"], original, deformed)
                if i == 0
            )
        )
        self.assertTrue(
            any(
                abs(a[0] - b[0]) > 0.08
                for i, a, b in zip(report["point_object_ids"], original, deformed)
                if i == 1
            )
        )
        self.assertEqual(len(result["break_indices"]), len(report["contours"]))
        self.assertEqual(result["break_indices"][0], 0)
        self.assertTrue(
            all(0 <= idx < len(deformed) for idx in result["break_indices"])
        )
        self.assertFalse(report["native_preview_validated"])
        self.assertFalse(report["physical_validation"])
        self.assertFalse(c.agent_context()["approval_current"])

    def test_cancel_during_work_cannot_publish_result(self):
        self.capture()
        entered = threading.Event()
        release = threading.Event()
        workers = []

        def paused(*args, **kw):
            workers.append(threading.current_thread())
            entered.set()
            if not release.wait(10):
                raise TimeoutError("Test worker exceeded its release deadline")
            return process_gcode(*args, **kw)

        with patch("orca_wave_studio.controller.process_gcode", side_effect=paused):
            try:
                self.controller.generate(["100"], {"start_height_mm": 0})
                self.assertTrue(entered.wait(5))
                self.controller.invalidate("Projeto transformado durante a geração.")
            finally:
                release.set()
                for worker in workers:
                    worker.join(10)
                    self.assertFalse(worker.is_alive())
        state = self.controller.state()
        self.assertIsNone(state["result"])
        self.assertIsNone(state["capture"])
        self.assertEqual(state["status"], "slicing_required")
        self.assertFalse(self.controller.agent_context()["approval_current"])

    def test_preview_breaks_between_copies_even_on_same_logical_layer(self):
        c = self.controller
        plates = cylinder_snapshot(two_objects=True)
        object_with_copies = plates.objects[0]
        object_with_copies["instances_data"].extend(plates.objects[1]["instances_data"])
        from dataclasses import replace

        snapshot = replace(plates, objects=(object_with_copies,))
        src = cylinder_gcode(layers=1, two_objects=True).replace(
            b"id:1 copy 0", b"id:0 copy 1"
        )
        self.source.write_bytes(src)
        c.capture_begin(snapshot, {0: "100"})
        c.captures.export_started(snapshot.session_id, str(self.source))
        c.capture_finished(snapshot.session_id, str(self.source), True)
        c.generate(["100"], {"mode": "xy", "start_height_mm": 0, "amplitude_mm": 0})
        result = self.result()
        _, boundary = result["break_indices"]
        self.assertEqual(set(result["layer_ids"]), {0})
        self.assertAlmostEqual(
            result["deformed_points"][boundary][0]
            - result["deformed_points"][boundary - 1][0],
            60.0,
        )

    def test_saved_preset_invalidates_even_while_waiting_for_preview(self):
        c = self.controller
        self.capture()
        c.generate(["100"], {"mode": "xy", "start_height_mm": 0, "amplitude_mm": 0})
        self.result()
        # Only request opening. No native acknowledgement or approval is supplied.
        c.host = Mock(spec=["open_preview", "capture_ready", "project_path"])
        c.host.project_path.return_value = str(self.root / "original.3mf")
        c.open_preview()
        with patch("orca_wave_studio.plugin.get_controller", return_value=c):
            WaveCapturePipeline().on_lifecycle_event("PresetSaved", None)
        self.assertIsNone(
            c.state()["result"], "PresetSaved must revoke the pending output"
        )
        self.assertIsNone(c.state()["capture"])
        self.assertFalse(c.agent_context()["approval_current"])

    def test_import_own_preset_selection_honors_only_synchronous_open_scope(self):
        c = self.controller
        self.capture()
        c.generate(["100"], {"mode": "xy", "start_height_mm": 0, "amplitude_mm": 0})
        self.result()
        c.host = Mock(spec=["open_preview", "capture_ready", "project_path"])
        c.host.project_path.return_value = str(self.root / "original.3mf")
        pipeline = WaveCapturePipeline()
        with patch("orca_wave_studio.plugin.get_controller", return_value=c):
            c.host.open_preview.side_effect = lambda _path: pipeline.on_lifecycle_event(
                "PresetSelected", None
            )
            c.open_preview()
            self.assertIsNotNone(c.captures.captured)
            self.assertFalse(c.agent_context()["approval_current"])
            pipeline.on_lifecycle_event("PresetSelected", None)
        self.assertIsNone(c.captures.captured)
        self.assertEqual(c.state()["status"], "slicing_required")

    def test_old_worker_cannot_replace_new_plate_package_or_report_at_same_gcode_hash(
        self,
    ):
        c = self.controller
        self.capture(0)
        entered = threading.Event()
        release = threading.Event()
        workers = []

        def paused_first(*args, **kw):
            if not entered.is_set():
                workers.append(threading.current_thread())
                entered.set()
                if not release.wait(10):
                    raise TimeoutError("Stale worker exceeded its release deadline")
            return process_gcode(*args, **kw)

        with patch(
            "orca_wave_studio.controller.process_gcode", side_effect=paused_first
        ):
            try:
                c.generate(
                    ["100"],
                    {"start_height_mm": 0, "amplitude_mm": 0, "wavelength_mm": 5.0},
                )
                self.assertTrue(entered.wait(5))
                inside = self.capture(1)
                c.generate(
                    ["100"],
                    {"start_height_mm": 0, "amplitude_mm": 0, "wavelength_mm": 25.0},
                )
                current = self.result()
                self.assertEqual(current["sha256"], digest(self.data))
            finally:
                release.set()
                for worker in workers:
                    worker.join(10)
                    self.assertFalse(worker.is_alive())
        state = c.state()
        self.assertEqual(state["result"]["plate_index"], 1)
        package = Path(current["package_path"])
        report = json.loads(
            package.with_name("report.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report["snapshot_revision"], inside.revision)
        self.assertEqual(report["parameters"]["100"]["wavelength_mm"], 25.0)
        self.assertEqual(extract_plate_gcode(package, 1), self.data)
        self.assertFalse(c.agent_context()["approval_current"])
