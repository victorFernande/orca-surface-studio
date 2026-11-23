"""Batched acceleration keeps complete scalar certificates, including knot ties."""
import unittest
import numpy as np
import test_spline_phase as fixtures


class BatchCertificateTests(unittest.TestCase):
    def test_scalar_and_batch_support_bounds_are_identical_at_knots(self):
        f=fixtures.SplinePhaseTests().field();rng=np.random.default_rng(923)
        queries=list(rng.uniform(-4,16,(700,3,3)))
        for k,knots in enumerate(f._support_knots):
            for value in knots:
                for edge in (np.nextafter(value,-np.inf),value,np.nextafter(value,np.inf)):
                    p=rng.uniform(1,9,(3,3));p[:,k]=edge;queries.append(p)
        queries=np.asarray(queries)
        h=f.hessian_bounds_many(queries);d=f.derivative_bounds_many(queries)
        for i,p in enumerate(queries):
            self.assertEqual({key:float(v[i]) for key,v in h.items()},f.hessian_bounds(p))
            low,high,gradient=f.derivative_bounds(p)
            self.assertEqual((float(d[0][i]),float(d[1][i]),tuple(d[2][i])),(low,high,gradient))

    def test_batch_triangle_edge_and_inverse_errors_keep_scalar_values(self):
        f=fixtures.SplinePhaseTests().field();p=np.random.default_rng(925).uniform(-3,14,(1300,3,3))
        p[:15,:,2]=f.anchor
        errors=f.phase_triangle_errors(p)
        np.testing.assert_array_equal(errors,[f.phase_triangle_error(q) for q in p])
        np.testing.assert_array_equal(f.inverse_phase_errors(p,errors),[f.inverse_phase_error(q,e) for q,e in zip(p,errors)])
        e=p[:,:2]
        np.testing.assert_array_equal(f.phase_edge_errors(e),[f.phase_edge_error(*q) for q in e])

    def test_empty_batches_and_cache_values_cannot_be_mutated(self):
        f=fixtures.SplinePhaseTests().field();empty=np.empty((0,3,3))
        self.assertEqual(f.phase_triangle_errors(empty).shape,(0,))
        self.assertEqual(f.inverse_phase_errors(empty,[]).shape,(0,))
        p=np.array([[[2.,2.,2.],[3.,3.,3.],[3.,2.,4.]]])
        initial=f.hessian_bounds(p[0]);batch=f.hessian_bounds_many(p)
        for value in batch.values():value[:]=999
        self.assertEqual(f.hessian_bounds(p[0]),initial)

    def test_full_chord_batch_matches_scalar_curvature(self):
        f=fixtures.SplinePhaseTests().field();rng=np.random.default_rng(930)
        a=rng.uniform(-2,12,(600,3));b=a+rng.uniform(-.5,.5,(600,3))
        pa=np.array([f.map_point(p) for p in a]);pb=np.array([f.map_point(p) for p in b])
        actual=f.chord_curvature_bounds_many(a,b,pa,pb)
        expected=np.array([f.chord_error_bound(u,v,p,q) for u,v,p,q in zip(a,b,pa,pb)])
        np.testing.assert_allclose(actual,expected,rtol=2e-15,atol=1e-18)
