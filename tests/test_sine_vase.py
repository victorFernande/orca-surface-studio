import math
import unittest
from dataclasses import replace
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from orca_wave_studio.contracts import WaveError, WaveParameters
from orca_wave_studio.engine import process_gcode
from test_engine import example, replay


def params(**changes):
    return WaveParameters(mode="combined", amplitude_mm=.6, wave_count=6,
                          z_ratio=.5, start_height_mm=.4, **changes)


def vase_source(*, seam_gap=False, absolute=False, relative_xyz=False):
    source = example(layers=20, absolute=absolute, relative_xyz=relative_xyz, second=True)
    if seam_gap:
        # Preserve a real source seam gap; do not append an extrusion to close it.
        lines = source.decode().splitlines(keepends=True)
        drops = [i-1 for i, line in enumerate(lines) if line.startswith('; stop printing object')]
        source = ''.join(line for i, line in enumerate(lines) if i not in drops).encode()
    return source


class SineVaseTests(unittest.TestCase):
    def test_sv06_start_resets_and_axis_shutdown_are_preserved(self):
        source=vase_source()
        source=b'M220 S100\nM221 S100\nM420 S1\n'+source+b'M84 X Y E\n'
        result=process_gcode(source,{'A':params()},{0:'A',1:'B'})
        self.assertTrue(result.gcode.startswith(b'M220 S100\nM221 S100\nM420 S1\n'))
        self.assertIn(b'M84 X Y E',result.gcode)
        with self.assertRaises(WaveError):
            process_gcode(source.replace(b'M221 S100',b'M221 S130'),{'A':params()},{0:'A',1:'B'})

    def test_coupled_radial_and_z_with_progressive_amplitude(self):
        source = vase_source()
        p = params()
        result = process_gcode(source, {'A': p}, {0: 'A', 1: 'B'})
        rows = replay(result.gcode)
        top = [r for r in rows if r[0] == 19 and r[1] == 0 and r[4] > 0]
        self.assertGreater(len(top), 80)
        zs = [r[3][2] for r in top]
        radii = [math.hypot(*r[3][:2]) for r in top]
        self.assertAlmostEqual(max(zs)-min(zs), .6, delta=.004)
        self.assertAlmostEqual(max(radii)-min(radii), 1.2, delta=.01)
        self.assertTrue(any(r[3][2] < r[2][2] for r in top))
        self.assertTrue(any(r[3][2] > r[2][2] for r in top))
        for r in top:
            x,y,z = r[3]
            expected = 4-.5*.6*math.sin(6*math.atan2(y,x))
            self.assertAlmostEqual(z, expected, delta=.00003)
        self.assertFalse(result.report['print_allowed'])
        self.assertLessEqual(result.report['max_geometric_error_mm'], .02)
        self.assertGreaterEqual(result.report['min_segment_mm'], .15)
        self.assertLessEqual(result.report['max_z_speed_mm_s'], p.max_z_speed_mm_s)
        self.assertLessEqual(result.report['max_z_acceleration_mm_s2'], p.max_z_acceleration_mm_s2+1e-10)
        before = [r for r in replay(source) if r[1] == 1 or r[0] < 2]
        after = [r for r in rows if r[1] == 1 or r[0] < 2]
        self.assertEqual(len(before),len(after))
        for a,b in zip(before,after):
            self.assertLess(math.dist(a[3],b[3]), .00002)
            self.assertAlmostEqual(a[4],b[4], places=7)
        self.assertEqual(result, process_gcode(source, {'A': p}, {0:'A',1:'B'}))

    def test_open_native_seam_and_variable_radius(self):
        # A 0.04 mm gap is smaller than Orca's usual bead width. The open
        # fixture reproduces modal roles and native progress commands.
        from pathlib import Path
        source=(Path(__file__).parent/'fixtures/orca_2_5_1_open_seam.gcode').read_bytes()
        p=replace(params(),start_height_mm=1,amplitude_mm=.1)
        result=process_gcode(source, {'83':p}, {0:'83'})
        self.assertGreater(result.report['segments'],0)
        self.assertFalse(result.report['print_allowed'])

    def test_modes_keep_following_extrusion_and_positions(self):
        for absolute, relative in ((False,False),(True,False),(False,True),(True,True)):
            with self.subTest(absolute=absolute,relative=relative):
                source=vase_source(absolute=absolute,relative_xyz=relative)
                result=process_gcode(source,{'A':params()},{0:'A',1:'B'})
                old=[r for r in replay(source) if r[1]==1]
                new=[r for r in replay(result.gcode) if r[1]==1]
                for a,b in zip(old,new):
                    self.assertLess(math.dist(a[3],b[3]),.00003)
                    self.assertAlmostEqual(a[4],b[4],places=7)

    def test_bad_settings_and_impossible_vertical_transition(self):
        for patch in ({'wave_count':2.5},{'wave_count':0},{'z_ratio':0},{'twist_deg_per_mm':1}):
            with self.assertRaises(WaveError):
                replace(params(),**patch)
        p=replace(params(),amplitude_mm=1.9,z_ratio=1,start_height_mm=3.8)
        with self.assertRaisesRegex(WaveError,'transição'):
            process_gcode(vase_source(),{'A':p},{0:'A',1:'B'})

    def test_volume_matches_cylindrical_map_for_constant_height_band(self):
        # Integrate the emitted filament independently over a full circle.
        # detJ averaged over theta is 1-q*Amean*dA/(2*r*h).
        source=example(layers=20,polygon=[(5*math.cos(i*math.tau/320),5*math.sin(i*math.tau/320)) for i in range(320)])
        p=params()
        result=process_gcode(source,{'A':p},{0:'A',1:'B'})
        old=sum(r[4] for r in replay(source) if r[0]==19 and r[1]==0 and r[4]>0)
        new=sum(r[4] for r in replay(result.gcode) if r[0]==19 and r[1]==0 and r[4]>0)
        a=.6
        prev=.6*((3.8-.4)/(4-.4))**2
        expected=1-.5*((a+prev)/2)*(a-prev)/(2*5*.2)
        self.assertAlmostEqual(new/old,expected,delta=.0001)


if __name__ == '__main__':
    unittest.main()
