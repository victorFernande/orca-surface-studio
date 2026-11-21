"""Finite-volume upper-surface flattening and its piecewise-rational inverse."""

from __future__ import annotations

import copy
import math
import heapq
from collections import defaultdict
from dataclasses import asdict, dataclass
from functools import lru_cache
from itertools import pairwise

from .contracts import ProjectSnapshot, WaveError
from .geometry import transform_point
from .surface import SurfaceMesh, SurfaceSettings
from .mesh_normalization import normalize_snapshot
from .mesh_refinement import refine_region


@dataclass(frozen=True)
class ConformalSettings:
    anchor_depth_mm: float = 1.2
    fade_start_depth_mm: float = 0.8
    fade_full_depth_mm: float = 0.4
    full_slope_deg: float = 20.0
    max_slope_deg: float = 30.0
    max_lift_mm: float = 0.6
    min_scale: float = 0.5
    step_mm: float = 0.4
    min_segment_mm: float = 0.15
    tolerance_mm: float = 0.02
    local_transition_mm: float = 2.0
    retain_native_short_edges: bool = False

    def __post_init__(self):
        if not all(
            type(v) in {int, float} and math.isfinite(v)
            for k,v in asdict(self).items() if k != 'retain_native_short_edges'
        ):
            raise WaveError("Parâmetros conformais devem ser números finitos.")
        if type(self.retain_native_short_edges) is not bool:
            raise WaveError('A proposta de preservar arestas nativas deve ser booleana.')
        if not (
            0
            <= self.fade_full_depth_mm
            < self.fade_start_depth_mm
            < self.anchor_depth_mm
            and 0 <= self.full_slope_deg < self.max_slope_deg < 90
            and self.max_lift_mm > 0
            and 0.5 <= self.min_scale <= 1
            and 0.15 <= self.min_segment_mm <= self.step_mm <= 2
            and 0 < self.tolerance_mm <= 0.02
            and 0.4 <= self.local_transition_mm <= 5
        ):
            raise WaveError(
                "Faixas de profundidade, inclinação, escala ou amostragem incompatíveis."
            )


def _smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def _local_z_direction(instance, volume):
    # Solve M * d_local = (0,0,1). Oriented affine matrices may include
    # rotations, reflection, nonuniform scales and shear.
    for m in (instance, volume):
        if tuple(m[3]) != (0.0, 0.0, 0.0, 1.0):
            raise WaveError("A transformação da peça deve ser afim.")
    m = [
        [sum(instance[i][k] * volume[k][j] for k in range(3)) for j in range(3)]
        for i in range(3)
    ]
    a, b, c = m
    d = (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )
    det = sum(x * y for x, y in zip(c, d))
    if abs(det) < 1e-14:
        raise WaveError("Transformação da instância não é invertível.")
    return tuple(x / det for x in d)


def _cap_polygon(points, anchor):
    result = []
    a = points[-1]
    for b in points:
        if (a[2] > anchor) != (b[2] > anchor):
            t = (anchor - a[2]) / (b[2] - a[2])
            result.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
        if b[2] > anchor:
            result.append(b[:2])
        a = b
    return result


def _overlap(a, b):
    # The separating axis theorem excludes shared boundaries. Interior overlap
    # means the upper cap cannot be represented by one height per XY position.
    for poly in (a, b):
        prev = poly[-1]
        for p in poly:
            nx, ny = p[1] - prev[1], prev[0] - p[0]
            prev = p
            size = math.hypot(nx, ny)
            if size < 1e-12:
                continue
            va = [nx * x + ny * y for x, y in a]
            vb = [nx * x + ny * y for x, y in b]
            if min(max(va), max(vb)) - max(min(va), min(vb)) <= 1e-9 * size:
                return False
    return True


