import unittest
import copy
import math
from dataclasses import replace
from unittest.mock import patch

from orca_wave_studio.roof_fixtures import roof_coupon
from orca_wave_studio.roof_regions import roof_region_catalog,selected_region
from orca_wave_studio.regional_shell import RegionalShellWarp
from orca_wave_studio.contracts import ProjectSnapshot


class RoofRegionTests(unittest.TestCase):
    def test_catalogue_binds_one_consistent_revision_without_reserializing_per_plane(self):
        snapshot,_=roof_coupon(25)
        revision_getter=ProjectSnapshot.revision.fget
        calls=[]
        def counted(value):
            calls.append(value.session_id)
            return revision_getter(value)
        with patch.object(ProjectSnapshot,'revision',property(counted)):
            catalog=roof_region_catalog(snapshot,'1')
        self.assertGreater(len(catalog['regions']),1)
        self.assertEqual(calls,[snapshot.session_id])
        self.assertEqual(catalog['revision'],revision_getter(snapshot))

    def test_catalog_uses_the_selected_second_object(self):
        first,_=roof_coupon(5);second,_=roof_coupon(25)
        other=copy.deepcopy(second.objects[0]);other['id']='2'
        combined=replace(first,objects=(*first.objects,other))
        catalog=roof_region_catalog(combined,'2')
        choice=selected_region(catalog)
        self.assertAlmostEqual(choice['top_plane_world'][0],math.tan(math.radians(25)),places=6)
        self.assertEqual(catalog['object_id'],'2')

    def test_auto_plane_uses_inclined_skin_and_manual_choices_are_revision_bound(self):
        snapshot,truth=roof_coupon(25)
        before=snapshot.to_dict()
        catalog=roof_region_catalog(snapshot,'1')
        region=selected_region(catalog)
        self.assertAlmostEqual(region['top_plane_world'][0],truth['roof']['top_plane_world'][0],places=6)
        warp=RegionalShellWarp(snapshot,'1',region=region)
        self.assertAlmostEqual(warp.summary['slope_deg'],25.,places=5)
        self.assertEqual(before,snapshot.to_dict())
        altered=replace(snapshot,session_id=snapshot.session_id+'new')
        new=roof_region_catalog(altered,'1')
        with self.assertRaisesRegex(ValueError,'região selecionada mudou'):
            selected_region(new,region['name'])

    def test_manual_correction_does_not_grant_printer_or_head_capability(self):
        catalog=roof_region_catalog(roof_coupon(20)[0],'1')
        for row in catalog['regions']:
            self.assertEqual(selected_region(catalog,row['id'])['name'],row['id'])
        self.assertIsNone(catalog['head_capability_deg'])
        self.assertFalse(catalog['print_allowed'])
        self.assertEqual(catalog['selected_faces'],['top','underside','border'])
