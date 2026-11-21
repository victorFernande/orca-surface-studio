import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from orca_wave_studio.contracts import WaveError
from orca_wave_studio.engine_parser import read
from orca_wave_studio.fixtures import cylinder_gcode,cylinder_snapshot
from orca_wave_studio.native_surfaces import contour_result,local_settings
from orca_wave_studio.printer_profile import PrinterProfile
from orca_wave_studio.project_io import write_model_project
from orca_wave_studio.package import build_sliced_package,extract_plate_gcode
from orca_wave_studio.surface_workflow import build_surface


class NativeSurfaceTests(unittest.TestCase):
    def test_local_workflow_uses_original_mesh_and_never_calls_roof_inverse_map(self):
        snapshot=cylinder_snapshot();before=snapshot.to_dict()
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);backup=root/'original.3mf';write_model_project(snapshot,backup,snapshot.settings)
            def slicer(executable,model,folder,cancelled,*,workspace):
                folder.mkdir(parents=True);data=self.source();source=folder/'plate_1.gcode';source.write_bytes(data)
                package=folder/'source.gcode.3mf'
                build_sliced_package(data,package,project_3mf=model)
                return source,package
            with patch('orca_wave_studio.surface_workflow.BendingWarp',side_effect=AssertionError('double map')):
                result=build_surface(snapshot,'100',backup,root/'job','unused',{'backend':'native_local'},slicer=slicer)
            self.assertEqual(result['settings']['backend'],'native_local')
            self.assertEqual(result['settings']['step_mm'],.4)
            self.assertEqual(before,snapshot.to_dict())
            self.assertEqual(extract_plate_gcode(result['package_path'],0),Path(result['gcode_path']).read_bytes())
            self.assertEqual(len(result['report']['effective_profile_verification']['verified_fields']),26)

    def source(self):
        data=cylinder_gcode(layers=2).decode()
        # A native-style varying-Z extrusion, kept separate from inverse mapping.
        lines=data.splitlines();indices=[i for i,l in enumerate(lines) if l.startswith('G1 X')]
        for n,i in enumerate(indices[:8]):lines[i]+=' Z'+str(.2+.005*(n%2))
        return ('; zaa_enabled = 1\n'+'\n'.join(lines)+'\n').encode()

    def test_native_local_preserves_every_xyz_and_extrusion_while_obeying_profile(self):
        settings={**cylinder_snapshot().settings,'machine_max_speed_z':['.01']}
        profile=PrinterProfile.from_settings(settings);data=self.source()
        result=contour_result(data,profile,{0:'100'})
        before=read(data,set(),{0:'100'},require_planar=False)
        after=read(result.gcode,set(),{0:'100'},require_planar=False)
        actual=lambda p:[(m.end,m.de) for m in p.moves.values() if m.start!=m.end or m.de]
        self.assertEqual(actual(before),actual(after))
        self.assertGreater(result.report['nonplanar_extrusion_segments_by_role']['outer wall'],0)
        self.assertLessEqual(result.report['max_z_speed_mm_s'],.01+1e-9)
        self.assertFalse(result.report['print_allowed'])
        self.assertEqual(result.report['surface_scope'],'eligible_top_facing_patches')

    def test_unrecognized_or_already_processed_source_is_not_accepted(self):
        profile=PrinterProfile.from_settings(cylinder_snapshot().settings)
        for data in (cylinder_gcode(layers=1),b'; OrcaWaveStudio BENCH ONLY\n'+self.source()):
            with self.subTest(data=data[:25]),self.assertRaises(WaveError):contour_result(data,profile,{0:'100'})

    def test_local_copy_preserves_heating_and_transport_and_does_not_modify_source(self):
        settings={**cylinder_snapshot().settings,'machine_start_gcode':'M109 S210',
                  'print_host':'test.invalid','printhost_apikey':'test-fixture-only'}
        local=local_settings(settings)
        self.assertNotIn('zaa_enabled',settings)
        self.assertEqual(local['zaa_enabled'],'1')
        for key in ('machine_start_gcode','print_host','printhost_apikey'):
            self.assertEqual(local[key],settings[key])
        self.assertEqual(local_settings({**settings,'layer_height':'.04'})['zaa_min_z'],'0.01')
