from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InterlockSignalEvent:
    """전후 공정 장비와 주고받은 연동 신호 1건의 관측 결과."""

    signal_id: str
    sequence_order: int
    response_delay_ms: float
    received: bool
