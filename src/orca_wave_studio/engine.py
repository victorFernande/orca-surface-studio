"""Offline benchmark only. No printer, slicer cache or filesystem access."""

from __future__ import annotations

import math
import re
from bisect import bisect_left, bisect_right
from collections import defaultdict

from .contracts import ProcessedResult, WaveError, WaveParameters, digest
from .engine_geometry import Path, circle, simple_polygon
from .engine_parser import NUM, OUTER, read
from .sine_vase import SineVasePath, contour_center


def _num(n, places=5):
    return f"{n:.{places}f}".rstrip("0").rstrip(".") or "0"


def _dynamics(pieces, params):
    """Finite-difference estimates for a linear-segment path at commanded feed."""
    dt, vz = [], []
    for piece in pieces:
        seconds = 60 * math.dist(piece.start, piece.end) / piece.f
        dt.append(seconds)
        vz.append((piece.end[2] - piece.start[2]) / seconds)
    speed = max(map(abs, vz))
    accel = max(
        abs(vz[0]) * 2 / dt[0],
        abs(vz[-1]) * 2 / dt[-1],
        max(
            (
                2 * abs(b - a) / (ta + tb)
                for a, b, ta, tb in zip(vz, vz[1:], dt, dt[1:])
            ),
            default=0,
        ),
    )
    scale = min(
        1.0,
        params.max_z_speed_mm_s / max(speed, 1e-16),
        math.sqrt(params.max_z_acceleration_mm_s2 / max(accel, 1e-16)),
    )
    for piece in pieces:
        piece.f = math.floor(piece.f * scale * 1000) / 1000
        if piece.f <= 0:
            raise WaveError("F insuficiente para representar os limites de Z.")
    return speed * scale, accel * scale**2


