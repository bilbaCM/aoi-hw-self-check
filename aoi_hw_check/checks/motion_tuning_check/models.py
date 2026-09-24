from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MotionTuningState:
    """축별 위치편차·오버슈트·정착시간 측정값. axis_id -> {metric: value}."""

    axes: dict[str, dict[str, float]] = field(default_factory=dict)

    def to_flat_dict(self) -> dict[str, float]:
        """"axis.metric" 형태로 평탄화한다 (동종 설비 비교 저장/조회 키로 사용)."""
        flat: dict[str, float] = {}
        for axis_id, metrics in self.axes.items():
            for metric, value in metrics.items():
                flat[f"{axis_id}.{metric}"] = value
        return flat
