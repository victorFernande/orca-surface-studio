import hashlib
from pathlib import Path
import tempfile
import unittest
import warnings
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile
import xml.etree.ElementTree as ET

from orca_wave_studio.contracts import WaveError, digest
from orca_wave_studio import package


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dest = self.root / "result.gcode.3mf"
        self.gcode = b"; study\r\nG1 X1.25\n; trailer\r\n"

    def rewrite(self, update, path=None):
        path = path or self.dest
        with ZipFile(path) as z:
            items = {name: z.read(name) for name in z.namelist()}
        update(items)
        with ZipFile(path, "w", ZIP_DEFLATED) as z:
            for name, data in items.items():
                z.writestr(name, data)

    def test_round_trip_plate_two(self):
        report = package.build_sliced_package(self.gcode, self.dest, plate_index=1)
        self.assertTrue(report["synthetic_metadata"])
        self.assertEqual(report["gcode_sha256"], digest(self.gcode))
        self.assertEqual(report["package_sha256"], digest(self.dest.read_bytes()))
        self.assertEqual(package.extract_plate_gcode(self.dest, 1), self.gcode)
        with self.assertRaises(WaveError):
            package.extract_plate_gcode(self.dest, 0)
        with ZipFile(self.dest) as z:
            self.assertEqual(z.read("Metadata/plate_2.gcode.md5"),
                             hashlib.md5(self.gcode).hexdigest().upper().encode())
            model = ET.fromstring(z.read(package.MODEL))
            self.assertFalse(model.findall(".//{*}object"))
            self.assertFalse(model.findall(".//{*}item"))
            config = ET.fromstring(z.read(package.SETTINGS))
            self.assertEqual([p.find("metadata").get("value") for p in config.findall("plate")], ["1", "2"])

    def test_preserve_project_selected_plate_assets_and_drop_geometry(self):
        project = self.root / "source.3mf"
        settings = b'{"filament_type":["PLA"],"nozzle_diameter":["0.4"],"filament_colour":["#123456"]}'
        with ZipFile(project, "w") as z:
            z.writestr(package.MODEL, b"<model><resources><object/></resources></model>")
            z.writestr(package.PROJECT, settings)
            z.writestr("Metadata/machine_settings_1.config", b'{"name":"M1"}')
            z.writestr("3D/Objects/original.model", b"x")
            z.writestr("Metadata/plate_1.png", b"fixture 1")
            z.writestr("Metadata/plate_2.png", b"fixture 2")
            z.writestr(package.SETTINGS, b'<config><plate><metadata key="plater_id" value="1"/></plate>'
                       b'<plate><metadata key="plater_id" value="2"/><metadata key="thumbnail_file" '
                       b'value="Metadata/plate_2.png"/><model_instance/></plate></config>')
            z.writestr(package.SLICE, b'<config><plate><metadata key="index" value="2"/>'
                       b'<filament id="1" type="PLA"/></plate></config>')
        original = project.read_bytes()
        report = package.build_sliced_package(self.gcode, self.dest, project_3mf=project, plate_index=1)
        self.assertEqual(report["slice_metadata_source"], "native")
        self.assertEqual(original, project.read_bytes())
        with ZipFile(self.dest) as z:
            self.assertNotIn("3D/Objects/original.model", z.namelist())
            self.assertNotIn("Metadata/plate_1.png", z.namelist())
            self.assertEqual(z.read("Metadata/plate_2.png"), b"fixture 2")
            self.assertEqual(z.read(package.PROJECT), settings)
            self.assertNotIn(b"model_instance", z.read(package.SETTINGS))
            self.assertIn(b'type="PLA"', z.read(package.SLICE))
            self.assertIn("Metadata/machine_settings_1.config", z.namelist())
        self.rewrite(lambda parts: parts.pop(package.SLICE), project)
        data = self.gcode + b"; filament used [mm] = 10.00\n; filament used [g] = 0.03\n"
        result = package.build_sliced_package(data, self.dest, project_3mf=project, plate_index=1)
        self.assertEqual(result["slice_metadata_source"], "project_and_gcode")
        with ZipFile(self.dest) as z:
            self.assertIn(b'used_m="0.01"', z.read(package.SLICE))

    def test_reject_mutations(self):
        name = "Metadata/plate_1.gcode"
        mutations = [
            lambda parts: parts.pop(name), lambda parts: parts.pop(name + ".md5"),
            lambda parts: parts.update({name: b"tampered"}),
            lambda parts: parts.update({"Metadata/plate_2.gcode": b"unrelated"}),
            lambda parts: parts.update({"../file": b"x"}),
            lambda parts: parts.update({"C:/temp/x": b"x"}),
            lambda parts: parts.update({name.upper(): b"duplicate"}),
            lambda parts: parts.update({package.MODEL_RELS: b"<Relationships/>"}),
            lambda parts: parts.pop(package.MODEL),
            lambda parts: parts.update({"_rels/.rels": b"<Relationships/>"}),
            lambda parts: parts.update({package.SLICE: b"<config/>"}),
            lambda parts: parts.update({package.SETTINGS: parts[package.SETTINGS].replace(b'plate_1.gcode', b'plate_2.gcode')}),
            lambda parts: parts.update({"Metadata/bomb.txt": b"A" * (2 << 20)}),
        ]
        for i, mutate in enumerate(mutations):
            with self.subTest(mutation=i):
                package.build_sliced_package(self.gcode, self.dest)
                self.rewrite(mutate)
                with self.assertRaises(WaveError):
                    package.extract_plate_gcode(self.dest)
        package.build_sliced_package(self.gcode, self.dest)
        with warnings.catch_warnings(), ZipFile(self.dest, "a") as z:
            warnings.simplefilter("ignore", UserWarning)
            z.writestr(name, self.gcode)
        with self.assertRaises(WaveError):
            package.extract_plate_gcode(self.dest)

    def test_backslash_in_raw_zip_member(self):
        package.build_sliced_package(self.gcode, self.dest)
        self.rewrite(lambda parts: parts.update({"Metadata/test-name": b"x"}))
        # The Windows ZipFile writer normalizes slashes. Patch both ZIP name records directly.
        self.dest.write_bytes(self.dest.read_bytes().replace(b"Metadata/test-name", b"Metadata\\test-name"))
        with self.assertRaises(WaveError):
            package.extract_plate_gcode(self.dest)

    def test_atomic_failure(self):
        self.dest.write_bytes(b"previous")
        with patch.object(package, "extract_plate_gcode", return_value=b"different"):
            with self.assertRaises(WaveError):
                package.build_sliced_package(self.gcode, self.dest)
        self.assertEqual(self.dest.read_bytes(), b"previous")
        self.assertEqual(list(self.root.iterdir()), [self.dest])
