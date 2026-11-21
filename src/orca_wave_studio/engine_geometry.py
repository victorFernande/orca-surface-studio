"""Polyline sampling, certified chord bounds and the single-wall cylinder model."""

from __future__ import annotations

import itertools
import math
from bisect import bisect_left, bisect_right
from dataclasses import dataclass

from .contracts import WaveError


def cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def simple_polygon(points):
    if len(points) < 4 or math.dist(points[0], points[-1]) > 1e-7:
        raise WaveError("Um perímetro externo precisa formar um contorno fechado.")
    edges = sorted(
        (min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1]), i, a, b)
        for i, (a, b) in enumerate(itertools.pairwise(points))
    )
    active = []
    for x, xmax, y, ymax, i, a, b in edges:
        if math.dist(a, b) < 1e-8:
            raise WaveError("Vértices duplicados no perímetro.")
        active = [e for e in active if e[0] >= x - 1e-9]
        for _, lo, hi, j, c, d in active:
            if abs(i - j) in {1, len(edges) - 1} or hi < y - 1e-9 or lo > ymax + 1e-9:
                continue
            if (
                cross(a, b, c) * cross(a, b, d) <= 1e-15
                and cross(c, d, a) * cross(c, d, b) <= 1e-15
            ):
                raise WaveError("Perímetro com autointerseção ou contato ambíguo.")
        active.append((xmax, y, ymax, i, a, b))
    area = sum(a[0] * b[1] - a[1] * b[0] for a, b in itertools.pairwise(points))
    if abs(area) < 1e-8:
        raise WaveError("Área do perímetro degenerada.")
    return 1 if area > 0 else -1


def circle(points, tol):
    pts = points[:-1]
    n = len(pts)
    if n < 12:
        raise WaveError("Z requer um cilindro circular amostrado.")
    a = pts[0]
    b = max(pts, key=lambda p: math.dist(a, p))
    c = max(pts, key=lambda p: abs(cross(a, b, p)))
    bx, by = b[0] - a[0], b[1] - a[1]
    cx, cy = c[0] - a[0], c[1] - a[1]
    det = 2 * (bx * cy - by * cx)
    if abs(det) < 1e-8:
        raise WaveError("Não foi possível identificar o cilindro.")
    ux = ((bx * bx + by * by) * cy - (cx * cx + cy * cy) * by) / det
    uy = (bx * (cx * cx + cy * cy) - cx * (bx * bx + by * by)) / det
    center = (a[0] + ux, a[1] + uy)
    radius = math.hypot(ux, uy)
    angles = []
    for p, q in itertools.pairwise(points):
        pv = (p[0] - center[0], p[1] - center[1])
        qv = (q[0] - center[0], q[1] - center[1])
        angles.append(
            math.atan2(pv[0] * qv[1] - pv[1] * qv[0], pv[0] * qv[0] + pv[1] * qv[1])
        )
        # Distance to the segment also checks the radial error between vertices.
        v = (q[0] - p[0], q[1] - p[1])
        t = max(
            0,
            min(
                1,
                ((center[0] - p[0]) * v[0] + (center[1] - p[1]) * v[1])
                / (v[0] ** 2 + v[1] ** 2),
            ),
        )
        foot = (p[0] + v[0] * t, p[1] + v[1] * t)
        if (
            abs(math.dist(p, center) - radius) > tol
            or abs(math.dist(foot, center) - radius) > tol
        ):
            raise WaveError(
                "Z aceita somente contornos circulares repetidos de cilindro."
            )
    if min(angles) * max(angles) <= 0 or abs(abs(sum(angles)) - math.tau) > 1e-6:
        raise WaveError("O perímetro deve dar exatamente uma volta no cilindro.")
    return center, radius


@dataclass
class Piece:
    start: tuple
    end: tuple
    original: tuple
    e: float
    f: float
    err: float
    comment: str


