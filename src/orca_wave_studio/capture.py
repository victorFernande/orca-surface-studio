from __future__ import annotations

from dataclasses import asdict
import copy
import json
import os
from pathlib import Path
import re
import threading
import uuid

from .contracts import CapturedSlice, ProjectSnapshot, StaleArtifactError, WaveError, digest


OBJECT_START = re.compile(r"^;\s*printing object\s+.*?\bid:(\d+)\s+copy\s+(\d+)", re.I)


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def validate_object_labels(source: bytes, mapping: dict[int, str]) -> set[int]:
    seen = set()
    for line in source.decode("utf-8", errors="strict").splitlines():
        match = OBJECT_START.match(line)
        if match:
            seen.add(int(match[1]))
    if not seen:
        raise WaveError("O fatiamento não identifica as peças. Ative os rótulos de objetos e fatie novamente.")
    unknown = seen.difference(mapping)
    if unknown:
        raise WaveError("Os identificadores das trajetórias não correspondem às peças desta geração.")
    return seen


class CaptureStore:
    """Bind a completed export to its own plate and immutable project revision."""

    def __init__(self, storage: Path, allowed_source_roots: tuple[Path, ...] = (), source_validator=None) -> None:
        self.storage = Path(storage).resolve()
        self.allowed_source_roots = tuple(Path(p).resolve() for p in allowed_source_roots)
        self.source_validator=source_validator
        self._lock = threading.RLock()
        self._pending: dict | None = None
        self._current: CapturedSlice | None = None
        self._staged: CapturedSlice | None = None
        self._epoch = 0
        self.last_invalidation = "Fatie a mesa com o estúdio carregado."

    def begin(self, snapshot: ProjectSnapshot, print_object_map: dict[int, str], *,
              effective_snapshot: ProjectSnapshot | None = None) -> str:
        if not print_object_map:
            raise WaveError("O grafo de fatiamento não contém peças identificáveis.")
        known = {str(obj["id"]) for obj in snapshot.objects}
        if not set(map(str, print_object_map.values())).issubset(known):
            raise WaveError("O mapa de objetos não pertence ao retrato do projeto.")
        with self._lock:
            self._epoch += 1
            capture_id = uuid.uuid4().hex
            self._pending = {"snapshot": copy.deepcopy(snapshot), "mapping": dict(print_object_map),
                             "effective": copy.deepcopy(effective_snapshot),
                             "id": capture_id, "epoch": self._epoch, "path": None}
            self._current = None
            self._staged = None
            return capture_id

    def export_started(self, model_id: str, source_path: str) -> None:
        with self._lock:
            pending = self._pending
            if pending is None or pending["snapshot"].session_id != str(model_id):
                raise StaleArtifactError("O início da exportação não pertence ao fatiamento acompanhado.")
            pending["path"] = str(Path(source_path).resolve())

    def finish(self, model_id: str, source_path: str, *, success: bool = True) -> CapturedSlice:
        with self._lock:
            pending = self._pending
            if not success:
                self.invalidate("O fatiamento foi cancelado ou falhou.")
                raise StaleArtifactError(self.last_invalidation)
            if pending is None:
                raise StaleArtifactError("Não há um mapa de peças desta geração. Fatie a mesa novamente.")
            snapshot = pending["snapshot"]
            path = Path(source_path).resolve(strict=True)
            if (str(model_id) != snapshot.session_id or pending["path"] != str(path)):
                raise StaleArtifactError("A exportação concluída não corresponde ao caminho e modelo acompanhados.")
            if self.allowed_source_roots and not any(path.is_relative_to(root) for root in self.allowed_source_roots):
                raise WaveError("O caminho recebido está fora dos diretórios permitidos para captura.")
            if self.source_validator and not self.source_validator(path,snapshot.session_id):
                raise WaveError("O caminho não corresponde ao cache deste processo e modelo Orca.")
            if path.suffix.lower() != ".gcode" or not path.is_file():
                raise WaveError("A captura requer um arquivo G-code textual concluído.")
            if path.stat().st_size > 512 * 1024 * 1024:
                raise WaveError("O arquivo excede o limite de 512 MiB deste estudo.")
            source = path.read_bytes()
            validate_object_labels(source, pending["mapping"])
            target = self.storage / "captures" / (pending["id"] + ".gcode")
            atomic_write(target, source)
            capture = CapturedSlice(pending["id"], snapshot.session_id, snapshot.plate_index,
                                    snapshot.revision, str(path), str(target), digest(source),
                                    pending["mapping"])
            metadata=asdict(capture)
            effective=pending["effective"]
            if effective is not None:
                audit=target.with_suffix(".snapshots.json")
                atomic_write(audit,json.dumps({"gui_before":snapshot.to_dict(),
                             "slicer_effective":effective.to_dict()},ensure_ascii=False).encode("utf-8"))
                metadata.update(effective_revision=effective.revision,snapshots_path=str(audit))
            atomic_write(target.with_suffix(".json"), json.dumps(metadata,
                         indent=2, ensure_ascii=False).encode("utf-8"))
            if effective is None:
                self._current = capture
            else:
                self._staged = capture
            self._pending = None
            return capture

    def confirm_gui(self, model_id: str, snapshot: ProjectSnapshot) -> CapturedSlice:
        with self._lock:
            capture=self._staged
            if (capture is None or capture.session_id != model_id or
                    snapshot.session_id != model_id or capture.plate_index != snapshot.plate_index or
                    capture.revision != snapshot.revision):
                self.invalidate("A interface mudou durante o fatiamento ou a exportação não terminou.")
                raise StaleArtifactError(self.last_invalidation)
            self._current=capture
            self._staged=None
            return capture

    def current(self, snapshot: ProjectSnapshot) -> CapturedSlice:
        with self._lock:
            capture = self._current
            if (capture is None or capture.revision != snapshot.revision
                    or capture.session_id != snapshot.session_id or capture.plate_index != snapshot.plate_index):
                raise StaleArtifactError("As peças ou configurações mudaram. Fatie a mesa novamente.")
            if digest(Path(capture.copy_path).read_bytes()) != capture.sha256:
                self.invalidate("A cópia capturada foi alterada.")
                raise StaleArtifactError(self.last_invalidation)
            return capture

    @property
    def captured(self) -> CapturedSlice | None:
        with self._lock:
            return self._current

    def invalidate(self, reason: str) -> None:
        with self._lock:
            self._epoch += 1
            self._pending = None
            self._staged = None
            self._current = None
            self.last_invalidation = reason
