"""Coupled radial/Z deformation of labelled, single-wall planar vase contours.

The cylindrical-coordinate map is R=r+A(z)sin(n theta+phase),
Z=z-q A(z)sin(n theta+phase). A grows quadratically with source height.
No slicing, printer transport, or host access occurs in this module.
"""
from __future__ import annotations

import math
from itertools import pairwise

from .contracts import WaveError
from .engine_geometry import Path, simple_polygon


def contour_center(moves):
    points = [m.start[:2] for m in moves] + [moves[-1].end[:2]]
    return tuple((min(c) + max(c)) / 2 for c in zip(*points))


class SineVasePath(Path):
    def __init__(self, moves, params, amplitude, previous, center):
        seam = math.dist(moves[0].start, moves[-1].end)
        if seam > min(0.25, (moves[0].w or 0) * 0.75):
            raise WaveError("O vaso tem uma abertura de contorno maior que a costura permitida.")
        super().__init__(moves, params, amplitude, previous, None, open_seam=True)
        self.center = center
        self.n = params.wave_count
        self.phase = math.radians(params.phase_deg)
        # Orca may change F or rounded E density very close to the seam.
        # Integrate E through those knots and use the slowest source feed for
        # the whole contour, instead of creating a new sub-minimum segment.
        self.events = {0.0, self.s[-1]}
        self.events.update(self.s[i] for i in range(len(moves))
                           if self.sharp[i] or moves[i-1].comment)
        self.feed = min(m.f for m in moves)
        closed = self.p + [self.p[0]] if self.open_seam else self.p
        direction = simple_polygon(closed)
        self.radius_min = math.inf
        turn = 0.0
        for a, b in pairwise(closed):
            u = (a[0] - center[0], a[1] - center[1])
            v = (b[0] - center[0], b[1] - center[1])
            da = math.atan2(u[0]*v[1] - u[1]*v[0], u[0]*v[0] + u[1]*v[1])
            if direction * da <= 1e-10 or abs(da) >= math.pi / 2:
                raise WaveError("Use um vaso com contorno radial simples, sem alças ou reentrâncias.")
            turn += da
            dx, dy = b[0]-a[0], b[1]-a[1]
            t = max(0, min(1, -(u[0]*dx+u[1]*dy)/(dx*dx+dy*dy)))
            self.radius_min = min(self.radius_min, math.hypot(u[0]+t*dx, u[1]+t*dy))
        if abs(abs(turn) - math.tau) > 1e-6:
            raise WaveError("O contorno do vaso deve envolver um único centro.")
        if amplitude >= self.radius_min * 0.45:
            raise WaveError("Reduza a intensidade: as ondas se aproximam demais do centro do vaso.")
        self.min_vertical_gap = math.inf
        self.max_vertical_gap = 0.0

    def sample(self):
        pieces = super().sample()
        for piece in pieces:
            piece.f = self.feed
        return pieces

    def at(self, s):
        _, _, p = self.location(s)
        dx, dy = p[0]-self.center[0], p[1]-self.center[1]
        r = math.hypot(dx, dy)
        d = self.amp * math.sin(self.n*math.atan2(dy, dx) + self.phase)
        return (p[0]+d*dx/r, p[1]+d*dy/r, self.z-self.par.z_ratio*d)

    def second_bound(self, i):
        # For a unit-speed straight source edge, |theta'| <= 1/r,
        # |theta''| <= 2/r², |radial_unit''| <= 3/r².
        radial = self.n*self.n + 4*self.n + 3
        vertical = self.par.z_ratio * (self.n*self.n + 2*self.n)
        return self.amp * math.hypot(radial, vertical) / self.radius_min**2

    def extrusion(self, a, b, p, q):
        # Integrate the finite-volume Jacobian, not 3D path length. Across
        # each source layer A is linearly interpolated between its two bounds:
        # det J = (1+A sin(theta*n)/r) * (1-q*dA/dz*sin(theta*n)).
        # Five-point Gauss quadrature follows the original polyline through
        # all source knots, including a sampler interval spanning vertices.
        nodes = (0, -.5384693101056831, .5384693101056831,
                 -.9061798459386640, .9061798459386640)
        weights = (.5688888888888889, .4786286704993665, .4786286704993665,
                   .2369268850561891, .2369268850561891)
        knots = [a] + [s for s in self.s if a < s < b] + [b]
        total = 0.0
        for lo, hi in pairwise(knots):
            mid, half = (lo+hi)/2, (hi-lo)/2
            integral = 0.0
            for node, weight in zip(nodes, weights):
                i, _, point = self.location(mid+half*node)
                move = self.moves[i]
                dx, dy = point[0]-self.center[0], point[1]-self.center[1]
                r = math.hypot(dx, dy)
                wave = math.sin(self.n*math.atan2(dy, dx)+self.phase)
                gap = move.h-self.par.z_ratio*(self.amp-self.previous)*wave
                if not move.w or not 0.25*move.h <= gap <= move.w:
                    raise WaveError("Reduza a intensidade ou inicie as ondas mais abaixo: transição entre camadas incompatível.")
                self.min_vertical_gap = min(self.min_vertical_gap, gap)
                self.max_vertical_gap = max(self.max_vertical_gap, gap)
                jacobian = (1+(self.amp+self.previous)*wave/(2*r))*gap/move.h
                integral += weight * jacobian * move.de/(self.s[i+1]-self.s[i])
            total += half*integral
        return total
