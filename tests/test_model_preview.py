import base64
import copy
import json
import math
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from collections import Counter

import numpy as np

from orca_wave_studio.contracts import fingerprint
from orca_wave_studio.fixtures import cylinder_mesh, cylinder_snapshot
from orca_wave_studio.geometry import transform_point
from orca_wave_studio.model_preview import model_preview
from orca_wave_studio.model_preview_ui import SCRIPT
from orca_wave_studio.controller import StudioController


def dense_snapshot():
    snapshot = cylinder_snapshot()
    volume = snapshot.objects[0]['volumes'][0]
    volume['vertices'], volume['triangles'] = cylinder_mesh(segments=2048)
    return snapshot


class ModelPreviewTests(unittest.TestCase):
    def test_poll_reuses_only_the_exact_mesh_known_by_that_view(self):
        with tempfile.TemporaryDirectory() as folder:
            controller=StudioController(Path(folder))
            preview=model_preview(cylinder_snapshot())
            controller._model_preview=preview
            for known in (None,'different-view-id'):
                state=controller.handle({'action':'poll','model_preview_id':known})['state']
                self.assertEqual(state['model_preview'],preview)
            state=controller.handle({'action':'poll','model_preview_id':preview['id']})['state']
            self.assertEqual(state['model_preview'],{'id':preview['id'],'unchanged':True})
            self.assertEqual(controller._model_preview,preview)
            controller._model_preview=None
            state=controller.handle({'action':'poll','model_preview_id':preview['id']})['state']
            self.assertIsNone(state['model_preview'])

    def test_dense_closed_mesh_keeps_every_oriented_face_and_original_position(self):
        snapshot = dense_snapshot()
        before = fingerprint(snapshot.objects)
        display = model_preview(snapshot)['objects'][0]
        mesh = display['mesh']
        vertices = np.frombuffer(base64.b64decode(mesh['positions']), dtype='<f4').reshape(-1, 3)
        faces = np.frombuffer(base64.b64decode(mesh['indices']), dtype='<u4').reshape(-1, 3)
        source = snapshot.objects[0]
        volume, instance = source['volumes'][0], source['instances_data'][0]
        transformed = np.array([transform_point(p, instance['matrix'], volume['matrix'])
                                for p in volume['vertices']], dtype=np.float32)
        expected = transformed[np.asarray(volume['triangles'])]
        np.testing.assert_array_equal(vertices[faces], expected)
        self.assertEqual(len(faces), 8192)
        self.assertEqual(display['source_triangles'], 8192)
        self.assertEqual(fingerprint(snapshot.objects), before)
        oriented, edges = Counter(), Counter()
        for a, b, c in faces.tolist():
            for x, y in ((a, b), (b, c), (c, a)):
                edges[tuple(sorted((x, y)))] += 1
                oriented[(x, y)] += 1
        self.assertTrue(all(value == 2 for value in edges.values()))
        self.assertTrue(all(oriented[(a, b)] == oriented[(b, a)] for a, b in oriented))
        self.assertEqual(len(vertices) - len(edges) + len(faces), 2)
        self.assertTrue(np.all(np.linalg.norm(np.cross(expected[:, 1]-expected[:, 0],
                                                       expected[:, 2]-expected[:, 0]), axis=1) > 0))
        self.assertLess(len(json.dumps(display)), len(json.dumps(expected.tolist())) / 2)

    def test_instances_and_part_filters_are_preserved_without_mutating_the_source(self):
        snapshot = cylinder_snapshot()
        obj = snapshot.objects[0]
        obj['volumes'].append({**copy.deepcopy(obj['volumes'][0]), 'negative': True})
        obj['volumes'].append({**copy.deepcopy(obj['volumes'][0]), 'kind': 'modifier'})
        second = copy.deepcopy(obj['instances_data'][0])
        second['matrix'][0][3] += 100
        obj['instances_data'].extend([second, {**copy.deepcopy(second), 'printable': False}])
        before = fingerprint(snapshot.objects)
        result = model_preview(snapshot)['objects'][0]
        self.assertEqual(result['source_triangles'], 2560)
        self.assertEqual(len(result['triangles']), 2560)
        self.assertEqual(result['bounds'], [[40, 40, 0], [180, 80, 8]])
        self.assertEqual(fingerprint(snapshot.objects), before)

    def test_coincident_opposite_faces_are_never_deduplicated(self):
        snapshot = cylinder_snapshot()
        volume = snapshot.objects[0]['volumes'][0]
        volume['vertices'] = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
        volume['triangles'] = [[0, 1, 2], [2, 1, 0]] * 2049
        result = model_preview(snapshot)['objects'][0]
        faces = np.frombuffer(base64.b64decode(result['mesh']['indices']), dtype='<u4').reshape(-1, 3)
        self.assertEqual(len(faces), 4098)
        np.testing.assert_array_equal(faces[0], faces[1][::-1])

    @unittest.skipUnless(shutil.which('node'), 'Node is required for renderer component checks')
    def test_renderer_keeps_dense_faces_rotation_rays_and_hard_edges(self):
        model = model_preview(dense_snapshot())['objects'][0]
        small = model_preview(cylinder_snapshot())['objects'][0]
        checks = r'''
const assert=require('node:assert/strict'),fs=require('node:fs');
const {model,small}=JSON.parse(fs.readFileSync(0,'utf8'));
const untouched=JSON.stringify(model),decoded=displayMesh(model),surface=displaySurface([model]);
assert.equal(surface.triangleCount,8192);assert.equal(surface.flat.length,8192*9);
assert.equal(displayMesh(model),decoded,'buffers should decode only once');
assert.equal(displayRayDistance(surface.flat,[60,60,-10],[0,0,1]),10);
assert.equal(displayRayDistance(surface.flat,[60,60,4],[0,0,1]),4);
assert.equal(displayRayDistance(surface.flat,[-100,-100,-10],[0,0,1]),null);
const rotated=displaySurface([{...model,display_rotation:{radians:Math.PI/2,center:[60,60]}}]);
for(let i=0;i<surface.flat.length;i+=3){
 assert(Math.abs(rotated.flat[i]-(120-surface.flat[i+1]))<2e-5);
 assert(Math.abs(rotated.flat[i+1]-surface.flat[i])<2e-5);
 assert.equal(rotated.flat[i+2],surface.flat[i+2]);
}
assert.equal(JSON.stringify(model),untouched,'rotation must preserve the source payload');
const lit=displaySurface([small]).shades,L=Math.hypot(.3,-.4,.86);
for(const i of [0,3,5])assert(Math.abs(lit[i]-(.42+.58*.3/L))<1e-5,'smooth radial side normal');
for(const i of [6,7,8])assert(Math.abs(lit[i]-(.42+.58*.86/L))<1e-5,'flat cap must keep its sharp edge');
const chamfer=displaySurface([{triangles:[[[0,0,0],[1,0,0],[0,1,0]],[[1,0,0],[0,0,0],[0,-1,1]]]}]).shades;
assert(Math.abs(chamfer[0]-(.42+.58*.86/L))<1e-5,'45-degree chamfer keeps the first face normal');
assert(Math.abs(chamfer[3]-(.42+.58*(.86-.4)/Math.SQRT2/L))<1e-5,'45-degree chamfer keeps the second face normal');
for(const value of surface.shades)assert(Number.isFinite(value)&&value>=.4199&&value<=1.0001);
assert.throws(()=>displayMesh({mesh:{...model.mesh,indices:'AA=='}}),/Tamanho/);
console.log(JSON.stringify({triangles:surface.triangleCount,sourceUnchanged:true,sharpEdgesPreserved:true}));
'''
        run = subprocess.run(['node', '-e', SCRIPT + checks],
                             input=json.dumps({'model': model, 'small': small}),
                             text=True, encoding='utf8', capture_output=True, timeout=45)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue(json.loads(run.stdout)['sharpEdgesPreserved'])


if __name__ == '__main__':
    unittest.main()