def _plans(parsed, params, report):
    grouped = defaultdict(lambda: defaultdict(list))
    for loop in parsed.loops:
        m = loop[0]
        p = params[m.obj]
        if p.start_height_mm - 1e-8 <= m.z and (
            p.end_height_mm is None or m.z <= p.end_height_mm + 1e-8
        ):
            grouped[m.label][m.layer].append(loop)
    if {
        loops[0][0].obj for layers in grouped.values() for loops in layers.values()
    } != set(params):
        raise WaveError("Objeto sem perímetro externo na faixa de alturas selecionada.")
    plans = {}
    preview = []
    for label, layers in grouped.items():
        ids = sorted(layers)
        p = params[layers[ids[0]][0][0].obj]
        if p.mode == "z" and p.amplitude_mm and len(ids) < 3:
            raise WaveError("Use ao menos três camadas para as transições planas.")
        cyl = None
        center = contour_center(layers[ids[0]][0]) if p.mode == "combined" else None
        top_z = layers[ids[-1]][0][0].z
        if p.mode == "combined" and p.amplitude_mm and top_z <= p.start_height_mm:
            raise WaveError("Deixe ao menos uma camada acima do início das ondas.")
        prev = 0.0
        prev_z = None
        for rank, layer in enumerate(ids):
            loops = layers[layer]
            if len(loops) != 1:
                raise WaveError(
                    "Mais de um contorno externo, furo ou perímetro interrompido."
                )
            loop = loops[0]
            m = loop[0]
            if p.mode in {"z", "combined"}:
                if not parsed.roles[label, layer] <= OUTER:
                    raise WaveError(
                        "Use Preparar vaso: a região com ondas precisa de uma parede, sem preenchimento ou topo sólido."
                    )
                if rank and (
                    ids[rank - 1] + 1 != layer or abs(m.z - prev_z - m.h) > 0.00005
                ):
                    raise WaveError(
                        "Camadas Z devem ser consecutivas e com separação conhecida."
                    )
                if any(move.h != m.h or move.w != m.w for move in loop):
                    raise WaveError("Largura ou altura variável dentro do perímetro Z.")
            pts = [x.start[:2] for x in loop] + [loop[-1].end[:2]]
            open_seam = p.mode == "combined" and math.dist(pts[0], pts[-1]) > 1e-7
            simple_polygon(pts + [pts[0]] if open_seam else pts)
            if p.mode == "z":
                fitted = circle(pts, p.tolerance_mm)
                if cyl is None:
                    cyl = fitted
                elif (
                    math.dist(cyl[0], fitted[0]) + abs(cyl[1] - fitted[1])
                    > p.tolerance_mm
                ):
                    raise WaveError("Centro ou raio variou entre camadas.")
            amp = p.amplitude_mm
            if p.mode == "z":
                amp *= min(
                    1.0, rank / p.fade_layers, (len(ids) - 1 - rank) / p.fade_layers
                )
            elif p.mode == "combined":
                progress = max(0.0, (m.z-p.start_height_mm)/(top_z-p.start_height_mm)) if top_z > p.start_height_mm else 0
                amp *= progress**2
            pieces = None
            if amp or (prev and p.mode == "z"):
                if p.mode == "z" and (
                    not m.w or m.h - abs(amp - prev) <= 0 or m.h + abs(amp - prev) > m.w
                ):
                    raise WaveError(
                        "A transição exige largura conhecida e separação positiva compatível."
                    )
                path = (SineVasePath(loop, p, amp, prev, center) if p.mode == "combined"
                        else Path(loop, p, amp, prev, cyl))
                pieces = path.sample()
                speed, accel = _dynamics(pieces, p)
                report["max_z_speed_mm_s"] = max(report["max_z_speed_mm_s"], speed)
                report["max_z_acceleration_mm_s2"] = max(
                    report["max_z_acceleration_mm_s2"], accel
                )
                if path.min_h != math.inf:
                    report["normal_spacing_mm"].extend([path.min_h, path.max_h])
                if p.mode == "combined":
                    report["vertical_spacing_mm"].extend([path.min_vertical_gap, path.max_vertical_gap])
                plans[m.i] = (loop, pieces, p)
                preview.append(
                    (
                        layer,
                        label,
                        [(*pts[0], m.z)] + [v.original for v in pieces],
                        [pieces[0].start] + [v.end for v in pieces],
                    )
                )
            else:
                original = [(*pt, m.z) for pt in pts]
                preview.append((layer, label, original, original))
            source_duration = sum(
                60 * math.dist(mv.start, mv.end) / mv.f for mv in loop
            )
            duration = (
                sum(
                    60 * math.dist(piece.start, piece.end) / piece.f for piece in pieces
                )
                if pieces
                else source_duration
            )
            report["estimates"]["source_selected_deposition_seconds"] += source_duration
            report["estimates"]["processed_selected_deposition_seconds"] += duration
            report["contours"].append(
                {
                    "layer_id": layer,
                    "object_id": m.obj,
                    "print_object_id": label[0],
                    "copy": label[1],
                    "z_mm": m.z,
                    "amplitude_mm": amp,
                    "wave_count": p.wave_count if p.mode == "combined" else (
                        max(1, round(math.tau * cyl[1] / p.wavelength_mm)) if cyl else None),
                    "z_amplitude_mm": amp*p.z_ratio if p.mode == "combined" else (amp if cyl else 0),
                }
            )
            prev, prev_z = amp, m.z
    return plans, preview


def _travel_plans(parsed, plans):
    targets = {}
    touched = {}
    restores = set()
    indices = sorted(parsed.moves)
    search_barriers = sorted(parsed.barrier)

    def nearest(i, step, target, parameter):
        k = bisect_left(indices, i) - 1 if step == -1 else bisect_right(indices, i)
        while 0 <= k < len(indices):
            other = indices[k]
            if bisect_right(search_barriers, min(i, other)) != bisect_left(
                search_barriers, max(i, other)
            ):
                break
            move = parsed.moves[other]
            if move.start != move.end:
                if move.de or None in move.end:
                    break
                if step == -1:
                    targets[other] = target
                touched.setdefault(other, []).append(parameter)
                return
            # Pure retraction/recovery changes E and F, not the seam position.
            # The normal emission path preserves both modal values verbatim.
            k += step
        if step == 1 and parameter.mode == "combined":
            restores.add(i)
            return
        raise WaveError(
            "Costura deslocada sem viagem linear de entrada/saída identificável."
        )

    for loop, pieces, p in plans.values():
        seam = pieces[0].start
        if math.dist(loop[0].start, seam) > 0.0000001:
            nearest(loop[0].i, -1, seam, p)
        if math.dist(loop[-1].end, pieces[-1].end) > 0.0000001:
            nearest(loop[-1].i, 1, None, p)
    return targets, touched, restores


