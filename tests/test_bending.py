import copy
import math
import unittest

from orca_wave_studio.bending import BendingWarp
from orca_wave_studio.contracts import ProjectSnapshot
from orca_wave_studio.geometry import IDENTITY
from orca_wave_studio.regional_shell import RegionalShellSettings
from orca_wave_studio.surface import SurfaceMesh,SurfaceSettings


def roof_with_hole():
    xy=[(95,95),(115,95),(115,115),(95,115),(102,102),(108,102),(108,108),(102,108)]
    vertices=[[x,y,0.] for x,y in xy]+[[x,y,10+.1*(x-95)] for x,y in xy]
    triangles=[]
    for i in range(4):
        j=(i+1)%4
        for q in ((8+i,8+j,12+j,12+i),(i,4+i,4+j,j),(i,j,8+j,8+i),(4+i,12+i,12+j,4+j)):
            a,b,c,d=q;triangles.extend(((a,b,c),(a,c,d)))
    return ProjectSnapshot('ring',0,({'id':'1','name':'Roof with through hole',
        'instances_data':[{'id':'1','printable':True,'matrix':copy.deepcopy(IDENTITY)}],
        'volumes':[{'kind':'part','negative':False,'matrix':copy.deepcopy(IDENTITY),'vertices':vertices,'triangles':triangles}]},),{})


def euler(obj):
    v=obj['volumes'][0];edges={tuple(sorted((a,b))) for tri in v['triangles'] for a,b in zip(tri,(*tri[1:],tri[0]))}
    used={i for t in v['triangles'] for i in t}
    return len(used)-len(edges)+len(v['triangles'])


class BendingTests(unittest.TestCase):
    def test_closed_solid_with_hole_keeps_topology_and_base(self):
        original=roof_with_hole();before=original.to_dict();warp=BendingWarp(original,'1')
        flat=warp.flattened_snapshot
        SurfaceMesh(flat.objects[0],SurfaceSettings())
        self.assertEqual(euler(flat.objects[0]),euler(original.objects[0]))
        self.assertEqual(euler(flat.objects[0]),0)
        self.assertIsNone(warp.expected_surface(105,105))
        self.assertAlmostEqual(warp.expected_surface(100,100),10.5)
        self.assertEqual(before,original.to_dict())
        self.assertTrue(warp.summary['holes_preserved'])
        self.assertLessEqual(warp.summary['mesh_roundtrip_error_bound_mm'],.01)
        self.assertGreater(warp.summary['min_vertical_jacobian'],0)
        for point in original.objects[0]['volumes'][0]['vertices']:
            self.assertLess(math.dist(warp.map_point(warp.flatten_point(point)),point),1e-10)
            if point[2]==0:self.assertEqual(warp.flatten_point(point),tuple(point))

    def test_plane_aligned_layers_cover_both_sides_without_a_flat_collar(self):
        warp=BendingWarp(roof_with_hole(),'1')
        z=warp.flat_top_z-.4
        p=warp.map_point((96,96,z));q=warp.map_point((114,96,z))
        self.assertGreater(q[2]-p[2],1.5)
        self.assertEqual(warp.summary['planar_collar_mm'],0)
        # Emitted chord certificate bounds the full path, including transitions.
        a=(96,96,warp.anchor_z-.5);b=(114,114,warp.flat_top_z+.5)
        pa,pb=warp.map_point(a),warp.map_point(b)
        bound=warp.chord_error_bound(a,b,pa,pb)
        for i in range(101):
            t=i/100;flat=tuple(x+t*(y-x) for x,y in zip(a,b));line=tuple(x+t*(y-x) for x,y in zip(pa,pb))
            self.assertLessEqual(math.dist(warp.map_point(flat),line),bound+1e-9)

    def test_rotated_and_scaled_instance_remains_invertible(self):
        snapshot=roof_with_hole();matrix=snapshot.objects[0]['instances_data'][0]['matrix']
        # Rotate around the bed center, with a distinct model/profile identity.
        matrix[0]=[0.,-1.,0.,210.];matrix[1]=[1.,0.,0.,0.];matrix[2][2]=1.2
        warp=BendingWarp(snapshot,'1',RegionalShellSettings(nominal_layer_height_mm=.16))
        self.assertEqual(warp.flattened_snapshot.objects[0]['instances_data'][0]['matrix'],matrix)
        for point in warp.original_world_vertices:
            self.assertLess(math.dist(warp.map_point(warp.flatten_point(point)),point),1e-9)
