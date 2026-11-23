import unittest
import numpy as np
import test_spline_phase as fixtures
from orca_wave_studio.spline_layers import _face_bounds,_crease_bounds


class GlobalCertificatePrefilterTests(unittest.TestCase):
    def test_global_prefilter_never_accepts_a_face_rejected_by_local_certificate(self):
        f=fixtures.SplinePhaseTests().field();rng=np.random.default_rng(704)
        origin=rng.uniform([1,1,.1],[8,8,8],(900,1,3))
        p=origin+rng.uniform(-1,1,(900,3,3))*np.geomspace(.002,4,900)[:,None,None]
        n=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]);length=np.linalg.norm(n,axis=1)
        exact=abs(n[:,2])/length*f.inverse_phase_errors(p,f.phase_triangle_errors(p))+1e-8
        inactive=(abs(n[:,2])<=1e-12*length)|(p[:,:,2].max(axis=1)<=f.anchor)
        exact[inactive]=0.
        for tolerance in (.001,.01,.02):
            bound=_face_bounds(f,p,tolerance)
            self.assertTrue(np.all(bound>=exact-2e-15))
            np.testing.assert_array_equal(bound>tolerance,exact>tolerance)
            self.assertGreater(np.count_nonzero((bound<=tolerance)&(bound>exact)),100)

    def test_global_prefilter_keeps_crease_acceptance_and_positive_enclosure(self):
        f=fixtures.SplinePhaseTests().field();rng=np.random.default_rng(705)
        p=rng.uniform([1,1,.1],[9,9,8],(700,2,3))
        p[:,1]=p[:,0]+(p[:,1]-p[:,0])*np.geomspace(.001,1,700)[:,None]
        exact=f.inverse_phase_errors(p,f.phase_edge_errors(p))+1e-8
        for tolerance in (.001,.01,.02):
            bound=_crease_bounds(f,p,tolerance)
            self.assertTrue(np.all(bound>=exact-2e-15))
            np.testing.assert_array_equal(bound>tolerance,exact>tolerance)
