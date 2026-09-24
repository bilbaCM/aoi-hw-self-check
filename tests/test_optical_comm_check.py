from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.checks.optical_comm_check.collector import OpticalCommCollector
from aoi_hw_check.checks.optical_comm_check.judge import run_optical_comm_check
from aoi_hw_check.checks.optical_comm_check.models import (
    ChannelResponse,
    GrayResponseSample,
    OpticalCommState,
)
from aoi_hw_check.core.models import Verdict
from aoi_hw_check.core.storage import SQLiteResultStore


class FixedCollector(OpticalCommCollector):
    def __init__(self, state: OpticalCommState):
        self._state = state

    def collect(self) -> OpticalCommState:
        return self._state


def _samples(*pairs: tuple[float, float]) -> list[GrayResponseSample]:
    return [GrayResponseSample(light_level=lvl, gray_value=gray) for lvl, gray in pairs]


class OpticalCommCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteResultStore(Path(self._tmpdir.name) / "results.sqlite3")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_monotonic_gray_response_passes(self) -> None:
        state = OpticalCommState(
            channels={
                "CH1": ChannelResponse(
                    channel_id="CH1",
                    communication_ok=True,
                    samples=_samples((0, 10), (50, 120), (100, 240)),
                )
            }
        )

        result = run_optical_comm_check(FixedCollector(state), self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.PASS)
        self.assertEqual(result.deviation, [])

    def test_non_monotonic_gray_response_fails(self) -> None:
        state = OpticalCommState(
            channels={
                "CH1": ChannelResponse(
                    channel_id="CH1",
                    communication_ok=True,
                    samples=_samples((0, 10), (50, 120), (100, 90)),
                )
            }
        )

        result = run_optical_comm_check(FixedCollector(state), self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertEqual([m.field_path for m in result.deviation], ["CH1"])

    def test_no_communication_response_fails(self) -> None:
        state = OpticalCommState(
            channels={
                "CH1": ChannelResponse(channel_id="CH1", communication_ok=False, samples=[])
            }
        )

        result = run_optical_comm_check(FixedCollector(state), self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertIn("통신 응답 없음", result.deviation[0].current_value)

    def test_plateau_at_saturation_ceiling_passes(self) -> None:
        # 255(8bit 상한)에 도달한 뒤 더 안 올라가는 건 센서 포화 — 정상이다.
        state = OpticalCommState(
            channels={
                "CH1": ChannelResponse(
                    channel_id="CH1",
                    communication_ok=True,
                    samples=_samples((0, 10), (50, 200), (75, 255), (100, 255)),
                )
            }
        )

        result = run_optical_comm_check(FixedCollector(state), self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.PASS)
        self.assertEqual(result.deviation, [])

    def test_decrease_at_saturation_ceiling_still_fails(self) -> None:
        # 255 부근이라도 값이 실제로 줄어드는 건 포화가 아니라 이상 신호다.
        state = OpticalCommState(
            channels={
                "CH1": ChannelResponse(
                    channel_id="CH1",
                    communication_ok=True,
                    samples=_samples((0, 10), (50, 200), (75, 255), (100, 240)),
                )
            }
        )

        result = run_optical_comm_check(FixedCollector(state), self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertEqual([m.field_path for m in result.deviation], ["CH1"])

    def test_flat_response_below_saturation_still_fails(self) -> None:
        # 255에 못 미치는 구간에서 안 올라가는 건 포화가 아니라 여전히 고장 후보다.
        state = OpticalCommState(
            channels={
                "CH1": ChannelResponse(
                    channel_id="CH1",
                    communication_ok=True,
                    samples=_samples((0, 10), (50, 100), (100, 100)),
                )
            }
        )

        result = run_optical_comm_check(FixedCollector(state), self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.FAIL)

    def test_only_failing_channels_are_reported(self) -> None:
        state = OpticalCommState(
            channels={
                "CH1": ChannelResponse(
                    channel_id="CH1",
                    communication_ok=True,
                    samples=_samples((0, 10), (100, 240)),
                ),
                "CH2": ChannelResponse(
                    channel_id="CH2",
                    communication_ok=True,
                    samples=_samples((0, 10), (100, 5)),
                ),
            }
        )

        result = run_optical_comm_check(FixedCollector(state), self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertEqual([m.field_path for m in result.deviation], ["CH2"])


if __name__ == "__main__":
    unittest.main()
