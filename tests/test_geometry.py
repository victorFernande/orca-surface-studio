import copy
import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from orca_wave_studio.fixtures import cylinder_snapshot
from orca_wave_studio.geometry import (
    IDENTITY,
    analyze_object,
    analyze_snapshot,
    freeze_model,
    transform_point,
)


class GeometryTests(unittest.TestCase):
    def test_unprintable_sibling_does_not_block_printable_object(self):
        snapshot = cylinder_snapshot(two_objects=True)
        snapshot.objects[1]["instances_data"][0]["printable"] = False
        result = analyze_snapshot(snapshot)
        printable = next(row for row in result if row["id"] == "100")
        self.assertEqual(printable["bounds"], [[40.0, 40.0, 0.0], [80.0, 80.0, 8.0]])

    def test_only_volume_config_changed_invalidates_frozen_project(self):
        settings = {"wall_loops": "1"}
        mesh = SimpleNamespace(
            vertices=lambda: [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
            triangles=lambda: [[0, 1, 2]],
            is_manifold=lambda: False,
        )
        vol = SimpleNamespace(
            id=lambda: 3,
            name="part",
            matrix=lambda: IDENTITY,
            is_model_part=lambda: True,
            is_negative_volume=lambda: False,
            mesh=lambda: mesh,
            type=lambda: "ModelPart",
            config_keys=lambda: list(settings),
            config_value=settings.__getitem__,
            extruder_id=lambda: 1,
        )
        instance = SimpleNamespace(
            id=lambda: 4, matrix=lambda: IDENTITY, is_printable=lambda: True
        )
        obj = SimpleNamespace(
            id=lambda: 2,
            name="same",
            volumes=lambda: [vol],
            instances=lambda: [instance],
            config_keys=list,
        )
        model = SimpleNamespace(
            id=lambda: 1, current_plate_index=lambda: 0, objects=lambda: [obj]
        )
        before = freeze_model(model)
        settings["wall_loops"] = "4"
        after = freeze_model(model)
        self.assertNotEqual(before.revision, after.revision)

    def test_volume_transform_precedes_rotated_scaled_instance(self):
        volume = [[1, 0, 0, 3], [0, 1, 0, 7], [0, 0, 1, 2], [0, 0, 0, 1]]
        instance = [[0, -2, 0, 10], [3, 0, 0, 20], [0, 0, 0.5, 30], [0, 0, 0, 1]]
        self.assertEqual(
            transform_point([1, 2, 4], instance, volume), [-8.0, 32.0, 33.0]
        )
        obj = {
            "id": "bound",
            "name": "triângulo",
            "instances_data": [{"matrix": instance, "printable": True}],
            "volumes": [
                {
                    "kind": "part",
                    "matrix": volume,
                    "vertices": [[1, 2, 4], [2, 2, 4], [1, 3, 4]],
                    "triangles": [[0, 1, 2]],
                }
            ],
        }
        result = analyze_object(obj)
        self.assertEqual(result["bounds"], [[-10.0, 32.0, 33.0], [-8.0, 35.0, 33.0]])
        self.assertAlmostEqual(result["geometry"]["horizontal_area_mm2"], 3.0)
        self.assertEqual(result["geometry"]["vertical_area_mm2"], 0.0)
        self.assertEqual(result["analysis_status"], "preliminary")

    def test_same_bounds_same_name_different_mesh_invalidates_identity(self):
        snap = cylinder_snapshot()
        edited = copy.deepcopy(snap)
        # Move a non-extremal perimeter vertex inwards, preserving the six extrema.
        vertex = edited.objects[0]["volumes"][0]["vertices"][3]
        vertex[0] *= 0.75
        vertex[1] *= 0.75
        original = analyze_snapshot(snap)[0]
        new = analyze_snapshot(edited)[0]
        self.assertEqual(original["bounds"], new["bounds"])
        self.assertNotEqual(
            original["geometry_fingerprint"], new["geometry_fingerprint"]
        )
        self.assertNotEqual(snap.revision, edited.revision)
        self.assertGreater(
            original["geometry"]["vertical_area_mm2"], 0.99 * math.tau * 20 * 8
        )

    def test_unprintable_copy_and_negative_volume_excluded_from_bounds(self):
        obj = copy.deepcopy(cylinder_snapshot().objects[0])
        instance = copy.deepcopy(obj["instances_data"][0])
        instance["matrix"][0][3] = 5000
        instance["printable"] = False
        obj["instances_data"].append(instance)
        negative = copy.deepcopy(obj["volumes"][0])
        negative["negative"] = True
        negative["matrix"][0][3] = 999
        obj["volumes"].append(negative)
        result = analyze_object(obj)
        self.assertEqual(result["bounds"], [[40.0, 40.0, 0.0], [80.0, 80.0, 8.0]])
        self.assertTrue(any("negativ" in s for s in result["reasons"]))
