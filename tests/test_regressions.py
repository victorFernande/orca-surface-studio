import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from orca_wave_studio.contracts import WaveError, WaveParameters
from orca_wave_studio.engine import process_gcode
from orca_wave_studio.fixtures import cylinder_gcode


class RegressionTests(unittest.TestCase):
    def test_own_output_cannot_be_deformed_again(self):
        params={"100":WaveParameters(amplitude_mm=.02,start_height_mm=.2,end_height_mm=1.6,fade_layers=2)}
        output=process_gcode(cylinder_gcode(layers=8),params,{0:"100"})
        with self.assertRaisesRegex(WaveError,"já contém ondas"):
            process_gcode(output.gcode,params,{0:"100"})
