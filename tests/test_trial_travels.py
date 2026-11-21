import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from orca_wave_studio.trial_travels import lift_trial_travels
from orca_wave_studio.engine_parser import read
from orca_wave_studio.contracts import WaveError

SOURCE = b'''G90
M83
M104 S200
G1 X10 Y10 Z0.2 F1200
;LAYER_CHANGE
;Z:2
;HEIGHT:0.2
; printing object sample id:0 copy 0
;TYPE:Outer wall
;WIDTH:0.4
G1 Z2
G1 X20 E1
G1 E-0.5 F1800
G1 X30 Y30 Z1.8 F3600
G1 E0.5 F1800
G1 F1200
G1 X31 E1
; stop printing object sample id:0 copy 0
'''


def moves(source):
    return list(read(source, set(), {0:'1'}).moves.values())


class TrialTravelTests(unittest.TestCase):
    def transform(self, source=SOURCE, **options):
        return lift_trial_travels(source, {0:'1'}, anchor_z_mm=1., clearance_mm=3.,
                                 maximum_z_mm=options.get('maximum_z_mm',250.))

    def test_lift_uses_printed_prefix_and_preserves_every_deposition_and_feed(self):
        result,report=self.transform()
        a=[(m.start,m.end,m.fields.get('E'),m.f) for m in moves(SOURCE) if m.deposits]
        b=[(m.start,m.end,m.fields.get('E'),m.f) for m in moves(result) if m.deposits]
        self.assertEqual(a,b)
        xy=[m for m in moves(result) if not m.deposits and m.start[:2]!=m.end[:2] and m.end[:2]==(30.,30.)]
        self.assertEqual(len(xy),1)
        self.assertEqual(xy[0].start[2],5.)
        self.assertEqual(xy[0].end[2],5.)
        self.assertEqual(report['changed_travels'],1)
        self.assertFalse(report['print_allowed'])
        self.assertIn(b'M104 S200',result)

    def test_absolute_e_keeps_following_state(self):
        source=SOURCE.replace(b'M83',b'M82').replace(b'E-0.5',b'E0.5')
        source=source.replace(b'G1 E0.5 F1800\nG1 F1200',b'G1 E1 F1800\nG1 F1200')
        source=source.replace(b'G1 X31 E1',b'G1 X31 E2')
        result,_=self.transform(source)
        self.assertAlmostEqual(moves(result)[-1].e,moves(source)[-1].e)
        self.assertAlmostEqual(sum(m.de for m in moves(result) if m.deposits),2.)

    def test_spatial_retraction_occurs_before_lift_without_changing_e(self):
        source=SOURCE.replace(b'G1 X30 Y30 Z1.8 F3600',b'G1 X30 Y30 Z1.8 E-0.25 F1800')
        result,_=self.transform(source)
        self.assertAlmostEqual(sum(m.de for m in moves(result)),sum(m.de for m in moves(source)))
        self.assertLess(result.index(b'preserve source retraction'),result.index(b'OWS prefix clearance'))

    def test_flat_base_is_byte_identical(self):
        source=SOURCE.replace(b'G1 Z2\n',b'G1 Z0.4\n').replace(b';Z:2\n',b';Z:0.4\n')
        result,report=self.transform(source)
        self.assertEqual(result,source)
        self.assertEqual(report['changed_travels'],0)

    def test_limits_and_relative_xyz_are_refused(self):
        with self.assertRaises(WaveError):self.transform(maximum_z_mm=4.9)
        with self.assertRaises(WaveError):self.transform(SOURCE.replace(b'G90',b'G91'))
        with self.assertRaises(WaveError):
            lift_trial_travels(SOURCE,{0:'1'},anchor_z_mm=1.,clearance_mm=float('nan'),maximum_z_mm=250.)


if __name__=='__main__':unittest.main()
