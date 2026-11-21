import copy
import math
import unittest
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))

from orca_wave_studio.contracts import ProjectSnapshot,WaveError
from orca_wave_studio.geometry import IDENTITY,transform_point
from orca_wave_studio.mesh_normalization import normalize_snapshot
from orca_wave_studio.mesh_refinement import refine_region
from orca_wave_studio.surface import SurfaceMesh,SurfaceSettings
from orca_wave_studio.conformal_geometry import ConformalWarp,ConformalSettings,_local_region,_region_weights


def snapshot(vertices,triangles):
    return ProjectSnapshot('local-top',0,({'id':'roof','name':'roof with taller detail',
        'instances_data':[{'id':'copy','printable':True,'matrix':copy.deepcopy(IDENTITY)}],
        'volumes':[{'id':'mesh','kind':'part','negative':False,'matrix':copy.deepcopy(IDENTITY),
                    'vertices':vertices,'triangles':triangles}]},),{})


def roof_with_taller_detail():
    n=17;vertices=[]
    for top in (True,False):
        for y in range(n):
            for x in range(n):
                z=(20 if x==y==8 else 6+.007*x*x) if top else 0
                vertices.append([x,y,z])
    faces=[];offset=n*n
    for y in range(n-1):
        for x in range(n-1):
            a=y*n+x;b=a+1;c=b+n;d=a+n
            faces.extend([(a,b,c),(a,c,d),(a+offset,c+offset,b+offset),(a+offset,d+offset,c+offset)])
    rim=[*range(n),*(y*n+n-1 for y in range(1,n)),
         *((n-1)*n+x for x in range(n-2,-1,-1)),*(y*n for y in range(n-2,0,-1))]
    for a,b in zip(rim,(*rim[1:],rim[0])):
        faces.extend([(a,b+offset,b),(a,a+offset,b+offset)])
    return snapshot(vertices,faces)


class LocalConformalTests(unittest.TestCase):
    def test_zero_area_t_junction_repair_preserves_the_surface_and_source(self):
        vertices=[[0,0,0],[2,0,0],[0,2,0],[0,0,2],[1,0,0]]
        source=snapshot(vertices,[(0,2,1),(0,4,3),(4,1,3),(1,2,3),(2,0,3),(0,1,4)])
        before=source.revision
        with self.assertRaisesRegex(WaveError,'degenerado'):SurfaceMesh(source.objects[0],SurfaceSettings())
        clean,report=normalize_snapshot(source,'roof')
        mesh=SurfaceMesh(clean.objects[0],SurfaceSettings())
        self.assertEqual(len(mesh.faces),6)
        self.assertEqual(report['vertices_moved'],0)
        self.assertEqual(report['removed_zero_area_triangles'],1)
        self.assertEqual(source.revision,before)
        self.assertEqual(clean.objects[0]['volumes'][0]['vertices'],vertices)
        self.assertEqual(mesh.bounds,[[0,0,0],[2,2,2]])

    def test_normalization_does_not_fill_a_real_hole(self):
        source=snapshot([[0,0,0],[2,0,0],[0,2,0],[0,0,2]],[(0,2,1),(0,1,3),(1,2,3)])
        clean,report=normalize_snapshot(source,'roof')
        self.assertEqual(report['removed_zero_area_triangles'],0)
        with self.assertRaisesRegex(WaveError,'fechada'):SurfaceMesh(clean.objects[0],SurfaceSettings())

    def test_refinement_is_conforming_and_keeps_existing_vertices(self):
        source=snapshot([[0,0,0],[2,0,0],[0,2,0],[0,0,2]],[(0,2,1),(0,1,3),(1,2,3),(2,0,3)])
        refined,report=refine_region(source,'roof',{0},max_edge_mm=.8)
        SurfaceMesh(refined.objects[0],SurfaceSettings())
        self.assertGreater(report['added_vertices'],0)
        self.assertEqual(refined.objects[0]['volumes'][0]['vertices'][:4],source.objects[0]['volumes'][0]['vertices'])
        # Every refined point remains on the original tetrahedron boundary.
        for p in refined.objects[0]['volumes'][0]['vertices']:
            self.assertTrue(min(p)==0 or abs(sum(p)-2)<1e-12)

    def test_local_roof_is_selected_below_the_taller_detail_and_roundtrips(self):
        source=roof_with_taller_detail();before=source.revision
        w=ConformalWarp(source,'roof')
        self.assertEqual(w.summary['surface_scope'],'local_top_region')
        self.assertLess(w.summary['zmax_mm'],10)
        self.assertEqual(w.summary['selected_region']['global_zmax_mm'],20)
        self.assertGreater(w.summary['lifted_vertices'],0)
        old=source.objects[0]['volumes'][0]['vertices'];new=w.flattened_snapshot.objects[0]['volumes'][0]['vertices']
        self.assertEqual(new[144],old[144])
        self.assertEqual(source.revision,before)
        changed=0
        for p,q in zip(old,new):
            if p!=q:
                changed+=1
                self.assertLess(math.dist(w.map_point(q),p),1e-8)
                self.assertEqual(p[:2],q[:2])
        self.assertGreater(changed,0)
        self.assertFalse(w.summary['print_allowed'])

    def test_local_roof_chord_certificate_bounds_dense_samples(self):
        w=ConformalWarp(roof_with_taller_detail(),'roof')
        for x in range(2,14):
            a=(x,3.,7.5);b=(x+.4,3.,7.5)
            p=w.map_point(a);q=w.map_point(b)
            bound=w.chord_error_bound(a,b,p,q)
            for j in range(41):
                t=j/40
                native=tuple(u+t*(v-u) for u,v in zip(a,b))
                chord=tuple(u+t*(v-u) for u,v in zip(p,q))
                self.assertLessEqual(math.dist(w.map_point(native),chord),bound+1e-8)

    def test_transition_has_no_jump_across_a_thin_triangle_next_to_the_collar(self):
        source=roof_with_taller_detail();obj=source.objects[0]
        mesh=SurfaceMesh(obj,SurfaceSettings());triangles=obj['volumes'][0]['triangles']
        region=_local_region(mesh,triangles,ConformalSettings())
        weights=_region_weights(mesh,triangles,region,5.8,2.)
        for i in region['ids']:
            face=mesh.faces[i];tri=triangles[i]
            for j in range(3):
                a,b=tri[j],tri[(j+1)%3]
                distance=math.dist(face.points[j],face.points[(j+1)%3])
                self.assertLessEqual(abs(weights[a]-weights[b]),.75*distance+1e-9)
