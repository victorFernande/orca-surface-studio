import unittest
from orca_wave_studio.contracts import WaveError
from orca_wave_studio.engine_parser import read
from orca_wave_studio.fixtures import cylinder_gcode


class ProfileParserTests(unittest.TestCase):
    def test_custom_start_is_preserved_but_unknown_in_body_is_rejected(self):
        source=cylinder_gcode()
        source=b'START_PRINT BED=60\n'+source
        parsed=read(source,{'100'},{0:'100'},profile_macros=True)
        self.assertTrue(parsed.seen)
        # A firmware macro inside deposition cannot silently change coordinates.
        inside=source.replace(b';TYPE:Outer wall',b'SET_GCODE_OFFSET Z=2\n;TYPE:Outer wall',1)
        with self.assertRaises(WaveError):read(inside,{'100'},{0:'100'},profile_macros=True)

    def test_start_macro_requires_explicit_e_mode_before_any_extrusion(self):
        source=b'START_PRINT\nG90\nG1 E1\n'
        with self.assertRaisesRegex(WaveError,'M82/M83'):read(source,set(),{},profile_macros=True)
