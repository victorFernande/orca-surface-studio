"""Offline conformal upper-surface geometry. No printer interface or deposition."""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from collections import defaultdict
from dataclasses import asdict, dataclass
from itertools import pairwise

from .contracts import ProcessedResult, ProjectSnapshot, WaveError, digest
from .geometry import transform_point


@dataclass(frozen=True)
class SurfaceSettings:
    max_slope_deg: float = 30.0
    row_spacing_mm: float = 0.4
    step_mm: float = 0.4
    min_segment_mm: float = 0.15
    tolerance_mm: float = 0.02
    prior_gap_mm: float = 0.2
    flat_tip_radius_mm: float = 0.30
    cone_half_angle_deg: float = 30.0
    check_radius_mm: float = 1.5
    travel_lift_mm: float = 2.0

    def __post_init__(self):
        if not all(
            type(v) in {int, float} and math.isfinite(v) and v > 0
            for v in asdict(self).values()
        ):
            raise WaveError(
                "Os parâmetros de superfície devem ser números positivos e finitos."
            )
        if not (
            self.max_slope_deg < 90
            and self.cone_half_angle_deg < 90
            and self.flat_tip_radius_mm < self.check_radius_mm
            and 0.15 <= self.min_segment_mm <= self.step_mm <= 2
            and self.tolerance_mm <= 0.02
        ):
            raise WaveError(
                "Limites de inclinação, bico, corda ou tolerância incompatíveis."
            )


@dataclass(slots=True)
class Face:
    points: tuple
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    zmax: float
    nz: float
    gx: float
    gy: float
    gradient: float

    def height(self, x, y):
        px, py, pz = self.points[0]
        return pz + self.gx * (x - px) + self.gy * (y - py)

    def span(self, y):
        # Use the same edge orientation on neighboring triangles. Shared
        # intersection coordinates then agree even at a facet boundary.
        ends = []
        a = self.points[-1]
        for b in self.points:
            low, high = (a, b) if a[1] < b[1] else (b, a)
            if low[1] <= y < high[1]:
                ends.append(
                    low[0] + (y - low[1]) * (high[0] - low[0]) / (high[1] - low[1])
                )
            a = b
        if len(ends) == 2 and ends[0] != ends[1]:
            return min(ends), max(ends)
        return None


