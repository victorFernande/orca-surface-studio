import unittest
import numpy as np
from orca_wave_studio.material_sampling import material_samples
from orca_wave_studio.surface import SurfaceMesh,SurfaceSettings
from orca_wave_studio.contracts import WaveError
from test_bending import roof_with_hole
from test_spline_planning import wedge


class MaterialSamplingTests(unittest.TestCase):
    def test_interior_near_base_is_included_and_source_is_unchanged(self):
        source=wedge();before=source.to_dict();mesh=SurfaceMesh(source.objects[0],SurfaceSettings())
        samples=material_samples(mesh)
        self.assertTrue(np.any((samples[:,0]>2)&(samples[:,0]<4)&(samples[:,1]>2)&(samples[:,1]<4)&
                               (samples[:,2]>.5)&(samples[:,2]<2.5)))
        self.assertEqual(source.to_dict(),before)

    def test_through_hole_is_not_filled_by_volume_sampling_and_cancel_is_honored(self):
        mesh=SurfaceMesh(roof_with_hole().objects[0],SurfaceSettings());samples=material_samples(mesh)
        hole=(samples[:,0]>102.000001)&(samples[:,0]<107.999999)&(samples[:,1]>102.000001)&(samples[:,1]<107.999999)
        self.assertFalse(hole.any())
        with self.assertRaisesRegex(WaveError,'cancelada'):
            material_samples(mesh,cancelled=lambda:True)


if __name__=='__main__':unittest.main()