def _local_region(mesh, triangles, cfg):
    """Find the highest substantial curved top, independent of a taller detail."""
    parents=list(range(len(triangles)));edges={}
    def find(i):
        while parents[i]!=i:
            parents[i]=parents[parents[i]];i=parents[i]
        return i
    eligible=[]
    for i,(face,tri) in enumerate(zip(mesh.faces,triangles)):
        if face.nz*mesh.orientation<=0 or face.gradient>math.tan(math.radians(cfg.max_slope_deg)):
            continue
        eligible.append(i)
        for a,b in zip(tri,(*tri[1:],tri[0])):
            edge=tuple(sorted((a,b)))
            if edge in edges:parents[find(i)]=find(edges[edge])
            else:edges[edge]=i
    groups=defaultdict(list)
    for i in eligible:groups[find(i)].append(i)
    threshold=max(4.,.02*(mesh.bounds[1][0]-mesh.bounds[0][0])*(mesh.bounds[1][1]-mesh.bounds[0][1]))
    candidates=[]
    for ids in groups.values():
        area=sum(abs(mesh.faces[i].nz)/2 for i in ids)
        if area<threshold:continue
        points=[p for i in ids for p in mesh.faces[i].points]
        low=min(p[2] for p in points);high=max(p[2] for p in points)
        if high-low<.05:continue
        candidates.append({'ids':set(ids),'area_xy_mm2':area,'z_range_mm':[low,high],
                           'bounds_mm':[[min(p[k] for p in points) for k in range(3)],
                                        [max(p[k] for p in points) for k in range(3)]]})
    if not candidates:return None
    chosen=max(candidates,key=lambda r:(r['z_range_mm'][1],r['area_xy_mm2']))
    if chosen['z_range_mm'][1]>=mesh.bounds[1][2]-cfg.anchor_depth_mm:
        return None  # Preserve the existing top-cap pilot for the torus.
    return {**chosen,'candidate_count':len(candidates),'selection':'highest substantial curved top',
            'global_zmax_mm':mesh.bounds[1][2]}


def _region_weights(mesh, triangles, region, anchor, fade):
    ids=region['ids'];boundary=set();graph=defaultdict(dict);points={}
    for i,(face,tri) in enumerate(zip(mesh.faces,triangles)):
        for k,p in zip(tri,face.points):points[k]=p
        if i not in ids:
            boundary.update(tri);continue
        for a,b in zip(tri,(*tri[1:],tri[0])):
            graph[a][b]=graph[b][a]=math.dist(points.get(a,face.points[tri.index(a)]),
                                           points.get(b,face.points[tri.index(b)]))
        # Do not map a cavity ceiling or an overhanging feature above the
        # anchor. Test projected triangle interiors, not bounding boxes alone.
        candidates=set()
        for iy in mesh.cells(face.ymin,face.ymax):
            for ix in mesh.cells(face.xmin,face.xmax):candidates.update(mesh.grid.get((ix,iy),()))
        poly=[p[:2] for p in face.points]
        for j in candidates:
            other=mesh.faces[j]
            occluding_detail=(j not in ids and other.zmax>region['z_range_mm'][1]+1e-8)
            if ((other.nz*mesh.orientation<0 and other.zmax>anchor) or occluding_detail):
                cap=_cap_polygon(other.points,anchor)
                if len(cap)>=3 and _overlap(poly,cap):
                    boundary.update(tri);break
    boundary.intersection_update(graph)
    distances={k:0. for k in boundary};queue=[(0.,k) for k in boundary];heapq.heapify(queue)
    while queue:
        value,k=heapq.heappop(queue)
        if value!=distances[k]:continue
        for other,length in graph[k].items():
            candidate=value+length
            if candidate<distances.get(other,math.inf):
                distances[other]=candidate;heapq.heappush(queue,(candidate,other))
    protected=set(boundary)
    for i in ids:
        tri=triangles[i]
        if min(distances.get(k,0.) for k in tri)<fade:
            protected.update(tri)
    # Recompute distance from the entire protected collar. Using the original
    # boundary distances here would jump from zero to full lift across a thin
    # adjacent triangle, creating steep artificial ridges in the field.
    distances={k:0. for k in protected};queue=[(0.,k) for k in protected];heapq.heapify(queue)
    while queue:
        value,k=heapq.heappop(queue)
        if value!=distances[k]:continue
        for other,length in graph[k].items():
            candidate=value+length
            if candidate<distances.get(other,math.inf):
                distances[other]=candidate;heapq.heappush(queue,(candidate,other))
    # Keep a planar collar for the native perimeter loops, hole boundaries
    # and their short corner segments; ramp only inside the top-surface patch.
    return {k:_smooth(distances.get(k,0.)/fade) for k in graph}


