from __future__ import annotations

from aoi_hw_check.checks.pc_check.judge import CHECK_ITEM
from aoi_hw_check.core.thresholds import CriteriaStore

# 개발/테스트용 예시 값이다. 실제 설비 출하 DATA(사양서 기준 CPU/메모리/디스크
# 여유공간·허용 에러 건수) 확보 전까지는 판정에 절대 신뢰하지 말 것 — 실측치
# 확보 즉시 교체 필요 (TBD).
_EXAMPLE_RANGES: dict[str, tuple[float, float]] = {
    "cpu.usage_percent": (0, 80),
    "memory.used_gb": (0, 28),
    "disk.c_free_gb": (20, 100_000),
    "disk.d_free_gb": (20, 100_000),
    "errors.event_log_errors_24h": (0, 5),
}


def seed_example_criteria(criteria_store: CriteriaStore) -> None:
    for key, (min_value, max_value) in _EXAMPLE_RANGES.items():
        criteria_store.save_criteria(CHECK_ITEM, key, min_value, max_value)
