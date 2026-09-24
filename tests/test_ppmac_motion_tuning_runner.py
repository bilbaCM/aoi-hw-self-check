from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.integrations.ppmac.motion_tuning_runner import (
    PPMACMotionTuningRunner,
    TuningMoveSpec,
    load_move_specs,
)


class _FakeConnection:
    def __init__(self, positions: list[float]):
        self._positions = list(positions)
        self.jog_calls: list[tuple[int, float]] = []

    def jog_to_position(self, motor: int, position: float) -> None:
        self.jog_calls.append((motor, position))

    def query(self, variable: str) -> float:
        return self._positions.pop(0)


class _FakeClock:
    """호출할 때마다 0부터 step_ms씩 증가하는 시간을 반환한다."""

    def __init__(self, step_ms: float):
        self._next = 0.0
        self._step = step_ms

    def __call__(self) -> float:
        value = self._next
        self._next += self._step
        return value


class PPMACMotionTuningRunnerTest(unittest.TestCase):
    def test_settling_metrics_are_computed_correctly(self) -> None:
        connection = _FakeConnection([110.0, 105.0, 100.5, 100.3, 100.2])
        spec = TuningMoveSpec(
            motor=1,
            position_variable="Motor[1].ActPos",
            start_position=0.0,
            target_position=100.0,
            settle_tolerance=1.0,
            settle_hold_ms=20.0,
            poll_interval_ms=10.0,
            timeout_ms=200.0,
        )
        runner = PPMACMotionTuningRunner(
            connection,  # type: ignore[arg-type]
            {"X": spec},
            now_ms=_FakeClock(step_ms=10.0),
            sleep=lambda ms: None,
        )

        state = runner.run_tuning_sequence()
        metrics = state.axes["X"]

        self.assertAlmostEqual(metrics["position_deviation_um"], 0.2, places=6)
        self.assertAlmostEqual(metrics["overshoot_percent"], 10.0, places=6)
        self.assertEqual(metrics["settling_time_ms"], 30.0)
        self.assertEqual(connection.jog_calls, [(1, 0.0), (1, 100.0)])

    def test_times_out_when_never_within_tolerance(self) -> None:
        connection = _FakeConnection([110.0, 105.0])
        spec = TuningMoveSpec(
            motor=1,
            position_variable="Motor[1].ActPos",
            start_position=0.0,
            target_position=100.0,
            settle_tolerance=0.1,
            settle_hold_ms=20.0,
            poll_interval_ms=10.0,
            timeout_ms=20.0,
        )
        runner = PPMACMotionTuningRunner(
            connection,  # type: ignore[arg-type]
            {"X": spec},
            now_ms=_FakeClock(step_ms=10.0),
            sleep=lambda ms: None,
        )

        state = runner.run_tuning_sequence()

        self.assertEqual(state.axes["X"]["settling_time_ms"], 20.0)

    def test_zero_move_distance_has_zero_overshoot(self) -> None:
        # settle_hold_ms=0이어도 "hold 조건 충족"은 다음 폴링에서 확인되므로 샘플이 2개 필요
        connection = _FakeConnection([0.0, 0.0])
        spec = TuningMoveSpec(
            motor=1,
            position_variable="Motor[1].ActPos",
            start_position=0.0,
            target_position=0.0,
            settle_tolerance=1.0,
            settle_hold_ms=0.0,
            poll_interval_ms=10.0,
            timeout_ms=200.0,
        )
        runner = PPMACMotionTuningRunner(
            connection,  # type: ignore[arg-type]
            {"X": spec},
            now_ms=_FakeClock(step_ms=10.0),
            sleep=lambda ms: None,
        )

        state = runner.run_tuning_sequence()

        self.assertEqual(state.axes["X"]["overshoot_percent"], 0.0)


class LoadMoveSpecsTest(unittest.TestCase):
    def test_loads_specs_and_skips_comment_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "moves.json"
            path.write_text(
                """
                {
                  "_comment": "note",
                  "X": {
                    "motor": 1,
                    "position_variable": "Motor[1].ActPos",
                    "start_position": 0.0,
                    "target_position": 100.0,
                    "settle_tolerance": 1.0,
                    "settle_hold_ms": 50.0,
                    "poll_interval_ms": 10.0,
                    "timeout_ms": 1000.0
                  }
                }
                """,
                encoding="utf-8",
            )

            specs = load_move_specs(path)

            self.assertEqual(set(specs), {"X"})
            self.assertEqual(specs["X"].motor, 1)

    def test_example_config_file_loads_without_comment_key(self) -> None:
        example_path = (
            Path(__file__).resolve().parent.parent / "config" / "ppmac_tuning_moves.example.json"
        )

        specs = load_move_specs(example_path)

        self.assertNotIn("_comment", specs)
        self.assertIn("X", specs)


if __name__ == "__main__":
    unittest.main()
