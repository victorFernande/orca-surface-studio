import copy
import json
import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from orca_wave_studio.capture import CaptureStore
from orca_wave_studio.contracts import StaleArtifactError, WaveError, digest
from orca_wave_studio.fixtures import cylinder_gcode, cylinder_snapshot
from orca_wave_studio.plugin import NativeHost


class CaptureTests(unittest.TestCase):
    def test_native_temp_root_does_not_create_a_permission_probe_file(self):
        folder=self.allowed.resolve()
        with patch.dict(os.environ,{"TEMP":str(folder)}), \
             patch("orca_wave_studio.plugin._storage",return_value=folder/'plugin'), \
             patch("orca_wave_studio.plugin.tempfile.gettempdir",side_effect=AssertionError('unexpected file probe')):
            self.assertEqual(NativeHost().allowed_source_roots(),((folder/'plugin').resolve(),folder))
        with patch.dict(os.environ,{"TEMP":"relative-path"}):
            with self.assertRaisesRegex(WaveError,'absoluto'):
                NativeHost().allowed_source_roots()

    def test_project_export_accepts_native_void_return_and_requires_output(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"copy.3mf"
            native=Mock()
            def export(value):
                Path(value).write_bytes(b"native export")
            native.host.plater.return_value.export_3mf_copy.side_effect=export
            with patch("orca_wave_studio.plugin.orca",native):
                NativeHost().export_project(path)
                self.assertEqual(path.read_bytes(),b"native export")
                native.host.plater.return_value.export_3mf_copy.side_effect=None
                native.host.plater.return_value.export_3mf_copy.return_value=None
                with self.assertRaises(WaveError):
                    NativeHost().export_project(Path(folder)/"missing.3mf")

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.allowed = root / "slicer"
        self.allowed.mkdir()
        self.source = self.allowed / "export.gcode"
        self.data = cylinder_gcode(layers=2, two_objects=True)
        self.source.write_bytes(self.data)
        self.snapshot = cylinder_snapshot(two_objects=True)
        self.ids = {0: "100", 1: "101"}
        self.store = CaptureStore(
            root / "private", allowed_source_roots=(self.allowed,)
        )

    def begin(self, path=None):
        self.store.begin(self.snapshot, self.ids)
        self.store.export_started(self.snapshot.session_id, str(path or self.source))

    def finish(self, path=None):
        return self.store.finish(self.snapshot.session_id, str(path or self.source))

    def test_capture_copy_and_source_independence(self):
        self.begin()
        capture = self.finish()
        self.assertEqual(self.store.current(self.snapshot), capture)
        self.assertNotEqual(self.source.resolve(), Path(capture.copy_path).resolve())
        self.assertEqual(Path(capture.copy_path).read_bytes(), self.data)
        self.assertEqual(
            json.loads(Path(capture.copy_path).with_suffix(".json").read_text())[
                "sha256"
            ],
            digest(self.data),
        )
        self.source.write_bytes(b"new slicer cache")
        self.assertEqual(self.store.current(self.snapshot), capture)
        Path(capture.copy_path).write_bytes(b"changed stored artifact")
        with self.assertRaises(StaleArtifactError):
            self.store.current(self.snapshot)
        self.assertIsNone(self.store.captured)

    def test_revision_plate_session_and_transform(self):
        self.begin()
        self.finish()
        geometry = copy.deepcopy(self.snapshot)
        geometry.objects[0]["instances_data"][0]["matrix"][1][3] += 1.0
        for changed in (
            geometry,
            replace(self.snapshot, plate_index=4),
            replace(self.snapshot, session_id="reopened"),
            replace(
                self.snapshot, settings={**self.snapshot.settings, "wall_loops": "3"}
            ),
        ):
            with (
                self.subTest(revision=changed.revision),
                self.assertRaises(StaleArtifactError),
            ):
                self.store.current(changed)

    def test_snapshot_cannot_silently_change_between_begin_and_finish(self):
        initial_revision = self.snapshot.revision
        self.begin()
        self.snapshot.objects[0]["instances_data"][0]["matrix"][0][3] += 7.0
        try:
            capture = self.finish()
        except StaleArtifactError:
            return
        self.assertEqual(capture.revision, initial_revision)
        with self.assertRaises(StaleArtifactError):
            self.store.current(self.snapshot)

    def test_cancel_invalidates_callbacks_and_prior_capture(self):
        self.begin()
        self.finish()
        self.begin()
        with self.assertRaises(StaleArtifactError):
            self.store.finish(self.snapshot.session_id, str(self.source), success=False)
        with self.assertRaises(StaleArtifactError):
            self.finish()
        self.assertIsNone(self.store.captured)

    def test_wrong_ids_path_and_missing_labels(self):
        with self.assertRaises(WaveError):
            self.store.begin(self.snapshot, {0: "999999"})
        self.store.begin(self.snapshot, {42: "100"})
        self.store.export_started(self.snapshot.session_id, str(self.source))
        with self.assertRaises(WaveError):
            self.finish()
        self.begin()
        with self.assertRaises(StaleArtifactError):
            self.store.finish("another-model", str(self.source))
        other = self.allowed / "other.gcode"
        other.write_bytes(self.data)
        with self.assertRaises(StaleArtifactError):
            self.finish(other)
        self.source.write_bytes(self.data.replace(b"; printing object", b"; absent"))
        with self.assertRaises(WaveError):
            self.finish()
        self.assertIsNone(self.store.captured)

    def test_real_file_outside_allowed_root_is_refused(self):
        lookalike = self.allowed.with_name("slicer-untrusted")
        lookalike.mkdir()
        outside = lookalike / self.source.name
        outside.write_bytes(self.data)
        self.begin(outside)
        with self.assertRaises(WaveError):
            self.finish(outside)
        self.assertFalse((self.store.storage / "captures").exists())

    def test_host_source_filter_accepts_only_matching_job_export_inside_root(self):
        host = NativeHost()
        source_root = self.allowed
        store = CaptureStore(
            self.store.storage, (source_root,), source_validator=host.validate_source
        )
        pid = os.getpid()
        snapshot=replace(self.snapshot,session_id="7")
        model = snapshot.session_id
        suffix = (
            Path("orcaslicer_model")
            / f"cache#{pid}#59"
            / "Metadata"
            / f".{pid}.7.gcode"
        )
        valid = source_root / suffix
        paths = [
            source_root / "unrelated.gcode",
            self.allowed.parent / "elsewhere" / suffix,
            valid.with_name(f".{pid + 1}.7.gcode"),
            source_root
            / "orcaslicer_model"
            / f"cache#{pid}#other"
            / "Metadata"
            / valid.name,
        ]
        for path in [*paths, valid]:
            with self.subTest(path=path):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(self.data)
                store.begin(snapshot, self.ids)
                store.export_started(model, str(path))
                if path == valid:
                    self.assertEqual(
                        store.finish(model, str(path)).sha256, digest(self.data)
                    )
                else:
                    with self.assertRaises(WaveError):
                        store.finish(model, str(path))
