import copy
import json
import math
import sys
import unittest
from itertools import pairwise
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from orca_wave_studio.contracts import ProjectSnapshot, WaveError
from orca_wave_studio.geometry import IDENTITY
from orca_wave_studio.surface import SurfaceSettings, build_surface_study


def ring_snapshot():
    # A sloping square roof with a true through hole. Its analytic height is
    # independent of the sampler and its large facets stress the cone bound.
    outer = [(-5, -5), (5, -5), (5, 5), (-5, 5)]
    inner = [(-2, -2), (2, -2), (2, 2), (-2, 2)]
    vertices = [
        (x, y, 3 + 0.1 * x + 0.05 * y if top else 0.0)
        for top in (False, True)
        for x, y in outer + inner
    ]
    triangles = []

    def quad(a, b, c, d):
        triangles.extend([(a, b, c), (a, c, d)])

    for i in range(4):
        j = (i + 1) % 4
        quad(i, j, j + 8, i + 8)
        quad(j + 4, i + 4, i + 12, j + 12)
        quad(i + 8, j + 8, j + 12, i + 12)
        quad(i + 4, j + 4, j, i)
    obj = {
        "id": "ring",
        "name": "Sloping ring",
        "instances_data": [
            {
                "printable": True,
                "matrix": [[0, -1, 0, 20], [1, 0, 0, 30], [0, 0, 1, 2], [0, 0, 0, 1]],
            }
        ],
        "volumes": [
            {
                "kind": "part",
                "negative": False,
                "matrix": copy.deepcopy(IDENTITY),
                "vertices": vertices,
                "triangles": triangles,
            }
        ],
    }
    return ProjectSnapshot("roof", 0, (obj,), {})


class SurfaceStudyTests(unittest.TestCase):
    def test_every_torus_stroke_clears_the_analytic_hole_and_tracks_upper_branch(self):
        major, tube = 10.0, 2.5
        around, section = 96, 48
        vertices = []
        triangles = []

        def index(i, j):
            return (i % around) * section + j % section

        for i in range(around):
            a = math.tau * i / around
            for j in range(section):
                b = math.tau * j / section
                radius = major + tube * math.cos(b)
                vertices.append(
                    [
                        radius * math.cos(a),
                        radius * math.sin(a),
                        tube + tube * math.sin(b),
                    ]
                )
                p, q, r, s = (
                    index(i, j),
                    index(i + 1, j),
                    index(i + 1, j + 1),
                    index(i, j + 1),
                )
                triangles.extend([(p, q, r), (p, r, s)])
        snap = ring_snapshot()
        obj = snap.objects[0]
        obj["instances_data"][0]["matrix"] = IDENTITY
        obj["volumes"][0].update(vertices=vertices, triangles=triangles)
        report = build_surface_study(snap, "ring").report
        points = report["deformed_points"]
        checked = 0
        for lo, hi in pairwise(report["break_indices"] + [len(points)]):
            for a, b in pairwise(points[lo:hi]):
                x0, x1 = sorted((a[0], b[0]))
                # Closest point on the whole XY chord, not just its endpoints.
                self.assertGreater(
                    math.hypot(min(max(0.0, x0), x1), a[1]), major - tube
                )
                for ratio in (0.0, 0.5, 1.0):
                    x, y, z = (u + (v - u) * ratio for u, v in zip(a, b))
                    radial = math.hypot(x, y)
                    mathematical_top = tube + math.sqrt(tube**2 - (radial - major) ** 2)
                    # Includes tessellation of this independent analytic test model.
                    self.assertLess(abs(mathematical_top - z), 0.035)
                checked += 1
        self.assertEqual(checked, report["segments"])
        self.assertGreater(checked, 500)

    def test_upper_surface_uses_transformed_mesh_height_and_no_extrusion(self):
        snap = ring_snapshot()
        source = snap.revision
        study = build_surface_study(snap, "ring")
        r = study.report
        json.dumps(r, allow_nan=False)
        self.assertEqual(build_surface_study(snap, "ring").sha256, study.sha256)
        self.assertEqual(source, snap.revision)
        self.assertFalse(r["print_allowed"])
        self.assertTrue(r["bench_only"])
        self.assertEqual(r["total_e_delta"], 0.0)
        for line in study.gcode.decode().splitlines():
            cmd = line.split(";")[0]
            self.assertFalse(any(v.startswith("E") for v in cmd.split()))
            self.assertFalse(cmd.startswith(("M", "G28")))
        for x, y, z in r["deformed_points"]:
            self.assertAlmostEqual(z, 5 + 0.1 * (y - 30) - 0.05 * (x - 20), places=5)
        self.assertAlmostEqual(
            r["max_surface_slope_deg"], math.degrees(math.atan(math.hypot(0.1, 0.05)))
        )
        self.assertLessEqual(r["max_geometric_error_mm"], 0.02)
        self.assertGreaterEqual(r["min_segment_mm"], 0.15)
        self.assertLessEqual(r["max_segment_mm"], 0.4 + 1e-9)
        self.assertGreaterEqual(r["conditional_min_clearance_mm"], 0.0)
        self.assertLessEqual(r["projected_coverage_fraction"], 1.0 + 1e-9)

    def test_no_stroke_bridges_hole_and_travel_retracts_over_it(self):
        r = build_surface_study(ring_snapshot(), "ring")
        points = r.report["deformed_points"]
        boundaries = r.report["break_indices"] + [len(points)]
        by_y = {}
        for a, b in pairwise(boundaries):
            path = points[a:b]
            self.assertGreaterEqual(len(path), 2)
            y = path[0][1]
            by_y.setdefault(y, []).append(path)
            self.assertEqual(len({v[1] for v in path}), 1)
            if 28 < y < 32:
                self.assertTrue(
                    max(v[0] for v in path) <= 18 or min(v[0] for v in path) >= 22
                )
        self.assertTrue(any(28 < y < 32 and len(st) >= 2 for y, st in by_y.items()))
        lines = r.gcode.decode().splitlines()
        moves = [i for i, s in enumerate(lines) if s.startswith("G0 X")]
        self.assertEqual(len(moves), r.report["strokes"])
        self.assertTrue(
            all(
                lines[i - 1].startswith("G0 Z") and lines[i + 1].startswith("G0 Z")
                for i in moves
            )
        )

    def test_slope_and_conditional_material_gap_are_independent_constraints(self):
        snap = ring_snapshot()
        with self.assertRaises(WaveError):
            build_surface_study(snap, "ring", {"max_slope_deg": 3})
        with self.assertRaises(WaveError):
            build_surface_study(
                snap, "ring", {"prior_gap_mm": 0.0001, "flat_tip_radius_mm": 1.0}
            )
        with self.assertRaises(WaveError):
            build_surface_study(snap, "missing")
        with self.assertRaises(WaveError):
            SurfaceSettings(cone_half_angle_deg=90)

    def test_rejects_open_inconsistent_or_nonfinite_meshes(self):
        for invalid in ("open", "flipped", "extra", "nan", "modifier"):
            with self.subTest(invalid=invalid):
                snap = ring_snapshot()
                v = snap.objects[0]["volumes"][0]
                if invalid == "open":
                    v["triangles"].pop()
                elif invalid == "flipped":
                    v["triangles"][1] = tuple(reversed(v["triangles"][1]))
                elif invalid == "extra":
                    v["triangles"].append(v["triangles"][0])
                elif invalid == "nan":
                    v["vertices"][0] = (0, math.nan, 0)
                else:
                    v["negative"] = True
                with self.assertRaises(WaveError):
                    build_surface_study(snap, "ring")
