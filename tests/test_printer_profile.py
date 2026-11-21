import copy
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from orca_wave_studio.contracts import WaveError
from orca_wave_studio.prepared_model import exported_settings
from orca_wave_studio.printer_profile import PrinterProfile


def settings(**overrides):
    return {'printer_settings_id':'Machine A','gcode_flavor':'marlin','nozzle_diameter':['0.4'],
            'filament_diameter':['1.75'],'layer_height':'0.2','initial_layer_print_height':'0.24',
            'machine_max_speed_z':['4','5'],'machine_max_acceleration_z':['80','100'],
            'filament_max_volumetric_speed':['8'],'printable_height':'180',
            'printable_area':['0x0','180x0','180x180','0x180'],**overrides}


class ProfileTests(unittest.TestCase):
    def test_profile_selection_drives_limits_without_brand_defaults(self):
        a=PrinterProfile.from_settings(settings())
        b=PrinterProfile.from_settings(settings(printer_settings_id='Machine B',gcode_flavor='klipper',
                nozzle_diameter=['0.6'],layer_height='.28',machine_max_speed_z=['12'],
                machine_max_acceleration_z=['300'],printable_area=['-150x-150','150x-150','150x150','-150x150']))
        self.assertEqual((a.z_speed_mm_s,b.z_speed_mm_s),(4,12))
        self.assertEqual((a.nozzle_mm,b.nozzle_mm),(.4,.6))
        self.assertEqual(b.layer_mm,.28)
        self.assertFalse(a.contains((-10,0,1)));self.assertTrue(b.contains((-10,0,1)))
        self.assertNotEqual(a.revision,b.revision)

    def test_round_bed_uses_polygon_not_only_bounding_box(self):
        p=PrinterProfile.from_settings(settings(printable_area=['0x-90','90x0','0x90','-90x0']))
        self.assertTrue(p.contains((0,0,1)));self.assertFalse(p.contains((80,80,1)))
        self.assertTrue(p.contains((45,45,180)));self.assertFalse(p.contains((0,0,181)))

    def test_missing_limits_or_belt_frame_are_explicit(self):
        x=settings();x.pop('machine_max_speed_z')
        with self.assertRaisesRegex(WaveError,'machine_max_speed_z'):PrinterProfile.from_settings(x)
        with self.assertRaisesRegex(WaveError,'PROFILE_FRAME'):PrinterProfile.from_settings(settings(belt_printer='1'))

    def test_serialized_host_vectors_match_exported_json_values(self):
        p=PrinterProfile.from_settings(settings(machine_max_speed_z='4,5',machine_max_acceleration_z='80,100'))
        self.assertEqual(p.z_speed_mm_s,4)
        self.assertEqual(p.z_acceleration_mm_s2,80)

    def test_exported_active_profile_preserves_heating_macros_retraction_and_transport(self):
        original=settings(machine_start_gcode='START_PRINT BED=60\nG90\nM83\n',machine_end_gcode='END_PRINT',
            nozzle_temperature=['205'],hot_plate_temp=['60'],retraction_length=['.8'],
            printer_agent='native_adapter',print_host='http://127.0.0.1:18080',post_process=[])
        before=copy.deepcopy(original)
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'source.3mf'
            with ZipFile(path,'w') as z:z.writestr('Metadata/project_settings.config',json.dumps(original))
            actual=exported_settings(path,active_profile=True)
            for key in before:self.assertEqual(actual[key],before[key],key)
            self.assertEqual(actual['slicing_pipeline_plugin'],[])
            self.assertEqual(actual['gcode_label_objects'],'1')
            self.assertEqual(actual['zaa_enabled'],'0')
            self.assertEqual(original,before)
