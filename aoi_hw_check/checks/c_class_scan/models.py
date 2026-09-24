from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PinHeightSample:
    """Stage PIN/PAD 1개 지점의 AF 측정 높이."""

    pin_id: str
    z_um: float


@dataclass(frozen=True)
class AFZSample:
    """AF가 면을 따라가며 기록한 1개 샘플 — 높이와 Beam Position 추종 오차."""

    x_mm: float
    y_mm: float
    z_um: float
    beam_position_error_um: float


@dataclass(frozen=True)
class AFZTrack:
    """광학계 1계통(Micro/Macro/계측)의 AF Z 추종 샘플 목록."""

    subsystem: str
    samples: list[AFZSample] = field(default_factory=list)


@dataclass(frozen=True)
class AFZMap:
    """AF Z 추종 맵 — Stage PIN 높이, 계통별 Tilt/AFM Setting 판정의 공통 입력."""

    pin_heights: list[PinHeightSample] = field(default_factory=list)
    tracks: dict[str, AFZTrack] = field(default_factory=dict)


@dataclass(frozen=True)
class CellCoordinateSample:
    """Gantry 구동 중 다점 취득한 Cell 패턴 좌표 1개 (Glass Edge 아님)."""

    stage_position_mm: float
    x_um: float
    y_um: float


@dataclass(frozen=True)
class ScanImageSet:
    """같은 Scan에서 취득한 영상에서 산출한 값들 — Focus 판정, Gantry 직각도 판정의 입력."""

    focus_measures: dict[str, float] = field(default_factory=dict)
    gantry_x_axis_samples: list[CellCoordinateSample] = field(default_factory=list)
    gantry_y_axis_samples: list[CellCoordinateSample] = field(default_factory=list)


@dataclass(frozen=True)
class ScanResult:
    """기준 시료 1회 Scan의 결과 — AF Z 추종 맵과 스캔 영상이 동시에 나온다."""

    af_z_map: AFZMap
    scan_images: ScanImageSet
