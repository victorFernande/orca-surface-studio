"""Unit geometry and explicit-input gate tests; no real printer profile."""
from dataclasses import replace
import unittest

from orca_wave_studio.contracts import WaveError
from orca_wave_studio.head_clearance import (
    AABB,HeadComponent,HeadProfile,TCPRegistration,TCPMotion,MaterialDeposit,
    REQUIRED_COMPONENTS,check_head_clearance,segment_aabb_interval,
)


def profile(*,provenance='synthetic_fixture',fan=None,uncertainty=0.):
    components=[]
    for i,kind in enumerate(sorted(REQUIRED_COMPONENTS)):
        if kind=='nozzle':box=AABB((-.1,-.1,1.),(.1,.1,2.))
        elif kind=='fan' and fan is not None:box=fan
        else:box=AABB((-.1,-.1,30.+3*i),(.1,.1,31.+3*i))
        components.append(HeadComponent(kind,kind,box))
    return HeadProfile('UNIT-TEST-INPUT-NOT-A-MACHINE-PROFILE',tuple(components),
        TCPRegistration('unit-test-source-frame',(0.,0.,0.),'test metadata',uncertainty,True),
        provenance=provenance,conservative_geometry_verified=True)


def audit(motions,material=(),head=None,**kwargs):
    return check_head_clearance(motions,material,head,motions_complete=True,
                                material_prefix_complete=True,**kwargs)


