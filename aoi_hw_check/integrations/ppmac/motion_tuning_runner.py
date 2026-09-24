from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from aoi_hw_check.checks.motion_tuning_check.models import MotionTuningState
from aoi_hw_check.checks.motion_tuning_check.runner import MotionTuningRunner
from aoi_hw_check.integrations.ppmac.connection import PmacAsciiConnection


@dataclass(frozen=True)
class TuningMoveSpec:
    """축 1개의 왕복 조그 시험 스펙. 값은 설비/PPMAC 설정에 맞춰 정의해야 한다 (TBD)."""

    motor: int
    position_variable: str
    start_position: float
    target_position: float
    settle_tolerance: float
    settle_hold_ms: float
    poll_interval_ms: float
    timeout_ms: float


def load_move_specs(path: str | Path) -> dict[str, TuningMoveSpec]:
    """축별 왕복 조그 시험 스펙을 로드한다. 사람이 정의하는 설정 파일이다 (TBD)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        axis_id: TuningMoveSpec(**spec)
        for axis_id, spec in data.items()
        if not axis_id.startswith("_")
    }


class PPMACMotionTuningRunner(MotionTuningRunner):
    """축을 조그 이동시키며 위치를 폴링해 위치편차·오버슈트·정착시간을 측정한다.

    실제 조그 명령 문법·좌표 단위·속도/가속도는 PPMAC 설정에 따라 다르므로
    실기 검증이 필요하다 (TBD) — 여기서는 표준 PMAC 조그 명령과 위치 폴링만
    으로 측정 로직을 구성했다. now_ms/sleep을 주입할 수 있어 테스트 시
    실제 시간을 기다리지 않고 검증할 수 있다.
    """

    def __init__(
        self,
        connection: PmacAsciiConnection,
        move_specs: dict[str, TuningMoveSpec],
        now_ms: Callable[[], float] = lambda: time.monotonic() * 1000.0,
        sleep: Callable[[float], None] = lambda ms: time.sleep(ms / 1000.0),
    ):
        self._connection = connection
        self._move_specs = move_specs
        self._now_ms = now_ms
        self._sleep = sleep

    def run_tuning_sequence(self) -> MotionTuningState:
        axes = {axis_id: self._measure_axis(spec) for axis_id, spec in self._move_specs.items()}
        return MotionTuningState(axes=axes)

    def _measure_axis(self, spec: TuningMoveSpec) -> dict[str, float]:
        self._connection.jog_to_position(spec.motor, spec.start_position)

        start_time = self._now_ms()
        self._connection.jog_to_position(spec.motor, spec.target_position)

        samples: list[float] = []
        settled_since: float | None = None
        settling_time_ms = spec.timeout_ms

        while True:
            elapsed_ms = self._now_ms() - start_time
            position = self._connection.query(spec.position_variable)
            samples.append(position)

            within_tolerance = abs(position - spec.target_position) <= spec.settle_tolerance
            if within_tolerance:
                if settled_since is None:
                    settled_since = elapsed_ms
                elif elapsed_ms - settled_since >= spec.settle_hold_ms:
                    settling_time_ms = settled_since
                    break
            else:
                settled_since = None

            if elapsed_ms >= spec.timeout_ms:
                break

            self._sleep(spec.poll_interval_ms)

        return self._compute_metrics(spec, samples, settling_time_ms)

    @staticmethod
    def _compute_metrics(
        spec: TuningMoveSpec, samples: list[float], settling_time_ms: float
    ) -> dict[str, float]:
        final_position = samples[-1]
        position_deviation_um = abs(final_position - spec.target_position)

        move_distance = abs(spec.target_position - spec.start_position)
        if move_distance > 0:
            direction = 1.0 if spec.target_position >= spec.start_position else -1.0
            excess_values = [direction * (p - spec.target_position) for p in samples]
            overshoot_amount = max(0.0, max(excess_values))
            overshoot_percent = overshoot_amount / move_distance * 100.0
        else:
            overshoot_percent = 0.0

        return {
            "position_deviation_um": position_deviation_um,
            "overshoot_percent": overshoot_percent,
            "settling_time_ms": settling_time_ms,
        }
