from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class IOPoint:
    """I/O Map 상의 시험 포인트: 입력을 강제 구동했을 때 기대되는 출력 값."""

    io_id: str
    forced_input_value: Any
    expected_output_value: Any
    description: str = ""
