import math
import unittest
from collections import Counter,defaultdict

from orca_wave_studio.contracts import WaveError
from orca_wave_studio.geometry import transform_point
from orca_wave_studio.roof_fixtures import ROOF_ANGLES,roof_coupon


def triangle_area(a,b,c):
    u=[b[k]-a[k] for k in range(3)];v=[c[k]-a[k] for k in range(3)]
    return math.hypot(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])/2


class RoofFixtureTests(unittest.TestCase):
    def test_manifold_orientation_connected_volume_and_exposed_surface_areas(self):
        for angle in ROOF_ANGLES:
            with self.subTest(angle=angle):
                s,truth=roof_coupon(angle);obj=s.objects[0];vol=obj['volumes'][0]
                vertices=vol['vertices'];faces=vol['triangles'];edges=Counter();neighbors=defaultdict(set)
                volume=0.
                for face in faces:
                    a,b,c=[vertices[k] for k in face]
                    self.assertGreater(triangle_area(a,b,c),1e-9)
                    cross=(b[1]*c[2]-b[2]*c[1],b[2]*c[0]-b[0]*c[2],b[0]*c[1]-b[1]*c[0])
                    volume+=sum(a[k]*cross[k] for k in range(3))/6
                    for x,y in zip(face,(*face[1:],face[0])):
                        edges[x,y]+=1;neighbors[x].add(y);neighbors[y].add(x)
                for (a,b),count in edges.items():
                    self.assertEqual(count,1)
                    self.assertEqual(edges[b,a],1)
                visited=set();queue=[faces[0][0]]
                while queue:
                    v=queue.pop()
                    if v in visited:continue
                    visited.add(v);queue.extend(neighbors[v]-visited)
                self.assertEqual(visited,set(neighbors))
                # Base + anchor + constant-vertical-thickness roof; no internal faces.
                expected=196+20*(2+math.tan(math.radians(angle)))+200
                self.assertAlmostEqual(volume,expected,places=8)
                for region,projected in [('top',100),('underside',80)]:
                    area=sum(triangle_area(*(vertices[k] for k in faces[i])) for i in truth['regions'][region]['triangle_indices'])
                    self.assertAlmostEqual(area,projected/math.cos(math.radians(angle)),places=9)

    def test_world_planes_dimensions_and_original_angle_are_exact(self):
        for angle in ROOF_ANGLES:
            s,t=roof_coupon(angle);obj=s.objects[0];vol=obj['volumes'][0]
            points=[transform_point(v,obj['instances_data'][0]['matrix'],vol['matrix']) for v in vol['vertices']]
            for name,key in [('top','top_plane_world'),('underside','bottom_plane_world')]:
                plane=t['roof'][key]
                self.assertAlmostEqual(math.degrees(math.atan(math.hypot(*plane[:2]))),angle)
                for index in t['regions'][name]['triangle_indices']:
                    for k in vol['triangles'][index]:
                        x,y,z=points[k];self.assertAlmostEqual(z,plane[0]*x+plane[1]*y+plane[2],places=10)
                        self.assertTrue(105<=x<=115 and 105<=y<=115)
                        if name=='underside':self.assertGreaterEqual(x,107)
            self.assertEqual(min(p[2] for p in points),0)
            self.assertEqual(t['roof']['top_plane_world'][2]-t['roof']['bottom_plane_world'][2],2)
            self.assertEqual(s.revision,roof_coupon(angle)[0].revision)
            self.assertFalse(t['physical_gate']['print_allowed'])

    def test_invalid_angle_does_not_create_a_fixture(self):
        for value in [0,30,float('nan'),True,'20']:
            with self.subTest(value=value),self.assertRaises(WaveError):roof_coupon(value)
