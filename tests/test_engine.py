import json
import math
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from orca_wave_studio.contracts import WaveError, WaveParameters
from orca_wave_studio.engine import process_gcode
from orca_wave_studio.engine_parser import read


def example(
    *,
    absolute=False,
    relative_xyz=False,
    polygon=None,
    layers=7,
    rotate=False,
    second=False,
):
    points = polygon or [
        (
            round(5 * math.cos(i * math.tau / 80), 4),
            round(5 * math.sin(i * math.tau / 80), 4),
        )
        for i in range(80)
    ]
    code = ["G90", "M82" if absolute else "M83", "G92 E0", "G1 X0 Y0 Z0 F1200"]
    if relative_xyz:
        code += ["G91", "M82" if absolute else "M83"]
    e = 0.0
    last = (0.0, 0.0, 0.0)

    def move(x, y, z, amount=0):
        nonlocal e, last
        coords = (
            (x, y, z)
            if not relative_xyz
            else tuple(round(v - b, 5) for v, b in zip((x, y, z), last))
        )
        e = round(e + amount, 6)
        last = (x, y, z)
        s = "G1 " + " ".join(k + str(round(v, 5)) for k, v in zip("XYZ", coords))
        if amount:
            s += " E" + str(e if absolute else amount)
        return s

    for n in range(layers):
        z = round((n + 1) * 0.2, 4)
        code += [";LAYER_CHANGE", ";Z:" + str(z), ";HEIGHT:0.2", ";WIDTH:0.45"]
        for obj in range(1 + second):
            label = f"identico.stl id:{obj} copy 0"
            code += ["; printing object " + label, ";TYPE:Outer wall"]
            off = n % len(points) if rotate else 0
            ring = [(x + 12 * obj, y) for x, y in (points[off:] + points[:off])]
            code.append(move(*ring[0], z))
            for a, b in zip(ring, ring[1:] + ring[:1]):
                code.append(move(*b, z, round(math.dist(a, b) * 0.035, 6)))
            code += ["; stop printing object " + label]
        if not rotate:
            code += [
                "G1 E" + str(round(e - 0.4, 6) if absolute else "-0.4") + " ;retract",
                "G1 E" + str(e if absolute else "0.4") + " ;recover",
                "G92 E0",
            ]
            e = 0.0
    code += ["M73 P90 R20", "; estimated printing time = 99m", "M107"]
    return ("\r\n".join(code) + "\r\n").encode()


def replay(data):
    pos = [0.0] * 3
    e = f = 0.0
    ab = ea = True
    records = []
    layer = -1
    obj = None
    for line in data.decode().splitlines():
        if line == ";LAYER_CHANGE":
            layer += 1
        if line.startswith("; printing object "):
            obj = int(re.search(r"id:(\d+)", line)[1])
        if line.startswith("; stop printing object "):
            obj = None
        command = line.split(";")[0].split()
        if not command:
            continue
        cmd = command[0]
        if cmd in {"G90", "G91"}:
            ab = cmd == "G90"
        elif cmd in {"M82", "M83"}:
            ea = cmd == "M82"
        elif cmd == "G92":
            for word in command[1:]:
                if word[0] == "E":
                    e = float(word[1:])
        elif cmd in {"G0", "G1"}:
            old = tuple(pos)
            de = 0.0
            for word in command[1:]:
                k = word[0]
                v = float(word[1:])
                if k in "XYZ":
                    j = "XYZ".index(k)
                    pos[j] = v if ab else pos[j] + v
                elif k == "E":
                    de = v - e if ea else v
                    e += de
                elif k == "F":
                    f = v
            records.append((layer, obj, old, tuple(pos), de, f, line))
    return records


def run(data, **kwargs):
    return process_gcode(
        data,
        {"A": WaveParameters(start_height_mm=0, fade_layers=2, **kwargs)},
        {0: "A", 1: "B"},
    )


