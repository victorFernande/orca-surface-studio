import math
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from orca_wave_studio.inclined_coupon_trial import (PITCH,BASE,SLOPE,FLAT_BOTTOM,
    upper_proxy,unflatten,cut_fraction,render_held_trial)
from orca_wave_studio.engine_parser import read
from orca_wave_studio.contracts import WaveError


class InclinedTrialTests(unittest.TestCase):
    def test_proxy_is_closed_and_shear_round_trip_keeps_original_roof(self):
        snapshot=upper_proxy()
        self.assertEqual(len(snapshot.objects),5)
        for obj in snapshot.objects:
            vol=obj['volumes'][0]
            edges=Counter(tuple(sorted((tri[j],tri[(j+1)%3])))
                for tri in vol['triangles'] for j in range(3))
            self.assertEqual(set(edges.values()),{2})
        original=[unflatten(p) for p in snapshot.objects[0]['volumes'][0]['vertices'] if p[0]<190]
        self.assertAlmostEqual(max(p[2] for p in original),5.+10*SLOPE)
        self.assertAlmostEqual(min(p[2] for p in original),1.-PITCH/2)
        for x in (105.,110.,115.):
            a=unflatten((x,110.,FLAT_BOTTOM))
            b=unflatten((x,110.,FLAT_BOTTOM+PITCH))
            self.assertAlmostEqual(b[2]-a[2],PITCH)
        self.assertLess(PITCH*math.cos(math.radians(25)),.28)

    def test_exact_clipped_cell_integral(self):
        self.assertAlmostEqual(cut_fraction(BASE-PITCH,BASE+2*PITCH),.5)
        self.assertAlmostEqual(cut_fraction(BASE+.25*PITCH,BASE+.75*PITCH),.5)
        self.assertEqual(cut_fraction(2,3),1.)
        self.assertEqual(cut_fraction(0,.9),0.)
        with self.assertRaises(WaveError):cut_fraction(1,2,float('nan'))

    def sources(self):
        base=b'''G90\nM83\nG1 X106 Y106 Z1 F1200\n;LAYER_CHANGE\n;Z:1\n;HEIGHT:0.2\n; printing object coupon id:0 copy 0\n;TYPE:Outer wall\n;WIDTH:0.4\nG1 X107 E1\n; stop printing object coupon id:0 copy 0\n'''
        z=1.1- (3.+SLOPE)+FLAT_BOTTOM
        upper=f'''G90\nM83\nG1 X114 Y106 Z{z:.9f} F1200\n;LAYER_CHANGE\n;Z:{z:.9f}\n;HEIGHT:{PITCH:.9f}\n; printing object upper id:0 copy 0\n;TYPE:Outer wall\n;WIDTH:0.4\nG1 X113.6 E1 F1200\n; stop printing object upper id:0 copy 0\n'''.encode()
        return base,upper

    def test_flat_base_unchanged_and_partial_cell_extrusion_integrates_without_length_scale(self):
        base,upper=self.sources()
        result,report=render_held_trial(base,upper)
        self.assertTrue(result.startswith(base.split(b'; stop printing')[0]))
        self.assertFalse(report['print_allowed'])
        parsed=read(result,set(),{0:'1'})
        emitted=[m for m in parsed.moves.values() if m.deposits][1:]
        self.assertGreater(emitted[-1].start[2],emitted[-1].end[2]-1)
        expected=cut_fraction(1.1,1.1+.4*SLOPE)
        self.assertAlmostEqual(sum(m.de for m in emitted),expected,places=7)
        self.assertEqual(report['lifted_transfers'],1)
        self.assertEqual(report['shear_jacobian'],1.)
        self.assertIn(b'PRINT DISABLED',result)

    def test_source_retractions_and_below_base_motion_refused(self):
        base,upper=self.sources()
        with self.assertRaises(WaveError):
            render_held_trial(base,upper.replace(b';LAYER_CHANGE',b'G1 E-0.5\n;LAYER_CHANGE'))
        with self.assertRaises(WaveError):
            render_held_trial(base,upper.replace(b'G1 X113.6',b'G1 X115.0'))

    def test_native_block_boundaries_and_preview_metadata_are_complete(self):
        base,upper=self.sources()
        base=(b'; HEADER_BLOCK_START\n; total layer number: 99\n; max_z_height: 99\n'
              b'; HEADER_BLOCK_END\n; EXECUTABLE_BLOCK_START\n'+base+
              b'; EXECUTABLE_BLOCK_END\n; CONFIG_BLOCK_START\n; filament_diameter = 1.75\n'
              b'; CONFIG_BLOCK_END\n')
        result,report=render_held_trial(base,upper)
        self.assertEqual(result.count(b'; EXECUTABLE_BLOCK_END'),1)
        self.assertEqual(result.count(b'; CONFIG_BLOCK_START'),1)
        self.assertIn(b'; total layer number: 2\n',result)
        self.assertNotIn(b'max_z_height: 99',result)
        self.assertIn(b';TYPE:Outer wall\n',result)
        self.assertEqual(result.count(b'; printing object'),result.count(b'; stop printing object'))


if __name__=='__main__':unittest.main()