def _preview(traces, report):
    count = sum(len(orig) for _, _, orig, _ in traces)
    stride = max(1, math.ceil(count / 15000))
    seen = 0
    for layer, label, orig, new in traces:
        indices = range((-seen) % stride, len(orig), stride)
        if indices:
            report["break_indices"].append(len(report["original_points"]))
        for j in indices:
            report["original_points"].append(list(orig[j]))
            report["deformed_points"].append(list(new[j]))
            report["layer_ids"].append(layer)
            report["point_object_ids"].append(label[0])
        seen += len(orig)


EWORD = re.compile(r"(E\s*)" + NUM, re.IGNORECASE)
STALE = re.compile(
    r"^\s*(?:M73\b|;\s*(?:estimated printing time|estimated total time|total estimated time|model printing time|filament (?:used|cost)|total filament (?:used|cost|length|volume|weight)))",
    re.IGNORECASE,
)
MATERIAL = re.compile(
    r"^(\s*;\s*(?:filament used|total filament (?:used|length|volume|weight))"
    r"\s*\[(mm|m|cm\^?3|mm\^?3|g|kg)\]\s*[:=]\s*)(" + NUM + r")(\s*)$",
    re.IGNORECASE,
)


def _material(parsed, delta, report):
    """Update only scalar single-tool metadata with unambiguous units."""
    dimensions = {}
    for line in parsed.lines:
        m = re.fullmatch(
            r"\s*;\s*(filament_density|filament_diameter)\s*=\s*(" + NUM + r")\s*",
            line,
            re.IGNORECASE,
        )
        if m and float(m[2]) > 0:
            dimensions[m[1].lower()] = float(m[2])
    conversions = {"mm": delta, "m": delta / 1000}
    if "filament_diameter" in dimensions:
        vol = delta * math.pi * (dimensions["filament_diameter"] / 2) ** 2
        conversions.update({"mm3": vol, "cm3": vol / 1000})
        if "filament_density" in dimensions:
            grams = vol / 1000 * dimensions["filament_density"]
            conversions.update({"g": grams, "kg": grams / 1000})
    replacements = {}
    for i, line in enumerate(parsed.lines):
        m = MATERIAL.fullmatch(line)
        if m:
            unit = m[2].lower().replace("^", "")
            if unit in conversions:
                value = float(m[3]) + conversions[unit]
                if value < 0:
                    continue
                replacements[i] = m[1] + _num(value, 6) + m[4]
                if unit in {"kg", "g"}:
                    report["estimates"]["mass_g"] = value * (
                        1000 if unit == "kg" else 1
                    )
    return replacements


