import unittest
from collections import Counter
import numpy as np
from orca_wave_studio.bending import _clip
import test_certified_refinement as fixtures


class PlaneClipTests(unittest.TestCase):
    def test_split_preserves_closed_oriented_volume_and_reference_interpolation(self):
        rng=np.random.default_rng(71)
        for plane in [(0.,0.,1.,0.),(0.,0.,1.,-2.),(1.,0.,0.,-1.),
                      *[tuple(rng.normal(size=3))+(-1.,) for _ in range(20)]]:
            vertices,faces=fixtures.CertifiedRefinementTests().cube()
            world=list(map(tuple,vertices));reference=[tuple(2*np.asarray(p)+3) for p in world]
            result=_clip(vertices,faces,world,plane,reference_world=reference)
            directed=Counter((a,b) for t in result for a,b in zip(t,(*t[1:],t[0])))
            self.assertTrue(all(n==1 and directed[b,a]==1 for (a,b),n in directed.items()))
            self.assertEqual(len(vertices)-len(directed)//2+len(result),2)
            p=np.asarray(vertices)[result];normal=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0])
            self.assertTrue(np.all(np.linalg.norm(normal,axis=1)>1e-12))
            self.assertAlmostEqual(float(np.einsum('ij,ij->',p[:,0],normal)/6),8.)
            np.testing.assert_array_equal(vertices,world)
            np.testing.assert_allclose(reference,2*np.asarray(world)+3,atol=1e-14,rtol=0.)
