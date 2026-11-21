import copy
from collections import Counter
import tempfile
from pathlib import Path
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import numpy as np

from orca_wave_studio.contracts import WaveError
from orca_wave_studio.fixtures import cylinder_snapshot,cylinder_gcode
from orca_wave_studio.project_io import write_model_project
from orca_wave_studio.native_surfaces import verify_area_modifiers
from orca_wave_studio.wall_selection import resolve_areas,sphere_modifier,audit_selected_paths


class WallSelectionTests(unittest.TestCase):
    def test_native_paths_must_have_an_effect_inside_the_chosen_area(self):
        lines=cylinder_gcode(layers=2).decode().splitlines()
        ids=[i for i,line in enumerate(lines) if line.startswith('G1 X')]
        for n,i in enumerate(ids[:8]):lines[i]+=' Z'+str(.2+.005*(n%2))
        lines[ids[8]]+=' Z0.2'
        data=('\n'.join(lines)+'\n').encode()
        areas=[{'center':[80,60,.2],'radius_mm':6}]
        audit=audit_selected_paths(data,{0:'100'},areas)
        self.assertGreater(audit['affected_segments'],0)
        self.assertEqual(audit['outside_scope_segments'],0)
        self.assertFalse(audit['print_allowed'])
        with self.assertRaisesRegex(WaveError,'WALL_SCOPE'):
            audit_selected_paths(data,{0:'100'},[{'center':[0,0,0],'radius_mm':6}])
        with self.assertRaisesRegex(WaveError,'WALL_NO_EFFECT'):
            audit_selected_paths(cylinder_gcode(layers=2),{0:'100'},areas)

    def options(self,snapshot):
        return {'selection_mode':'paint','selection_revision':snapshot.revision,
                'wall_selection':[{'origin':[100,60,4],'direction':[-2,0,0],'radius_mm':6}]}

    def test_click_resolves_original_transformed_mesh_and_keeps_input_immutable(self):
        snapshot=cylinder_snapshot();before=copy.deepcopy(snapshot.to_dict())
        areas=resolve_areas(snapshot,'100',self.options(snapshot))
        np.testing.assert_allclose(areas[0]['center'],[80,60,4],atol=1e-9)
        self.assertEqual(before,snapshot.to_dict())
        self.assertEqual(areas[0]['radius_mm'],6)
        self.assertGreater(areas[0]['normal'][0],.99)

    def test_stale_missing_or_malformed_selection_never_expands_to_all_faces(self):
        snapshot=cylinder_snapshot();options=self.options(snapshot)
        for change in ({'selection_revision':'old'}, {'wall_selection':[]},
                       {'wall_selection':options['wall_selection']*25},
                       {'wall_selection':[{'origin':[0,0,100],'direction':[0,0,1],'radius_mm':6}]},
                       {'wall_selection':[{'origin':[100,60,4],'direction':[0,0,0],'radius_mm':6}]},
                       {'wall_selection':[{'origin':[100,60,float('nan')],'direction':[-1,0,0],'radius_mm':6}]},
                       {'wall_selection':[{'origin':[100,60,4],'direction':[-1,0,0],'radius_mm':99}]},
                       {'selection_mode':'all'}):
            with self.subTest(change=change),self.assertRaises(WaveError):
                resolve_areas(snapshot,'100',{**options,**change})
        self.assertEqual(resolve_areas(snapshot,'100',{}),[])

    def test_spheres_are_closed_outward_and_do_not_add_printable_material(self):
        snapshot=cylinder_snapshot();area=resolve_areas(snapshot,'100',self.options(snapshot))[0]
        snapshot.objects[0]['volumes'][0]['config']={'outer_wall_speed':'12'}
        modifier=sphere_modifier(area,1)
        edge_counts=Counter(tuple(sorted((a,b))) for f in modifier['triangles']
                            for a,b in zip(f,(*f[1:],f[0])))
        self.assertEqual(set(edge_counts.values()),{2})
        points=np.asarray(modifier['vertices'])-area['center']
        for a,b,c in modifier['triangles']:
            self.assertGreater(np.dot(np.cross(points[b]-points[a],points[c]-points[a]),points[a]),0)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'selected.3mf'
            write_model_project(snapshot,path,snapshot.settings,modifiers=[modifier])
            verify_area_modifiers(path,1)
            with ZipFile(path) as archive:
                root=ET.fromstring(archive.read('3D/3dmodel.model'))
                ns={'m':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
                mesh=root.find("m:resources/m:object[@id='1']/m:mesh",ns)
                self.assertEqual(len(mesh.findall('m:triangles/m:triangle',ns)),
                                 len(snapshot.objects[0]['volumes'][0]['triangles']))
                config=ET.fromstring(archive.read('Metadata/model_settings.config'))
                parts=config.findall('object/part')
                self.assertEqual([p.get('subtype') for p in parts],['normal_part','modifier_part'])
                self.assertEqual({m.get('key'):m.get('value') for m in parts[0].findall('metadata')}['outer_wall_speed'],'12')
                self.assertEqual(len(root.findall('m:build/m:item',ns)),1)
            with self.assertRaisesRegex(WaveError,'WALL_NATIVE'):verify_area_modifiers(path,2)
