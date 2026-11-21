from __future__ import annotations

import math
from typing import Any

from .contracts import ProjectSnapshot, WaveError, fingerprint


IDENTITY = [[1., 0., 0., 0.], [0., 1., 0., 0.], [0., 0., 1., 0.], [0., 0., 0., 1.]]
SETTING_KEYS = ("printer_model", "nozzle_diameter", "layer_height", "initial_layer_print_height",
                "wall_loops", "sparse_infill_density", "gcode_flavor", "filament_type",
                "filament_diameter", "filament_density", "post_process", "slicing_pipeline_plugin",
                "gcode_label_objects", "print_sequence", "outer_wall_speed", "inner_wall_speed",
                "enable_arc_fitting", "seam_position", "resolution", "slice_closing_radius")


def _value(item: Any, name: str, default: Any = None) -> Any:
    value = getattr(item, name, default)
    return value() if callable(value) else value


def _rows(value: Any) -> list:
    return value.tolist() if hasattr(value, "tolist") else [list(row) for row in value]


def transform_point(point: list | tuple, instance: list, volume: list) -> list[float]:
    vector = [float(point[0]), float(point[1]), float(point[2]), 1.]
    for matrix in (volume, instance):
        vector = [sum(float(matrix[i][j]) * vector[j] for j in range(4)) for i in range(4)]
    if abs(vector[3]) < 1e-12:
        raise WaveError("Transformação geométrica inválida.")
    return [vector[i] / vector[3] for i in range(3)]


def bounds_of(points: list[list[float]]) -> list[list[float]]:
    if not points:
        raise WaveError("A peça não contém vértices analisáveis.")
    return [[min(p[axis] for p in points) for axis in range(3)],
            [max(p[axis] for p in points) for axis in range(3)]]


def freeze_model(model: Any, settings: dict[str, Any] | None = None) -> ProjectSnapshot:
    objects = []
    for obj in model.objects():
        volumes = []
        for volume in obj.volumes():
            mesh = volume.mesh()
            try:
                vertices = _rows(mesh.vertices())
                triangles = _rows(mesh.triangles())
            except (AttributeError, ImportError, RuntimeError):
                vertices = [list(mesh.vertex(i)) for i in range(mesh.vertex_count())]
                triangles = [list(mesh.triangle(i)) for i in range(mesh.triangle_count())]
            volumes.append({"id": str(volume.id()), "matrix": _rows(volume.matrix()),
                            "kind": "part" if volume.is_model_part() else "modifier",
                            "negative": bool(_value(volume, "is_negative_volume", False)),
                            "vertices": vertices, "triangles": triangles,
                            "config": {str(key):volume.config_value(key) for key in getattr(volume,"config_keys",lambda:[])()},
                            "manifold": bool(_value(mesh, "is_manifold", False))})
        instances = [{"id": str(inst.id()), "matrix": _rows(inst.matrix()),
                      "printable": bool(_value(inst, "is_printable", True))} for inst in obj.instances()]
        objects.append({"id": str(obj.id()), "name": str(_value(obj, "name", "Peça")),
                        "volumes": volumes, "instances_data": instances,
                        "config": {str(key): obj.config_value(key) for key in obj.config_keys()}})
    return ProjectSnapshot(str(model.id()), int(model.current_plate_index()), tuple(objects), settings or {})


def analyze_object(obj: dict[str, Any], *, layer_height: float = 0.2) -> dict[str, Any]:
    all_points = []
    shapes = []
    negative_or_modifier = False
    for instance in obj.get("instances_data", [{"matrix": IDENTITY, "printable": True}]):
        if not instance.get("printable", True):
            continue
        for volume in obj.get("volumes", []):
            if volume.get("kind") != "part" or volume.get("negative"):
                negative_or_modifier = True
                continue
            transformed = [transform_point(p, instance["matrix"], volume.get("matrix", IDENTITY))
                           for p in volume["vertices"]]
            all_points.extend(transformed)
            shapes.append((transformed, volume.get("triangles", [])))
    bounds = bounds_of(all_points)
    dimensions = [bounds[1][i] - bounds[0][i] for i in range(3)]
    minimum_xy = min(dimensions[:2])
    perimeter_estimate = math.pi * (dimensions[0] + dimensions[1]) / 2
    wavelength = max(1., min(50., perimeter_estimate / max(3, round(perimeter_estimate / 10))))
    start = bounds[0][2] + max(1., 5 * layer_height)
    end = bounds[1][2] - max(1., 5 * layer_height)
    reasons = ["Sugestão geométrica preliminar; a trajetória fatiada ainda será validada."]
    if negative_or_modifier:
        reasons.append("Há modificadores ou volumes negativos; é necessário verificar a topologia fatiada.")
    if end <= start:
        reasons.append("A altura não oferece espaço para as regiões planas e transições do piloto Z.")
    normal_stats = {"vertical_area_mm2": 0., "horizontal_area_mm2": 0., "sloped_area_mm2": 0.}
    for points, triangles in shapes:
        for indices in triangles:
            a, b, c = [points[int(index)] for index in indices]
            u, v = [[q[i] - a[i] for i in range(3)] for q in (b, c)]
            cross = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
            size = math.sqrt(sum(x*x for x in cross))
            if size:
                cos_z = abs(cross[2]) / size
                key = "horizontal_area_mm2" if cos_z > .95 else ("vertical_area_mm2" if cos_z < .05 else "sloped_area_mm2")
                normal_stats[key] += size / 2
    return {"id": str(obj["id"]), "name": obj["name"], "bounds": bounds,
            "dimensions_mm": dimensions, "instances": len(obj.get("instances_data", [1])),
            "geometry_fingerprint": fingerprint(obj), "geometry": normal_stats,
            "suggestion": {"mode": "z", "amplitude_mm": round(min(.08, layer_height * .4, minimum_xy / 200), 4),
                           "wavelength_mm": round(wavelength, 3), "step_mm": .4,
                           "start_height_mm": round(start, 3), "end_height_mm": round(end, 3) if end > start else None},
            "analysis_status": "preliminary", "reasons": reasons}


def analyze_snapshot(snapshot: ProjectSnapshot) -> list[dict[str, Any]]:
    try:
        height = float(str(snapshot.settings.get("layer_height", "0.2")).strip('"'))
    except (ValueError, TypeError):
        height = .2
    return [analyze_object(obj, layer_height=height) for obj in snapshot.objects
            if any(instance.get("printable",True) for instance in obj.get("instances_data",[{"printable":True}]))]
