import copy
import math
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from orca_wave_studio.contracts import WaveError
from orca_wave_studio.geometry import transform_point
from orca_wave_studio.placement import HeadMapStore,rotate_study_copy
from orca_wave_studio.printer_profile import PrinterProfile
from test_spline_planning import wedge


class PlacementTests(unittest.TestCase):
    def profile(self):
        return PrinterProfile('selected','marlin',.4,1.75,.2,.24,10,100,12,100,((0,0),(100,0),(100,100),(0,100)),'id')
    def test_rotation_is_rigid_preserves_height_and_does_not_modify_other_objects(self):
        source=wedge();other=copy.deepcopy(source.objects[0]);other['id']='2'
        source=replace(source,objects=(*source.objects,other));before=source.to_dict()
        rotated,report=rotate_study_copy(source,'1',90,self.profile())
        self.assertEqual(source.to_dict(),before);self.assertEqual(rotated.objects[1],other)
        original=source.objects[0];result=rotated.objects[0]
        self.assertEqual(original['volumes'],result['volumes'])
        volume=original['volumes'][0]
        a=[transform_point(p,original['instances_data'][0]['matrix'],volume['matrix']) for p in volume['vertices']]
        b=[transform_point(p,result['instances_data'][0]['matrix'],volume['matrix']) for p in volume['vertices']]
        self.assertNotEqual(a,b)
        for i in range(len(a)):
            self.assertEqual(a[i][2],b[i][2])
            for j in range(len(a)):self.assertAlmostEqual(math.dist(a[i],a[j]),math.dist(b[i],b[j]),places=12)
        self.assertFalse(report['scale_changed']);self.assertFalse(report['print_allowed'])
    def test_rotation_refuses_a_piece_outside_bed_and_nonfinite_angle(self):
        with self.assertRaisesRegex(WaveError,'mesa'):
            rotate_study_copy(wedge(),'1',45,replace(self.profile(),bed=((0,0),(5,0),(5,5),(0,5))))
        for angle in (float('nan'),361,True):
            with self.assertRaises(WaveError):rotate_study_copy(wedge(),'1',angle,self.profile())
    def test_maps_are_separate_by_exact_profile_and_never_physical_approval(self):
        a={'name':'printer A','nozzle_mm':.4};b={'name':'printer B','nozzle_mm':.4}
        part={'name':'rear housing','x_min':-12,'x_max':8,'y_min':10,'y_max':45,'clearance_z':3}
        with tempfile.TemporaryDirectory() as folder:
            store=HeadMapStore(folder);key=store.load(a)['profile_key'];store.save(a,key,[part])
            loaded=store.load(a);self.assertEqual(loaded['components'],[part]);self.assertEqual(store.load(b)['components'],[])
            self.assertFalse(loaded['registration_verified']);self.assertFalse(loaded['print_allowed'])
            with self.assertRaisesRegex(WaveError,'mudou'):store.save(b,key,[part])
            with self.assertRaises(WaveError):store.save(a,key,[{**part,'clearance_z':float('nan')}])
            self.assertEqual(store.load(a)['components'],[part])


if __name__=='__main__':unittest.main()
