"""Prepared queries must retain complete certificates and actual endpoint error."""
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
import test_spline_phase as fixtures
from orca_wave_studio.surface_coordinates import SurfaceCoordinates
from orca_wave_studio.continuous_layers import LayerGridStage
from orca_wave_studio.regional_shell import RegionalShellSettings
from orca_wave_studio.conformal import _gap_and_scale


class PreparedCoordinateTests(unittest.TestCase):
    def warp(self):
        w=SurfaceCoordinates();w.grid=fixtures.SplinePhaseTests().field()
        w.layer_grid=LayerGridStage([.5,3.6,8.5],[.5,3.5,8.5])
        w.anchor_z=.5;w.settings=RegionalShellSettings(retain_native_short_edges=True)
        return w

    def test_prepared_chord_covers_curve_and_emitted_rounding(self):
        w=self.warp();a=(3.,4.,4.);b=(3.32,4.08,4.)
        move=SimpleNamespace(start=a,end=b,deposits=True)
        w.prepare_layer([move],.2)
        pa=tuple(round(x,6) for x in w.map_point(a));pb=tuple(round(x,6) for x in w.map_point(b))
        cached=w.chord_error_bound(a,b,pa,pb)
        for t in np.linspace(0,1,201):
            point=tuple(x+(y-x)*t for x,y in zip(a,b))
            chord=tuple(x+(y-x)*t for x,y in zip(pa,pb))
            self.assertLessEqual(math.dist(w.map_point(point),chord),cached)
        shifted=(pa[0],pa[1],pa[2]+.01)
        self.assertGreaterEqual(w.chord_error_bound(a,b,shifted,pb),cached+.009998)
        # Switching grids invalidates the prepared certificate even with the
        # same input points. Compare with a fresh uncached coordinate wrapper.
        w.layer_grid=LayerGridStage([.5,3.6,8.5],[.5,3.9,8.5])
        fresh=self.warp();fresh.grid=w.grid;fresh.layer_grid=w.layer_grid
        self.assertEqual(w.chord_error_bound(a,b,pa,pb),fresh.chord_error_bound(a,b,pa,pb))

    def test_global_short_chord_proof_covers_full_curve_and_boundary(self):
        w=self.warp();rng=np.random.default_rng(491)
        for a in rng.uniform([-.1,1,.45],[9.9,9,8.2],(150,3)):
            b=a+np.r_[rng.uniform(-.14,.14,2),0.]
            bound=w._planar_chord_bound(a,b);pa=w.map_point(a);pb=w.map_point(b)
            for t in np.linspace(0,1,41):
                p=a+(b-a)*t;q=np.asarray(pa)+(np.asarray(pb)-pa)*t
                self.assertLessEqual(math.dist(w.map_point(p),q),bound+2e-9)
        self.assertTrue(math.isinf(w._planar_chord_bound((3,4,4),(3,4,5))))

    def test_prepared_travel_chords_cross_layer_grid_corners_and_base(self):
        w=self.warp()
        moves=[SimpleNamespace(start=(3.,4.,2.8),end=(3.2,4.1,4.1),deposits=False),
               SimpleNamespace(start=(4.,4.,.24),end=(4.1,4.,.8),deposits=False)]
        w.prepare_layer(moves,.2)
        self.assertFalse(w._prepared_chords,'nonplanar grid crossings retain the complete scalar fallback')
        for move in moves:
            a,b=move.start,move.end;p,q=w.map_point(a),w.map_point(b)
            pa=tuple(round(x,6) for x in p);pb=tuple(round(x,6) for x in q)
            bound=w.chord_error_bound(a,b,pa,pb)
            for t in np.linspace(0,1,101):
                u=np.asarray(a)+t*(np.asarray(b)-a)
                v=np.asarray(pa)+t*(np.asarray(pb)-pa)
                self.assertLessEqual(math.dist(w.map_point(u),v),bound+2e-9)

    def test_paired_cell_cache_uses_pitch_and_current_grids(self):
        w=self.warp();point=(4.,4.,3.6)
        for pitch in (.15,.2,.24):
            scale=w.volume_scale(*point,pitch)
            expected=(pitch*scale/math.hypot(1,*w.gradient(*point)),scale)
            self.assertEqual(_gap_and_scale(w,point,pitch),expected)
            self.assertEqual(w.normal_gap(*point,pitch),expected[0])
        previous=w.gap_and_scale(*point,.2)
        w.layer_grid=LayerGridStage([.5,3.6,8.5],[.5,3.9,8.5])
        now=w.gap_and_scale(*point,.2)
        self.assertNotEqual(previous,now)
        self.assertEqual(now[1],w.volume_scale(*point,.2))

    def test_short_preflight_does_not_prepare_beads_or_change_inverse(self):
        w=self.warp();a=(3.,4.,4.);b=(3.05,4.02,4.)
        expected=[w.map_point(p) for p in (a,b)]
        with patch.object(w.grid,'evaluate',wraps=w.grid.evaluate) as evaluate:
            w.prepare_short_edges([SimpleNamespace(start=a,end=b,deposits=True)],.2)
        # The inverse itself needs d/dZ for Newton, but preflight does not need
        # the two additional XY differential evaluations used by finite beads.
        self.assertTrue(all(len(call.args)==1 or call.args[1]==(0,0,1) for call in evaluate.call_args_list))
        np.testing.assert_allclose([w.map_point(p) for p in (a,b)],expected,rtol=0,atol=2e-9)
        self.assertFalse(w.grid._prepared_differentials)

