from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class PCCheckConfig:
    """WMI로 조회할 대상 목록. 실제 설비 PC 구성에 맞춰 사람이 정의한다 (TBD)."""

    service_names: list[str] = field(default_factory=list)
    disk_drives: list[str] = field(default_factory=list)
    device_names: list[str] = field(default_factory=list)
    error_log_lookback_hours: float = 24.0


def load_pc_check_config(path: str | Path) -> PCCheckConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return PCCheckConfig(
        service_names=data.get("service_names", []),
        disk_drives=data.get("disk_drives", []),
        device_names=data.get("device_names", []),
        error_log_lookback_hours=data.get("error_log_lookback_hours", 24.0),
    )
