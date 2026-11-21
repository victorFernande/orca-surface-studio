import copy
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from orca_wave_studio.contracts import WaveError
from orca_wave_studio.fixtures import cylinder_snapshot
from orca_wave_studio.project_io import write_model_project
from orca_wave_studio.surface_finishing import finishing_plan,verify_finishing_ranges,audit_finishing


class SurfaceFinishingTests(unittest.TestCase):
    def test_profile_minimum_bands_and_first_layer_are_preserved_without_moving_mesh(self):
        snapshot=cylinder_snapshot();obj=snapshot.objects[0];before=copy.deepcopy(obj)
        settings={**snapshot.settings,'min_layer_height':['0.07'],'max_layer_height':['.28']}
        plan=finishing_plan(settings,obj,[{'center':[60,60,4],'radius_mm':1}])
        self.assertEqual(plan['finishing_layer_mm'],.07)
        self.assertEqual(plan['nominal_layer_mm'],.2)
        self.assertAlmostEqual(plan['minimum_z_mm'],.035)
        self.assertGreaterEqual(plan['ranges'][0]['min_z'],plan['first_layer_mm'])
        self.assertLess(plan['ranges'][0]['max_z'],8)
        self.assertEqual(obj,before)
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'model.3mf'
            write_model_project(snapshot,p,settings,layer_ranges=plan['ranges'])
            self.assertTrue(verify_finishing_ranges(p,plan)['matched'])
            wrong={**plan,'ranges':[{**plan['ranges'][0],'layer_height':.08}]}
            with self.assertRaisesRegex(WaveError,'FINISH_NATIVE'):verify_finishing_ranges(p,wrong)

    def test_translated_piece_bands_are_relative_to_the_native_object_base(self):
        snapshot=cylinder_snapshot();obj=snapshot.objects[0]
        obj['instances_data'][0]['matrix'][2][3]=10
        plan=finishing_plan(snapshot.settings,obj,[{'center':[60,60,14],'radius_mm':1}])
        self.assertLess(plan['ranges'][0]['max_z'],8)

    def source(self,*,steep=False):
        end='X10.02 Z0.24' if steep else 'X10.2 Z0.27'
        return f'''G90
M83
;WIDTH:0.42
;LAYER_CHANGE
;Z:0.2
;HEIGHT:0.2
; printing object fixture id:0 copy 0
G0 X10 Y10 Z0.2 F1200
;TYPE:Outer wall
G1 X11 Y10 E0.01
;LAYER_CHANGE
;Z:0.28
;HEIGHT:0.08
G0 X10 Y10 Z0.28
G1 {end} E0.001
G1 X10.4 Z0.28 E0.001
; stop printing object fixture id:0 copy 0
'''.encode()

    def test_actual_63_degree_move_is_refused_but_gentle_extrusion_passes(self):
        plan={'first_layer_mm':.2,'finishing_layer_mm':.08}
        passed=audit_finishing(self.source(),{0:'100'},plan,30)
        self.assertTrue(passed['first_layer_preserved'])
        self.assertTrue(passed['within_study_limit'])
        with self.assertRaisesRegex(WaveError,'FINISH_SLOPE.*63.4'):
            audit_finishing(self.source(steep=True),{0:'100'},plan,30)

    def test_first_layer_change_or_native_ignored_refinement_is_not_accepted(self):
        plan={'first_layer_mm':.2,'finishing_layer_mm':.08}
        with self.assertRaisesRegex(WaveError,'FINISH_FIRST_LAYER'):
            audit_finishing(self.source().replace(b'Z0.2 F',b'Z0.19 F'),{0:'100'},plan,30)
        with self.assertRaisesRegex(WaveError,'FINISH_NATIVE'):
            audit_finishing(self.source().replace(b';Z:0.28',b';Z:0.4'),{0:'100'},plan,30)

    def test_bridge_feature_height_does_not_masquerade_as_nominal_layer_spacing(self):
        plan={'first_layer_mm':.2,'finishing_layer_mm':.08}
        audit=audit_finishing(self.source().replace(b';HEIGHT:0.08',b';HEIGHT:0.368'),{0:'100'},plan,30)
        self.assertAlmostEqual(audit['maximum_layer_step_mm'],.08)
        self.assertAlmostEqual(audit['maximum_feature_height_mm'],.368)

    def test_invalid_profile_layer_interval_never_changes_the_model_to_force_a_pass(self):
        snapshot=cylinder_snapshot()
        with self.assertRaisesRegex(WaveError,'FINISH_PROFILE'):
            finishing_plan({**snapshot.settings,'min_layer_height':['.3'],'max_layer_height':['.28']},snapshot.objects[0],[])
