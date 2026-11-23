import unittest
from collections import Counter
import numpy as np
from orca_wave_studio.certified_refinement import refine_mesh
from orca_wave_studio.contracts import WaveError


class CertifiedRefinementTests(unittest.TestCase):
    def cube(self):
        v=[[float(x),float(y),float(z)] for z in (0,2) for y in (0,2) for x in (0,2)]
        t=[(0,2,3),(0,3,1),(4,5,7),(4,7,6),(0,1,5),(0,5,4),
           (2,6,7),(2,7,3),(0,4,6),(0,6,2),(1,3,7),(1,7,5)]
        return v,t

    def test_conforming_rounds_preserve_oriented_closed_surface_and_volume(self):
        v,t=self.cube();before=np.asarray(v).copy();world=list(map(tuple,v));ref=list(map(tuple,v))
        edges={tuple(sorted((a,b))) for row in t for a,b in zip(row,(*row[1:],row[0]))}
        # Complete quadratic interpolation envelope, with an edge bound that
        # forces different one/two/three-edge split configurations as it shrinks.
        def faces(points,triangles,original):
            p=np.asarray(original)[triangles];d=np.roll(p,-1,axis=1)-p
            return np.sum(d*d,axis=-1).max(axis=1)/6
        def creases(p):return np.sum((p[:,1]-p[:,0])**2,axis=1)/8
        result,error=refine_mesh(v,t,world,.08,100000,reference_world=ref,crease_edges=edges,
                                 face_bounds=faces,edge_bounds=creases)
        self.assertLessEqual(error,.08);self.assertGreater(len(result),len(t))
        np.testing.assert_array_equal(np.asarray(v)[:len(before)],before)
        directed=Counter((a,b) for row in result for a,b in zip(row,(*row[1:],row[0])))
        self.assertTrue(all(count==1 and directed[b,a]==1 for (a,b),count in directed.items()))
        self.assertEqual(len(v)-len(directed)//2+len(result),2)
        p=np.asarray(v)[result];norm=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0])
        self.assertTrue(np.all(np.linalg.norm(norm,axis=1)>0))
        self.assertAlmostEqual(float(np.einsum('ij,ij->',p[:,0],norm)/6),8.)
        self.assertTrue(np.all(np.any((np.asarray(v)==0)|(np.asarray(v)==2),axis=1)))
        np.testing.assert_array_equal(v,world);np.testing.assert_array_equal(v,ref)

    def test_cancellation_and_face_budget_fail_without_claiming_a_result(self):
        v,t=self.cube()
        def should_not_run(*a):raise AssertionError('Cancelled refinement evaluated a certificate')
        with self.assertRaisesRegex(WaveError,'cancelada'):
            refine_mesh(v,t,list(map(tuple,v)),.01,100,reference_world=v.copy(),crease_edges=set(),
                        face_bounds=should_not_run,edge_bounds=should_not_run,cancelled=lambda:True)
        with self.assertRaisesRegex(WaveError,'COMPLEXITY'):
            refine_mesh(v,t,list(map(tuple,v)),.01,10,reference_world=v.copy(),crease_edges=set(),
                        face_bounds=should_not_run,edge_bounds=should_not_run)
