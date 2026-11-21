"""Identify an imported one-piece study model in the plate coordinate system."""
from __future__ import annotations

import hashlib
import json
import re
import struct
from collections import Counter
from itertools import product
from pathlib import Path
from zipfile import ZipFile

from .contracts import ProjectSnapshot, WaveError
from .geometry import transform_point


def exported_settings(path: Path, *, regional: bool=False) -> dict:
    with ZipFile(path) as archive:
        entry = archive.getinfo("Metadata/project_settings.config")
        if entry.file_size > 20 * 1024 * 1024:
            raise WaveError("Configurações do projeto excedem o tamanho de estudo.")
        settings = json.loads(archive.read(entry).decode("utf-8-sig"))
    if not isinstance(settings, dict) or not settings.get("printer_settings_id"):
        raise WaveError("A cópia original não contém o perfil completo da impressora.")
    # Orca embeds a separate machine preset for this preview project. The source
    # ZIP stays untouched, including the printer's homing/levelling/parking macros.
    base = re.sub(r"\s*\([^()]*\.3mf\)$", "", str(settings["printer_settings_id"]), flags=re.I)
    suffix = hashlib.sha256((str(path.resolve()) + "\0" + base).encode()).hexdigest()[:8]
    name = "OWS Preview " + base[:72] + " " + suffix
    settings.update({
        "printer_settings_id": name, "print_compatible_printers": [name],
        "printer_agent": "orca_wave_octoprint", "print_host": "", "printhost_apikey": "",
        "gcode_label_objects": "1", "slicing_pipeline_plugin": ["Orca Wave Studio Capture"],
        "post_process": [], "enable_arc_fitting": "disabled",
        "machine_start_gcode": "G90\nG21\nM83\nG92 E0\n", "use_relative_e_distances": "1",
        "machine_end_gcode": "M104 S0\nM140 S0\nM84\n",
        "layer_change_gcode": "G92 E0\n", "before_layer_change_gcode": "",
        "use_firmware_retraction": "0",
        # Keep native narrow solid regions rectilinear. Concentric micro-loops
        # can be shorter than the certified 0.15 mm conformal segment minimum.
        "detect_narrow_internal_solid_infill": "0",
        "zaa_enabled": "0",
    })
    for key in ("file_start_gcode", "change_filament_gcode", "change_extrusion_role_gcode",
                "process_change_extrusion_role_gcode", "printing_by_object_gcode",
                "machine_pause_gcode", "time_lapse_gcode", "wrapping_detection_gcode",
                "template_custom_gcode", "printhost_user", "printhost_password"):
        if key in settings:
            settings[key] = ""
    for key, value in (("wipe", "0"), ("filament_wipe", "0"), ("retraction_length", "0"),
                       ("filament_retraction_length", "0"), ("filament_start_gcode", "; OWS preview"),
                       ("filament_end_gcode", "; OWS preview"), ("filament_change_extrusion_role_gcode", "")):
        previous = settings.get(key, [])
        count = max(1, len(previous)) if isinstance(previous, list) else 1
        settings[key] = [value] * count
    # The native emitter can add heating even when startup macros are empty.
    # These temperatures belong only to the deliberately non-printable copy.
    for key,value in list(settings.items()):
        if (key in {'nozzle_temperature','nozzle_temperature_initial_layer','chamber_temperature','idle_temperature'}
                or key.endswith('_plate_temp') or key.endswith('_plate_temp_initial_layer')):
            settings[key]=['0']*max(1,len(value)) if isinstance(value,list) else '0'
    if regional:
        settings.update({'enable_support':'1','support_type':'normal(auto)',
            'support_top_z_distance':'0.2','support_bottom_z_distance':'0.2',
            'support_object_xy_distance':'0.35','support_interface_top_layers':'3',
            'support_interface_bottom_layers':'3','support_interface_spacing':'0.2'})
    return settings


def _cycle(a, b, c):
    return min((a, b, c), (b, c, a), (c, a, b))


def _mesh(snapshot: ProjectSnapshot):
    if len(snapshot.objects) != 1:
        raise WaveError("O fatiamento conformal requer uma única peça na placa.")
    obj = snapshot.objects[0]
    copies, volumes = obj["instances_data"], obj["volumes"]
    if len(copies) != 1 or not copies[0].get("printable", True) or len(volumes) != 1:
        raise WaveError("O estudo requer um único volume e uma única instância imprimível.")
    volume = volumes[0]
    if volume.get("negative") or volume.get("kind") != "part":
        raise WaveError("A peça preparada precisa conter somente o sólido de estudo.")
    points = [tuple(transform_point(p, copies[0]["matrix"], volume["matrix"]))
              for p in volume["vertices"]]
    return points, volume["triangles"]


class PreparedMesh:
    def __init__(self, snapshot: ProjectSnapshot) -> None:
        points, triangles = _mesh(snapshot)
        if not triangles:
            raise WaveError("A malha preparada está vazia.")
        keys = [tuple(round(v * 100000) for v in point) for point in points]
        self.cells = set(keys)
        self.triangles = Counter(_cycle(*(keys[i] for i in face)) for face in triangles)
        sha = hashlib.sha256()
        for face, count in sorted(self.triangles.items()):
            sha.update(struct.pack("<10q", *(n for vertex in face for n in vertex), count))
        self.sha256 = sha.hexdigest()

    def matches(self, snapshot: ProjectSnapshot) -> bool:
        points, triangles = _mesh(snapshot)
        if len(triangles) != self.triangles.total():
            return False
        keys = []
        for point in points:
            scaled = tuple(v * 100000 for v in point)
            key = tuple(round(v) for v in scaled)
            if key not in self.cells:
                # Native 3MF loads use float vertices. A coordinate can straddle the
                # rounded bin; match only an unambiguous neighbour within 0.000015 mm.
                neighbours = [candidate for offset in product((-1, 0, 1), repeat=3)
                              if (candidate := tuple(key[i]+offset[i] for i in range(3))) in self.cells
                              and max(abs(candidate[i]-scaled[i]) for i in range(3)) <= 1.5]
                if len(neighbours) != 1:
                    return False
                key = neighbours[0]
            keys.append(key)
        return Counter(_cycle(*(keys[i] for i in face)) for face in triangles) == self.triangles