class SurfaceMesh:
    def __init__(self, obj, settings):
        instances = [i for i in obj["instances_data"] if i.get("printable", True)]
        volumes = obj["volumes"]
        if (
            len(instances) != 1
            or len(volumes) != 1
            or volumes[0]["kind"] != "part"
            or volumes[0].get("negative", False)
        ):
            raise WaveError(
                "O estudo requer uma instância imprimível e um volume sólido simples."
            )
        vol = volumes[0]
        if len(vol["triangles"]) > 250_000 or len(vol["vertices"]) > 250_000:
            raise WaveError("O estudo aceita até 250 mil faces e vértices.")
        verts = [
            tuple(transform_point(v, instances[0]["matrix"], vol["matrix"]))
            for v in vol["vertices"]
        ]
        if len(verts) < 4 or not all(math.isfinite(n) for v in verts for n in v):
            raise WaveError("Malha sem coordenadas finitas suficientes.")
        self.bounds = [[min(c) for c in zip(*verts)], [max(c) for c in zip(*verts)]]
        self.faces = []
        boundary = {}
        closed = set()
        parents = list(range(len(vol["triangles"])))

        def component(i):
            while parents[i] != i:
                parents[i] = parents[parents[i]]
                i = parents[i]
            return i

        volume6 = 0.0
        for face_id, tri in enumerate(vol["triangles"]):
            if len(tri) != 3 or any(
                type(k) is not int or not 0 <= k < len(verts) for k in tri
            ):
                raise WaveError("Índice de triângulo inválido.")
            a, b, c = (verts[k] for k in tri)
            u = tuple(v - w for v, w in zip(b, a))
            v = tuple(v - w for v, w in zip(c, a))
            nx, ny, nz = (
                u[1] * v[2] - u[2] * v[1],
                u[2] * v[0] - u[0] * v[2],
                u[0] * v[1] - u[1] * v[0],
            )
            area2 = math.hypot(nx, ny, nz)
            if not math.isfinite(area2) or area2 < 1e-12:
                raise WaveError("Triângulo degenerado na malha.")
            volume6 += sum((j - k) * n for j, k, n in zip(a, verts[0], (nx, ny, nz)))
            for i, j in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                key = (min(i, j), max(i, j))
                if key in closed:
                    raise WaveError(
                        "Uma aresta da malha pertence a mais de duas faces."
                    )
                if key in boundary:
                    direction, other = boundary.pop(key)
                    if direction == (i < j):
                        raise WaveError(
                            "Orientações incompatíveis nas faces de uma aresta."
                        )
                    parents[component(face_id)] = component(other)
                    closed.add(key)
                else:
                    boundary[key] = (i < j, face_id)
            xs, ys, zs = zip(a, b, c)
            gx, gy = (-nx / nz, -ny / nz) if nz else (0.0, 0.0)
            self.faces.append(
                Face(
                    (a, b, c),
                    min(xs),
                    max(xs),
                    min(ys),
                    max(ys),
                    max(zs),
                    nz,
                    gx,
                    gy,
                    math.hypot(gx, gy),
                )
            )
        if (
            not self.faces
            or boundary
            or not math.isfinite(volume6)
            or abs(volume6) < 1e-10
            or any(component(i) != component(0) for i in range(len(parents)))
        ):
            raise WaveError(
                "A malha deve ser fechada, com duas faces orientadas por aresta."
            )
        self.orientation = 1 if volume6 > 0 else -1
        self.cell = max(
            settings.check_radius_mm,
            (self.bounds[1][0] - self.bounds[0][0]) / 128,
            (self.bounds[1][1] - self.bounds[0][1]) / 128,
        )
        self.grid = defaultdict(list)
        self.bands = defaultdict(list)
        memberships = 0
        for index, f in enumerate(self.faces):
            memberships += len(self.cells(f.xmin, f.xmax)) * len(
                self.cells(f.ymin, f.ymax)
            )
            if memberships > 3_000_000:
                raise WaveError(
                    "A complexidade do índice espacial supera o limite do estudo."
                )
            for y in self.cells(f.ymin, f.ymax):
                self.bands[y].append(index)
                for x in self.cells(f.xmin, f.xmax):
                    self.grid[x, y].append(index)

    def cells(self, a, b):
        return range(math.floor(a / self.cell), math.floor(b / self.cell) + 1)

    def upper_runs(self, y, slope_limit):
        events = defaultdict(list)
        for i in self.bands[math.floor(y / self.cell)]:
            face = self.faces[i]
            if face.nz and face.ymin <= y < face.ymax:
                span = face.span(y)
                if span:
                    events[span[0]].append((True, i))
                    events[span[1]].append((False, i))
        active = set()
        runs = []
        current = []
        steep = 0.0
        for lo, hi in pairwise(sorted(events)):
            for entering, i in events[lo]:
                if entering:
                    active.add(i)
                else:
                    active.discard(i)
            if hi - lo < 1e-10 and active:
                continue
            top = None
            if active:
                top = max(
                    (self.faces[i] for i in active),
                    key=lambda f: f.height((lo + hi) * 0.5, y),
                )
                zl, zr = top.height(lo, y), top.height(hi, y)
                for i in active:
                    other = self.faces[i]
                    if (
                        other.height(lo, y) > zl + 1e-7
                        or other.height(hi, y) > zr + 1e-7
                    ):
                        raise WaveError(
                            "As faces superiores se cruzam no interior de uma faixa."
                        )
            if (
                top is None
                or top.nz * self.orientation <= 0
                or top.gradient > slope_limit
            ):
                if top is not None:
                    steep += hi - lo
                if current:
                    runs.append(current)
                    current = []
                continue
            if current and (
                abs(current[-1][1] - lo) > 1e-8 or abs(current[-1][3] - zl) > 1e-7
            ):
                runs.append(current)
                current = []
            current.append((lo, hi, zl, zr, top.gradient))
        if current:
            runs.append(current)
        return runs, steep

    def clearance(self, a, b, cfg):
        """Lower bound for all tip centers on the chord and all nearby faces.

        The assumed previous material is bounded above by the upper surface
        minus the vertical gap. Test the flat tip and truncated cone against
        every triangle whose projected box can enter that envelope.
        """
        rad = cfg.check_radius_mm
        x0, x1 = sorted((a[0], b[0]))
        y = a[1]
        ids = set()
        for iy in self.cells(y - rad, y + rad):
            for ix in self.cells(x0 - rad, x1 + rad):
                ids.update(self.grid.get((ix, iy), ()))
        cone = 1 / math.tan(math.radians(cfg.cone_half_angle_deg))
        flat = cfg.flat_tip_radius_mm
        zmin = min(a[2], b[2])
        bound = math.inf
        for i in ids:
            f = self.faces[i]
            r = math.hypot(
                max(0.0, f.xmin - x1, x0 - f.xmax), max(0.0, f.ymin - y, y - f.ymax)
            )
            if r > rad:
                continue
            # Conservative box bound, including vertical facets and overhangs.
            low = zmin + max(0.0, r - flat) * cone - f.zmax
            if f.nz:
                # A second bound uses the plane extended to the tool center.
                # The maximum plane-minus-tip height over this chord is at an
                # endpoint. The piecewise linear radial bound has at most one kink.
                d = max(f.height(a[0], y) - a[2], f.height(b[0], y) - b[2])
                worst_r = rad if f.gradient > cone else max(r, flat)
                low = max(
                    low, max(0.0, worst_r - flat) * cone - f.gradient * worst_r - d
                )
            bound = min(bound, low + cfg.prior_gap_mm)
            if bound < 0:
                break
        return bound


