import unittest
from orca_wave_studio.contracts import WaveParameters
from orca_wave_studio.engine import process_gcode
from orca_wave_studio.engine_parser import read
from orca_wave_studio.fixtures import cylinder_gcode,cylinder_snapshot
from orca_wave_studio.printer_profile import PrinterProfile
from orca_wave_studio.profile_limits import limit_result


class WaveProfileLimitTests(unittest.TestCase):
    def test_all_wave_modes_obey_another_profiles_z_and_flow_without_moving_points(self):
        settings={**cylinder_snapshot().settings,'printer_settings_id':'Slow Z test machine',
                  'machine_max_speed_z':['.05'],'machine_max_acceleration_z':['2'],
                  'filament_max_volumetric_speed':['.15']}
        profile=PrinterProfile.from_settings(settings)
        for mode in ('xy','z','combined'):
            with self.subTest(mode=mode):
                original=process_gcode(cylinder_gcode(layers=12),{'100':WaveParameters(mode=mode,amplitude_mm=.04,start_height_mm=.4)},{0:'100'})
                limited=limit_result(original,profile,{0:'100'})
                before=read(original.gcode,{'100'},{0:'100'},require_planar=False)
                after=read(limited.gcode,{'100'},{0:'100'},require_planar=False)
                a=[(m.end,m.de) for m in before.moves.values() if m.start!=m.end or m.de]
                b=[(m.end,m.de) for m in after.moves.values() if m.start!=m.end or m.de]
                self.assertEqual(a,b)
                report=limited.report['profile_limits']
                self.assertGreater(report['feed_changes'],0)
                self.assertGreater(limited.report['estimates']['processed_selected_deposition_seconds'],
                                   original.report['estimates']['processed_selected_deposition_seconds'])
                self.assertLessEqual(report['max_z_speed_mm_s'],.05+1e-9)
                self.assertLessEqual(report['max_z_acceleration_mm_s2'],2+1e-9)
                self.assertLessEqual(report['max_volumetric_mm3_s'],.15+1e-9)
