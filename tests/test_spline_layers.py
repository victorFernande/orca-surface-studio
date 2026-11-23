import math
import unittest
from collections import Counter
import numpy as np
from orca_wave_studio.contracts import ProjectSnapshot
from orca_wave_studio.spline_phase import SplinePhase
from orca_wave_studio.spline_layers import SplineLayerWarp
from orca_wave_studio.continuous_layers import LayerGridStage
from orca_wave_studio.geometry import IDENTITY,transform_point
from orca_wave_studio.regional_shell import RegionalShellSettings


class SplineLayerTests(unittest.TestCase):
    def test_smooth_copy_preserves_closed_source_geometry_with_complete_face_budget(self):
        vertices=[[x,y,z] for z in (0.,4.) for y in (1.,5.) for x in (1.,5.)]
        faces=[[0,2,3],[0,3,1],[4,5,7],[4,7,6],[0,1,5],[0,5,4],
               [2,6,7],[2,7,3],[0,4,6],[0,6,2],[1,3,7],[1,7,5]]
        source=ProjectSnapshot('spline',0,({'id':'1','name':'box','config':{},
            'instances_data':[{'id':'1','printable':True,'matrix':IDENTITY}],
            'volumes':[{'id':'1','kind':'part','negative':False,'matrix':IDENTITY,'vertices':vertices,'triangles':faces}]},))
        before=source.to_dict();axes=[np.arange(-4.,11.,2),np.arange(-4.,11.,2),np.arange(-3.5,11.,2)]
        coefficients=np.zeros(tuple(len(a) for a in axes));coefficients[3:5,3:5,4]=[[.1,-.1],[.1,-.1]]
        field=SplinePhase(axes,coefficients);regrid=LayerGridStage([.5,3.6,8.5],[.5,3.5,8.5])
        warp=SplineLayerWarp(source,'1',field,regrid,RegionalShellSettings(tolerance_mm=.01),
                             reference_audit={'reference_regions':[],'optimizer_status':'fixture'})
        self.assertEqual(before,source.to_dict())
        obj=warp.flattened_snapshot.objects[0];volume=obj['volumes'][0];instance=obj['instances_data'][0]
        points=[transform_point(p,instance['matrix'],volume['matrix']) for p in volume['vertices']]
        edges=Counter(tuple(sorted((a,b))) for tri in volume['triangles'] for a,b in zip(tri,(*tri[1:],tri[0])))
        self.assertTrue(all(count==2 for count in edges.values()))
        budget=warp.summary['mesh_normal_and_crease_error_budget_mm'];self.assertLessEqual(budget,.01)
        for tri in volume['triangles']:
            for weights in ((1/3,1/3,1/3),(.1,.2,.7)):
                p=tuple(sum(weights[j]*points[i][k] for j,i in enumerate(tri)) for k in range(3));q=warp.map_point(p)
                distance=min(abs(q[0]-1),abs(q[0]-5),abs(q[1]-1),abs(q[1]-5),abs(q[2]),abs(q[2]-4))
                self.assertLessEqual(distance,budget+1e-7)
        self.assertFalse(warp.summary['partial_adaptation'])
        old_bound=warp.summary['mesh_normal_and_crease_error_budget_mm']
        phase=field
        # Change knot locations as well as the native pitch. Whole triangle
        # interiors must restore the same preceding phase surface.
        warp.regrid_phase(LayerGridStage([.5,3.3,8.5],[.5,3.7,8.5]),
            {'reference_regions':[],'pitch':.19,'whole_reference_band_certificate_version':2})
        self.assertIs(warp.grid,phase)
        self.assertEqual(warp.summary['mesh_normal_and_crease_error_budget_mm'],old_bound)
        self.assertEqual(source.to_dict(),before)
        self.assertEqual(warp.map_point((2,2,.24)),(2,2,.24))
        volume=warp.flattened_snapshot.objects[0]['volumes'][0]
        edges=Counter(tuple(sorted((a,b))) for tri in volume['triangles'] for a,b in zip(tri,(*tri[1:],tri[0])))
        self.assertTrue(all(count==2 for count in edges.values()))
        for tri in volume['triangles']:
            for weights in ((1/3,1/3,1/3),(.1,.2,.7)):
                p=np.asarray([warp.flat_world_vertices[k] for k in tri]);q=warp.map_point(weights@p)
                distance=min(abs(q[0]-1),abs(q[0]-5),abs(q[1]-1),abs(q[1]-5),abs(q[2]),abs(q[2]-4))
                self.assertLessEqual(distance,old_bound+1e-7)


if __name__=='__main__':unittest.main()
