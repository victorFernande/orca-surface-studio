import copy
import json
import math
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from orca_wave_studio.conformal_geometry import ConformalSettings, ConformalWarp
from orca_wave_studio.contracts import ProjectSnapshot, WaveError
from orca_wave_studio.geometry import IDENTITY, transform_point


def rotated_torus():
    verts = []
    tris = []
    around, section = 40, 64

    def idx(i, j):
        return (i % around) * section + j % section

    for i in range(around):
        a = i * math.tau / around
        for j in range(section):
            b = j * math.tau / section
            radius = 10 + 2.5 * math.cos(b)
            # Part-local torus plane is XZ. The instance rotates it onto the bed.
            verts.append(
                [radius * math.cos(a), 2.5 + 2.5 * math.sin(b), -radius * math.sin(a)]
            )
            p, q, r, s = idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)
            tris.extend([(p, q, r), (p, r, s)])
    obj = {
        "id": "41",
        "name": "Local torus",
        "instances_data": [
            {
                "printable": True,
                "id": "55",
                "matrix": [
                    [1.0, 0.0, 0.0, 20.0],
                    [0.0, 0.0, -1.0, 30.0],
                    [0.0, 1.0, 0.0, 0.0],
                    [0.0, 0.0, 0.0, 1.0],
                ],
            }
        ],
        "volumes": [
            {
                "id": "30",
                "kind": "part",
                "negative": False,
                "matrix": copy.deepcopy(IDENTITY),
                "vertices": verts,
                "triangles": tris,
            }
        ],
    }
    return ProjectSnapshot("geometry-fixture", 2, (obj,), {})


class ConformalGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = rotated_torus()
        cls.warp = ConformalWarp(cls.source, "41")

    def test_flatten_clone_xy_base_ids_and_surface_roundtrip(self):
        w = self.warp
        old = self.source.objects[0]
        flat = w.flattened_snapshot.objects[0]
        self.assertEqual(old["instances_data"], flat["instances_data"])
        self.assertEqual(
            old["volumes"][0]["triangles"], flat["volumes"][0]["triangles"]
        )
        self.assertEqual(old["id"], flat["id"])
        self.assertEqual(self.source.plate_index, w.flattened_snapshot.plate_index)
        self.assertNotEqual(self.source.revision, w.flattened_snapshot.revision)
        self.assertFalse(w.summary["print_allowed"])
        json.dumps(w.summary, allow_nan=False)
        inst = old["instances_data"][0]["matrix"]
        vol = old["volumes"][0]["matrix"]
        count = 0
        for a, b in zip(old["volumes"][0]["vertices"], flat["volumes"][0]["vertices"]):
            p = transform_point(a, inst, vol)
            q = transform_point(b, inst, vol)
            self.assertAlmostEqual(p[0], q[0])
            self.assertAlmostEqual(p[1], q[1])
            if p[2] <= w.anchor_z:
                self.assertEqual(a, b)
            if q[2] > p[2] + 1e-10:
                count += 1
                self.assertLess(math.dist(w.map_point(q), p), 1e-9)
                self.assertGreaterEqual(w.local_scale(*p[:2]), 0.5 - 1e-10)
        self.assertGreater(count, 50)
        self.assertAlmostEqual(w.anchor_z, 3.8)

    def test_face_centroid_heights_and_differential_against_numeric_derivative(self):
        w = self.warp
        face = next(p for p in w.patches if p.active and math.hypot(p.dx, p.dy) > 0.05)
        (x, y, z) = tuple(sum(t) / 3 for t in zip(*face.face.points))
        h, t = w.surface_heights(x, y)
        self.assertAlmostEqual(h, z)
        self.assertGreater(t, h)
        self.assertAlmostEqual(w.map_point((x, y, t))[2], h)
        zflat = (t + w.anchor_z) * 0.5
        eps = 1.0e-6
        fx = (
            w.map_point((x + eps, y, zflat))[2] - w.map_point((x - eps, y, zflat))[2]
        ) / (2 * eps)
        fy = (
            w.map_point((x, y + eps, zflat))[2] - w.map_point((x, y - eps, zflat))[2]
        ) / (2 * eps)
        gx, gy = w.gradient(x, y, zflat)
        self.assertAlmostEqual(gx, fx, places=7)
        self.assertAlmostEqual(gy, fy, places=7)
        for upper, layer in [(zflat, 0.1), (w.anchor_z + 0.02, 0.2)]:
            dz = w.map_point((x, y, upper))[2] - w.map_point((x, y, upper - layer))[2]
            gx, gy = w.gradient(x, y, upper)
            self.assertAlmostEqual(
                w.normal_gap(x, y, upper, layer), dz / math.hypot(1, gx, gy)
            )

    def test_hole_and_travel_outside_are_identity(self):
        w = self.warp
        for x, y in ((20, 30), (300, 350)):
            self.assertIsNone(w.surface_heights(x, y))
            self.assertEqual(w.map_point((x, y, 15)), (x, y, 15))
            self.assertEqual(w.normal_gap(x, y, 8.0, 0.2), 0.2)
        self.assertEqual(
            w.chord_error_bound(
                (1000, 1000, 8), (2000, 2000, 8), (1000, 1000, 8), (2000, 2000, 8)
            ),
            0.0,
        )

    def test_analytic_chord_bound_encloses_dense_samples_across_facets_and_anchor(self):
        w = self.warp
        rand = random.Random(152)
        nonzero = 0
        for _ in range(28):
            a = (rand.uniform(8, 12), rand.uniform(27, 33), rand.uniform(3.6, 5.2))
            b = (rand.uniform(28, 32), rand.uniform(27, 33), rand.uniform(4.5, 5.3))
            oa = tuple(round(z, 4) for z in w.map_point(a))
            ob = tuple(round(z, 4) for z in w.map_point(b))
            bound = w.chord_error_bound(a, b, oa, ob)
            for j in range(151):
                t = j / 150
                sample = tuple(x + t * (y - x) for x, y in zip(a, b))
                chord = tuple(x + t * (y - x) for x, y in zip(oa, ob))
                error = math.dist(w.map_point(sample), chord)
                self.assertLessEqual(error, bound + 1e-9)
                nonzero += error > 0.01
        self.assertGreater(nonzero, 50)

    def test_noop_and_upper_undercut_rejection(self):
        with self.assertRaises(WaveError):
            ConformalSettings(min_scale=0.49)
        ident = ConformalWarp(self.source, "41", ConformalSettings(min_scale=1))
        self.assertEqual(ident.summary["max_lift_mm"], 0.0)
        self.assertEqual(ident.summary["min_local_scale"], 1.0)
        self.assertEqual(ident.flattened_snapshot.revision, self.source.revision)
        standing = copy.deepcopy(self.source)
        standing.objects[0]["instances_data"][0]["matrix"] = copy.deepcopy(IDENTITY)
        with self.assertRaisesRegex(WaveError, "inferior|cavidade"):
            ConformalWarp(standing, "41", ConformalSettings(anchor_depth_mm=12.0))
