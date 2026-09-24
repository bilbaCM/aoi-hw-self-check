from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MotionHWState:
    """축별 Encoder/PWM/I/O 상태값. axis_id -> {field_name: value}."""

    axes: dict[str, dict[str, float]] = field(default_factory=dict)

    def to_flat_dict(self) -> dict[str, float]:
        """"axis.field" 형태로 평탄화한다 (CriteriaStore 조회 키로 사용)."""
        flat: dict[str, float] = {}
        for axis_id, readings in self.axes.items():
            for name, value in readings.items():
                flat[f"{axis_id}.{name}"] = value
        return flat
