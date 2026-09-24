from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GrayResponseSample:
    """특정 광량 설정에서 취득한 채널의 평균 Gray 값."""

    light_level: float
    gray_value: float


@dataclass(frozen=True)
class ChannelResponse:
    """카메라/조명 채널 1개의 통신 응답 여부와 광량-Gray 샘플 목록."""

    channel_id: str
    communication_ok: bool
    samples: list[GrayResponseSample] = field(default_factory=list)


@dataclass(frozen=True)
class OpticalCommState:
    channels: dict[str, ChannelResponse] = field(default_factory=dict)
