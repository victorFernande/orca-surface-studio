from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from typing import Any


class WaveError(ValueError):
    """An input cannot be processed without breaking an explicit constraint."""


class StaleArtifactError(WaveError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint(value: Any) -> str:
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False).encode("utf-8"))


@dataclass(frozen=True)
class WaveParameters:
    mode: str = "z"
    amplitude_mm: float = 0.08
    wavelength_mm: float = 10.0
    step_mm: float = 0.4
    min_segment_mm: float = 0.15
    tolerance_mm: float = 0.02
    start_height_mm: float = 1.0
    end_height_mm: float | None = None
    fade_layers: int = 3
    phase_deg: float = 0.0
    twist_deg_per_mm: float = 0.0
    corner_threshold_deg: float = 45.0
    max_z_speed_mm_s: float = 5.0
    max_z_acceleration_mm_s2: float = 50.0
    bench_only: bool = True
    wave_count: int = 6
    z_ratio: float = 0.5

    def __post_init__(self) -> None:
        if self.mode not in {"xy", "z", "combined"}:
            raise WaveError("Escolha Vaso senoidal, X/Y ou Z.")
        for key, value in asdict(self).items():
            if isinstance(value, float) and not math.isfinite(value):
                raise WaveError(f"{key}: valor não finito.")
        if self.amplitude_mm < 0 or not 1 <= self.wavelength_mm <= 50:
            raise WaveError("Amplitude ou comprimento de onda inválido.")
        if not 0.15 <= self.min_segment_mm <= self.step_mm <= 2:
            raise WaveError("O passo deve respeitar o mínimo de 0,15 mm.")
        if not 0 < self.tolerance_mm <= 0.02:
            raise WaveError("A tolerância geométrica deve ser de até 0,02 mm.")
        if self.start_height_mm < 0 or (self.end_height_mm is not None
                                       and self.end_height_mm <= self.start_height_mm):
            raise WaveError("Faixa de alturas inválida.")
        if self.fade_layers < 1:
            raise WaveError("Use ao menos uma camada de transição.")
        if self.mode == "z" and self.twist_deg_per_mm:
            raise WaveError("No piloto Z as ondas devem permanecer alinhadas entre camadas.")
        if (type(self.wave_count) is not int or not 1 <= self.wave_count <= 24
                or not 0 < self.z_ratio <= 1):
            raise WaveError("Use de 1 a 24 ondas e proporção de Z entre 0 e 1.")
        if self.mode == "combined" and self.twist_deg_per_mm:
            raise WaveError("O vaso senoidal mantém a fase alinhada entre as voltas.")
        if self.max_z_speed_mm_s <= 0 or self.max_z_acceleration_mm_s2 <= 0:
            raise WaveError("Os limites de Z devem ser positivos.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectSnapshot:
    session_id: str
    plate_index: int
    objects: tuple[dict[str, Any], ...]
    settings: dict[str, Any] = field(default_factory=dict)

    @property
    def revision(self) -> str:
        return fingerprint(asdict(self))

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "revision": self.revision}


@dataclass(frozen=True)
class CapturedSlice:
    capture_id: str
    session_id: str
    plate_index: int
    revision: str
    source_path: str
    copy_path: str
    sha256: str
    print_object_map: dict[int, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProcessedResult:
    gcode: bytes
    report: dict[str, Any]

    @property
    def sha256(self) -> str:
        return digest(self.gcode)
