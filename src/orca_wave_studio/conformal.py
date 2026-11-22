"""Restore a flattened Orca toolpath in physical XYZ for a preview-only conformal study."""
from __future__ import annotations

from collections import Counter
from bisect import bisect_right
from dataclasses import replace
from itertools import pairwise
import math
import re

from .contracts import ProcessedResult, WaveError, digest
from .engine import EWORD, STALE, _material, _num
from .engine_parser import read


MARK = "; OrcaWaveStudio BENCH ONLY - conformal_full_part"
MAX_Z_SPEED = 5.0
MAX_Z_ACCEL = 50.0


def _lerp(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def _role_warp(warp, move):
    return getattr(warp, 'support_warp', warp) if 'support' in move.role else warp


def _point(warp, p, mapped):
    if mapped == 'support':
        warp = warp.support_warp
    value = warp.map_point(p) if mapped and p[2] > warp.anchor_z else p
    if len(value) != 3 or not all(math.isfinite(v) for v in value):
        raise WaveError("Campo conforme retornou uma coordenada inválida.")
    return tuple(value)


def _ownership(parsed, selected, warp=None):
    # A bridge from another object must arrive at the transformed first vertex,
    # and the first outgoing travel must end at the next native position.
    owners = {}
    previous = False
    pending = []

    def close(next_owner):
        nonlocal previous
        for j, m in enumerate(pending):
            if m.obj is not None and m.obj != selected:
                wanted = False
            else:
                wanted = next_owner if j + 1 == len(pending) else previous if previous == next_owner else False
            # The last travel ends exactly at the next deposition start.
            if j + 1 == len(pending):
                wanted = next_owner
            owners[m.i] = previous, wanted
            previous = wanted
        pending.clear()

    for m in parsed.moves.values():
        if m.start == m.end:
            continue
        if m.deposits:
            wanted = m.obj == selected
            if wanted and warp is not None and hasattr(warp, 'support_warp') and 'support' in m.role:
                wanted = 'support'
            close(wanted)
            owners[m.i] = wanted, wanted
            previous = wanted
        else:
            pending.append(m)
    close(False)
    return owners


def _geometry(m, owners, warp, step, minimum, tolerance):
    a, b = m.start, m.end
    mapped_a, mapped_b = owners
    physical_a, physical_b = _point(warp, a, mapped_a), _point(warp, b, mapped_b)
    above = max(a[2], b[2]) > warp.anchor_z
    conformal = bool(mapped_a) and mapped_a == mapped_b and above
    field = warp.support_warp if conformal and mapped_a == 'support' else warp
    baseline_length = math.dist(a, b)
    count = max(1, math.ceil(max(baseline_length, math.dist(physical_a, physical_b)) / step - 1e-8))

    def at(t):
        flat = _lerp(a, b, t)
        if conformal:
            physical = _point(warp, flat, mapped_a)
        else:
            # An ownership transition is a non-depositing, straight travel between
            # known physical endpoints. The transform is not extended to the other part.
            physical = _lerp(physical_a, physical_b, t)
        return flat, tuple(round(v, 6) for v in physical)

    def score(left, right):
        u, p = left
        v, q = right
        length = math.dist(p, q)
        bound = field.chord_error_bound(u, v, p, q) if conformal else 0.0
        if not math.isfinite(bound) or bound < 0:
            raise WaveError("Limite de erro da corda inválido.")
        return length, bound

    while count <= max(2, math.ceil(max(baseline_length, math.dist(physical_a, physical_b)) / minimum) * 4):
        points = [at(j / count) for j in range(count + 1)]
        error = longest = 0.0
        shortest = math.inf
        for left, right in pairwise(points):
            length, bound = score(left, right)
            if length <= 1e-10:
                raise WaveError(f"Linha {m.i+1}: segmento colapsado na representação XYZ.")
            shortest, longest = min(shortest, length), max(longest, length)
            error = max(error, bound)
        if count > 1 and shortest < minimum - 2e-6:
            break
        if longest <= step + 2e-6 and error <= tolerance:
            return points, error, shortest, longest
        count = max(count + 1, math.ceil(count * longest / step - 1e-8),
                    math.ceil(count * math.sqrt(error / tolerance)))
    # A native edge can cross a change of slope off-center. Three equal pieces
    # might violate the minimum even though two unequal pieces meet both limits.
    grid_n = max(2, math.ceil(baseline_length / (minimum / 12)))
    points = [at(j / grid_n) for j in range(grid_n + 1)]
    previous = {0: None}
    for j in range(1, grid_n + 1):
        for i in range(j - 1, -1, -1):
            u, p = points[i]
            v, q = points[j]
            if math.dist(u[:2], v[:2]) > step + 2e-6:
                break
            if i not in previous or not minimum - 2e-6 <= math.dist(p,q) <= step + 2e-6:
                continue
            length, bound = score(points[i], points[j])
            if bound <= tolerance:
                previous[j] = (i, length, bound)
                break
    if grid_n not in previous:
        raise WaveError(f"Linha {m.i+1}: tolerância de corda incompatível com o segmento mínimo.")
    j = grid_n
    path = [points[j]]
    lengths, errors = [], []
    while j:
        j, length, bound = previous[j]
        path.append(points[j])
        lengths.append(length)
        errors.append(bound)
    return list(reversed(path)), max(errors), min(lengths), max(lengths)


def _gap_and_scale(warp, p, h):
    x, y, z = p
    if z <= warp.anchor_z:
        return h, 1.0
    gap = warp.normal_gap(x, y, z, h)
    # The layer cell can straddle the anchor. Only its fraction above the
    # anchor undergoes vertical dilation; the part below retains unit Jacobian.
    cell_scale = getattr(warp, 'volume_scale', None)
    if callable(cell_scale):
        scale = cell_scale(x, y, z, h)
    else:
        fraction = min(1.0, (z - warp.anchor_z) / h)
        scale = 1.0 + fraction * (warp.local_scale(x, y) - 1.0)
    if not math.isfinite(gap) or not math.isfinite(scale) or min(gap, scale) <= 0:
        raise WaveError("Altura normal ou jacobiano da célula inválido.")
    return gap, scale


def _joined_geometry(first, second, warp, step, minimum, tolerance, extra=()):
    """Resample a native polyline, certifying every original edge and corner."""
    chain = (first, second, *extra)
    lengths = [math.dist(m.start, m.end) for m in chain]
    knots = [0.0]
    for length in lengths:
        knots.append(knots[-1] + length)
    total = knots[-1]
    if total > 8 or min(lengths) <= 0:
        return None  # Bound the local search; an uncertified chain is refused.

    def sample(s):
        index = min(len(chain)-1, bisect_right(knots, s)-1)
        m, origin, length = chain[index], knots[index], lengths[index]
        u = _lerp(m.start, m.end, (s - origin) / length)
        p = tuple(round(x, 6) for x in _point(warp, u, True))
        return u, p

    count = max(3, math.ceil(total / (minimum / 20)))
    positions = sorted({*knots, *(total*i/count for i in range(1, count))})
    nodes = [sample(s) for s in positions]
    previous = {0: None}
    for j in range(1, len(nodes)):
        v, q = nodes[j]
        for i in range(j):
            if i not in previous:
                continue
            u, p = nodes[i]
            length = math.dist(p, q)
            if not minimum - 2e-6 <= length <= step + 2e-6:
                continue
            a, b = positions[i], positions[j]
            cuts = [a, *(k for k in knots[1:-1] if a < k < b), b]
            bound = 0.0
            pieces = []
            for l, r in pairwise(cuts):
                left, right = sample(l)[0], sample(r)[0]
                # Compare the physical chord at each *native* subinterval. The
                # analytic certificate includes the residual at the corner.
                cp, cq = _lerp(p, q, (l-a)/(b-a)), _lerp(p, q, (r-a)/(b-a))
                error = warp.chord_error_bound(left, right, cp, cq)
                if not math.isfinite(error) or error < 0:
                    raise WaveError("Limite de erro inválido na união de arestas.")
                bound = max(bound, error)
                index = min(len(chain)-1, bisect_right(knots, (l+r)/2)-1)
                m, density = chain[index], chain[index].de / lengths[index]
                pieces.append((left, right, m, (r-l)*density))
            if bound <= tolerance:
                previous[j] = i, pieces, length, bound
                break
    j = len(nodes) - 1
    if j not in previous:
        return None
    points, portions, sizes, bounds = [nodes[j]], [], [], []
    while j:
        j, pieces, length, bound = previous[j]
        points.append(nodes[j])
        portions.append(pieces)
        sizes.append(length)
        bounds.append(bound)
    return (list(reversed(points)), max(bounds), min(sizes), max(sizes)), list(reversed(portions))


def _join_short_edges(parsed, selected, warp, step, minimum, tolerance,*,progress=lambda message:None,cancelled=lambda:False):
    moves = list(parsed.moves.values())
    skipped, plans = set(), {}
    prepare_layer=getattr(warp,'prepare_layer',None);prepared_layer=None;layer_moves={}
    if callable(prepare_layer):
        for move in moves:
            if move.obj==selected and move.deposits:layer_moves.setdefault(move.layer,[]).append(move)
    for index, m in enumerate(moves):
        if index%1000==0 and cancelled():raise WaveError('Geração cancelada.')
        if index%10000==0:progress(f'Conferindo quinas e movimentos curtos: {100*index/max(1,len(moves)):.0f}%…')
        if (not m.deposits or m.obj != selected or m.i in skipped or m.i in plans
                or None in m.start or None in m.end or m.end[2] <= warp.anchor_z):
            continue
        field = _role_warp(warp, m)
        if callable(prepare_layer) and m.layer!=prepared_layer:
            prepare_layer(layer_moves.get(m.layer,()),m.h or .2);prepared_layer=m.layer
        p, q = _point(field, m.start, True), _point(field, m.end, True)
        if math.dist(p, q) >= minimum - 2e-6:
            continue
        if (getattr(warp.settings,'retain_native_short_edges',False)
                and math.dist(m.start,m.end) < minimum
                and field.chord_error_bound(m.start,m.end,p,q) <= tolerance):
            continue
        if (max(math.dist(p, m.start), math.dist(q, m.end)) <= 2e-6
                and all(abs(_gap_and_scale(field, at, m.h)[1]-1) < 1e-9
                        for at in (m.start, _lerp(m.start, m.end, .5), m.end))):
            continue
        windows = [(start, size) for size in (2, 3, 4)
                   for start in range(index, index-size, -1)
                   if 0 <= start and start+size <= len(moves)]
        for start, size in windows:
            chain = moves[start:start+size]
            if any(not other.deposits or other.i in plans or other.i in skipped or other.label != m.label
                   or other.comment or None in other.start or None in other.end
                   or (other.layer, other.role, other.h, other.f, other.e_abs) != (m.layer, m.role, m.h, m.f, m.e_abs)
                   for other in chain):
                continue
            if chain[0].start == chain[-1].end:
                continue
            if any(first.end != second.start or
                   any(not re.fullmatch(r"\s*;\s*(?:WIDTH|LINE_WIDTH)\s*:[^\r\n]+\s*", ln, re.I)
                       for ln in parsed.lines[first.i+1:second.i]) for first, second in pairwise(chain)):
                continue
            plan = _joined_geometry(*chain[:2], field, step, minimum, tolerance, extra=chain[2:])
            if plan:
                virtual = replace(chain[-1], start=chain[0].start, de=sum(edge.de for edge in chain))
                plans[chain[-1].i] = virtual, plan, tuple(chain)
                skipped.update(edge.i for edge in chain[:-1])
                break
        else:
            raise WaveError(f"Linha {m.i+1}: aresta curta deformada sem união certificada na mesma função.")
    return skipped, plans


def _feed(start, end, requested, z_speed=MAX_Z_SPEED, z_accel=MAX_Z_ACCEL):
    length = math.dist(start, end)
    dz = abs(end[2] - start[2])
    if requested <= 0 or not math.isfinite(requested):
        raise WaveError("Movimento conforme sem avanço conhecido.")
    if not dz:
        return requested, 0.0, 0.0
    # Conservative per-segment rest-to-Z-speed bound. This also bounds the
    # centered finite difference across a reversal between consecutive segments.
    feed = min(requested, 60 * z_speed * length / dz,
               60 * length * math.sqrt(z_accel / (2 * dz)))
    feed = math.floor(feed * 1000) / 1000
    if not feed:
        raise WaveError("Avanço de Z abaixo da resolução de saída.")
    dt = 60 * length / feed
    return feed, dz / dt, 2 * dz / (dt * dt)


def _top_layer_audit(warp, original, mapped):
    """Compare emitted vertices on the highest native plane to both mesh roofs."""
    z = max(p[2] for p in original)
    flat_offsets, restored_offsets = [], []
    seen = set()
    for u, q in zip(original, mapped):
        xy = u[:2]
        if abs(u[2] - z) > 1e-8 or xy in seen:
            continue
        seen.add(xy)
        roofs = warp.surface_heights(*xy)
        if roofs is not None:
            original_roof, flat_roof = roofs
            flat_offsets.append(flat_roof - u[2])
            restored_offsets.append(original_roof - q[2])
    return {
        "scope": "Vértices XY distintos da deposição na camada plana mais alta, incluindo todos os papéis.",
        "sign": "Valor positivo indica linha central abaixo do teto da malha nesse XY.",
        "native_plane_z_mm": z, "sampled_xy": len(seen),
        "inside_mesh_projection": len(restored_offsets),
        "outside_mesh_projection": len(seen) - len(restored_offsets),
        "flat_roof_minus_native_z_range_mm": [min(flat_offsets), max(flat_offsets)] if flat_offsets else None,
        "original_roof_minus_emitted_z_range_mm": [min(restored_offsets), max(restored_offsets)] if restored_offsets else None,
        "original_roof_minus_emitted_z_rms_mm": math.sqrt(sum(v*v for v in restored_offsets) / len(restored_offsets)) if restored_offsets else None,
    }


def process_conformal_gcode(source: bytes, warp, print_object_map: dict[int, str],
                            selected_object_id: str, *, printer_profile=None,
                            progress=lambda message:None,cancelled=lambda:False) -> ProcessedResult:
    """Map one labelled model from its flattened slice. No printer interface is used."""
    if not selected_object_id or selected_object_id not in print_object_map.values():
        raise WaveError("Peça conforme sem correspondência no G-code.")
    if getattr(warp, "object_id", selected_object_id) != selected_object_id:
        raise WaveError("O campo conforme pertence a outra peça.")
    if b"OrcaWaveStudio BENCH ONLY" in source:
        raise WaveError("Use a fatia da malha achatada ainda sem pós-processamento.")
    if re.search(rb'(?mi)^;\s*zaa_enabled\s*=\s*1\s*$',source):
        raise WaveError('O Z Contouring nativo já modifica Z e extrusão. Use uma captura planar para o motor regional.')
    parsed = read(source, {selected_object_id}, print_object_map, profile_macros=printer_profile is not None)
    if len([label for label in parsed.seen if print_object_map[label[0]] == selected_object_id]) != 1:
        raise WaveError("O campo de coordenadas exige uma única instância da peça selecionada.")
    if any(not move.xyz_abs and move.obj==selected_object_id for move in parsed.moves.values()):
        raise WaveError("O estudo conforme exige posicionamento XYZ absoluto (G90).")
    if any(i > min(parsed.moves, default=-1) and re.match(r"^\s*G92\b[^;]*[XYZ]", parsed.lines[i], re.I)
           for i in parsed.barrier):
        raise WaveError("Mudança de origem XYZ durante o percurso não suportada.")

    step, minimum, tolerance = (warp.settings.step_mm, warp.settings.min_segment_mm, warp.settings.tolerance_mm)
    if not (0.15 <= minimum <= step <= 2 and 0 < tolerance <= 0.02):
        raise WaveError("Parâmetros de amostragem conforme fora do intervalo.")
    owners = _ownership(parsed, selected_object_id, warp)
    skipped, joins = _join_short_edges(parsed, selected_object_id, warp, step, minimum, tolerance,progress=progress,cancelled=cancelled)
    bead_policy=getattr(warp,'deposition_model',None)
    if bead_policy:
        from .bead_deposition import layer_pitches,bead_portion,section_area
        pitches=layer_pitches(parsed,selected_object_id)
    prepare_layer=getattr(warp,'prepare_layer',None);prepared_layer=None;layer_moves={}
    if callable(prepare_layer):
        for move in parsed.moves.values():
            if move.obj==selected_object_id and move.deposits:layer_moves.setdefault(move.layer,[]).append(move)
    report = {
        "study_type": "conformal_full_part", "bench_only": True, "print_allowed": False,
        "physical_validation": False, "native_preview_validated": False,
        "source_sha256": digest(source), "selected_object_id": selected_object_id,
        "original_points": [], "deformed_points": [], "layer_ids": [], "break_indices": [],
        "point_object_ids": [], "segments": 0, "segment_count": 0, "travel_segments": 0,
        "min_segment_mm": None, "max_segment_mm": 0.0, "max_geometric_error_mm": 0.0,
        "min_subdivided_segment_mm": None, "preserved_short_source_segments": 0,
        "coalesced_short_source_edges": len(joins),
        "native_short_edge_proposal": bool(getattr(warp.settings,'retain_native_short_edges',False)),
        "inherited_mapped_short_deposition_segments": 0,
        "inherited_mapped_short_deposition_min_mm": None,
        "nonplanar_extrusion_segments_by_role": {},
        "nonplanar_extrusion_layers": {},
        "short_native_edges": {"deposition": 0, "travel": 0, "xyz_changed": 0, "e_delta_changed": 0,
                               "max_endpoint_displacement_mm": 0.0, "max_abs_e_delta_change_mm": 0.0},
        "max_z_speed_mm_s": 0.0, "max_z_acceleration_mm_s2": 0.0,
        "normal_spacing_mm": [], "cell_volume_scale_range": [], "gaps_above_nominal_width": 0,
        "estimates": {"mass_g": None, "updated_time_s": None, "source_selected_deposition_seconds": 0.0,
                      "processed_selected_deposition_seconds": 0.0},
        "extrusion_model": "Volume da célula de camada mapeada; integral do jacobiano vertical por Simpson. "
                           "O cordão finito é aproximado. A largura efetiva pode variar com a direção.",
        "travel_model": "Campo da peça entre deposições próprias; ligações entre peças por viagem linear em XYZ físico.",
        "z_dynamics": "Comandos emitidos na trajetória mapeada, com limite conservador por segmento. "
                      "Sem simulação do planejador de movimento ou de colisões.",
    }
    if bead_policy:report['bead_deposition']={**bead_policy,'minimum_supported_height_mm':None,'maximum_supported_height_mm':0.,
        'below_profile_minimum_occurrences':0,'above_profile_maximum_occurrences':0,'native_section_contributions':0,
        'height_metadata':'physical normal gap for supported beads; native section for bridges and ironing',
        'extrusion_model':'finite stadium section integrated on mapped half-chords, with native flow factor',
        'physical_qualification':False}
    if bead_policy:report['extrusion_model']='Finite stadium section from actual logical-pitch normal gap; native flow factor retained. Bridges retain native section.'
    report['native_retraction_rounding']=parsed.retraction_rounding
    original, mapped, layers = report["original_points"], report["deformed_points"], report["layer_ids"]
    source_roles, emitted_roles = Counter(), Counter()
    # Orca writes support-layer metadata with more digits than its XYZ words.
    # Accept only the half-quantum discrepancy; endpoints must still be planar.
    native_quantum = .000501 if any(re.match(r'^;\s*generated by OrcaSlicer\b', ln, re.I)
                                     for ln in parsed.lines[:12]) else .00002
    report['source_z_metadata_rounding_allowance_mm'] = native_quantum
    hmin = smin = math.inf
    hmax = smax = max_part_z = 0.0
    e_shift = total_delta = retract_debt = 0.0
    current_feed = 0.0
    actual_pos = None
    last_trace = None
    output = []
    displayed_section=[None,None]
    metadata_locations = {}
    newline = "\r\n" if b"\r\n" in source else "\n"
    def emit(text):
        output.append(text + newline)

    def ensure_section(h,w):
        if not bead_policy or h is None or w is None:return
        for k,(tag,value) in enumerate((('HEIGHT',h),('WIDTH',w))):
            rounded=round(value,6)
            if displayed_section[k]!=rounded:emit(';'+tag+':'+_num(rounded,6));displayed_section[k]=rounded

    for i, line in enumerate(parsed.lines):
        if i%1000==0 and cancelled():raise WaveError('Geração cancelada.')
        if i%20000==0:progress(f'Restaurando cordões e extrusão: {100*i/max(1,len(parsed.lines)):.0f}%…')
        if i in skipped:
            if retract_debt > 1e-7:
                raise WaveError(f"Linha {i+1}: união de arestas após retração não recuperada.")
            continue
        if i in parsed.resets:
            e_shift = 0.0
        m = parsed.moves.get(i)
        plan = joins.get(i)
        if plan:
            m = plan[0]
        if m is None:
            if bead_policy:
                match=re.fullmatch(r'\s*;\s*(HEIGHT|LAYER_HEIGHT|WIDTH|LINE_WIDTH)\s*:\s*([-+0-9.eE]+)\s*',line)
                if match:displayed_section[0 if match[1] in {'HEIGHT','LAYER_HEIGHT'} else 1]=round(float(match[2]),6)
            if STALE.match(line) or re.match(r"^\s*;\s*(estimated first layer printing time|max_z_height\s*:)", line, re.I):
                metadata_locations[i] = len(output)
                output.append("")
            else:
                output.append(line)
            continue
        spatial = any(k in m.fields for k in "XYZ") and m.start != m.end
        dep = m.deposits and m.obj == selected_object_id
        if i in parsed.retraction_rounding:retract_debt=0.
        if dep:
            if (retract_debt > 1e-7 or not m.w or m.w <= 0 or not m.h or m.h <= 0
                    or m.z is None or None in m.start or None in m.end or m.f <= 0
                    or abs(m.start[2] - m.end[2]) > 2e-5
                    or abs(m.start[2] - m.z) > native_quantum
                    or abs(m.end[2] - m.z) > native_quantum):
                raise WaveError(f"Linha {i+1}: deposição não planar, largura indefinida ou retração não recuperada.")
        if m.deposits and m.end[2] is not None and not dep:
            max_part_z = max(max_part_z, m.end[2])
        retract_debt = max(0.0, retract_debt - m.de)
        own = owners.get(i, (False, False))
        complete = None not in m.start and None not in m.end
        needs_mapping = spatial and any(own) and complete
        if spatial and not complete and any(own):
            if None in m.end or math.dist(_point(warp, m.end, own[1]), m.end) > 1e-7:
                raise WaveError(f"Linha {i+1}: início de viagem conforme em posição desconhecida.")
        if not needs_mapping:
            if m.deposits:ensure_section(m.h,m.w)
            if spatial:
                if complete and actual_pos is not None and math.dist(actual_pos, m.start) > 2e-5:
                    raise WaveError(f"Linha {i+1}: viagem de transição ausente antes de outra peça.")
                actual_pos = m.end if None not in m.end else None
                last_trace = None
            if "F" not in m.fields and current_feed != m.f and m.f > 0:
                emit("G1 F" + _num(m.f, 8))
            current_feed = m.f
            if "E" in m.fields and m.e_abs and abs(e_shift) > 5e-9:
                body, sep, annotation = line.partition(";")
                line = EWORD.sub(lambda match: match[1] + _num(m.e + e_shift, 8), body, count=1) + sep + annotation
            output.append(line)
            continue

        # The 0.15 mm minimum applies to recreated deposition segments. Travel
        # can use smaller steps to cross the local field and layer transitions.
        if dep and callable(prepare_layer) and m.layer!=prepared_layer:
            if cancelled():raise WaveError('Geração cancelada.')
            prepare_layer(layer_moves.get(m.layer,()),pitches[m.layer] if bead_policy else m.h)
            prepared_layer=m.layer
        geometry = plan[1][0] if plan else _geometry(m, own, warp, step, minimum if dep else .01, tolerance)
        points, error, shortest, longest = geometry
        if actual_pos is not None and math.dist(points[0][1], actual_pos) > 2e-5:
            raise WaveError(f"Linha {i+1}: mudança de referencial sem uma viagem contínua.")
        n = len(points) - 1
        short = shortest < minimum - 2e-6
        inherited = (short and dep and n == 1 and not plan
                     and getattr(warp.settings,'retain_native_short_edges',False)
                     and math.dist(m.start,m.end) < minimum and error <= tolerance)
        if short:
            report["preserved_short_source_segments"] += 1
            audit = report["short_native_edges"]
            audit["deposition" if dep else "travel"] += 1
            displacement = max(math.dist(flat, physical) for flat, physical in points)
            audit["xyz_changed"] += displacement > 2e-6
            audit["max_endpoint_displacement_mm"] = max(audit["max_endpoint_displacement_mm"], displacement)
            if displacement > 2e-6 and dep and not inherited:
                raise WaveError(f"Linha {i+1}: aresta curta com XYZ alterado.")
        if n > 1 and dep:
            report["min_subdivided_segment_mm"] = min(report["min_subdivided_segment_mm"] or shortest, shortest)
        report["min_segment_mm"] = min(report["min_segment_mm"] or shortest, shortest)
        report["max_segment_mm"] = max(report["max_segment_mm"], longest)
        report["max_geometric_error_mm"] = max(report["max_geometric_error_mm"], error)
        if dep:
            source_roles[m.role] += len(plan[2]) if plan else 1
            emitted_roles[m.role] += n
            report["segments"] += n
            native_length = (sum(math.dist(edge.start, edge.end) for edge in plan[2])
                             if plan else math.dist(m.start, m.end))
            report["estimates"]["source_selected_deposition_seconds"] += 60 * native_length / m.f
            trace = (m.layer, m.label, m.role)
            if trace != last_trace:
                report["break_indices"].append(len(original))
                original.append(points[0][0])
                mapped.append(points[0][1])
                layers.append(m.layer)
                report["point_object_ids"].append(m.label[0])
            last_trace = trace
        else:
            report["travel_segments"] += n
            last_trace = None

        emitted_de = ideal_de = 0.0
        flat_length = math.dist(m.start, m.end)
        start_e = m.e - m.de + e_shift
        for j, ((u, p), (v, q)) in enumerate(pairwise(points)):
            extrusion = 0 if plan else m.de * math.dist(u, v) / flat_length
            if dep:
                portions = plan[1][1][j] if plan else [(u, v, m, extrusion)]
                extrusion = 0.0;display_height=display_area=display_length=0.
                for left, right, native, base_e in portions:
                    mid = _lerp(left, right, 0.5)
                    field=_role_warp(warp,native)
                    if bead_policy:
                        amount,h,w,gaps_range=bead_portion(field,left,right,native,base_e,pitches[native.layer])
                        extrusion+=amount
                        length=math.dist(field.map_point(left),field.map_point(right))
                        display_length+=length;display_height+=h*length;display_area+=section_area(w,h)*length
                        bead_report=report['bead_deposition']
                        if gaps_range is None:
                            bead_report['native_section_contributions']+=1
                            continue
                        gaps=(gaps_range[0],gaps_range[1])
                        scales=tuple(_gap_and_scale(field,at,pitches[native.layer])[1] for at in (left,mid,right))
                        bead_report['minimum_supported_height_mm']=min(bead_report['minimum_supported_height_mm'] or math.inf,*gaps)
                        bead_report['maximum_supported_height_mm']=max(bead_report['maximum_supported_height_mm'],*gaps)
                        bead_report['below_profile_minimum_occurrences']+=min(gaps)<bead_policy['profile_minimum_mm']-2e-5
                        bead_report['above_profile_maximum_occurrences']+=max(gaps)>bead_policy['profile_maximum_mm']+2e-5
                        if bead_policy.get('reject_below_profile_minimum') and min(gaps)<bead_policy['profile_minimum_mm']-2e-5:
                            raise WaveError(f'BEAD_MINIMUM: linha {i+1}, cordão de {min(gaps):.6f} mm abaixo de {bead_policy["profile_minimum_mm"]:g} mm; replaneje o espaçamento.')
                        if max(gaps)>bead_policy['profile_maximum_mm']+2e-5:
                            raise WaveError(f'BEAD_HEIGHT: linha {i+1}, cordão de {max(gaps):.6f} mm acima de {bead_policy["profile_maximum_mm"]:g} mm; replaneje o espaçamento.')
                    else:
                        gaps, scales = zip(*(_gap_and_scale(field, at, native.h) for at in (left, mid, right)))
                        extrusion += base_e * (scales[0] + 4 * scales[1] + scales[2]) / 6
                    hmin, hmax = min(hmin, *gaps), max(hmax, *gaps)
                    smin, smax = min(smin, *scales), max(smax, *scales)
                    report["gaps_above_nominal_width"] += max(gaps) > native.w + 2e-5
                if bead_policy and display_length:
                    h=display_height/display_length
                    w=display_area/display_length/h+(1-math.pi/4)*h
                    ensure_section(h,w)
                original.append(v)
                mapped.append(q)
                layers.append(m.layer)
                report["point_object_ids"].append(m.label[0])
                max_part_z = max(max_part_z, p[2], q[2])
                if abs(q[2]-p[2]) > 2e-6:
                    counts=report['nonplanar_extrusion_segments_by_role']
                    counts[m.role]=counts.get(m.role,0)+1
                    row=report['nonplanar_extrusion_layers'].setdefault(str(m.layer),{
                        'logical_z_mm':m.z,'up':0,'down':0,'z_min_mm':min(p[2],q[2]),'z_max_mm':max(p[2],q[2])})
                    row['up' if q[2]>p[2] else 'down']+=1
                    row['z_min_mm']=min(row['z_min_mm'],p[2],q[2])
                    row['z_max_mm']=max(row['z_max_mm'],p[2],q[2])
            requested=m.f
            if printer_profile:
                if not printer_profile.contains(p) or not printer_profile.contains(q):
                    raise WaveError(f'PROFILE_BOUNDS: linha {i+1} fora do volume da impressora selecionada.')
                if dep and extrusion>0 and printer_profile.max_volumetric_mm3_s:
                    volume=extrusion*math.pi*(printer_profile.filament_mm/2)**2
                    requested=min(requested,60*math.dist(p,q)*printer_profile.max_volumetric_mm3_s/volume)
            feed, speed, accel = _feed(p, q, requested,
                printer_profile.z_speed_mm_s if printer_profile else MAX_Z_SPEED,
                printer_profile.z_acceleration_mm_s2 if printer_profile else MAX_Z_ACCEL)
            report["max_z_speed_mm_s"] = max(report["max_z_speed_mm_s"], speed)
            report["max_z_acceleration_mm_s2"] = max(report["max_z_acceleration_mm_s2"], accel)
            if dep:
                report["estimates"]["processed_selected_deposition_seconds"] += 60 * math.dist(p, q) / feed
            words = [m.cmd, *[axis + _num(val, 6) for axis, val in zip("XYZ", q)]]
            if "E" in m.fields:
                ideal_de += extrusion
                if m.e_abs:
                    cmd_e = round(start_e + ideal_de, 8)
                    emitted_de = cmd_e - start_e
                else:
                    cmd_e = round(ideal_de - emitted_de, 8)
                    emitted_de += cmd_e
                words.append("E" + _num(cmd_e, 8))
            restore_feed = feed != current_feed and "F" not in m.fields
            if feed != current_feed or (j == 0 and "F" in m.fields):
                words.append("F" + _num(feed, 8))
            current_feed = feed
            if j == n - 1 and m.comment:
                words.append(";" + m.comment)
            if (short and feed == m.f and abs(emitted_de - m.de) < 1e-8
                    and math.dist(p,m.start)<5e-9 and math.dist(q,m.end)<5e-9):
                if restore_feed:
                    emit("G1 F" + _num(feed, 8))
                if m.e_abs and abs(e_shift) >= 5e-9 and "E" in m.fields:
                    body, sep, annotation = line.partition(";")
                    line = EWORD.sub(lambda match: match[1] + _num(m.e + e_shift, 8), body, count=1) + sep + annotation
                output.append(line)
            else:
                emit(" ".join(words))
        delta = emitted_de - m.de
        if short:
            if inherited and (displacement>2e-6 or abs(delta)>1e-8):
                report['inherited_mapped_short_deposition_segments'] += 1
                report['inherited_mapped_short_deposition_min_mm'] = min(
                    report['inherited_mapped_short_deposition_min_mm'] or shortest,shortest)
            audit["e_delta_changed"] += int(abs(delta) > 1e-8)
            audit["max_abs_e_delta_change_mm"] = max(audit["max_abs_e_delta_change_mm"], abs(delta))
            if abs(delta) > 1e-8 and not inherited:
                raise WaveError(f"Linha {i+1}: aresta curta com fluxo alterado.")
        e_shift += delta
        total_delta += delta
        actual_pos = points[-1][1]

    if not source_roles:
        raise WaveError("Nenhuma deposição identificada na malha achatada.")
    if output and not output[-1].endswith(("\n", "\r")):
        output.append(newline)
    emit(MARK + " / PREVIEW ONLY / PRINT DISABLED")
    for i, text in _material(parsed, total_delta, report).items():
        if i in metadata_locations:
            output[metadata_locations[i]] = text
    for i, location in metadata_locations.items():
        if re.match(r"^\s*;\s*max_z_height\s*:", parsed.lines[i], re.I):
            output[location] = "; max_z_height: " + _num(max_part_z, 6) + newline
    result = "".join(output).encode("latin1")
    report.update(segment_count=report["segments"], total_e_delta=total_delta,
                  source_deposition_moves_by_role=dict(source_roles), output_segments_by_role=dict(emitted_roles),
                  normal_spacing_mm=[hmin, hmax], cell_volume_scale_range=[smin, smax],
                  max_deposition_z_mm=max_part_z, processed_sha256=digest(result))
    report["top_layer_roof_audit"] = _top_layer_audit(warp, original, mapped)
    if printer_profile:
        report['printer_profile']=printer_profile.public_summary()
        report['profile_preserved']=True
    return ProcessedResult(result, report)
