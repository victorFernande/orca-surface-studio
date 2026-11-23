import unittest
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import numpy as np
from orca_wave_studio.contracts import WaveError
from orca_wave_studio.regional_shell import RegionalShellSettings
from orca_wave_studio.spline_planning import curve_height_certificate,prepare_spline_warp,phase_cache_key,_references
from orca_wave_studio.printer_profile import PrinterProfile
from test_spline_planning import wedge
from orca_wave_studio.curve_height import audit_curve_height


class CurveHeightTests(unittest.TestCase):
    def test_host_rejects_explicit_null_before_reading_project(self):
        from orca_wave_studio.surface_workflow import build_surface
        with tempfile.TemporaryDirectory() as folder,self.assertRaisesRegex(WaveError,'CURVE_HEIGHT'):
            build_surface(wedge(),'1','missing.3mf',folder,'unused',
                          {'backend':'continuous_layers','max_curve_height_mm':None})
    def test_emitted_audit_separates_layers_and_rejects_internal_peaks(self):
        points=[(0,0,.2),(1,0,.3),(0,0,40.),(1,0,40.2)]
        r=audit_curve_height(points,[0,0,100,100],.2)
        self.assertAlmostEqual(r['maximum_deposited_layer_span_mm'],.2)
        self.assertFalse(r['head_clearance_verified'])
        with self.assertRaisesRegex(WaveError,'CURVE_HEIGHT'):
            audit_curve_height([(0,0,2.),(1,0,2.21),(2,0,2.)],[1,1,1],.2)
        with self.assertRaisesRegex(WaveError,'incompleta'):
            audit_curve_height(points,[0],.2)
    def test_range_and_tenths_are_validated_on_host(self):
        for value in (.1,.2,1.,4.9,5.):
            self.assertEqual(RegionalShellSettings(max_curve_height_mm=value).max_curve_height_mm,value)
        for value in (0.,.09,.15,5.1,float('nan'),True,'1'):
            with self.subTest(value=value),self.assertRaises(WaveError):
                RegionalShellSettings(max_curve_height_mm=value)

    def test_certificate_checks_complete_hull_including_zero_extension(self):
        field=SimpleNamespace(coefficients=np.array([.2,.4]))
        certificate=curve_height_certificate(field,.4)
        self.assertEqual(certificate['certified_peak_to_valley_upper_bound_mm'],.4)
        self.assertFalse(certificate['head_clearance_verified'])
        with self.assertRaisesRegex(WaveError,'CURVE_HEIGHT'):
            curve_height_certificate(field,.3)

    def test_limited_wedge_preserves_shape_cache_identity_and_curve_range(self):
        source=wedge();before=source.to_dict()
        profile=PrinterProfile('fixture','marlin',.4,1.75,.2,.24,10.,100.,12.,100.,
                               ((0.,0.),(100.,0.),(100.,100.),(0.,100.)),'fixture')
        settings=RegionalShellSettings(max_curve_height_mm=5.)
        with tempfile.TemporaryDirectory() as cache:
            warp=prepare_spline_warp(source,'1',settings,profile,{'min_layer_height':.07,'max_layer_height':.28},cache_folder=cache)
            with patch('orca_wave_studio.spline_planning._solve',side_effect=AssertionError('cache miss')):
                repeated=prepare_spline_warp(source,'1',settings,profile,{'min_layer_height':.07,'max_layer_height':.28},cache_folder=cache)
            self.assertTrue(repeated.summary['phase_cache']['proposal_reused'])
        self.assertLessEqual(warp.summary['curve_height']['certified_peak_to_valley_upper_bound_mm'],5.+1e-7)
        self.assertEqual(before,source.to_dict())
        points=[warp.map_point((x,3.,4.)) for x in np.linspace(1.,5.,21)]
        self.assertLessEqual(np.ptp([p[2] for p in points]),5.+1e-7)
        self.assertTrue(all(r['core_in_one_band'] for r in warp.summary['reference_alignment']))
        self.assertFalse(warp.summary['curve_height']['head_clearance_verified'])
        mesh,_=_references(source,'1',30.,1.6)
        self.assertNotEqual(phase_cache_key(mesh,profile,.07,.28,30.,.4,1.),
                            phase_cache_key(mesh,profile,.07,.28,30.,.4,.9))

    def test_impossible_limit_rejects_before_material_sampling_or_slicing(self):
        source=wedge();before=source.to_dict()
        with patch('orca_wave_studio.spline_planning.material_samples',side_effect=AssertionError('must reject early')):
            with self.assertRaisesRegex(WaveError,'CURVE_HEIGHT'):
                prepare_spline_warp(source,'1',RegionalShellSettings(max_curve_height_mm=.1),None,{})
        self.assertEqual(before,source.to_dict())
