import json
from pathlib import Path
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from orca_wave_studio import package


class MetadataTests(unittest.TestCase):
    def test_changed_gcode_drops_old_time_and_replaces_native_material_stats(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"source.3mf"
            output=Path(folder)/"result.gcode.3mf"
            with ZipFile(source,"w") as archive:
                archive.writestr(package.PROJECT,json.dumps({"filament_type":["PETG"],"nozzle_diameter":["0.4"]}))
                archive.writestr(package.SETTINGS,'<config><plate><metadata key="plater_id" value="1"/></plate></config>')
                archive.writestr(package.SLICE,'<config><plate><metadata key="index" value="1"/><metadata key="prediction" value="9999"/><metadata key="weight" value="999"/><filament id="1" type="PETG" used_g="999" used_m="999"/></plate></config>')
                archive.writestr('Metadata/plate_1.gcode',b'; original\n')
            gcode=b'G1 X10 E1\n; filament used [mm] = 10.00\n; filament used [g] = 0.03\n'
            package.build_sliced_package(gcode,output,project_3mf=source)
            with ZipFile(output) as archive:
                plate=ET.fromstring(archive.read(package.SLICE)).find('plate')
                values={item.get('key'):item.get('value') for item in plate.findall('metadata')}
                self.assertNotIn('prediction',values)
                self.assertEqual(float(values['weight']),.03)
                self.assertEqual(float(plate.find('filament').get('used_g')),.03)
                self.assertEqual(float(plate.find('filament').get('used_m')),.01)
