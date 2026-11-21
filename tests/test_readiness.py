import unittest
from orca_wave_studio.readiness import nominal_body_height_bound


class NominalBodyTests(unittest.TestCase):
    def source(self,travel_z):
        return f'''G90
M83
G0 X10 Y10 Z1 F600
;LAYER_CHANGE
;Z:1
;HEIGHT:0.2
;WIDTH:0.4
; printing object test id:0 copy 0
;TYPE:Outer wall
G1 X11 Y10 Z1 E0.1
G0 X12 Y10 Z{travel_z}
; stop printing object test id:0 copy 0
'''.encode()

    def test_travel_minimum_and_material_order_are_included_in_continuous_bound(self):
        r=nominal_body_height_bound(self.source(.5),{0:'1'},1.8)
        self.assertEqual(r['status'],'PASS_NOMINAL_BODY_BOUND')
        self.assertAlmostEqual(r['minimum_nominal_body_gap_mm'],1.3)
        self.assertEqual(r['worst_bound']['motion'],'travel')
        self.assertEqual(r['growing_bead_body_checks'],1)
        self.assertFalse(r['print_allowed'])

    def test_overlap_of_enclosing_height_bound_is_not_called_a_real_collision(self):
        r=nominal_body_height_bound(self.source(-2),{0:'1'},1.8)
        self.assertEqual(r['status'],'INCONCLUSIVE')
        self.assertLess(r['minimum_nominal_body_gap_mm'],0)
        self.assertEqual(r['nozzle_contact'],'UNASSESSED')
        self.assertFalse(r['print_allowed'])

    def test_unmeasured_nominal_and_even_declared_registration_do_not_approve_print(self):
        for flag in (True,False):
            r=nominal_body_height_bound(self.source(1),{0:'1'},1.8,registration_verified=flag)
            self.assertEqual(r['installed_head_registration_verified'],flag)
            self.assertFalse(r['physical_validation']);self.assertFalse(r['print_allowed'])