class Path:
    def __init__(self, moves, params, amplitude, previous, cylinder, *, open_seam=False):
        self.moves = moves
        self.par = params
        self.amp, self.previous = amplitude, previous
        self.z = moves[0].z
        self.p = [m.start[:2] for m in moves] + [moves[-1].end[:2]]
        self.open_seam = open_seam and math.dist(self.p[0], self.p[-1]) > 1e-7
        direction = simple_polygon(self.p + [self.p[0]] if self.open_seam else self.p)
        self.s = [0.0]
        self.total_e = [0.0]
        self.normals = []
        for m, a, b in zip(moves, self.p, self.p[1:]):
            length = math.dist(a, b)
            self.s.append(self.s[-1] + length)
            self.total_e.append(self.total_e[-1] + m.de)
            self.normals.append(
                (
                    direction * (b[1] - a[1]) / length,
                    -direction * (b[0] - a[0]) / length,
                )
            )
        self.events = {0.0, self.s[-1]}
        self.knots = set(self.s)
        self.vertex = []
        self.sharp = []
        self.ramp = min(params.wavelength_mm / 4, 2.0)
        for i, v in enumerate(self.normals):
            u = self.normals[i - 1]
            dot = max(-1, min(1, v[0] * u[0] + v[1] * u[1]))
            turn = math.degrees(math.acos(dot))
            if turn > 179.999:
                raise WaveError("Inversão de sentido no contorno.")
            sharp = turn >= params.corner_threshold_deg
            self.sharp.append(sharp)
            mag = math.hypot(u[0] + v[0], u[1] + v[1])
            self.vertex.append(((u[0] + v[0]) / mag, (u[1] + v[1]) / mag))
            if sharp or moves[i - 1].comment or moves[i].f != moves[i - 1].f:
                self.events.add(self.s[i])
            a = self.s[i + 1] - self.s[i]
            b = self.s[i] - self.s[i - 1] if i else self.s[-1] - self.s[-2]
            if abs(moves[i].de / a - moves[i - 1].de / b) > 0.000025 * (1 / a + 1 / b):
                self.events.add(self.s[i])
        for i, v in enumerate(self.sharp):
            start, end = self.s[i : i + 2]
            if v or self.sharp[(i + 1) % len(moves)]:
                self.knots.update(
                    [
                        min(start + self.ramp, end),
                        max(end - self.ramp, start),
                        (start + end) * 0.5,
                    ]
                )
        self.knots = sorted(self.knots)
        self.cylinder = cylinder
        perimeter = math.tau * cylinder[1] if cylinder else self.s[-1]
        self.n = max(1, round(perimeter / params.wavelength_mm))
        self.k = math.tau * self.n / perimeter
        self.phase = math.radians(params.phase_deg + self.z * params.twist_deg_per_mm)
        self.min_h = math.inf
        self.max_h = 0.0

    def location(self, s):
        i = min(len(self.moves) - 1, bisect_right(self.s, s) - 1)
        t = (s - self.s[i]) / (self.s[i + 1] - self.s[i])
        a, b = self.p[i : i + 2]
        return i, t, (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))

    def at(self, s):
        i, t, p = self.location(s)
        if self.cylinder:
            center, _r = self.cylinder
            theta = math.atan2(p[1] - center[1], p[0] - center[0])
            return (*p, self.z + self.amp * math.sin(self.n * theta + self.phase))
        j = (i + 1) % len(self.moves)
        u = self.normals[i] if self.sharp[i] else self.vertex[i]
        v = self.normals[i] if self.sharp[j] else self.vertex[j]
        fade = min(
            1.0,
            (s - self.s[i]) / self.ramp if self.sharp[i] else 1.0,
            (self.s[i + 1] - s) / self.ramp if self.sharp[j] else 1.0,
        )
        d = self.amp * fade * math.sin(self.k * s + self.phase)
        return (
            p[0] + d * (u[0] + t * (v[0] - u[0])),
            p[1] + d * (u[1] + t * (v[1] - u[1])),
            self.z,
        )

    def second_bound(self, i):
        if self.cylinder:
            r = self.cylinder[1] - 2 * self.par.tolerance_mm
            if r <= 0:
                raise WaveError("Raio insuficiente.")
            return self.amp * (self.n**2 + 2 * self.n) / r**2
        j = (i + 1) % len(self.moves)
        u = self.normals[i] if self.sharp[i] else self.vertex[i]
        v = self.normals[i] if self.sharp[j] else self.vertex[j]
        dn = math.dist(u, v) / (self.s[i + 1] - self.s[i])
        df = 1 / self.ramp if self.sharp[i] or self.sharp[j] else 0.0
        return self.amp * (self.k**2 + 2 * self.k * (df + dn) + 2 * df * dn)

    def error(self, a, b, p, q):
        # On each smooth subinterval the linear interpolation remainder is
        # bounded by max ||curve''|| * ds² / 8. Endpoint distances include
        # coordinate rounding and crossing original polygon vertices.
        knots = (
            [a]
            + self.knots[bisect_right(self.knots, a) : bisect_left(self.knots, b)]
            + [b]
        )

        def endpoint(s):
            t = (s - a) / (b - a)
            return math.dist(self.at(s), tuple(x + t * (y - x) for x, y in zip(p, q)))

        best = 0.0
        for l, r in itertools.pairwise(knots):
            i = self.location((l + r) * 0.5)[0]
            best = max(
                best,
                max(endpoint(l), endpoint(r)) + self.second_bound(i) * (r - l) ** 2 / 8,
            )
        return best

    def cumulative_e(self, s):
        i, t, _ = self.location(s)
        return self.total_e[i] + t * self.moves[i].de

    def extrusion(self, a, b, p, q):
        base = (self.cumulative_e(b) - self.cumulative_e(a)) * math.dist(p, q) / (b - a)
        if not self.cylinder:
            return base
        i, _, mid = self.location((a + b) * 0.5)
        m = self.moves[i]
        center, r = self.cylinder
        phase = self.n * math.atan2(mid[1] - center[1], mid[0] - center[0]) + self.phase
        slope = self.amp * self.n / r * math.cos(phase)
        dz = m.h + (self.amp - self.previous) * math.sin(phase)
        hn = dz / math.sqrt(1 + slope * slope)
        if not m.w or not 0 < hn <= m.w or m.h > m.w:
            raise WaveError(
                "Seção do cordão incompatível com a altura normal ou largura desconhecida."
            )
        self.min_h = min(self.min_h, hn)
        self.max_h = max(self.max_h, hn)

        # Cross-section of a bead with semicircular ends, h(w-h)+pi*h²/4.
        def area(h):
            return h * (m.w - h) + math.pi * h * h / 4

        return base * area(hn) / area(m.h)

    def sample(self):
        out = []
        events = sorted(self.events)
        for lo, hi in itertools.pairwise(events):
            target = max(1, math.ceil((hi - lo) / self.par.step_mm - 1e-9))
            for count in range(
                target,
                max(target + 1, math.ceil((hi - lo) / self.par.min_segment_mm) * 2 + 2),
            ):
                trial = []
                for j in range(count):
                    a = lo + (hi - lo) * j / count
                    b = hi if j + 1 == count else lo + (hi - lo) * (j + 1) / count
                    p, q = [tuple(round(v, 5) for v in self.at(s)) for s in (a, b)]
                    length = math.dist(p, q)
                    if length < self.par.min_segment_mm:
                        raise WaveError(
                            "Uma quina, evento ou curvatura exige segmento abaixo do mínimo."
                        )
                    if length > self.par.step_mm + 1e-10:
                        break
                    err = self.error(a, b, p, q)
                    if err > self.par.tolerance_mm:
                        break
                    _i, _t, point = self.location(b)
                    end_index = bisect_left(self.s, b)
                    comment = (
                        self.moves[end_index - 1].comment
                        if end_index
                        and end_index < len(self.s)
                        and abs(self.s[end_index] - b) < 1e-9
                        else ""
                    )
                    feed = self.moves[self.location((a + b) * 0.5)[0]].f
                    trial.append(
                        Piece(
                            p,
                            q,
                            (*point, self.z),
                            self.extrusion(a, b, p, q),
                            feed,
                            err,
                            comment,
                        )
                    )
                else:
                    out.extend(trial)
                    break
            else:
                raise WaveError("Tolerância e mínimo de segmento incompatíveis.")
        projected = [out[0].start[:2]] + [piece.end[:2] for piece in out]
        simple_polygon(projected + [projected[0]] if self.open_seam else projected)
        return out
