from __future__ import annotations

from abc import ABC, abstractmethod

from aoi_hw_check.checks.optical_comm_check.models import (
    ChannelResponse,
    GrayResponseSample,
    OpticalCommState,
)


class OpticalCommCollector(ABC):
    """실제 구현은 카메라/조명 채널마다 광량을 단계적으로 올리며 Gray 응답을 취득한다."""

    @abstractmethod
    def collect(self) -> OpticalCommState: ...


class MockOpticalCommCollector(OpticalCommCollector):
    """실제 카메라/조명 SDK 연동 전까지 사용하는 고정 샘플 Mock 구현체."""

    def __init__(self, state: OpticalCommState | None = None):
        self._state = state or self._default_state()

    def collect(self) -> OpticalCommState:
        return self._state

    @staticmethod
    def _default_state() -> OpticalCommState:
        light_levels = (0, 25, 50, 75, 100)

        def linear_response(gain: float) -> list[GrayResponseSample]:
            return [
                GrayResponseSample(light_level=level, gray_value=level * gain)
                for level in light_levels
            ]

        return OpticalCommState(
            channels={
                "Micro_CH1": ChannelResponse(
                    channel_id="Micro_CH1",
                    communication_ok=True,
                    samples=linear_response(2.4),
                ),
                "Macro_CH1": ChannelResponse(
                    channel_id="Macro_CH1",
                    communication_ok=True,
                    samples=linear_response(1.8),
                ),
            }
        )