class HeadClearanceTests(unittest.TestCase):
    def test_continuous_middle_of_segment_collision_is_not_missed_by_endpoints(self):
        material=MaterialDeposit(-1,AABB((-.01,-.01,1.4),(.01,.01,1.6)),material_id='thin-obstacle')
        move=TCPMotion(1,(-1.,0.,0.),(1.,0.,0.))
        head=profile()
        result=audit([move],[material],head)
        self.assertEqual(result['status'],'UNKNOWN')
        self.assertEqual(result['geometry_status'],'POTENTIAL_COLLISION')
        hit=next(row for row in result['collisions'] if row['component_kind']=='nozzle')
        lo,hi=hit['tcp_segment_parameter_interval']
        self.assertGreater(lo,0);self.assertLess(hi,1)
        self.assertAlmostEqual(lo,.445);self.assertAlmostEqual(hi,.555)
        self.assertFalse(result['conservative_box_hits_are_exact_shape_collisions'])

    def test_material_order_excludes_future_then_includes_completed_deposit(self):
        material=MaterialDeposit(5,AABB((-.1,-.1,1.4),(.1,.1,1.6)),material_id='later')
        first=TCPMotion(1,(-2.,0.,0.),(2.,0.,0.),motion_id='before')
        second=TCPMotion(6,(2.,0.,0.),(-2.,0.,0.),motion_id='after')
        result=audit([first,second],[material],profile())
        self.assertTrue(result['collisions'])
        self.assertEqual({hit['motion_id'] for hit in result['collisions']},{'after'})
        early=audit([first],[material],profile())
        self.assertEqual(early['geometry_status'],'PASS_DIGITAL')

    def test_asymmetric_component_offset_uses_signed_minkowski_expansion(self):
        obstacle=MaterialDeposit(-1,AABB((4.5,-.02,1.4),(4.6,.02,1.6)))
        move=TCPMotion(1,(0.,0.,0.),(.1,0.,0.))
        right=profile(fan=AABB((4.,-.1,1.),(5.,.1,2.)))
        left=profile(fan=AABB((-5.,-.1,1.),(-4.,.1,2.)))
        yes=audit([move],[obstacle],right);no=audit([move],[obstacle],left)
        self.assertEqual(yes['geometry_status'],'POTENTIAL_COLLISION')
        self.assertEqual({hit['component_kind'] for hit in yes['collisions']},{'fan'})
        self.assertEqual(no['geometry_status'],'PASS_DIGITAL')

    def test_support_interface_and_travel_are_not_excluded(self):
        obstacle=MaterialDeposit(0,AABB((-.02,-.02,1.4),(.02,.02,1.6)),
                                 role='support interface',material_id='interface')
        move=TCPMotion(1,(-1.,0.,0.),(1.,0.,0.),kind='travel')
        result=audit([move],[obstacle],profile())
        self.assertEqual(result['geometry_status'],'POTENTIAL_COLLISION')
        self.assertEqual(result['collisions'][0]['material_role'],'support interface')
        self.assertEqual(result['collisions'][0]['motion_kind'],'travel')

    def test_no_real_profile_missing_tcp_component_and_units_remain_unknown(self):
        move=TCPMotion(1,(0.,0.,0.),(1.,0.,0.));head=profile()
        examples=(None,replace(head,tcp_registration=None),
                  replace(head,components=tuple(c for c in head.components if c.kind!='sensor')),
                  replace(head,units='inch'),
                  replace(head,tcp_registration=replace(head.tcp_registration,tcp_in_source_frame_mm=None)))
        for item in examples:
            with self.subTest(profile=item):
                self.assertEqual(audit([move],head=item)['status'],'UNKNOWN')
        missing=audit([move],head=examples[2])
        self.assertNotEqual(missing['geometry_status'],'PASS_DIGITAL')

    def test_synthetic_can_exercise_geometry_but_never_approve_machine_clearance(self):
        move=TCPMotion(1,(0.,0.,0.),(1.,0.,0.))
        result=audit([move],head=profile())
        self.assertEqual(result['status'],'UNKNOWN')
        self.assertEqual(result['geometry_status'],'PASS_DIGITAL')
        self.assertIn('SYNTHETIC_PROFILE',result['reason_codes'])
        self.assertFalse(result['print_allowed']);self.assertFalse(result['physical_validation'])
        # Pure gate test of producer-declared metadata, not a claimed real head.
        declared=audit([move],head=profile(provenance='measured'))
        self.assertEqual(declared['status'],'PASS_DIGITAL')
        self.assertFalse(declared['print_allowed'])

    def test_registration_uncertainty_is_added_conservatively(self):
        obstacle=MaterialDeposit(-1,AABB((.13,-.01,1.4),(.15,.01,1.6)))
        move=TCPMotion(1,(0.,0.,0.),(0.,0.,0.))
        self.assertEqual(audit([move],[obstacle],profile())['geometry_status'],'PASS_DIGITAL')
        expanded=audit([move],[obstacle],profile(uncertainty=.05))
        self.assertEqual(expanded['geometry_status'],'POTENTIAL_COLLISION')
        self.assertEqual(expanded['registration_uncertainty_mm'],.05)

    def test_current_extrusion_contact_is_uncertified_never_blanket_ignored(self):
        move=TCPMotion(1,(-1.,0.,0.),(1.,0.,0.),kind='extrusion')
        current=MaterialDeposit(1,AABB((-.1,-.1,1.4),(.1,.1,1.6)))
        result=audit([move],[current],profile(provenance='measured'))
        self.assertEqual(result['geometry_status'],'UNCERTIFIED')
        self.assertEqual(result['current_deposition_contact_status'],'UNCERTIFIED')
        prior=replace(current,sequence=0)
        hit=audit([move],[prior],profile(provenance='measured'))
        self.assertEqual(hit['geometry_status'],'POTENTIAL_COLLISION')
        self.assertTrue(all(not row['nozzle_contact_ignored'] for row in hit['collisions']))

    def test_incomplete_inputs_and_work_budget_cannot_produce_pass(self):
        move=TCPMotion(1,(0.,0.,0.),(1.,0.,0.));head=profile(provenance='measured')
        incomplete=check_head_clearance([move],[],head)
        self.assertEqual(incomplete['geometry_status'],'UNCERTIFIED')
        material=MaterialDeposit(-1,AABB((100.,100.,100.),(101.,101.,101.)))
        budget=audit([move],[material],head,max_pair_checks=1)
        self.assertEqual(budget['geometry_status'],'UNCERTIFIED')
        self.assertIn('RESOURCE_BUDGET_EXHAUSTED',budget['reason_codes'])
        self.assertFalse(budget['coverage_complete'])
        jump=TCPMotion(2,(3.,0.,0.),(4.,0.,0.))
        self.assertIn('INCOMPLETE_MOTION_CHAIN',audit([move,jump],head=head)['reason_codes'])

    def test_stationary_touch_and_invalid_boxes_are_explicit(self):
        box=AABB((0.,0.,0.),(1.,1.,1.))
        self.assertEqual(segment_aabb_interval((0.,.5,.5),(0.,.5,.5),box),(0.,1.))
        self.assertIsNone(segment_aabb_interval((-1.,0.,0.),(-1.,1.,1.),box))
        grazing=segment_aabb_interval((-1.,1.,.5),(1.,-1.,.5),box)
        self.assertIsNotNone(grazing)
        self.assertLessEqual(grazing[0],.5);self.assertGreaterEqual(grazing[1],.5)
        with self.assertRaises(WaveError):AABB((1.,0.,0.),(0.,1.,1.))
        with self.assertRaises(WaveError):AABB((0.,0.,float('nan')),(1.,1.,1.))
