"""OrcaSlicer 2.5.1 sliced-only project envelope. Plate indexes in the API start at zero."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile

from .contracts import WaveError, digest


MODEL = "3D/3dmodel.model"
SETTINGS = "Metadata/model_settings.config"
PROJECT = "Metadata/project_settings.config"
SLICE = "Metadata/slice_info.config"
MODEL_RELS = "Metadata/_rels/model_settings.config.rels"
SEQUENCE = "Metadata/filament_sequence.json"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
MODEL_REL = "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"
GCODE_REL = "http://schemas.bambulab.com/package/2021/gcode"
MAX_TOTAL = 1024 * 1024 * 1024
MAX_MEMBER = 512 * 1024 * 1024
MAX_METADATA = 16 * 1024 * 1024

_EMPTY_MODEL = b"""<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:BambuStudio="http://schemas.bambulab.com/package/2021">
 <metadata name="Application">BambuStudio-02.08.01.55</metadata>
 <metadata name="OrcaSlicer">2.5.1</metadata>
 <metadata name="BambuStudio:3mfVersion">1</metadata>
 <resources/><build/>
</model>"""


def _plate_number(index: int) -> int:
    if type(index) is not int or not 0 <= index < 36:
        raise WaveError("Índice de mesa fora do intervalo suportado.")
    return index + 1


def _names(z: ZipFile) -> set[str]:
    seen = set()
    total = 0
    if len(z.infolist()) > 4096:
        raise WaveError("Pacote com excesso de entradas.")
    for item in z.infolist():
        name = item.orig_filename
        path = name.removesuffix("/")
        parts = path.split("/")
        if (not path or any(part in {"", ".", ".."} or part.endswith((" ", ".")) for part in parts)
                or any(char in name for char in '\\:*?"<>|') or any(ord(c) < 32 for c in name)
                or stat.S_ISLNK(item.external_attr >> 16)
                or item.flag_bits & 1 or item.compress_type not in (ZIP_STORED, ZIP_DEFLATED)):
            raise WaveError("Entrada ZIP insegura ou incompatível.")
        key = path.casefold()
        if key in seen:
            raise WaveError("Entrada ZIP duplicada ou ambígua.")
        seen.add(key)
        total += item.file_size
        if (item.file_size > MAX_MEMBER or total > MAX_TOTAL
                or item.file_size > max(1024 * 1024, 250 * item.compress_size)):
            raise WaveError("Tamanho ou expansão ZIP excede o limite.")
    return set(z.namelist())


def _metadata_bytes(z, name):
    if name not in z.namelist() or z.getinfo(name).file_size > MAX_METADATA:
        raise WaveError(f"Metadado ausente ou grande demais: {name}.")
    return z.read(name)


def _xml(z, name):
    data = _metadata_bytes(z, name)
    if b"\x00" in data or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise WaveError("XML com declaração não permitida.")
    return ET.fromstring(data)


def _xml_bytes(root):
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _meta(element, key, value):
    return ET.SubElement(element, "metadata", key=key, value=str(value))


def _value(element, key):
    fields = [m.get("value") for m in element.findall("metadata") if m.get("key") == key]
    if len(fields) > 1:
        raise WaveError(f"Campo duplicado: {key}.")
    return fields[0] if fields else None


def _plate(config, key, number, required=True):
    matches = [p for p in config.findall("plate") if _value(p, key) == str(number)]
    if len(matches) > 1 or (not matches and required):
        raise WaveError(f"Mesa {number} ambígua ou ausente em {key}.")
    return matches[0] if matches else None


def _relations(entries):
    root = ET.Element("Relationships", xmlns=REL_NS)
    for i, (name, kind) in enumerate(entries, 1):
        ET.SubElement(root, "Relationship", Id=f"rel-{i}", Target="/" + name, Type=kind)
    return _xml_bytes(root)


def _types():
    root = ET.Element("Types", xmlns="http://schemas.openxmlformats.org/package/2006/content-types")
    types = {"rels": "application/vnd.openxmlformats-package.relationships+xml",
             "model": "application/vnd.ms-package.3dmanufacturing-3dmodel+xml",
             "png": "image/png", "json": "application/json", "gcode": "text/x.gcode"}
    for extension, mime in types.items():
        ET.SubElement(root, "Default", Extension=extension, ContentType=mime)
    return _xml_bytes(root)


def _slice_header():
    root = ET.Element("config")
    header = ET.SubElement(root, "header")
    for key, value in (("X-BBL-Client-Type", "slicer"), ("X-BBL-Client-Version", "02.08.01.55"),
                       ("OrcaSlicer-Version", "2.5.1")):
        ET.SubElement(header, "header_item", key=key, value=value)
    return root


def _list(settings, key):
    value = settings.get(key, [])
    return [str(v) for v in value] if isinstance(value, list) else [str(value)]


def _reconstruct_slice(number, settings, gcode):
    # An export_3mf_copy without slice info still carries the actual machine/filament presets.
    # A multi-nozzle assignment cannot be inferred reliably from those presets alone.
    plate = ET.Element("plate")
    _meta(plate, "index", number)
    diameters = _list(settings, "nozzle_diameter")
    maps = _list(settings, "filament_map")
    if len(diameters) > 1 or any(v != "1" for v in maps):
        raise WaveError("Configuração multibico exige slice_info nativo da mesa.")
    types = _list(settings, "filament_type")
    colours = _list(settings, "filament_colour")
    ids = _list(settings, "filament_ids")
    if diameters:
        _meta(plate, "nozzle_diameters", diameters[0])
    if maps:
        _meta(plate, "filament_maps", " ".join(maps))
    # Orca writes statistics after CONFIG_BLOCK_END. Use only positive, reported material usage.
    trailer = gcode[-256_000:]
    def usages(unit):
        match = re.search(rb"(?m)^; filament used \[" + unit + rb"\] = ([\d., ]+)\r?$", trailer)
        return [float(v) for v in match[1].split(b",")] if match else []
    lengths, weights = usages(b"mm"), usages(b"g")
    for i, length in enumerate(lengths):
        if length > 0 and i < len(types) and diameters:
            attrs = dict(id=str(i + 1), type=types[i], used_m=str(length / 1000),
                         nozzle_diameter=diameters[0], group_id="0", volume_type="Standard")
            if i < len(colours):
                attrs["color"] = colours[i]
            if i < len(ids):
                attrs["tray_info_idx"] = ids[i]
            if i < len(weights):
                attrs["used_g"] = str(weights[i])
            ET.SubElement(plate, "filament", attrs)
    if weights:
        _meta(plate, "weight", sum(weights))
    return plate


def _parts(project_path, number, gcode):
    payload = f"Metadata/plate_{number}.gcode"
    parts = {"[Content_Types].xml": _types(), MODEL: _EMPTY_MODEL}
    source_plate = ET.Element("plate")
    slice_plate = None
    project_settings = {}
    original_payload=None
    assets = {
        f"Metadata/plate_{number}.png", f"Metadata/plate_{number}_small.png",
        f"Metadata/plate_no_light_{number}.png", f"Metadata/top_{number}.png",
        f"Metadata/pick_{number}.png", f"Metadata/plate_{number}.json",
    }
    if project_path is not None:
        with ZipFile(project_path) as z:
            names = _names(z)
            parts[PROJECT] = _metadata_bytes(z, PROJECT)
            project_settings = json.loads(parts[PROJECT])
            if not isinstance(project_settings, dict):
                raise WaveError("Configuração do projeto inválida.")
            source_plate = _plate(_xml(z, SETTINGS), "plater_id", number)
            if SLICE in names:
                slice_plate = _plate(_xml(z, SLICE), "index", number, required=False)
            if payload in names:
                original_payload=z.read(payload)
            for name in sorted(names):
                if (name in assets or re.fullmatch(r"Metadata/(?:process|filament|machine)_settings_\d+\.config", name)
                        or re.fullmatch(r"Metadata/print_setting_\d+\.config", name)):
                    parts[name] = _metadata_bytes(z, name)
            if SEQUENCE in names:
                key = f"plate_{number}"
                sequences = json.loads(_metadata_bytes(z, SEQUENCE))
                if isinstance(sequences, dict) and key in sequences:
                    parts[SEQUENCE] = json.dumps({key: sequences[key]}).encode()
    else:
        parts[PROJECT] = b'{"name":"project_settings","from":"project","version":"2.5.1.0"}'

    model = ET.Element("config")
    for i in range(1, number + 1):
        plate = ET.SubElement(model, "plate")
        _meta(plate, "plater_id", i)
    for field in source_plate.findall("metadata"):
        key = field.get("key", "")
        if key not in {"plater_id", "gcode_file"}:
            if key.endswith("_file") and field.get("value") not in parts:
                continue
            plate.append(field)
    _meta(plate, "gcode_file", payload)
    ET.SubElement(model, "assemble")
    parts[SETTINGS] = _xml_bytes(model)
    info = _slice_header()
    origin = "native" if slice_plate is not None else ("project_and_gcode" if project_path else "synthetic")
    if slice_plate is not None and original_payload!=gcode:
        fresh=_reconstruct_slice(number,project_settings,gcode)
        mutable={"prediction","time","estimated_time","weight","cost"}
        for item in list(slice_plate):
            if item.tag=="metadata" and item.get("key") in mutable:
                slice_plate.remove(item)
        for item in fresh.findall("metadata"):
            if item.get("key")=="weight":
                slice_plate.append(item)
        fresh_filaments={item.get("id"):item for item in fresh.findall("filament")}
        for item in slice_plate.findall("filament"):
            replacement=fresh_filaments.get(item.get("id"))
            for attribute in ("used_m","used_g"):
                item.attrib.pop(attribute,None)
                if replacement is not None and replacement.get(attribute) is not None:
                    item.set(attribute,replacement.get(attribute))
    info.append(slice_plate if slice_plate is not None else _reconstruct_slice(number, project_settings, gcode))
    parts[SLICE] = _xml_bytes(info)
    parts[MODEL_RELS] = _relations([(payload, GCODE_REL)])
    relations = [(MODEL, MODEL_REL)]
    preview = f"Metadata/plate_{number}.png"
    if preview in parts:
        relations.append((preview, REL_NS + "/metadata/thumbnail"))
    parts["_rels/.rels"] = _relations(relations)
    parts[payload + ".md5"] = hashlib.md5(gcode, usedforsecurity=False).hexdigest().upper().encode()
    parts[payload] = gcode
    return parts, origin


def extract_plate_gcode(path: Path, plate_index: int = 0) -> bytes:
    number = _plate_number(plate_index)
    name = f"Metadata/plate_{number}.gcode"
    try:
        with ZipFile(path) as z:
            names = _names(z)
            required = {MODEL, PROJECT, SETTINGS, SLICE, MODEL_RELS, "_rels/.rels", "[Content_Types].xml"}
            if not required.issubset(names):
                raise WaveError("Estrutura do projeto 3MF incompleta.")
            model_links = [r for r in _xml(z, "_rels/.rels") if r.get("Type") == MODEL_REL]
            if (len(model_links) != 1 or model_links[0].get("Target") != "/" + MODEL
                    or model_links[0].get("TargetMode") == "External"):
                raise WaveError("Relacionamento com o modelo 3MF divergente.")
            candidates = {n for n in names if n.lower().endswith((".gcode", ".gco", ".g"))}
            if candidates != {name}:
                raise WaveError("G-code ausente, em outra mesa ou múltiplo.")
            model_settings = _xml(z, SETTINGS)
            selected = _plate(model_settings, "plater_id", number)
            pointers = [_value(p, "gcode_file") for p in model_settings.findall("plate")]
            if _value(selected, "gcode_file") != name or [p for p in pointers if p] != [name]:
                raise WaveError("Referência ao G-code divergente.")
            _plate(_xml(z, SLICE), "index", number)
            links = [r for r in _xml(z, MODEL_RELS) if r.get("Type") == GCODE_REL]
            if len(links) != 1 or links[0].get("Target") != "/" + name or links[0].get("TargetMode") == "External":
                raise WaveError("Relacionamento com o G-code divergente.")
            data = z.read(name)
            checksum = _metadata_bytes(z, name + ".md5")
            if not data or checksum.upper() != hashlib.md5(data, usedforsecurity=False).hexdigest().upper().encode():
                raise WaveError("G-code vazio ou MD5 divergente.")
            return data
    except (BadZipFile, ET.ParseError, KeyError) as exc:
        raise WaveError("Pacote 3MF inválido.") from exc


def build_sliced_package(gcode: bytes, destination: Path, *, project_3mf: Path | None = None,
                         plate_index: int = 0, metadata: dict | None = None) -> dict:
    number = _plate_number(plate_index)
    if not isinstance(gcode, bytes) or not 0 < len(gcode) <= MAX_MEMBER:
        raise WaveError("G-code vazio ou grande demais.")
    dest = Path(destination)
    if project_3mf is not None and Path(project_3mf).resolve() == dest.resolve():
        raise WaveError("O destino deve ser diferente do projeto de origem.")
    try:
        parts, origin = _parts(project_3mf, number, gcode)
    except (BadZipFile, ET.ParseError, KeyError, UnicodeError, json.JSONDecodeError) as exc:
        raise WaveError("Projeto 3MF inválido.") from exc
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as temp:
        staging = Path(temp.name)
    try:
        with ZipFile(staging, "w", ZIP_DEFLATED, compresslevel=3) as z:
            for name, data in parts.items():
                z.writestr(name, data)
        if extract_plate_gcode(staging, plate_index) != gcode:
            raise WaveError("Falha na conferência dos bytes do pacote.")
        with staging.open("rb") as source:
            package_sha = hashlib.file_digest(source, "sha256").hexdigest()
        os.replace(staging, dest)
    finally:
        staging.unlink(missing_ok=True)
    return {"path": str(dest.resolve()), "plate_index": plate_index, "gcode_sha256": digest(gcode),
            "package_sha256": package_sha, "slice_metadata_source": origin,
            "synthetic_metadata": project_3mf is None, "metadata": dict(metadata or {})}