class EngineTests(unittest.TestCase):
    def test_orca_251_modal_roles_and_m73_do_not_close_native_seam_gap(self):
        source = (
            Path(__file__).parent / "fixtures" / "orca_2_5_1_open_seam.gcode"
        ).read_bytes()
        p = WaveParameters(start_height_mm=1.0, end_height_mm=7.6)
        parsed = read(source, {"83": p}, {0: "83"})
        self.assertEqual(len(parsed.loops), 5)
        self.assertEqual(source.count(b";TYPE:Outer wall"), 1)
        self.assertIn(b"M73", source)
        for loop in parsed.loops[1:]:
            self.assertAlmostEqual(
                math.dist(loop[0].start, loop[-1].end), 0.040012498, places=7
            )
        with self.assertRaisesRegex(WaveError, "fechado"):
            process_gcode(source, {"83": p}, {0: "83"})

    def test_progress_inside_native_contour_while_role_remains_modal(self):
        source = example(rotate=True)
        rows = []
        tagged = False
        for row in source.splitlines(keepends=True):
            if row.startswith(b";TYPE:Outer wall"):
                if tagged:
                    continue
                tagged = True
            if row.startswith(b";LAYER_CHANGE"):
                rows.append(b"G92 E0\r\n")
            if row.startswith(b"G1 X") and b" E" in row and len(rows) % 7 == 0:
                rows.append(b"M73 P20 R8\r\n")
            rows.append(row)
        source = b"; generated by OrcaSlicer 2.5.1\r\n" + b"".join(rows)
        result = run(source, phase_deg=23)
        self.assertGreater(result.report["segments"], 200)
        self.assertNotIn(b"M73", result.gcode)
        self.assertLessEqual(result.report["max_geometric_error_mm"], 0.02)

    def test_identity_and_determinism(self):
        source = example()
        self.assertEqual(run(source, amplitude_mm=0).gcode, source)
        result = run(source)
        self.assertEqual(result, run(source))
        self.assertEqual(result.sha256, result.report["output_sha256"])
        json.dumps(result.report, allow_nan=False)
        self.assertTrue(result.report["bench_only"])
        self.assertNotIn(b"M73", result.gcode)
        self.assertLessEqual(result.report["max_geometric_error_mm"], 0.02)
        self.assertGreaterEqual(result.report["min_segment_mm"], 0.15)
        self.assertLessEqual(len(result.report["original_points"]), 15000)

    def test_z_actually_rises_and_falls_in_one_layer_and_fades(self):
        result = run(example())
        records = replay(result.gcode)
        depositing = [r for r in records if r[0] == 3 and r[4] > 0 and r[2] != r[3]]
        diffs = [r[3][2] - r[2][2] for r in depositing]
        self.assertLess(min(diffs), -0.001)
        self.assertGreater(max(diffs), 0.001)
        self.assertEqual(
            [r["amplitude_mm"] for r in result.report["contours"]],
            [0, 0.04, 0.08, 0.08, 0.08, 0.04, 0],
        )
        self.assertLess(result.report["normal_spacing_mm"][0], 0.17)
        self.assertGreater(result.report["normal_spacing_mm"][1], 0.23)
        # The flat final layer still compensates for the wavy predecessor.
        rates = [
            r[4] / math.dist(r[2], r[3])
            for r in records
            if r[0] == 6 and r[4] > 0 and r[2] != r[3]
        ]
        self.assertGreater(max(rates) / min(rates), 1.3)

    def test_seam_moves_and_spatial_phase_survives_rotated_starts(self):
        result = run(example(rotate=True), phase_deg=23)
        layers = {r["layer_id"]: r for r in result.report["contours"]}
        for layer, b in zip(
            result.report["layer_ids"], result.report["deformed_points"]
        ):
            m = layers[layer]
            expected = m["z_mm"] + m["amplitude_mm"] * math.sin(
                m["wave_count"] * math.atan2(b[1], b[0]) + math.radians(23)
            )
            self.assertAlmostEqual(b[2], expected, places=4)

    def test_object_identity_retraction_modes_and_offsets(self):
        for absolute, relative in [
            (True, False),
            (False, False),
            (True, True),
            (False, True),
        ]:
            with self.subTest(absolute=absolute, relative=relative):
                source = example(absolute=absolute, relative_xyz=relative, second=True)
                result = run(source)
                before, after = replay(source), replay(result.gcode)
                others = lambda seq: [
                    r
                    for r in seq
                    if r[1] == 1 or ";retract" in r[-1] or ";recover" in r[-1]
                ]
                old, new = others(before), others(after)
                self.assertEqual(len(old), len(new))
                for a, b in zip(old, new):
                    self.assertLess(math.dist(a[3], b[3]), 0.00002)
                    self.assertAlmostEqual(a[4], b[4], places=7)
                    self.assertEqual(a[5], b[5])
                    if not absolute:
                        self.assertEqual(a[-1], b[-1])
                measured = sum(r[4] for r in after) - sum(r[4] for r in before)
                self.assertAlmostEqual(
                    measured, result.report["total_e_delta"], places=6
                )

    def test_xy_keeps_sharp_corners_and_z(self):
        corners = [(0.0, 0.0), (8.0, 0.0), (8.0, 8.0), (0.0, 8.0)]
        result = run(example(polygon=corners), mode="xy", amplitude_mm=0.25)
        mids = [r for r in replay(result.gcode) if r[0] == 2 and r[1] == 0 and r[4] > 0]
        for c in corners:
            self.assertIn(c, [r[3][:2] for r in mids])
        self.assertTrue(any(r[3][1] < -0.01 for r in mids))
        self.assertTrue(all(r[3][2] == 0.6 for r in mids))

    def test_refuses_incompatible_edges_and_topology(self):
        for polygon in [
            [(0, 0), (0.06, 0), (0.06, 5), (0, 5)],
            [(0, 0), (5, 5), (0, 5), (5, 0)],
        ]:
            with self.subTest(polygon=polygon), self.assertRaises(WaveError):
                run(example(polygon=polygon), mode="xy")
        data = example()
        additional = b"G1 X1 Y1\r\nG1 X2 Y1 E.01\r\nG1 X1 Y2 E.01\r\nG1 X1 Y1 E.01\r\n"
        for invalid in [
            data.replace(b"; stop printing", additional + b"; stop printing"),
            data.replace(
                b"; stop printing",
                b";TYPE:Sparse infill\r\n" + additional + b"; stop printing",
            ),
            data.replace(b";TYPE:Outer wall", b";TYPE:"),
            data.replace(b"G1 X", b"G2 X", 1),
            data.replace(b" id:0", b" id:9"),
            data.replace(b";WIDTH:0.45", b";width unknown"),
        ]:
            with self.assertRaises(WaveError):
                run(invalid)

    def test_estimated_axis_limits_cap_and_restore_feed(self):
        source = example()
        result = run(source, max_z_speed_mm_s=0.3, max_z_acceleration_mm_s2=0.5)
        self.assertLessEqual(result.report["max_z_speed_mm_s"], 0.3 + 1e-9)
        self.assertLessEqual(result.report["max_z_acceleration_mm_s2"], 0.5 + 1e-9)
        records = replay(result.gcode)
        self.assertTrue(any(r[5] < 100 for r in records if r[1] == 0))
        self.assertTrue(all(r[5] == 1200 for r in records if ";retract" in r[-1]))

    def test_updates_only_material_metadata_with_known_units(self):
        prefix = (
            b"; filament_diameter = 1.75\r\n; filament_density = 1.24\r\n"
            b"; filament used [mm] = 20.0\r\n; total filament volume [cm^3] : 0.048\r\n"
            b"; total filament weight [g] : 0.06\r\n; total filament cost = 3.45\r\n"
        )
        result = run(prefix + example(), mode="xy", amplitude_mm=0.25)
        delta = result.report["total_e_delta"]
        self.assertGreater(abs(delta), 0.001)
        for key, value in [
            ("filament used [mm] = ", 20 + delta),
            (
                "total filament volume [cm^3] : ",
                0.048 + delta * math.pi * 0.875**2 / 1000,
            ),
        ]:
            match = re.search(re.escape(key) + r"([0-9.]+)", result.gcode.decode())
            self.assertAlmostEqual(float(match[1]), value, places=6)
        self.assertNotIn(b"total filament cost", result.gcode)
        self.assertAlmostEqual(
            result.report["estimates"]["mass_g"],
            0.06 + delta * math.pi * 0.875**2 * 0.00124,
        )
        unknown = run(b"; filament used [g] = 20\r\n" + example())
        self.assertNotIn(b"filament used [g]", unknown.gcode)
        self.assertIsNone(unknown.report["estimates"]["mass_g"])

    def test_refuses_mixed_prime_after_coordinate_reset(self):
        src = example().replace(
            b";TYPE:Outer wall", b"G1 E-0.4\r\nG92 E0\r\n;TYPE:Outer wall", 1
        )
        with self.assertRaisesRegex(WaveError, "retração"):
            run(src)

    def test_xy_merges_tiny_collinear_edge_and_preserves_infill_literally(self):
        source = example(polygon=[(0, 0), (0.03, 0), (8, 0), (8, 8), (0, 8)], layers=1)
        insert = b";TYPE:Sparse infill\r\nG1 X2 Y2 F1500\r\nG1 X5 Y2 E0.1\r\n"
        source = source.replace(b"; stop printing", insert + b"; stop printing")
        result = run(source, mode="xy", amplitude_mm=0.2)
        self.assertIn(insert, result.gcode)
        self.assertGreaterEqual(result.report["min_segment_mm"], 0.15)
        self.assertGreater(result.report["segments"], 10)


if __name__ == "__main__":
    unittest.main()