@dataclass(slots=True)
class Patch:
    face: object
    lift: float
    dx: float
    dy: float
    active: bool
    # Barycentric weights b and c are affine in XY; weight a = 1-b-c.
    weights: tuple

    def barycentric(self, x, y):
        a = self.face.points[0]
        x, y = x - a[0], y - a[1]
        bx, by, cx, cy = self.weights
        return bx * x + by * y, cx * x + cy * y

    def field(self, x, y):
        f = self.face
        h = f.height(x, y)
        return h, h + self.lift + self.dx * (x - f.points[0][0]) + self.dy * (
            y - f.points[0][1]
        )

    def clip(self, a, b):
        u0, v0 = self.barycentric(*a[:2])
        u1, v1 = self.barycentric(*b[:2])
        lo, hi = 0.0, 1.0
        for s, e in ((u0, u1), (v0, v1), (1 - u0 - v0, 1 - u1 - v1)):
            if s < 0 and e < 0:
                return None
            if s < 0:
                lo = max(lo, -s / (e - s))
            elif e < 0:
                hi = min(hi, -s / (e - s))
        return (lo, hi) if hi > lo else None


class ConformalWarp:
    def __init__(self, snapshot: ProjectSnapshot, object_id: str, settings=None):
        self.settings = (
            settings
            if isinstance(settings, ConformalSettings)
            else ConformalSettings(**(settings or {}))
        )
        self.object_id = str(object_id)
        cfg = self.settings
        source_revision=snapshot.revision
        snapshot,normalization=normalize_snapshot(snapshot,self.object_id)
        obj = next(
            (o for o in snapshot.objects if str(o["id"]) == self.object_id), None
        )
        if obj is None:
            raise WaveError("A peça selecionada não pertence ao projeto.")
        mesh = SurfaceMesh(obj, SurfaceSettings())
        region=_local_region(mesh,obj['volumes'][0]['triangles'],cfg)
        refinement=None
        if region:
            snapshot,refinement=refine_region(snapshot,self.object_id,region['ids'])
            obj=next(o for o in snapshot.objects if str(o['id'])==self.object_id)
            mesh=SurfaceMesh(obj,SurfaceSettings())
            region=_local_region(mesh,obj['volumes'][0]['triangles'],cfg)
            if region is None:raise WaveError('O refinamento perdeu a região superior selecionada.')
        vol = obj["volumes"][0]
        inst = next(i for i in obj["instances_data"] if i.get("printable", True))
        matrix = inst["matrix"]
        direction = _local_z_direction(matrix, vol["matrix"])
        original = [transform_point(v, matrix, vol["matrix"]) for v in vol["vertices"]]
        zmax = region['z_range_mm'][1] if region else mesh.bounds[1][2]
        self.anchor_z = (region['z_range_mm'][0]-min(.2,cfg.anchor_depth_mm) if region
                         else zmax - cfg.anchor_depth_mm)
        if self.anchor_z <= mesh.bounds[0][2] + 1e-8:
            raise WaveError(
                "Altura insuficiente para preservar uma base plana sob a âncora."
            )
        anchor = self.anchor_z
        weights=_region_weights(mesh,vol['triangles'],region,anchor,cfg.local_transition_mm) if region else None
        angle = [0.0] * len(original)
        cap = []
        for face_id,(f, tri) in enumerate(zip(mesh.faces, vol["triangles"])):
            if region and face_id not in region['ids']:
                continue
            if f.zmax <= anchor + 1e-10:
                continue
            if f.nz * mesh.orientation < 0:
                raise WaveError(
                    "A malha contém face inferior ou cavidade acima da âncora."
                )
            if f.nz == 0:
                for i in tri:
                    angle[i] = 90.0
                continue
            slope = math.degrees(math.atan(f.gradient))
            for i in tri:
                angle[i] = max(angle[i], slope)
            poly = _cap_polygon(f.points, anchor)
            if len(poly) >= 3:
                xs, ys = zip(*poly)
                cap.append((min(xs), max(xs), min(ys), max(ys), poly))
        live = []
        for xmin, xmax, ymin, ymax, p in sorted(cap, key=lambda r: r[0]):
            live = [r for r in live if r[0] > xmin + 1e-9]
            for _, yl, yh, q in live:
                if min(ymax, yh) > max(ymin, yl) + 1e-9 and _overlap(p, q):
                    raise WaveError(
                        "A projeção da faixa superior tem múltiplas faces sobrepostas."
                    )
            live.append((xmax, ymin, ymax, p))
        lifts = []
        scales = []
        for p, slope in zip(original, angle):
            z = p[2]
            band = (weights.get(len(lifts),0.) if region else _smooth(
                (z - (zmax - cfg.fade_start_depth_mm))
                / (cfg.fade_start_depth_mm - cfg.fade_full_depth_mm)
            ))
            tilt = _smooth(
                (cfg.max_slope_deg - slope) / (cfg.max_slope_deg - cfg.full_slope_deg)
            )
            lift = min(
                (zmax - z) * band * tilt,
                cfg.max_lift_mm,
                max(0.0, (z - anchor) * (1 / cfg.min_scale - 1)),
            )
            lifts.append(lift)
            if lift:
                scales.append((z - anchor) / (z + lift - anchor))
        self.flattened_snapshot = copy.deepcopy(snapshot)
        flat_obj = next(
            o for o in self.flattened_snapshot.objects if str(o["id"]) == self.object_id
        )
        flat_obj["volumes"][0]["vertices"] = [
            [v + d * lift for v, d in zip(p, direction)] if lift else list(p)
            for p, lift in zip(vol["vertices"], lifts)
        ]
        self.cell = max((mesh.bounds[1][i] - mesh.bounds[0][i]) / 128 for i in (0, 1))
        self.cell = max(0.15, self.cell)
        self._xy_bounds = (
            mesh.bounds[0][0],
            mesh.bounds[1][0],
            mesh.bounds[0][1],
            mesh.bounds[1][1],
        )
        self.grid = defaultdict(list)
        self.active_grid = defaultdict(list)
        self.patches = []
        entries = 0
        for f, tri in zip(mesh.faces, vol["triangles"]):
            ds = [lifts[k] for k in tri]
            active = max(ds) > 0
            if active and (
                min(p[2] for p in f.points) <= anchor + 1e-9
                or f.nz * mesh.orientation <= 0
            ):
                raise WaveError(
                    "Uma face afetada atravessaria a âncora ou uma parede vertical."
                )
            if f.nz * mesh.orientation <= 0:
                continue
            a, b, c = f.points
            bx, by, cx, cy = (
                (c[1] - a[1]) / f.nz,
                (a[0] - c[0]) / f.nz,
                (a[1] - b[1]) / f.nz,
                (b[0] - a[0]) / f.nz,
            )
            dx = (ds[1] - ds[0]) * bx + (ds[2] - ds[0]) * cx
            dy = (ds[1] - ds[0]) * by + (ds[2] - ds[0]) * cy
            patch = Patch(f, ds[0], dx, dy, active, (bx, by, cx, cy))
            i = len(self.patches)
            self.patches.append(patch)
            keys = self._cells(f.xmin, f.xmax, f.ymin, f.ymax)
            for key in keys:
                self.grid[key].append(i)
                if active:
                    self.active_grid[key].append(i)
                entries += 1
                if entries > 3_000_000:
                    raise WaveError(
                        "O índice espacial do modelo supera o limite do estudo."
                    )
        self._cached = lru_cache(maxsize=32768)(self._lookup)
        self.summary = {
            "object_id": self.object_id,
            "anchor_z_mm": anchor,
            "zmax_mm": zmax,
            "bounds_mm": mesh.bounds,
            "source_revision": source_revision,
            "normalized_revision":snapshot.revision,
            "normalization":normalization,
            "refinement":refinement,
            "surface_scope":"local_top_region" if region else "global_top_cap",
            "selected_region":{k:v for k,v in region.items() if k!='ids'} if region else None,
            "flattened_revision": self.flattened_snapshot.revision,
            "triangles": len(mesh.faces),
            "vertices": len(original),
            "lifted_vertices": len(scales),
            "modified_upper_triangles": sum(p.active for p in self.patches),
            "max_lift_mm": max(lifts),
            "min_local_scale": min(scales, default=1.0),
            "xy_preserved": True,
            "lower_region_unchanged": True,
            "bench_only": True,
            "print_allowed": False,
            "normal_gap_model": "Espaçamento normal local aproximado pela tangente da camada atual.",
            "pending": [
                "suporte e adesão físicos",
                "geometria e colisões do cabeçote",
                "ensaio físico",
            ],
            "settings": asdict(cfg),
        }

    def _cells(self, x0, x1, y0, y1):
        xmin, xmax, ymin, ymax = self._xy_bounds
        x0, x1 = max(xmin, x0), min(xmax, x1)
        y0, y1 = max(ymin, y0), min(ymax, y1)
        if x1 < x0 or y1 < y0:
            return
        for iy in range(math.floor(y0 / self.cell), math.floor(y1 / self.cell) + 1):
            for ix in range(math.floor(x0 / self.cell), math.floor(x1 / self.cell) + 1):
                yield ix, iy

    def _lookup(self, x, y):
        top = None
        height = -math.inf
        for i in self.grid.get(
            (math.floor(x / self.cell), math.floor(y / self.cell)), ()
        ):
            p = self.patches[i]
            u, v = p.barycentric(x, y)
            if u >= -1e-10 and v >= -1e-10 and u + v <= 1 + 1e-10:
                h = p.face.height(x, y)
                if h > height:
                    top, height = p, h
        return top

    def surface_heights(self, x, y):
        p = self._cached(x, y)
        return p.field(x, y) if p else None

    def local_scale(self, x, y):
        p = self._cached(x, y)
        if not p or not p.active:
            return 1.0
        h, t = p.field(x, y)
        return (h - self.anchor_z) / (t - self.anchor_z)

    def map_point(self, point):
        x, y, z = point
        if z <= self.anchor_z:
            return x, y, z
        scale = self.local_scale(x, y)
        return x, y, z if scale == 1.0 else self.anchor_z + (z - self.anchor_z) * scale

    def gradient(self, x, y, z_flat):
        if z_flat <= self.anchor_z:
            return 0.0, 0.0
        p = self._cached(x, y)
        if not p or not p.active:
            return 0.0, 0.0
        h, t = p.field(x, y)
        w = t - self.anchor_z
        s = (h - self.anchor_z) / w
        factor = (z_flat - self.anchor_z) / w
        return (
            factor * (p.face.gx - s * (p.face.gx + p.dx)),
            factor * (p.face.gy - s * (p.face.gy + p.dy)),
        )

    def normal_gap(self, x, y, z_flat, h_flat):
        if not math.isfinite(h_flat) or h_flat <= 0:
            raise WaveError("Altura da camada de origem inválida.")
        if z_flat <= self.anchor_z:
            return h_flat
        s = self.local_scale(x, y)
        if s == 1 and self._cached(x, y) is None:
            return h_flat
        warped = min(h_flat, z_flat - self.anchor_z)
        gx, gy = self.gradient(x, y, z_flat)
        return (h_flat - warped + s * warped) / math.hypot(1.0, gx, gy)

    def chord_error_bound(self, flat_a, flat_b, out_a, out_b):
        """Bound XYZ deviation including rounded endpoints, all cap facets and anchor."""
        dx, dy, dz = (b - a for a, b in zip(flat_a, flat_b))
        hx = max(math.dist(flat_a[:2], out_a[:2]), math.dist(flat_b[:2], out_b[:2]))
        oz = out_b[2] - out_a[2]
        cuts = {0.0, 1.0}
        if dz:
            t = (self.anchor_z - flat_a[2]) / dz
            if 0 < t < 1:
                cuts.add(t)
        if max(flat_a[2], flat_b[2]) > self.anchor_z:
            ids = set()
            for key in self._cells(
                min(flat_a[0], flat_b[0]),
                max(flat_a[0], flat_b[0]),
                min(flat_a[1], flat_b[1]),
                max(flat_a[1], flat_b[1]),
            ):
                ids.update(self.active_grid.get(key, ()))
            for i in ids:
                clip = self.patches[i].clip(flat_a, flat_b)
                if clip:
                    cuts.update(clip)
        zerr = 0.0
        for l, r in pairwise(sorted(cuts)):
            mid = (l + r) * 0.5

            def point(t):
                return flat_a[0] + t * dx, flat_a[1] + t * dy, flat_a[2] + t * dz

            a, b = point(l), point(r)
            m = point(mid)
            patch = self._cached(m[0], m[1]) if m[2] > self.anchor_z else None
            if patch is None or not patch.active:
                za, zb = a[2], b[2]
                curvature = 0.0
            else:
                ha, ta = patch.field(*a[:2])
                hb, tb = patch.field(*b[:2])
                va, vb = ha - self.anchor_z, hb - self.anchor_z
                wa, wb = ta - self.anchor_z, tb - self.anchor_z
                ua, ub = a[2] - self.anchor_z, b[2] - self.anchor_z
                za = self.anchor_z + ua * va / wa
                zb = self.anchor_z + ub * vb / wb
                # For u*v/w with affine u,v,w, the second derivative is
                # 2(v' w - v w')(u' w - u w') / w^3 on this unit interval.
                k = (vb - va) * wa - va * (wb - wa)
                j = (ub - ua) * wa - ua * (wb - wa)
                curvature = abs(k * j) / (4 * min(wa, wb) ** 3)
            endpoints = max(abs(za - out_a[2] - oz * l), abs(zb - out_a[2] - oz * r))
            zerr = max(zerr, endpoints + curvature)
        return math.hypot(hx, zerr)