def sample_run(run, y, cfg):
    xs = [s[0] for s in run] + [run[-1][1]]
    zs = [s[2] for s in run] + [run[-1][3]]
    # Round inward, so a rounded endpoint never crosses a hole or slope boundary.
    lo = math.ceil(xs[0] * 1e5) / 1e5
    hi = math.floor(xs[-1] * 1e5) / 1e5
    if hi - lo < 1e-5:
        return []

    def height(x):
        i = max(0, min(len(run) - 1, bisect_right(xs, x) - 1))
        return zs[i] + (zs[i + 1] - zs[i]) * (x - xs[i]) / (xs[i + 1] - xs[i])

    max_gradient = max(s[4] for s in run)
    n = max(1, math.ceil((hi - lo) * math.hypot(1.0, max_gradient) / cfg.step_mm))
    while n <= (hi - lo) * math.hypot(1.0, max_gradient) / cfg.min_segment_mm + 1:
        points = []
        for j in range(n + 1):
            x = round(lo + (hi - lo) * j / n, 5)
            points.append((x, y, round(height(x), 5)))
        result = []
        for a, b in pairwise(points):
            d = math.dist(a, b)
            if d < cfg.min_segment_mm or b[0] <= a[0]:
                return []
            # Both mesh and chord are linear within each projected face.
            # Checking all crossed facet boundaries bounds vertical error exactly.
            x0, x1 = a[0], b[0]
            slope = (b[2] - a[2]) / (x1 - x0)
            err = max(abs(height(x0) - a[2]), abs(height(x1) - b[2]))
            for k in range(bisect_right(xs, x0), bisect_left(xs, x1)):
                err = max(err, abs(zs[k] - a[2] - slope * (xs[k] - x0)))
            if err > cfg.tolerance_mm or d > cfg.step_mm + 1e-9:
                break
            left = min(len(run) - 1, max(0, bisect_right(xs, x0) - 1))
            right = min(len(run), max(left + 1, bisect_left(xs, x1)))
            result.append((a, b, err, max(s[4] for s in run[left:right])))
        else:
            return result
        n += 1
    return []