def process_gcode(
    source: bytes,
    parameters_by_object: dict[str, WaveParameters],
    print_object_map: dict[int, str],
) -> ProcessedResult:
    if b"; OrcaWaveStudio BENCH ONLY" in source:
        raise WaveError(
            "Este arquivo já contém ondas do estúdio. Gere novamente a partir da captura original."
        )
    if not parameters_by_object or not print_object_map:
        raise WaveError("Selecione um objeto com mapeamento para a placa.")
    if not all(p.bench_only for p in parameters_by_object.values()):
        raise WaveError("O piloto admite somente estudo de bancada.")
    parsed = read(source, parameters_by_object, print_object_map)
    for p in parameters_by_object.values():
        if not isinstance(p.fade_layers, int) or not 0 < p.corner_threshold_deg <= 180:
            raise WaveError(
                "Transição em camadas inteiras e ângulo de quina entre 0 e 180 graus."
            )
    report = {
        "bench_only": True,
        "segments": 0,
        "segment_count": 0,
        "original_points": [],
        "deformed_points": [],
        "layer_ids": [],
        "break_indices": [],
        "point_object_ids": [],
        "contours": [],
        "source_sha256": digest(source),
        "total_e_delta": 0.0,
        "max_z_speed_mm_s": 0.0,
        "max_z_acceleration_mm_s2": 0.0,
        "min_segment_mm": None,
        "max_geometric_error_mm": 0.0,
        "max_segment_mm": None,
        "normal_spacing_mm": [],
        "vertical_spacing_mm": [],
        "print_allowed": not any(p.mode == "combined" for p in parameters_by_object.values()),
        "wave_modes": sorted({p.mode for p in parameters_by_object.values()}),
        "deposition_model": "Finite-volume radial/Z map, layer-linear amplitude; preview only"
            if any(p.mode == "combined" for p in parameters_by_object.values()) else "legacy bead section",
        "label_validation": {
            "verified": True,
            "labels": [list(key) for key in sorted(parsed.seen)],
            "mapping": {str(k): v for k, v in print_object_map.items()},
        },
        "estimates": {
            "scope": "Movimentos comandados; sem simulação do firmware ou ensaio físico.",
            "z_dynamics": "Diferenças finitas entre segmentos, entrada e saída de cada perímetro.",
            "material_unit": "mm de E no dialeto linear de ferramenta única; sem E volumétrico",
            "mass_g": None,
            "updated_time_s": None,
            "source_selected_deposition_seconds": 0.0,
            "processed_selected_deposition_seconds": 0.0,
        },
    }
    plans, preview = _plans(parsed, parameters_by_object, report)
    _preview(preview, report)
    report["original_deposition_e_mm"] = sum(
        m.de for m in parsed.moves.values() if m.deposits
    )
    report["source_deposition_segments"] = sum(
        m.deposits for m in parsed.moves.values()
    )
    report["processed_deposition_e_mm"] = report["original_deposition_e_mm"]
    if not plans:
        report["output_sha256"] = report["source_sha256"]
        return ProcessedResult(source, report)
    targets, touched, restores = _travel_plans(parsed, plans)
    if report["normal_spacing_mm"]:
        ns = report["normal_spacing_mm"]
        report["normal_spacing_mm"] = [min(ns), max(ns)]
    if report["vertical_spacing_mm"]:
        values = report["vertical_spacing_mm"]
        report["vertical_spacing_mm"] = [min(values), max(values)]
    newline = "\r\n" if any(line.endswith("\r\n") for line in parsed.lines) else "\n"
    out = []
    delta = total_delta = 0.0
    shift = (0.0, 0.0, 0.0)
    skip = -1
    metadata_slots = {}

    def emit(text):
        out.append(text + newline)

    for i, line in enumerate(parsed.lines):
        if i <= skip:
            continue
        if i in plans:
            loop, pieces, p = plans[i]
            m = loop[0]
            begin = tuple(v + d for v, d in zip(m.start, shift))
            if math.dist(begin, pieces[0].start) > 0.000015:
                raise WaveError("Entrada de costura incompatível.")
            e = m.e - m.de + delta
            start_e = e
            feed = None
            for piece in pieces:
                coords = (
                    piece.end
                    if m.xyz_abs
                    else tuple(b - a for a, b in zip(piece.start, piece.end))
                )
                xyz = " ".join(k + _num(n) for k, n in zip("XYZ", coords))
                ev = round(e + piece.e, 8) if m.e_abs else round(piece.e, 8)
                if (ev - e if m.e_abs else ev) <= 0:
                    raise WaveError("Resolução de E insuficiente.")
                fword = (" F" + _num(piece.f, 3)) if feed != piece.f else ""
                tail = (" ;" + piece.comment) if piece.comment else ""
                emit("G1 " + xyz + " E" + _num(ev, 8) + fword + tail)
                feed = piece.f
                e = ev if m.e_abs else e + ev
                length = math.dist(piece.start, piece.end)
                current = report["min_segment_mm"]
                report["min_segment_mm"] = (
                    length if current is None else min(current, length)
                )
                report["max_segment_mm"] = max(report["max_segment_mm"] or 0.0, length)
                report["max_geometric_error_mm"] = max(
                    report["max_geometric_error_mm"], piece.err
                )
            net = e - start_e - sum(move.de for move in loop)
            total_delta += net
            delta += net
            shift = tuple(v - o for v, o in zip(pieces[-1].end, loop[-1].end))
            if loop[-1].i in restores:
                # A final contour can be followed by a mode change or shutdown
                # with no eligible exit travel. Restore its source position
                # before those commands, without adding any extrusion.
                begin, dest = pieces[-1].end, loop[-1].end
                length, dz = math.dist(begin, dest), abs(begin[2]-dest[2])
                exit_feed = min(piece.f for piece in pieces)
                if dz:
                    exit_feed = min(exit_feed, 60*p.max_z_speed_mm_s*length/dz,
                                    60*length*math.sqrt(p.max_z_acceleration_mm_s2/(2*dz)))
                exit_feed = math.floor(exit_feed*1000)/1000
                if exit_feed <= 0:
                    raise WaveError("Saída do vaso sem avanço representável.")
                coords = dest if m.xyz_abs else tuple(b-a for a,b in zip(begin,dest))
                emit("G0 "+" ".join(k+_num(v) for k,v in zip("XYZ",coords))+" F"+_num(exit_feed,3)+" ; OWS seam exit")
                feed = exit_feed
                shift = (0.0,0.0,0.0)
            if feed != loop[-1].f:
                emit("G1 F" + _num(loop[-1].f, 8))
            skip = loop[-1].i
            report["segments"] += len(pieces)
            continue
        if i in parsed.resets:
            delta = 0.0
        m = parsed.moves.get(i)
        if i in touched:
            dest = targets.get(i, m.end)
            if None in m.start:
                raise WaveError("Viagem de entrada sem origem definida.")
            begin = tuple(v + d for v, d in zip(m.start, shift))
            length = math.dist(begin, dest)
            endpoints = touched[i]
            if length < max(p.min_segment_mm for p in endpoints):
                raise WaveError("Viagem da costura abaixo do segmento mínimo.")
            dz = abs(dest[2] - begin[2])
            feed = m.f
            if dz:
                feed = min(
                    feed,
                    60 * min(p.max_z_speed_mm_s for p in endpoints) * length / dz,
                    60
                    * length
                    * math.sqrt(
                        min(p.max_z_acceleration_mm_s2 for p in endpoints) / (2 * dz)
                    ),
                )
            feed = math.floor(feed * 1000) / 1000
            if feed <= 0:
                raise WaveError("Viagem da costura sem avanço conhecido.")
            xyz = dest if m.xyz_abs else tuple(v - b for v, b in zip(dest, begin))
            tail = (" ;" + m.comment) if m.comment else ""
            natural_end = tuple(
                v + (0 if m.xyz_abs and k in m.fields else d)
                for k, v, d in zip("XYZ", m.end, shift)
            )
            if feed == m.f and math.dist(natural_end, dest) < 1e-9:
                out.append(line)
            elif m.obj is not None and m.obj not in parameters_by_object:
                raise WaveError(
                    "A transição da costura exigiria editar a viagem de outro objeto."
                )
            else:
                emit(
                    m.cmd
                    + " "
                    + " ".join(k + _num(v) for k, v in zip("XYZ", xyz))
                    + " F"
                    + _num(feed, 3)
                    + tail
                )
            if feed != m.f:
                emit("G1 F" + _num(m.f, 8))
            shift = tuple(v - o for v, o in zip(dest, m.end))
            report["max_z_speed_mm_s"] = max(
                report["max_z_speed_mm_s"], dz * feed / (60 * length)
            )
            report["max_z_acceleration_mm_s2"] = max(
                report["max_z_acceleration_mm_s2"], 2 * dz * (feed / (60 * length)) ** 2
            )
            continue
        if m and any(abs(d) > 1e-8 for d in shift):
            if m.start != m.end:
                raise WaveError("Viagem não resolvida após costura.")
            if any(k in m.fields for k in "XYZ"):
                # A zero-length positioning command would undo the seam offset.
                # Keep any feed change; extrusion resets/prime cannot be hidden.
                if m.de or m.comment or "E" in m.fields:
                    raise WaveError("Evento intermediário na posição da costura.")
                if "F" in m.fields:
                    emit("G1 F" + _num(m.f, 8))
                continue
        if m and m.e_abs and "E" in m.fields and abs(delta) > 0.000000005:
            code, marker, tail = line.partition(";")
            line = (
                EWORD.sub(r"\g<1>" + _num(m.e + delta, 8), code, count=1)
                + marker
                + tail
            )
        if STALE.match(line):
            metadata_slots[i] = len(out)
            out.append("")
            continue
        out.append(line)
    report["total_e_delta"] = total_delta
    report["segment_count"] = report["segments"]
    report["processed_deposition_e_mm"] += total_delta
    for i, value in _material(parsed, total_delta, report).items():
        if i in metadata_slots:
            out[metadata_slots[i]] = value
    # Include the measured change in commanded E. Original time, cost and
    # mass cannot be derived from segment durations or guessed densities.
    if out and not out[-1].endswith(("\n", "\r")):
        out.append(newline)
    emit("; OrcaWaveStudio BENCH ONLY - original time estimates removed")
    emit("; deposition E delta [mm] = " + _num(total_delta, 8))
    result = "".join(out).encode("latin1")
    report["output_sha256"] = digest(result)
    return ProcessedResult(result, report)
