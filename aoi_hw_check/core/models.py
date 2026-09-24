from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class Verdict(enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NA = "NA"


class GateStatus(enum.Enum):
    """자동 산출된 보정값/설정값/판정 결과가 실사용에 반영되기까지의 단계.

    GENERATED(최초 산출) -> TRIAL(시험 적용) -> OPTIMIZED(반복 안정화)
    -> VALIDATED(기준 충족 확인) -> APPLIED(실사용 반영)
    """

    GENERATED = "GENERATED"
    TRIAL = "TRIAL"
    OPTIMIZED = "OPTIMIZED"
    VALIDATED = "VALIDATED"
    APPLIED = "APPLIED"


@dataclass(frozen=True)
class FieldMismatch:
    field_path: str
    baseline_value: Any
    current_value: Any


@dataclass(frozen=True)
class CheckResult:
    equipment_id: str
    check_item: str
    verdict: Verdict
    deviation: list[FieldMismatch] = field(default_factory=list)
    detail: str = ""
    measured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    gate_status: GateStatus = GateStatus.GENERATED
    criteria_version: str = ""
