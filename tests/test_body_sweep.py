import unittest
from orca_wave_studio.body_sweep import nominal_spatial_body_bound


def paths():
    return b'''G90
M83
G0 X20 Y20 Z0.2
;LAYER_CHANGE
;Z:0.2
;HEIGHT:0.2
; printing object Part id:0 copy 0
;TYPE:Outer wall
;WIDTH:0.4
G1 X25 E0.1
G0 X30 Y30 Z0.2
; stop printing object Part id:0 copy 0
'''


class BodySweepTests(unittest.TestCase):
    def test_fine_resolution_keeps_margin_and_limits_memory(self):
        from orca_wave_studio.contracts import WaveError
        envelope={'name':'sensor','minimum':[-1.,-1.,2.],'maximum':[1.,1.,5.]}
        fine=nominal_spatial_body_bound(paths(),{0:'part'},[envelope],bed_mm=(40.,40.),cell_mm=.05)
        self.assertEqual(fine['status'],'PASS_NOMINAL_SPATIAL_BODY_BOUND')
        self.assertEqual(fine['minimum_required_gap_mm'],.5)
        with self.assertRaisesRegex(WaveError,'memória'):
            nominal_spatial_body_bound(paths(),{0:'part'},[envelope],bed_mm=(1000.,1000.),cell_mm=.05)

    def test_current_bead_and_travel_are_checked_without_printer_access(self):
        envelope={'name':'sensor','minimum':[-1.,-1.,2.],'maximum':[1.,1.,5.]}
        result=nominal_spatial_body_bound(paths(),{0:'part'},[envelope])
        self.assertEqual(result['status'],'PASS_NOMINAL_SPATIAL_BODY_BOUND')
        self.assertAlmostEqual(result['minimum_nominal_gap_mm'],2.,places=10)
        self.assertFalse(result['printer_contacted']);self.assertFalse(result['print_allowed'])
        self.assertGreater(result['component_motion_sweeps_checked'],0)

    def test_earlier_material_in_sensor_box_is_inconclusive(self):
        gcode=paths().replace(b'G0 X30 Y30 Z0.2',b'G0 X30 Y30 Z5\nG1 X35 E0.1\nG0 X30 Y30 Z0.2')
        envelope={'name':'sensor','minimum':[-1.,-1.,2.],'maximum':[1.,1.,5.]}
        result=nominal_spatial_body_bound(gcode,{0:'part'},[envelope])
        self.assertEqual(result['status'],'INCONCLUSIVE')
        self.assertLess(result['minimum_nominal_gap_mm'],0)
        self.assertTrue(result['potential_overlaps'])

    def test_positive_microscopic_clearance_does_not_pass_the_margin(self):
        envelope={'name':'sensor','minimum':[-1.,-1.,.000001],'maximum':[1.,1.,5.]}
        result=nominal_spatial_body_bound(paths(),{0:'part'},[envelope])
        self.assertEqual(result['status'],'INCONCLUSIVE')
        self.assertGreater(result['minimum_nominal_gap_mm'],0.)

    def test_high_material_outside_component_footprint_does_not_block_clearance(self):
        gcode=paths().replace(b'G0 X30 Y30 Z0.2',b'G0 X100 Y100 Z5\nG1 X105 E0.1\nG0 X30 Y30 Z0.2')
        envelope={'name':'sensor','minimum':[-1.,-1.,2.],'maximum':[1.,1.,5.]}
        result=nominal_spatial_body_bound(gcode,{0:'part'},[envelope])
        # The diagonal travel is swept too and crosses the high bead at its
        # departure. Its AABB is deliberately conservative: no false pass.
        self.assertEqual(result['status'],'INCONCLUSIVE')
        self.assertFalse(result['installed_head_registration_verified'])

    def test_parent_overlap_is_refined_and_parent_clearance_proves_children(self):
        gcode=paths().replace(b'G0 X30 Y30 Z0.2',b'G0 X30 Y30 Z5\nG1 X35 E0.1\nG0 X30 Y30 Z0.2')
        components=[{'name':'left','minimum':[-21.,-1.,2.],'maximum':[-19.,1.,5.],'group':'pair'},
                    {'name':'right','minimum':[19.,-1.,2.],'maximum':[21.,1.,5.],'group':'pair'}]
        grouped=nominal_spatial_body_bound(gcode,{0:'part'},components)
        control=nominal_spatial_body_bound(gcode,{0:'part'},[{k:v for k,v in c.items() if k!='group'} for c in components])
        self.assertEqual(grouped['status'],control['status'])
        self.assertEqual(grouped['status'],'PASS_NOMINAL_SPATIAL_BODY_BOUND')
        self.assertGreater(grouped['child_sweeps_proven_by_parent'],0)
        self.assertGreater(grouped['leaf_sweeps_evaluated'],0)

    def test_tiny_global_gap_is_refined_when_high_material_is_far_from_the_head(self):
        gcode=paths().replace(b'G0 X30 Y30 Z0.2',
            b'G0 X100 Y100 Z5\nG1 X105 E0.1\nG0 X30 Y30 Z5\nG0 Z0.2')
        envelope={'name':'sensor','minimum':[-1.,-1.,4.800001],'maximum':[1.,1.,7.]}
        report=nominal_spatial_body_bound(gcode,{0:'part'},[envelope])
        self.assertEqual(report['status'],'PASS_NOMINAL_SPATIAL_BODY_BOUND')
        self.assertGreater(report['minimum_nominal_gap_mm'],.5)
        self.assertGreater(report['spatial_queries'],0)


if __name__=='__main__':unittest.main()
