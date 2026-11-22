import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from orca_wave_studio.contracts import ProjectSnapshot,WaveError
from orca_wave_studio.geometry import IDENTITY
from orca_wave_studio.printer_profile import PrinterProfile
from orca_wave_studio.regional_shell import RegionalShellSettings
from orca_wave_studio.spline_planning import prepare_spline_warp
from orca_wave_studio.phase_planning import _references


def wedge():
    vertices=[[x,y,z if z==0 else z+.1*x] for z in (0.,4.) for y in (1.,5.) for x in (1.,5.)]
    faces=[[0,2,3],[0,3,1],[4,5,7],[4,7,6],[0,1,5],[0,5,4],
           [2,6,7],[2,7,3],[0,4,6],[0,6,2],[1,3,7],[1,7,5]]
    return ProjectSnapshot('wedge',0,({'id':'1','name':'wedge','config':{},
        'instances_data':[{'id':'1','printable':True,'matrix':IDENTITY}],
        'volumes':[{'id':'1','kind':'part','negative':False,'matrix':IDENTITY,'vertices':vertices,'triangles':faces}]},))


class SplinePlanningTests(unittest.TestCase):
    def test_inclined_reference_is_aligned_without_attenuation_or_source_changes(self):
        source=wedge();before=source.to_dict()
        profile=PrinterProfile('fixture','marlin',.4,1.75,.2,.24,10.,100.,12.,100.,
                               ((0.,0.),(100.,0.),(100.,100.),(0.,100.)),'fixture')
        with tempfile.TemporaryDirectory() as cache:
            warp=prepare_spline_warp(source,'1',RegionalShellSettings(),profile,
                {'min_layer_height':.07,'max_layer_height':.28},cache_folder=cache)
            with patch('orca_wave_studio.spline_planning._solve',side_effect=AssertionError('cache missed')):
                repeated=prepare_spline_warp(source,'1',RegionalShellSettings(),profile,
                    {'min_layer_height':.07,'max_layer_height':.28},cache_folder=cache)
            self.assertTrue(repeated.summary['phase_cache']['proposal_reused'])
            self.assertFalse(repeated.summary['phase_cache']['qualification_reused'])
            self.assertEqual(repeated.map_point((3.,3.,4.)),warp.map_point((3.,3.,4.)))
            self.assertEqual(len(list(Path(cache).glob('*.npz'))),1)
        self.assertEqual(before,source.to_dict())
        self.assertEqual(warp.summary['transition_kernel'],'cubic_spline_phase_v1')
        self.assertFalse(warp.summary['partial_adaptation'])
        self.assertTrue(all(r['core_in_one_band'] for r in warp.summary['reference_alignment']))
        self.assertFalse(warp.summary['print_allowed'])
        self.assertTrue(warp.summary['enforce_height_limits'])
        a,b=(1.,3.,4.1),(5.,3.,4.5)
        self.assertLess(abs(warp.flatten_point(a)[2]-warp.flatten_point(b)[2]),.06)
        self.assertEqual(warp.map_point((2.,2.,.24)),(2.,2.,.24))

    def test_cancellation_precedes_planning_or_slicing(self):
        with self.assertRaisesRegex(WaveError,'cancelada'):
            prepare_spline_warp(wedge(),'1',RegionalShellSettings(),None,{},cancelled=lambda:True)

    def test_large_roof_faces_are_checked_in_the_interior_with_area_weights(self):
        _,regions=_references(wedge(),'1',30.,1.6)
        self.assertEqual(len(regions),1)
        region=regions[0]
        self.assertGreater(len(region['points']),30)
        self.assertAlmostEqual(float(region['weights'].sum()),16.,places=10)
        for point in region['points']:
            self.assertAlmostEqual(point[2],4.+.1*point[0],places=10)
        self.assertTrue(any(2<p[0]<4 and 2<p[1]<4 for p in region['points']))


if __name__=='__main__':unittest.main()