def build_surface_study(
    snapshot: ProjectSnapshot, object_id: str, settings=None
) -> ProcessedResult:
    cfg = (
        settings
        if isinstance(settings, SurfaceSettings)
        else SurfaceSettings(**(settings or {}))
    )
    obj = next((o for o in snapshot.objects if str(o["id"]) == str(object_id)), None)
    if obj is None:
        raise WaveError("A peça selecionada não pertence ao projeto.")
    mesh = SurfaceMesh(obj, cfg)
    (xmin, ymin, _), (xmax, ymax, zmax) = mesh.bounds
    proposed_rows = (ymax - ymin) / cfg.row_spacing_mm
    if (
        proposed_rows > 4096
        or proposed_rows * (xmax - xmin) / cfg.min_segment_mm > 2_000_000
    ):
        raise WaveError("A seleção excede a resolução do estudo de bancada.")
    rows = math.floor(proposed_rows)
    slope_limit = math.tan(math.radians(cfg.max_slope_deg))
    strokes = []
    short_runs = rejected = 0
    steep = 0.0
    lower = math.inf
    max_error = max_gradient = visible_length = accepted_xy = 0.0
    for row in range(rows):
        y = round((ymin + ymax) / 2 + (row - (rows - 1) / 2) * cfg.row_spacing_mm, 5)
        runs, skipped = mesh.upper_runs(y, slope_limit)
        steep += skipped
        visible_length += sum(r[-1][1] - r[0][0] for r in runs) + skipped
        row_paths = []
        for run in runs:
            segments = sample_run(run, y, cfg)
            if not segments:
                short_runs += 1
                continue
            stroke = []
            for a, b, err, gradient in segments:
                clearance = mesh.clearance(a, b, cfg)
                if not math.isfinite(clearance):
                    raise WaveError(
                        "Não foi possível delimitar a folga do bico no segmento."
                    )
                if clearance < 0:
                    rejected += 1
                    if stroke:
                        row_paths.append(stroke)
                        stroke = []
                    continue
                lower = min(lower, clearance)
                max_error = max(max_error, err)
                max_gradient = max(max_gradient, gradient)
                accepted_xy += abs(b[0] - a[0])
                if not stroke:
                    stroke.append(a)
                stroke.append(b)
            if stroke:
                row_paths.append(stroke)
        strokes.extend(
            [list(reversed(p)) for p in reversed(row_paths)] if row % 2 else row_paths
        )
    if not strokes:
        raise WaveError(
            "Nenhuma faixa contínua atende às restrições geométricas do estudo."
        )
    code = [
        "; Orca Wave Studio - SURFACE GEOMETRY STUDY ONLY - NO DEPOSITION",
        "G21",
        "G90",
        ";LAYER_CHANGE",
        f";Z:{zmax:.5f}",
        f";HEIGHT:{cfg.prior_gap_mm:.5f}",
        ";TYPE:Custom",
    ]
    safe = math.ceil((zmax + cfg.travel_lift_mm) * 1e5) / 1e5
    total_points = sum(map(len, strokes))
    stride = max(1, math.ceil(total_points / 15000))
    points = []
    breaks = []
    lo = math.inf
    hi = total = 0.0
    visited = 0
    for stroke in strokes:
        a = stroke[0]
        code.extend(
            [
                f"G0 Z{safe:.5f} F300",
                f"G0 X{a[0]:.5f} Y{a[1]:.5f} F1200",
                f"G0 Z{a[2]:.5f} F300",
                "; surface trace",
            ]
        )
        for a, b in pairwise(stroke):
            code.append(f"G1 X{b[0]:.5f} Y{b[1]:.5f} Z{b[2]:.5f} F600")
            length = math.dist(a, b)
            total += length
            lo = min(lo, length)
            hi = max(hi, length)
        indices = range((-visited) % stride, len(stroke), stride)
        if indices:
            breaks.append(len(points))
            points.extend([list(stroke[i]) for i in indices])
        visited += len(stroke)
    code.append(f"G0 Z{safe:.5f} F300")
    data = ("\n".join(code) + "\n").encode("ascii")
    report = {
        "study_type": "conformal_top_surface",
        "bench_only": True,
        "print_allowed": False,
        "object_id": str(object_id),
        "snapshot_revision": snapshot.revision,
        "settings": asdict(cfg),
        "bounds_mm": mesh.bounds,
        "mesh_triangles": len(mesh.faces),
        "mesh_closed_oriented": True,
        "scan_rows": rows,
        "strokes": len(strokes),
        "segments": total_points - len(strokes),
        "path_length_mm": total,
        "min_segment_mm": lo,
        "max_segment_mm": hi,
        "max_surface_slope_deg": math.degrees(math.atan(max_gradient)),
        "visible_projected_area_estimate_mm2": cfg.row_spacing_mm * visible_length,
        "covered_projected_area_estimate_mm2": cfg.row_spacing_mm * accepted_xy,
        "projected_coverage_fraction": accepted_xy / visible_length,
        "max_geometric_error_mm": max_error,
        "conditional_min_clearance_mm": lower,
        "rejected_clearance_segments": rejected,
        "rejected_short_runs": short_runs,
        "projected_length_over_slope_mm": steep,
        "trace_z_range_mm": [
            min(p[2] for st in strokes for p in st),
            max(p[2] for st in strokes for p in st),
        ],
        "material_model": "Material anterior hipotético limitado por H(x,y) menos prior_gap_mm.",
        "nozzle_model": "Bico vertical com ponta plana e cone truncado no raio de verificação.",
        "pending": [
            "base e interior conformes",
            "camada anterior e apoio reais",
            "extrusão e fluxo",
            "geometria física completa do cabeçote e obstáculos da máquina",
        ],
        "total_e_delta": 0.0,
        "reference_plane_z_mm": zmax,
        "deformed_points": points,
        "original_points": [[x, y, zmax] for x, y, _ in points],
        "break_indices": breaks,
        "layer_ids": [0] * len(points),
        "output_sha256": digest(data),
    }
    return ProcessedResult(data, report)
